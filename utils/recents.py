# -*- coding: utf-8 -*-
"""Gestión de carpetas recientes (open_recents.txt)."""
import os

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECENTS_FILE = os.path.join(APP_DIR, "open_recents.txt")
MAX_RECENTS = 15


def load_recents():
    """Devuelve la lista de carpetas recientes (paths absolutos)."""
    if not os.path.exists(RECENTS_FILE):
        return []
    try:
        with open(RECENTS_FILE, "r", encoding="utf-8") as f:
            paths = [line.strip() for line in f if line.strip()]
    except OSError:
        return []
    # Filtrar inexistentes, mantener orden, sin duplicados
    seen = set()
    out = []
    for p in paths:
        rp = os.path.realpath(p)
        if rp not in seen and os.path.isdir(rp):
            seen.add(rp)
            out.append(rp)
    return out


def add_recent(path):
    """Agrega path al inicio de open_recents.txt (sin duplicados)."""
    if not path or not os.path.isdir(path):
        return
    path = os.path.realpath(path)
    recents = load_recents()
    if path in recents:
        recents.remove(path)
    recents.insert(0, path)
    recents = recents[:MAX_RECENTS]
    try:
        with open(RECENTS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(recents) + "\n")
    except OSError:
        pass


def remove_recent(path):
    """Quita path de open_recents.txt."""
    if not path:
        return
    path = os.path.realpath(path)
    recents = load_recents()
    if path in recents:
        recents.remove(path)
        try:
            with open(RECENTS_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(recents) + "\n")
        except OSError:
            pass
