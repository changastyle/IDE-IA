# -*- coding: utf-8 -*-
"""TERMINAL-UTILS — interfaz común de backends de terminal.

Equivalente Python de una `interface` de Java: una ABC (Abstract Base
Class) con @abstractmethod. Las implementaciones concretas viven en:

    TERMINAL-UNIX-UTILS.py     → UnixTerminalBackend  (pty.fork + zsh)
    TERMINAL-WINDOWS-UTILS.py  → WindowsTerminalBackend (pywinpty/ConPTY)

El contrato es I/O puro de proceso — la emulación de terminal (pyte) y
el render viven en la UI (TerminalTab). Los backends entregan bytes
crudos por callbacks:

    backend.on_data = fn(bytes)   # stdout/stderr de la shell
    backend.on_exit = fn(int)     # la shell terminó (código)

Los callbacks pueden dispararse desde un thread lector — la UI los
puentea con una Signal (emit es thread-safe → entrega encolada).
"""
import os
from abc import ABC, abstractmethod


class TerminalBackend(ABC):
    """Contrato de un backend de terminal (la "interface").

    Métodos:
        spawn(cwd)   → arranca la shell; True si quedó viva
        write(data)  → bytes/str al stdin de la shell
        resize(cols, rows) → avisa el tamaño visible al pty
        is_alive()   → la shell sigue corriendo
        kill()       → mata la shell y libera recursos (idempotente)

    Callbacks (asignar antes de spawn):
        on_data(bytes)  → datos crudos de la shell
        on_exit(int)    → la shell terminó
    """

    def __init__(self):
        self.on_data = None   # callable(bytes)
        self.on_exit = None   # callable(int)

    @abstractmethod
    def spawn(self, cwd=None):
        """Arranca la shell interactiva. Devuelve True si quedó viva."""

    @abstractmethod
    def write(self, data):
        """Escribe bytes (o str) al stdin de la shell."""

    @abstractmethod
    def resize(self, cols, rows):
        """Informa el tamaño visible (columnas, filas) al pty."""

    @abstractmethod
    def is_alive(self):
        """True si la shell sigue corriendo."""

    @abstractmethod
    def kill(self):
        """Mata la shell y libera recursos. Idempotente."""

    # ---- helpers compartidos ----
    def _emit_data(self, data):
        if self.on_data is not None:
            self.on_data(data)

    def _emit_exit(self, code):
        if self.on_exit is not None:
            self.on_exit(code)


def create_backend():
    """Factory: devuelve el backend de la plataforma actual.

    Windows → WindowsTerminalBackend (ConPTY vía pywinpty)
    macOS/Linux → UnixTerminalBackend (pty.fork + zsh/bash)
    """
    if os.name == "nt":
        from UTILS.terminal.windows import WindowsTerminalBackend
        return WindowsTerminalBackend()
    from UTILS.terminal.unix import UnixTerminalBackend
    return UnixTerminalBackend()
