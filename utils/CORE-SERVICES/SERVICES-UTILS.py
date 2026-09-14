# -*- coding: utf-8 -*-
"""Servicios concretos de NG-Studio.

- `GitWatchService`: envuelve `GitListener` (watcher + poll de git) en
  su propio QThread. Los `git status` cada 2s dejan de correr en el
  hilo UI — si tardan, la app no se congela.

- `SysInfoWorker` / `SysInfoService`: poll de RAM del proceso + hijos
  cada 3s en un thread (hoy el BottomBar corre `ps -axo` en el hilo UI
  y en Windows falla silencioso → 0 MB).

- `FileWatchWorker` / `FileWatchService`: QFileSystemWatcher del
  workspace + análisis de archivos (walk de subcarpetas, conteo de
  líneas para badges) en un QThread. Los walks corren en daemon
  threads para que el heartbeat del servicio siga respondiendo.
"""
import os
import subprocess
import threading

from PySide6.QtCore import (
    QObject, QFileSystemWatcher, QTimer, Signal)

from UTILS.core_services.app_log import log
from UTILS.core_services.service_manager import Service
from UTILS.file_utils import walk_dirs, count_lines


class GitWatchService(Service):
    """GitListener en un QThread.

    - `set_repo(path)` se pide por señal → corre en el thread del
      worker (QFileSystemWatcher exige eso).
    - `subscribe(cb)` conecta cb a la señal `changed` del listener →
      entrega encolada al hilo UI (los callbacks SIEMPRE corren en la
      UI, aunque el listener viva en otro thread).
    """

    repo_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__("git-watch", self._make, parent)
        self.repo_requested.connect(self.worker.set_repo)

    @staticmethod
    def _make():
        from UTILS.listeners import GitListener
        return GitListener()

    def set_repo(self, path):
        """Pide al listener (en su thread) que apunte a `path`."""
        self.repo_requested.emit(path or "")

    def subscribe(self, cb):
        """cb se ejecuta en el hilo UI cuando cambia status/rama."""
        self.worker.changed.connect(cb)


def _rss_mb():
    """RSS total (MB) del proceso actual + descendientes.

    Usa psutil si está instalado; si no, cae a `ps -axo` (macOS/Linux).
    En Windows sin psutil devuelve 0 — igual que antes, pero ahora el
    subprocess corre en el thread del servicio, no en la UI.
    """
    try:
        import psutil
        total = 0
        me = psutil.Process(os.getpid())
        for p in [me] + me.children(recursive=True):
            try:
                total += p.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return total / (1024 * 1024)
    except ImportError:
        pass
    try:
        r = subprocess.run(
            ["ps", "-axo", "rss=,pid=,ppid="],
            capture_output=True, text=True, timeout=5)
        # sumar el proceso y sus descendientes
        rows = {}
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                try:
                    rows[int(parts[1])] = (int(parts[0]), int(parts[2]))
                except ValueError:
                    continue
        pid = os.getpid()
        total_kb = 0
        for p, (rss, ppid) in rows.items():
            q = p
            while q in rows:
                if q == pid:
                    total_kb += rss
                    break
                q = rows[q][1]
        return total_kb / 1024
    except (OSError, subprocess.TimeoutExpired):
        return 0.0


class SysInfoWorker(QObject):
    """Poll de RAM en su propio thread. Emite `ram_mb(float)`."""

    ram_mb = Signal(float)
    POLL_MS = 3000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = None

    def start(self):
        """Corre en el thread del worker (conectado a thread.started)."""
        if self._timer is not None:
            return  # restart: no duplicar el timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(self.POLL_MS)
        self._poll()

    def _poll(self):
        try:
            self.ram_mb.emit(_rss_mb())
        except Exception as e:
            log(f"sys-info poll falló: {e}", "core")


class SysInfoService(Service):
    """Servicio de info de sistema (RAM del IDE + hijos)."""

    def __init__(self, parent=None):
        super().__init__("sys-info", SysInfoWorker, parent)

    @property
    def ram_signal(self):
        """Señal `ram_mb(float)` del worker — conectar en la UI."""
        return self.worker.ram_mb


class FileWatchWorker(QObject):
    """Watcher + análisis de archivos del workspace en su thread.

    - `set_root(path)` (slot): apunta el watcher a la carpeta. El walk
      de subcarpetas corre en un daemon thread y el addPaths vuelve acá
      por señal — el heartbeat del servicio nunca se bloquea.
    - Cambios en el fs → debounce 300ms → `changed` + re-conteo de
      líneas → `diffs_ready(root, counts)`.
    - `busy(bool)`: True mientras haya trabajo de fondo (walk o diffs)
      → los paneles muestran su indicador de escaneo.
    """

    changed = Signal()
    diffs_ready = Signal(str, dict)      # (root, {path: líneas})
    busy = Signal(bool)
    _walk_done = Signal(list, str, int)  # (dirs, root, generación)
    _diffs_done = Signal(str, dict)      # (root, counts)

    DEBOUNCE_MS = 300

    def __init__(self, parent=None):
        super().__init__(parent)
        self.root = ""
        self._watcher = None
        self._debounce = None
        self._walk_gen = 0
        self._diffs_running = False
        self._diffs_pending = False
        self._jobs = 0
        self._walk_done.connect(self._arm_dirs)
        self._diffs_done.connect(self._on_diffs_done)

    def start(self):
        """Corre en el thread del worker (conectado a thread.started)."""
        if self._watcher is not None:
            return  # restart: no duplicar watcher/timer
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_fs_event)
        self._watcher.fileChanged.connect(self._on_fs_event)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._on_debounced)
        self._arm_root()  # por si set_root llegó antes del start

    # ---- API (slots — corren en el thread del worker) ----
    def set_root(self, path):
        self.root = path or ""
        self._arm_root()

    def request_diffs(self):
        """Lanza el conteo de líneas en un daemon thread."""
        if not self.root:
            return
        if self._diffs_running:
            self._diffs_pending = True   # re-correr al terminar
            return
        self._diffs_running = True
        self._job_begin()
        root = self.root

        def _run():
            self._diffs_done.emit(root, count_lines(root))

        threading.Thread(target=_run, daemon=True).start()

    # ---- internals ----
    def _arm_root(self):
        """Configura el watcher para self.root (thread del worker)."""
        if self._watcher is None:
            return
        old = self._watcher.files() + self._watcher.directories()
        if old:
            self._watcher.removePaths(old)
        if not self.root or not os.path.isdir(self.root):
            return
        self._watcher.addPath(self.root)  # raíz ya, sin esperar el walk
        self._walk_gen += 1
        gen = self._walk_gen
        root = self.root
        self._job_begin()

        def _walk():
            self._walk_done.emit(walk_dirs(root), root, gen)

        threading.Thread(target=_walk, daemon=True).start()
        self.request_diffs()  # baseline de líneas

    def _arm_dirs(self, dirs, root, gen):
        """Aplica el resultado del walk (thread del worker)."""
        self._job_end()
        if gen != self._walk_gen or root != self.root:
            return  # el root cambió mientras caminaba
        self._watcher.addPaths(dirs)

    def _on_fs_event(self, _path):
        if self._debounce is not None:
            self._debounce.start(self.DEBOUNCE_MS)

    def _on_debounced(self):
        self.changed.emit()
        self.request_diffs()

    def _on_diffs_done(self, root, counts):
        self._diffs_running = False
        self._job_end()
        if root == self.root:
            self.diffs_ready.emit(root, counts)
        if self._diffs_pending:
            self._diffs_pending = False
            self.request_diffs()

    # ---- indicador de trabajo ----
    def _job_begin(self):
        self._jobs += 1
        if self._jobs == 1:
            self.busy.emit(True)

    def _job_end(self):
        self._jobs = max(0, self._jobs - 1)
        if self._jobs == 0:
            self.busy.emit(False)


class FileWatchService(Service):
    """Watcher + análisis de archivos del workspace en un QThread.

    - `set_root(path)` va por señal → corre en el thread del worker
      (QFileSystemWatcher lo exige).
    - `subscribe_changed/diffs/busy(cb)`: los callbacks corren en el
      hilo del suscriptor (la UI) aunque el worker viva en otro thread.
    """

    root_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__("file-watch", FileWatchWorker, parent)
        self.root_requested.connect(self.worker.set_root)

    def set_root(self, path):
        """Pide al worker (en su thread) que apunte a `path`."""
        self.root_requested.emit(path or "")

    def subscribe_changed(self, cb):
        """cb() en el hilo UI cuando cambia el filesystem (debounced)."""
        self.worker.changed.connect(cb)

    def subscribe_diffs(self, cb):
        """cb(root, {path: líneas}) en el hilo UI al terminar un conteo."""
        self.worker.diffs_ready.connect(cb)

    def subscribe_busy(self, cb):
        """cb(bool) en el hilo UI: hay trabajo de fondo o no."""
        self.worker.busy.connect(cb)
