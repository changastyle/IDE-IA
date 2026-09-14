# -*- coding: utf-8 -*-
"""AppLog — log central de NG-Studio.

Buffer en memoria (ring) + señal Qt por línea. Cualquier thread puede
loguear: la señal se entrega encolada al hilo UI. El LogOverlay y el
monitor de servicios consumen de acá.

Uso:
    from UTILS.core_services.app_log import log
    log("servicio git-watch iniciado", source="core")
"""
import datetime
import os
import sys
import threading
import time
import traceback
from collections import deque

from PySide6.QtCore import QObject, Signal


class AppLog(QObject):
    """Log central: buffer + señal `line(str)` por cada entrada."""

    line = Signal(str)

    MAX_LINES = 5000
    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buf = deque(maxlen=self.MAX_LINES)
        self._lock = threading.Lock()

    @classmethod
    def instance(cls):
        """Singleton perezoso (se crea en el thread que lo pida primero;
        en la práctica lo crea el core al arrancar)."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    def log(self, msg, source="app"):
        """Agrega una línea `[hh:mm:ss] [source] msg` y la emite."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] [{source}] {msg}"
        with self._lock:
            self._buf.append(line)
        try:
            self.line.emit(line)
        except RuntimeError:
            pass  # app cerrando / objeto destruido

    def lines(self):
        """Copia del buffer actual (para poblar el overlay al abrirlo)."""
        with self._lock:
            return list(self._buf)

    def clear(self):
        with self._lock:
            self._buf.clear()


def log(msg, source="app"):
    """Atajo global: log("algo") → AppLog.instance().log(...)."""
    AppLog.instance().log(msg, source)


def _crash_log_path():
    """NG-STUDIO-STUFF/CRASH.LOG junto a la raíz de la app."""
    root = os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "NG-STUDIO-STUFF", "CRASH.LOG")


def _dump_crash(text):
    """Escribe un bloque en CRASH.LOG (persiste aunque la app muera)."""
    try:
        path = _crash_log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n===== UI-FREEZE "
                    f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
            f.write(text + "\n")
    except OSError:
        pass


def install_freeze_watchdog(parent, threshold=2.0):
    """Detecta congelamientos del hilo UI y vuelca el stack exacto.

    Un QTimer en el hilo UI actualiza un tick cada 250ms. Un daemon
    thread vigila ese tick: si queda viejo más de `threshold` segundos,
    el event loop está trabado → vuelca el stack VIVO del hilo UI
    (sys._current_frames) a CRASH.LOG y avisa al AppLog con los frames
    internos (la línea culpable). Un dump por episodio; al recuperarse
    loguea cuánto duró.

    Devuelve el QTimer (hay que mantenerlo referenciado).
    """
    from PySide6.QtCore import QTimer

    state = {"tick": time.monotonic()}
    main_id = threading.main_thread().ident
    timer = QTimer(parent)
    timer.timeout.connect(
        lambda: state.__setitem__("tick", time.monotonic()))
    timer.start(250)

    def _watch():
        dumped = False
        while True:
            time.sleep(0.5)
            lag = time.monotonic() - state["tick"]
            if lag > threshold:
                if not dumped:
                    dumped = True
                    frame = sys._current_frames().get(main_id)
                    stack = ("".join(traceback.format_stack(frame))
                             if frame is not None else "(sin frame)")
                    _dump_crash(f"UI congelada {lag:.1f}s\n{stack}")
                    # Al AppLog van solo los frames internos (la causa)
                    inner = "".join(
                        traceback.format_stack(frame)[-4:]
                        if frame is not None else [])
                    log(f"UI congelada {lag:.1f}s — stack en CRASH.LOG\n"
                        f"{inner.rstrip()}", source="ui-watchdog")
            else:
                if dumped:
                    log("UI respondió de nuevo", source="ui-watchdog")
                dumped = False

    threading.Thread(target=_watch, daemon=True).start()
    return timer
