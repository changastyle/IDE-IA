# -*- coding: utf-8 -*-
"""FILE-UTILS — lógica de análisis de archivos (sin UI).

Funciones puras que el FilesPanel ejecuta desde workers en segundo
plano. Nada de Qt acá: entran paths, salen datos.

  - list_entries(dir_path) → un nivel del árbol, filtrado y ordenado
  - walk_dirs(root)        → todas las subcarpetas visibles (watcher)
  - count_lines(root)      → {path: nº de líneas} para badges de diff
"""
import os

# Carpetas que no se muestran ni se escanean
IGNORED_DIRS = {".git", "__pycache__", ".idea", "node_modules",
                ".venv", "venv", "ns-code"}

# Archivos que existen pero no se muestran en el árbol (ruido visual)
IGNORED_FILES = {"__init__.py"}

# Dotfiles que sí se muestran en el árbol
VISIBLE_DOTFILES = {".gitignore"}

# Extensiones ejecutables desde el árbol (botón play)
RUNNABLE_EXTS = {".py", ".js", ".java"}

# No contar líneas de archivos mayores a esto (binarios/pesados) — el
# badge de diff no aplica y frenaría el escaneo.
MAX_DIFF_BYTES = 1_000_000


def _skip_dir(name):
    """Carpeta que no se muestra ni se escanea (dotdir o ignorada)."""
    return name in IGNORED_DIRS or name.startswith(".")


def list_entries(dir_path):
    """Un nivel del árbol: [(name, path, is_dir)].

    Filtrado (dotfiles salvo VISIBLE_DOTFILES, IGNORED_FILES,
    IGNORED_DIRS) y ordenado como IntelliJ: carpetas primero,
    alfabético case-insensitive.
    """
    try:
        entries = sorted(
            os.scandir(dir_path),
            key=lambda e: (not e.is_dir(), e.name.lower()))
    except OSError:
        return []
    out = []
    for e in entries:
        if e.name.startswith(".") and e.name not in VISIBLE_DOTFILES:
            continue
        if e.name in IGNORED_FILES:
            continue
        if e.is_dir(follow_symlinks=False):
            if e.name in IGNORED_DIRS:
                continue
            out.append((e.name, e.path, True))
        else:
            out.append((e.name, e.path, False))
    return out


def walk_dirs(root):
    """Todas las subcarpetas visibles bajo root (para el watcher).

    Incluye root como primer elemento. Pensado para correr en un
    thread — en carpetas grandes (Desktop) puede tardar.
    """
    dirs = [root]
    try:
        for dirpath, dirnames, _f in os.walk(root):
            dirnames[:] = [d for d in dirnames if not _skip_dir(d)]
            dirs.append(dirpath)
    except OSError:
        pass
    return dirs


def count_lines(root):
    """{path: nº de líneas} de cada archivo de texto < MAX_DIFF_BYTES.

    Los binarios (contienen \\0) y los archivos grandes se saltan.
    Pensado para correr en un thread.
    """
    counts = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _skip_dir(d)]
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            try:
                if os.path.getsize(fpath) > MAX_DIFF_BYTES:
                    continue
                with open(fpath, "rb") as f:
                    data = f.read()
                if b"\0" in data:
                    continue            # binario → sin badge de líneas
                counts[fpath] = data.count(b"\n") + bool(
                    data and not data.endswith(b"\n"))
            except OSError:
                continue
    return counts
