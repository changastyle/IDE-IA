# -*- coding: utf-8 -*-
"""Colores persistentes de ramas (ng-studio/colores-branches/).

Cada (repo, rama, nacimiento) tiene un color único que jamás se reutiliza:
si una rama se borra y se recrea, su timestamp de creación cambia y toma
un color nuevo — el anterior queda reservado para siempre en el archivo.
"""
import colorsys
import os

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE_DIR = os.path.join(APP_DIR, "ng-studio", "colores-branches")
STORE_FILE = os.path.join(STORE_DIR, "colores-branches.txt")
# Ubicación histórica (ng-studio-stuff/): se migra una sola vez si existe.
_LEGACY_FILE = os.path.join(APP_DIR, "ng-studio-stuff", "branch-colors",
                            "branch-colors.txt")

PALETTE = ["#3574f0", "#2ec4a5", "#e8804a", "#a78bfa", "#e05561",
           "#32ade6", "#22c55e", "#eab308"]

_SEP = "\t"


def _load():
    """[(repo, branch, birth_ts, color)] — todo el historial."""
    entries = []
    try:
        with open(STORE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split(_SEP)
                if len(parts) == 4:
                    entries.append(tuple(parts))
    except OSError:
        if not entries and os.path.exists(_LEGACY_FILE):
            try:
                with open(_LEGACY_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.rstrip("\n").split(_SEP)
                        if len(parts) == 4:
                            entries.append(tuple(parts))
                if entries:
                    _save(entries)
            except OSError:
                pass
    return entries


def _save(entries):
    try:
        os.makedirs(STORE_DIR, exist_ok=True)
        with open(STORE_FILE, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(_SEP.join(e) + "\n")
    except OSError:
        pass


def _gen_color(i):
    """Color fuera de PALETTE: tonos por ángulo dorado (infinitos)."""
    h = (i * 137.508) % 360
    r, g, b = colorsys.hsv_to_rgb(h / 360.0, 0.62, 0.92)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def _next_color(used):
    for c in PALETTE:
        if c not in used:
            return c
    i = 0
    while True:
        c = _gen_color(i)
        if c not in used:
            return c
        i += 1


def get_colors(repo, branches):
    """{rama: color} persistente para las ramas dadas.

    branches: {nombre: birth_ts} — el ts de creación vía reflog.
    Una entrada con birth distinto (rama recreada) toma color nuevo;
    los colores nunca se repiten entre ramas ni entre nacimientos.
    """
    repo = os.path.realpath(repo)
    entries = _load()
    used = {e[3] for e in entries}
    by_key = {(e[0], e[1], e[2]): e[3] for e in entries}
    out = {}
    changed = False
    for b, birth in branches.items():
        key = (repo, b, str(birth))
        color = by_key.get(key)
        if color is None:
            color = _next_color(used)
            used.add(color)
            entries.append((repo, b, str(birth), color))
            changed = True
        out[b] = color
    if changed:
        _save(entries)
    return out
