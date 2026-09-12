#!/usr/bin/env python3
"""Skill: move_file — mueve o renombra un archivo/carpeta dentro del workspace.

Uso: python3 move_file.py <origen> <destino>
Ejemplos:
  move_file.py snake.js js/snake.js      # mueve snake.js a la carpeta js/
  move_file.py js src/js                 # renombra la carpeta
  move_file.py a.txt b.txt               # renombra el archivo
Las carpetas de destino se crean si no existen. No permite salir del workspace.
Salida: informe de texto. 0 = OK, 1 = error.
"""
import os
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.realpath(os.getcwd())


def _resolve(rel):
    """Resuelve una ruta relativa dentro del workspace."""
    rel = str(rel or "").strip().lstrip("/")
    if not rel or rel == ".":
        return None
    p = os.path.realpath(os.path.join(ROOT, rel))
    if p != ROOT and not p.startswith(ROOT + os.sep):
        return None
    return p


def main():
    if len(sys.argv) < 3:
        print("Uso: move_file.py <origen> <destino>")
        return 2
    src_rel, dst_rel = sys.argv[1], sys.argv[2]
    src = _resolve(src_rel)
    dst = _resolve(dst_rel)
    if src is None or dst is None:
        print("ERROR: ruta fuera de la carpeta de trabajo")
        return 1
    if not os.path.exists(src):
        print(f"ERROR: no existe '{src_rel}'")
        return 1
    if os.path.exists(dst):
        print(f"ERROR: el destino '{dst_rel}' ya existe")
        return 1
    # Crear carpeta de destino si hace falta
    dst_dir = os.path.dirname(dst)
    if dst_dir and not os.path.exists(dst_dir):
        os.makedirs(dst_dir, exist_ok=True)
    try:
        shutil.move(src, dst)
    except Exception as e:
        print(f"ERROR moviendo '{src_rel}' → '{dst_rel}': {e}")
        return 1
    kind = "carpeta" if os.path.isdir(dst) else "archivo"
    print(f"OK: movido {kind} {src_rel} → {dst_rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
