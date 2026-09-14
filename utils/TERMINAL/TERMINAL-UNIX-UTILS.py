# -*- coding: utf-8 -*-
"""TERMINAL-UNIX-UTILS — backend de terminal para macOS/Linux.

Implementa TerminalBackend con `pty.fork()` + shell interactiva
(zsh, cae a bash/sh). La lectura corre en un daemon thread que hace
os.read() bloqueante sobre el fd del pty y dispara `on_data`.

Solo se importa en plataformas POSIX (create_backend lo elige por
os.name) — `pty`, `fcntl` y `termios` no existen en Windows.
"""
import os
import signal
import threading

from UTILS.terminal.base import TerminalBackend

_SHELLS = ("/bin/zsh", "/bin/bash", "/bin/sh")


class UnixTerminalBackend(TerminalBackend):
    """Shell real sobre un pty POSIX: edición, historial, ANSI."""

    def __init__(self):
        super().__init__()
        self.pid = None
        self.fd = None
        self._alive = False

    def spawn(self, cwd=None):
        pid, fd = _fork()
        if pid is None:
            return False
        if pid == 0:  # hijo: shell interactiva en el pty
            os.environ["TERM"] = "xterm-256color"
            if cwd and os.path.isdir(cwd):
                try:
                    os.chdir(cwd)
                except OSError:
                    pass
            for shell in _SHELLS:
                try:
                    os.execv(shell, [os.path.basename(shell), "-i"])
                except OSError:
                    continue
            os._exit(1)
        # padre
        self.pid, self.fd = pid, fd
        self._alive = True
        self.resize(120, 30)  # tamaño inicial razonable
        threading.Thread(target=self._read_loop, daemon=True).start()
        return True

    def write(self, data):
        if not self._alive:
            return
        if isinstance(data, str):
            data = data.encode("utf-8")
        try:
            os.write(self.fd, data)
        except OSError:
            self._alive = False

    def resize(self, cols, rows):
        if not self._alive:
            return
        try:
            import fcntl
            import struct
            import termios
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ,
                        struct.pack("HHHH", rows, cols, 0, 0))
            os.killpg(os.getpgid(self.pid), signal.SIGWINCH)
        except (OSError, ProcessLookupError):
            pass

    def is_alive(self):
        return self._alive

    def kill(self):
        if self._alive:
            try:
                os.killpg(os.getpgid(self.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            self._alive = False
        if self.fd is not None:
            try:
                os.close(self.fd)   # despierta al reader con OSError
            except OSError:
                pass
            self.fd = None

    # ---- internals ----
    def _read_loop(self):
        """Daemon thread: os.read bloqueante → on_data / on_exit."""
        while True:
            try:
                data = os.read(self.fd, 65536)
            except OSError:
                data = b""
            if not data:
                break           # EOF o fd cerrado → la shell murió
            self._emit_data(data)
        if self._alive:
            self._alive = False
            self._emit_exit(0)


def _fork():
    """pty.fork() envuelto — devuelve (pid, fd) o (None, None)."""
    import pty
    try:
        return pty.fork()
    except OSError:
        return None, None
