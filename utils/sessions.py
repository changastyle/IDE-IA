# -*- coding: utf-8 -*-
"""Sesiones de proyectos abiertos (open_sessions.json).

Guarda qué carpetas tenían abiertas las instancias del IDE al cerrarse,
para que al reabrir vuelva a la última ubicación. Soporta múltiples
instancias: cada instancia guarda su carpeta en el array.
"""
import json
import os

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSIONS_FILE = os.path.join(APP_DIR, "open_sessions.json")


def load_sessions():
    """Devuelve la lista de carpetas abiertas (paths absolutos)."""
    if not os.path.exists(SESSIONS_FILE):
        return []
    try:
        with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        paths = data.get("open_folders", [])
    except (OSError, json.JSONDecodeError):
        return []
    # Filtrar inexistentes, sin duplicados
    seen = set()
    out = []
    for p in paths:
        rp = os.path.realpath(p)
        if rp not in seen and os.path.isdir(rp):
            seen.add(rp)
            out.append(rp)
    return out


def save_sessions(paths):
    """Guarda la lista de carpetas abiertas."""
    clean = []
    seen = set()
    for p in paths:
        if p and os.path.isdir(p):
            rp = os.path.realpath(p)
            if rp not in seen:
                seen.add(rp)
                clean.append(rp)
    try:
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump({"open_folders": clean}, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def add_session(path):
    """Agrega una carpeta a las sesiones abiertas."""
    if not path or not os.path.isdir(path):
        return
    sessions = load_sessions()
    rp = os.path.realpath(path)
    if rp not in sessions:
        sessions.append(rp)
    save_sessions(sessions)


def remove_session(path):
    """Quita una carpeta de las sesiones abiertas (al cerrar instancia)."""
    if not path:
        return
    sessions = load_sessions()
    rp = os.path.realpath(path)
    if rp in sessions:
        sessions.remove(rp)
    save_sessions(sessions)


def last_session():
    """Devuelve la última carpeta abierta, o None si no hay."""
    sessions = load_sessions()
    return sessions[-1] if sessions else None
