# -*- coding: utf-8 -*-
"""TERMINAL-WINDOWS-UTILS — backend de terminal para Windows.

Implementa TerminalBackend con ConPTY vía `pywinpty`
(`winpty.PtyProcess`) — el pseudo-terminal real de Windows 10+.
La shell es PowerShell (cae a cmd.exe). La lectura corre en un
daemon thread: `proc.read()` bloquea hasta que hay datos y dispara
`on_data`.

Requiere:  pip install pywinpty
Solo se importa en Windows (create_backend lo elige por os.name).
"""
import shutil
import threading

from UTILS.terminal.base import TerminalBackend


class WindowsTerminalBackend(TerminalBackend):
    """Shell real sobre ConPTY: ANSI, colores, apps interactivas."""

    def __init__(self):
        super().__init__()
        self.proc = None
        self._alive = False

    def spawn(self, cwd=None):
        try:
            from winpty import PtyProcess
        except ImportError:
            return False  # sin pywinpty no hay ConPTY
        shell = shutil.which("powershell.exe") or shutil.which("cmd.exe")
        if shell is None:
            return False
        try:
            self.proc = PtyProcess.spawn(
                [shell], cwd=cwd or None, dimensions=(30, 120))
        except Exception:
            self.proc = None
            return False
        self._alive = True
        threading.Thread(target=self._read_loop, daemon=True).start()
        return True

    def write(self, data):
        if not self._alive or self.proc is None:
            return
        if isinstance(data, bytes):
            data = data.decode("utf-8", "replace")
        try:
            self.proc.write(data)
        except Exception:
            self._alive = False

    def resize(self, cols, rows):
        if not self._alive or self.proc is None:
            return
        try:
            self.proc.setwinsize(rows, cols)  # winpty: (rows, cols)
        except Exception:
            pass

    def is_alive(self):
        if self._alive and self.proc is not None:
            try:
                self._alive = self.proc.isalive()
            except Exception:
                self._alive = False
        return self._alive

    def kill(self):
        self._alive = False
        if self.proc is not None:
            try:
                self.proc.terminate(force=True)
            except Exception:
                pass
            self.proc = None

    # ---- internals ----
    def _read_loop(self):
        """Daemon thread: proc.read() bloqueante → on_data / on_exit."""
        while True:
            try:
                data = self.proc.read()   # str; bloquea hasta datos
            except Exception:
                data = ""
            if not data:
                break                     # EOF → la shell murió
            self._emit_data(data.encode("utf-8", "replace"))
        code = 0
        try:
            code = self.proc.exitstatus or 0
        except Exception:
            pass
        if self._alive:
            self._alive = False
            self._emit_exit(code)
