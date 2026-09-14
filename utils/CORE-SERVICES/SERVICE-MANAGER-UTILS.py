# -*- coding: utf-8 -*-
"""ServiceManager — ciclo de vida de los servicios de NG-Studio.

Cada `Service` envuelve un worker QObject viviendo en su propio QThread.
El manager los registra, los arranca escalonados (boot queue) y vigila
su heartbeat con un watchdog.

Heartbeat: en vez de exigir que cada worker emita "estoy vivo", el
servicio agenda un callback en el event loop del worker con
`QTimer.singleShot(0, worker, cb)`. Si el thread está sano, el callback
corre y emite `beat`. Si el thread está colgado (ej: subprocess sin
timeout), el callback nunca corre → el watchdog lo marca "hung".

Estados: stopped → starting → running → hung → stopping → stopped
                              ↘ error (excepción al arrancar)

Nunca se usa QThread.terminate(): mata el thread a mitad de operación
y puede dejar locks corruptos. El stop es cooperativo (quit + wait).
"""
import time

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from UTILS.core_services.app_log import log


class Service(QObject):
    """Un worker QObject corriendo en su propio QThread.

    `factory` es un callable() → QObject. El worker se crea en el
    thread del manager (barato) y se mueve a su thread en start().

    Convenciones del worker:
      - slot `start()` opcional: se conecta a thread.started (crear
        QTimers adentro, para que vivan en el thread del worker).
      - señales propias: se emiten desde el thread del worker y llegan
        encoladas a la UI — seguro por diseño.
    """

    state_changed = Signal(str, str)   # (name, state)
    beat = Signal(str)                 # (name) — heartbeat respondió

    PING_MS = 2000        # cada cuánto se pincha el event loop
    STOP_WAIT_MS = 3000   # cuánto se espera al quit antes de rendirse

    def __init__(self, name, factory, parent=None):
        super().__init__(parent)
        self.name = name
        self._factory = factory
        self.worker = factory()
        self._thread = None
        self.state = "stopped"
        self.last_beat = 0.0
        self._ping_on = False
        self.beat.connect(self._on_beat)

    # ---- estado ----
    def _set_state(self, state):
        if self.state == state:
            return
        self.state = state
        self.state_changed.emit(self.name, state)

    def _on_beat(self, _name):
        self.last_beat = time.monotonic()
        if self.state == "hung":
            log(f"servicio '{self.name}' respondió de nuevo", "core")
            self._set_state("running")

    # ---- ciclo de vida ----
    def start(self):
        if self.state in ("starting", "running", "hung"):
            return
        self._set_state("starting")
        try:
            self._thread = QThread(self)
            self.worker.moveToThread(self._thread)
            if hasattr(self.worker, "start"):
                self._thread.started.connect(self.worker.start)
            self._thread.start()
        except Exception as e:
            log(f"servicio '{self.name}' falló al arrancar: {e}", "core")
            self._set_state("error")
            return
        self.last_beat = time.monotonic()
        self._ping_on = True
        self._ping()
        self._set_state("running")
        log(f"servicio '{self.name}' iniciado", "core")

    def stop(self):
        if self._thread is None:
            self._set_state("stopped")
            return
        self._set_state("stopping")
        self._ping_on = False
        self._thread.quit()
        if not self._thread.wait(self.STOP_WAIT_MS):
            # No terminate(): se reporta y queda a cargo del usuario
            log(f"servicio '{self.name}' no respondió al stop "
                f"(thread sigue vivo)", "core")
            self._set_state("hung")
            return
        # devolver el worker al thread del manager para poder relanzarlo
        self.worker.moveToThread(self.thread())
        self._thread = None
        self._set_state("stopped")
        log(f"servicio '{self.name}' detenido", "core")

    def restart(self):
        log(f"servicio '{self.name}' reiniciando…", "core")
        self.stop()
        if self.state == "stopped":
            self.start()

    # ---- heartbeat ----
    def _ping(self):
        """Agenda un callback en el event loop del worker. Si corre,
        el thread está vivo → beat. Si está colgado, no corre y el
        watchdog del manager lo detecta por last_beat viejo."""
        if not self._ping_on or self.worker is None:
            return
        try:
            QTimer.singleShot(0, self.worker,
                              lambda: self.beat.emit(self.name))
        except RuntimeError:
            pass  # worker destruido
        QTimer.singleShot(self.PING_MS, self._ping)


class ServiceManager(QObject):
    """Registra servicios, los bootea escalonados y los vigila.

    Señales para la UI (MonitorPanel):
        service_state(name, state)     → cambio de estado
        boot_progress(name, done, total) → progreso de la boot queue
        boot_finished()                → terminaron de arrancar todos
    """

    service_state = Signal(str, str)
    boot_progress = Signal(str, int, int)
    boot_finished = Signal()

    WATCHDOG_MS = 1000   # frecuencia del chequeo
    HUNG_MS = 8000       # beat más viejo que esto → hung

    def __init__(self, parent=None):
        super().__init__(parent)
        self._services = {}
        self._order = []
        self._wd = QTimer(self)
        self._wd.timeout.connect(self._watchdog)
        self._wd.start(self.WATCHDOG_MS)

    # ---- registro ----
    def register(self, service):
        self._services[service.name] = service
        if service.name not in self._order:
            self._order.append(service.name)
        service.state_changed.connect(self.service_state)

    def get(self, name):
        return self._services.get(name)

    def services(self):
        return [self._services[n] for n in self._order]

    # ---- boot queue ----
    def start_all(self, stagger_ms=200):
        """Arranca los servicios en orden, escalonados. La ventana ya
        está visible: cada paso emite boot_progress para el monitor."""
        total = len(self._order)
        log(f"boot queue: {total} servicios por iniciar", "core")
        for i, name in enumerate(self._order):
            svc = self._services[name]
            QTimer.singleShot(
                i * stagger_ms,
                lambda s=svc, k=i: self._boot_step(s, k, total))
        QTimer.singleShot(total * stagger_ms, self.boot_finished.emit)

    def _boot_step(self, svc, i, total):
        self.boot_progress.emit(svc.name, i + 1, total)
        try:
            svc.start()
        except Exception as e:
            log(f"boot: '{svc.name}' lanzó excepción: {e}", "core")
            svc._set_state("error")

    # ---- control individual ----
    def start(self, name):
        svc = self._services.get(name)
        if svc:
            svc.start()

    def stop(self, name):
        svc = self._services.get(name)
        if svc:
            svc.stop()

    def restart(self, name):
        svc = self._services.get(name)
        if svc:
            svc.restart()

    def stop_all(self):
        """Apaga todo en orden inverso (al cerrar la app)."""
        for name in reversed(self._order):
            try:
                self._services[name].stop()
            except Exception as e:
                log(f"stop_all: '{name}' falló: {e}", "core")

    # ---- watchdog ----
    def _watchdog(self):
        now = time.monotonic()
        for svc in self._services.values():
            if svc.state != "running":
                continue
            if now - svc.last_beat > self.HUNG_MS / 1000:
                log(f"servicio '{svc.name}' colgado "
                    f"(sin heartbeat hace {now - svc.last_beat:.0f}s)",
                    "core")
                svc._set_state("hung")
