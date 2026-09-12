# -*- coding: utf-8 -*-
"""Atajos de teclado configurables (shortcuts.json).

Permite ver y reconfigurar todos los shortcuts del IDE.
"""
import json
import os

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHORTCUTS_FILE = os.path.join(APP_DIR, "shortcuts.json")

# Atajos por defecto: id → (descripción, secuencia)
DEFAULT_SHORTCUTS = {
    "save":           ("Guardar archivo actual",        "Ctrl+S"),
    "close_tab":      ("Cerrar pestaña actual",          "Ctrl+W"),
    "next_tab":       ("Pestaña siguiente",              "Ctrl+Shift+Right"),
    "prev_tab":       ("Pestaña anterior",               "Ctrl+Shift+Left"),
    "run_file":       ("Ejecutar archivo (play)",        "Ctrl+R"),
    "toggle_terminal":("Mostrar/ocultar terminal",      "Ctrl+`"),
    "refresh_files":  ("Refrescar árbol de archivos",    "F5"),
    "rename_file":    ("Renombrar archivo (F2)",          "F2"),
    "delete_file":    ("Eliminar archivo (Delete)",      "Delete"),
    "polish_text":    ("Pulir texto (✨)",               "Ctrl+P"),
}


def load_shortcuts():
    """Devuelve dict id → secuencia (con defaults si no existe)."""
    out = {k: v[1] for k, v in DEFAULT_SHORTCUTS.items()}
    if not os.path.exists(SHORTCUTS_FILE):
        return out
    try:
        with open(SHORTCUTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.get("shortcuts", {}).items():
            if k in out:
                out[k] = v
    except (OSError, json.JSONDecodeError):
        pass
    return out


def save_shortcuts(shortcuts_dict):
    """Guarda id → secuencia."""
    try:
        with open(SHORTCUTS_FILE, "w", encoding="utf-8") as f:
            json.dump({"shortcuts": shortcuts_dict}, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def reset_shortcuts():
    """Vuelve todos los shortcuts a sus defaults."""
    out = {k: v[1] for k, v in DEFAULT_SHORTCUTS.items()}
    save_shortcuts(out)
    return out
