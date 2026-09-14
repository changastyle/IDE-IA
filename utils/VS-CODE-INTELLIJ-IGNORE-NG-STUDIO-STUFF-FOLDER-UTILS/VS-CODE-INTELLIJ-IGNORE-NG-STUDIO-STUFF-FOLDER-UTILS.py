# -*- coding: utf-8 -*-
"""Marca ng-studio-stuff/ como no-indexable para IDEs y buscadores.

Cuando NG-STUDIO abre una carpeta crea <workspace>/ng-studio-stuff/ para
guardar su estado interno (conversaciones, planner, trash...). Para que
VSCode, IntelliJ y los indexadores del SO no pierdan tiempo analizándola,
escribimos dentro una serie de archivos-marca estándar:

- CACHEDIR.TAG            JetBrains la auto-excluye (2023.3+) + tools de backup
- .gitignore  ("*")       git la ignora + VSCode search (useIgnoreFiles)
- .ignore     ("*")       ripgrep y buscadores que respetan .ignore
- .metadata_never_index   macOS Spotlight
- .noindex                macOS Spotlight (variante)
- attrib +I (Windows)     FILE_ATTRIBUTE_NOT_CONTENT_INDEXED → Windows Search
"""
import os
import sys

STUFF_DIR = "ng-studio-stuff"   # nombre de la carpeta interna del workspace

_MARKERS = {
    "CACHEDIR.TAG": (
        "Signature: 8a477f597d28d172789f06886806bc55\n"
        "# This file is a cache directory tag created by NG-STUDIO.\n"
        "# For information about cache directory tags, see:\n"
        "#\thttps://bford.info/cachedir/\n"
    ),
    ".gitignore": "*\n",
    ".ignore": "*\n",
    ".metadata_never_index": "",
    ".noindex": "",
}


def mark_no_index(path):
    """Crea path si no existe y escribe las marcas anti-indexado dentro."""
    if not path:
        return
    try:
        os.makedirs(path, exist_ok=True)
        for name, content in _MARKERS.items():
            f = os.path.join(path, name)
            if not os.path.exists(f):
                with open(f, "w", encoding="ascii") as fh:
                    fh.write(content)
    except OSError:
        pass
    if sys.platform == "win32":
        try:
            import subprocess
            subprocess.run(["attrib", "+I", path], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass


def ensure_stuff_dir(root):
    """Crea <root>/ng-studio-stuff/ con las marcas y devuelve su path."""
    d = os.path.join(root, STUFF_DIR) if root else ""
    mark_no_index(d)
    return d
