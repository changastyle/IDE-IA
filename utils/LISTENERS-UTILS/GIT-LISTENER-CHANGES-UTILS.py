# -*- coding: utf-8 -*-
"""Listener central del repo git.

Vigila la raíz del repo + .git/HEAD + .git/index + .git/refs con un
QFileSystemWatcher, y hace poll de `git status` / rama actual cada 2s
(el watcher de directorios no es recursivo; el poll cubre subcarpetas).

Los componentes se suscriben con `listener.subscribe(cb)` y se les
avisa cuando cambia el status o la rama. También emite señales Qt:

    status_changed()          → cambió `git status --porcelain`
    branch_changed(branch)    → cambió la rama actual
    changed()                 → cualquiera de los dos
"""
import os
import subprocess

from PySide6.QtCore import QObject, QFileSystemWatcher, QTimer, Signal


class GitListener(QObject):
    status_changed = Signal()
    branch_changed = Signal(str)
    changed = Signal()

    POLL_MS = 2000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo = ""
        self._root = ""
        self._subs = []            # componentes a refrescar
        self._last_status = None
        self._last_branch = None

        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._poll)
        self._watcher.fileChanged.connect(self._poll)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(self.POLL_MS)

    # ---- suscriptores ----
    def subscribe(self, callback):
        """Registra un componente/callback a refrescar ante cambios."""
        if callback not in self._subs:
            self._subs.append(callback)

    def unsubscribe(self, callback):
        if callback in self._subs:
            self._subs.remove(callback)

    def _notify(self):
        for cb in list(self._subs):
            try:
                cb()
            except Exception:
                pass

    # ---- repo ----
    def set_repo(self, path):
        self.repo = path or ""
        self._root = self._git_root() if self.repo else ""
        self._last_status = None
        self._last_branch = None
        old = self._watcher.directories() + self._watcher.files()
        if old:
            self._watcher.removePaths(old)
        self._arm_watcher()
        self._poll()

    def _arm_watcher(self):
        paths = []
        if self._root:
            paths.append(self._root)
            gitdir = os.path.join(self._root, ".git")
            for rel in ("HEAD", "index", "refs", "packed-refs"):
                p = os.path.join(gitdir, rel)
                if os.path.exists(p):
                    paths.append(p)
        if paths:
            self._watcher.addPaths(paths)

    def _git_root(self):
        try:
            r = subprocess.run(
                ["git", "-C", self.repo, "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return r.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
        return self.repo

    def _git(self, *args):
        try:
            r = subprocess.run(
                ["git", "-C", self.repo, *args],
                capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=15)
            return r.stdout
        except (OSError, subprocess.TimeoutExpired):
            return ""

    # ---- polling ----
    def _poll(self, *_):
        if not self.repo:
            return
        is_repo = bool(self._root) and os.path.isdir(
            os.path.join(self._root, ".git"))
        if not is_repo:
            # por si aparece un .git después (git init externo)
            if self.repo and os.path.isdir(os.path.join(self.repo, ".git")):
                self.set_repo(self.repo)
            return
        status = self._git("status", "--porcelain", "-uall")
        branch = self._git("symbolic-ref", "--short", "-q", "HEAD").strip()
        fired = False
        if status != self._last_status:
            self._last_status = status
            self.status_changed.emit()
            fired = True
        if branch != self._last_branch:
            first = self._last_branch is not None
            self._last_branch = branch
            if first:
                self.branch_changed.emit(branch)
            fired = True
        if fired:
            self.changed.emit()
            self._notify()
