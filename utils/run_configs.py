# -*- coding: utf-8 -*-
"""Configuraciones de ejecución (run configs) persistidas en el proyecto.

Guarda en .run_configs.json dentro de la carpeta del proyecto:
  { "configs": [
      {"name": "start", "type": "npm", "script": "start", "args": "",
       "open_browser": true},
      {"name": "server", "type": "node", "path": "server.js", "args": "",
       "open_browser": true},
      {"name": "build", "type": "terminal", "command": "npm run build",
       "open_browser": false},
  ] }

Formato legacy (solo {name, path}) se convierte a type=node al cargar.
"""
import json
import os

VALID_TYPES = ("node", "npm", "python", "java", "springboot", "quarkus",
               "terminal", "compound")

# Tipos que ejecutan un archivo directamente (interpreter, filtro, placeholder)
FILE_TYPES = {
    "node": ("node", "JavaScript (*.js)", "server.js"),
    "python": ("python3", "Python (*.py)", "main.py"),
    "java": ("java", "Java (*.java)", "Main.java"),
}

# Tipos de build tool: comando por defecto según archivos del proyecto
GOAL_TYPES = {
    "springboot": "mvn spring-boot:run",
    "quarkus": "mvn quarkus:dev",
}


def _configs_file(project_dir):
    return os.path.join(project_dir, ".run_configs.json")


def _normalize(c):
    """Normaliza una config (soporta formato legacy {name, path})."""
    c = dict(c)
    if "type" not in c:
        c["type"] = "node"
    if c["type"] not in VALID_TYPES:
        c["type"] = "terminal"
    c.setdefault("name", "config")
    c.setdefault("args", "")
    c.setdefault("open_browser", False)
    if c["type"] in FILE_TYPES:
        c.setdefault("path", "")
    elif c["type"] == "npm":
        c.setdefault("script", "start")
    elif c["type"] in GOAL_TYPES:
        c.setdefault("goal", GOAL_TYPES[c["type"]])
    elif c["type"] == "terminal":
        c.setdefault("command", "")
    elif c["type"] == "compound":
        c.setdefault("members", [])
    return c


def load_configs(project_dir):
    """Devuelve lista de configs normalizadas del proyecto."""
    p = _configs_file(project_dir)
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Soporta {"configs": [...]} y formato legacy lista plana [...]
        items = data.get("configs", []) if isinstance(data, dict) else data
        return [_normalize(c) for c in items]
    except (OSError, json.JSONDecodeError):
        return []


def save_configs(project_dir, configs):
    """Guarda la lista completa de configs."""
    p = _configs_file(project_dir)
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"configs": configs}, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def add_config(project_dir, name, path):
    """Agrega o actualiza una config node por nombre. Devuelve la lista."""
    configs = load_configs(project_dir)
    for c in configs:
        if c["name"] == name:
            c["type"], c["path"] = "node", path
            save_configs(project_dir, configs)
            return configs
    configs.append(_normalize({"name": name, "path": path}))
    save_configs(project_dir, configs)
    return configs


def remove_config(project_dir, name):
    """Elimina una config por nombre."""
    configs = load_configs(project_dir)
    configs = [c for c in configs if c["name"] != name]
    save_configs(project_dir, configs)
    return configs


def get_config(project_dir, name):
    """Devuelve una config por nombre, o None."""
    for c in load_configs(project_dir):
        if c["name"] == name:
            return c
    return None


def npm_scripts(project_dir):
    """Devuelve los scripts de package.json del proyecto (o lista vacía)."""
    p = os.path.join(project_dir, "package.json")
    if not os.path.isfile(p):
        return []
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return sorted((data.get("scripts") or {}).keys())
    except (OSError, json.JSONDecodeError):
        return []


def build_command(cfg, project_dir):
    """Construye el comando shell para una config."""
    t = cfg.get("type", "terminal")
    args = (cfg.get("args") or "").strip()
    if t in FILE_TYPES:
        interp = FILE_TYPES[t][0]
        path = cfg.get("path", "")
        cmd = f"{interp} {shlex_quote(path)}" if path else ""
    elif t == "npm":
        cmd = f"npm run {cfg.get('script', 'start')}"
    elif t in GOAL_TYPES:
        cmd = cfg.get("goal") or GOAL_TYPES[t]
    elif t == "compound":
        # Corre las configs miembro en paralelo: "cmd1 & cmd2 & wait"
        all_cfgs = {c["name"]: c for c in load_configs(project_dir)}
        subs = []
        for name in cfg.get("members", []):
            sub = all_cfgs.get(name)
            if not sub or sub.get("type") == "compound":
                continue  # sin recursión de compounds
            sub_cmd = build_command(sub, project_dir)
            if sub_cmd:
                subs.append(sub_cmd)
        cmd = " & ".join(subs)
        if len(subs) > 1:
            cmd += " & wait"
    else:
        cmd = cfg.get("command", "")
    if args:
        cmd = f"{cmd} {args}"
    env = (cfg.get("env") or "").strip()
    if env:
        # "A=1 B=2" o "A=1;B=2" → prefijo de asignaciones shell
        parts = [p for p in env.replace(";", " ").split() if "=" in p]
        if parts:
            cmd = " ".join(parts) + " " + cmd
    return cmd.strip()


def shlex_quote(s):
    import shlex
    return shlex.quote(str(s))
