# -*- coding: utf-8 -*-
"""UTILS — shim de compatibilidad de imports.

Las utilidades viven en subcarpetas con guiones (GIT-UTILS/, MD-UTILS/…)
que NO son nombres de paquete válidos para `import`. Este __init__ carga
cada archivo con importlib y lo registra en sys.modules bajo el nombre
histórico, así los call-sites (`from UTILS.git import …`,
`from UTILS.git_utils import GitUtils`, etc.) siguen funcionando sin
cambios.

Mapa:
    UTILS.git                      → GIT-UTILS/GIT-COMMANDS-UTILS.py
    UTILS.git_utils                → GIT-UTILS/GIT-UTILS.py
    UTILS.listeners                → LISTENERS-UTILS/GIT-LISTENER-CHANGES-UTILS.py
    UTILS.markdown_utils.renderer  → MD-UTILS/MD-RENDER-UTILS.py
    UTILS.markdown_utils.viewer    → MD-UTILS/MD-VIEWER-UTILS.py
    UTILS.ia                       → IA-UTILS/IA-UTILS.py
    UTILS.shortcuts                → SHORCUTS-UTILS/SHORCUT-UTILS.py
    UTILS.stuff_dir                → VS-CODE-INTELLIJ-IGNORE-…/….py
    UTILS.screen_resolution        → SCREEN-RESOLUTION-UTILS/CHECK-MONITOR-RESOLUTION-UTILS.py
    UTILS.file_utils               → FILE-UTILS/FILE-UTILS.py
    UTILS.core_services.app_log          → CORE-SERVICES/APP-LOG-UTILS.py
    UTILS.core_services.service_manager  → CORE-SERVICES/SERVICE-MANAGER-UTILS.py
    UTILS.core_services.services         → CORE-SERVICES/SERVICES-UTILS.py
    UTILS.terminal.base      → TERMINAL/TERMINAL-UTILS.py
    UTILS.terminal.unix      → TERMINAL/TERMINAL-UNIX-UTILS.py
    UTILS.terminal.windows   → TERMINAL/TERMINAL-WINDOWS-UTILS.py
"""
import importlib.util
import os
import sys
import types

_DIR = os.path.dirname(os.path.abspath(__file__))
_PKG = __name__  # "UTILS"


def _load(alias, relpath):
    """Carga `relpath` (relativo a UTILS/) y lo registra como `alias`."""
    path = os.path.join(_DIR, relpath)
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


# --- git ---
# Funciones sueltas (is_repo, pull, push, clone…) restauradas en
# GIT-COMMANDS-UTILS.py; la clase GitUtils vive en GIT-UTILS.py.
_load(_PKG + ".git", "GIT-UTILS/GIT-COMMANDS-UTILS.py")
_load(_PKG + ".git_utils", "GIT-UTILS/GIT-UTILS.py")
# alias por si algo importa la ruta vieja del subpaquete
if _PKG + ".git" in sys.modules:
    sys.modules[_PKG + ".git.git_utils"] = sys.modules[_PKG + ".git"]

# --- listeners ---
_load(_PKG + ".listeners",
      "LISTENERS-UTILS/GIT-LISTENER-CHANGES-UTILS.py")
if _PKG + ".listeners" in sys.modules:
    sys.modules[_PKG + ".listeners.git_listener"] = \
        sys.modules[_PKG + ".listeners"]

# --- markdown ---
# Paquete sintético: el viewer importa `UTILS.markdown_utils.renderer`,
# así que renderer se registra ANTES de cargar el viewer.
_md = types.ModuleType(_PKG + ".markdown_utils")
_md.__path__ = []  # se comporta como paquete
sys.modules[_PKG + ".markdown_utils"] = _md
_load(_PKG + ".markdown_utils.renderer", "MD-UTILS/MD-RENDER-UTILS.py")
_load(_PKG + ".markdown_utils.viewer", "MD-UTILS/MD-VIEWER-UTILS.py")
for _n in ("md_to_html", "is_markdown_file"):
    _r = sys.modules.get(_PKG + ".markdown_utils.renderer")
    if _r is not None and hasattr(_r, _n):
        setattr(_md, _n, getattr(_r, _n))
for _n in ("MarkdownViewerDialog", "MD_EXTS"):
    _v = sys.modules.get(_PKG + ".markdown_utils.viewer")
    if _v is not None and hasattr(_v, _n):
        setattr(_md, _n, getattr(_v, _n))

# --- resto ---
_load(_PKG + ".ia", "IA-UTILS/IA-UTILS.py")
_load(_PKG + ".shortcuts", "SHORCUTS-UTILS/SHORCUT-UTILS.py")
_load(_PKG + ".stuff_dir",
      "VS-CODE-INTELLIJ-IGNORE-NG-STUDIO-STUFF-FOLDER-UTILS/"
      "VS-CODE-INTELLIJ-IGNORE-NG-STUDIO-STUFF-FOLDER-UTILS.py")
_load(_PKG + ".screen_resolution",
      "SCREEN-RESOLUTION-UTILS/CHECK-MONITOR-RESOLUTION-UTILS.py")
_load(_PKG + ".file_utils", "FILE-UTILS/FILE-UTILS.py")

# --- core services ---
# Paquete sintético (como markdown_utils): app_log se carga primero
# porque service_manager y services lo importan.
_cs = types.ModuleType(_PKG + ".core_services")
_cs.__path__ = []  # se comporta como paquete
sys.modules[_PKG + ".core_services"] = _cs
_load(_PKG + ".core_services.app_log", "CORE-SERVICES/APP-LOG-UTILS.py")
_load(_PKG + ".core_services.service_manager",
      "CORE-SERVICES/SERVICE-MANAGER-UTILS.py")
_load(_PKG + ".core_services.services", "CORE-SERVICES/SERVICES-UTILS.py")
for _n in ("AppLog", "log"):
    _m = sys.modules.get(_PKG + ".core_services.app_log")
    if _m is not None and hasattr(_m, _n):
        setattr(_cs, _n, getattr(_m, _n))
for _n in ("Service", "ServiceManager"):
    _m = sys.modules.get(_PKG + ".core_services.service_manager")
    if _m is not None and hasattr(_m, _n):
        setattr(_cs, _n, getattr(_m, _n))
for _n in ("GitWatchService", "SysInfoService", "FileWatchService"):
    _m = sys.modules.get(_PKG + ".core_services.services")
    if _m is not None and hasattr(_m, _n):
        setattr(_cs, _n, getattr(_m, _n))

# --- terminal ---
# Paquete sintético: base (interfaz ABC + factory) primero porque
# unix/windows la importan. Los backends se cargan siempre — cada uno
# solo FUNCIONA en su plataforma, pero importarlos es seguro (los
# imports específicos de OS son lazy, dentro de los métodos).
_tm = types.ModuleType(_PKG + ".terminal")
_tm.__path__ = []  # se comporta como paquete
sys.modules[_PKG + ".terminal"] = _tm
_load(_PKG + ".terminal.base", "TERMINAL/TERMINAL-UTILS.py")
_load(_PKG + ".terminal.unix", "TERMINAL/TERMINAL-UNIX-UTILS.py")
_load(_PKG + ".terminal.windows", "TERMINAL/TERMINAL-WINDOWS-UTILS.py")
for _n in ("TerminalBackend", "create_backend"):
    _m = sys.modules.get(_PKG + ".terminal.base")
    if _m is not None and hasattr(_m, _n):
        setattr(_tm, _n, getattr(_m, _n))
