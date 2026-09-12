# -*- coding: utf-8 -*-
"""Configuraciones de ejecución (run configs) persistidas en el proyecto.

Guarda en .run_configs.json dentro de la carpeta del proyecto:
  { "configs": [ {"name": "test", "path": "/abs/path/to/file.py"}, ... ] }
"""
import json
import os


def _configs_file(project_dir):
    return os.path.join(project_dir, ".run_configs.json")


def load_configs(project_dir):
    """Devuelve lista de {name, path} guardadas en el proyecto."""
    p = _configs_file(project_dir)
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("configs", [])
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
    """Agrega o actualiza una config por nombre. Devuelve la lista completa."""
    configs = load_configs(project_dir)
    # Si ya existe una con el mismo nombre, actualizar el path
    for c in configs:
        if c["name"] == name:
            c["path"] = path
            save_configs(project_dir, configs)
            return configs
    configs.append({"name": name, "path": path})
    save_configs(project_dir, configs)
    return configs


def remove_config(project_dir, name):
    """Elimina una config por nombre."""
    configs = load_configs(project_dir)
    configs = [c for c in configs if c["name"] != name]
    save_configs(project_dir, configs)
    return configs


def get_config(project_dir, name):
    """Devuelve el path de una config por nombre, o None."""
    for c in load_configs(project_dir):
        if c["name"] == name:
            return c["path"]
    return None
