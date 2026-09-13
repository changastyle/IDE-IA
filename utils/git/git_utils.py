# -*- coding: utf-8 -*-
"""Lógica de git aislada: rama actual, ramas, pull, push, commits.

Todas las funciones operan sobre un path de repo y devuelven
(ok: bool, payload) donde payload es str en error o lista/str en éxito.
"""
import os
import subprocess


def _run(repo, *args, timeout=15):
    """Ejecuta git en repo. Devuelve (ok, stdout) o (False, stderr)."""
    try:
        r = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout)
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or "error desconocido").strip()
        return True, r.stdout.strip()
    except FileNotFoundError:
        return False, "git no está instalado"
    except subprocess.TimeoutExpired:
        return False, "timeout ejecutando git"
    except Exception as e:
        return False, str(e)


def is_repo(path):
    """¿path es (parte de) un repo git?"""
    ok, out = _run(path, "rev-parse", "--is-inside-work-tree")
    return ok and out == "true"


def get_current_branch(path):
    """Rama actual o '' si detached/no repo."""
    ok, out = _run(path, "rev-parse", "--abbrev-ref", "HEAD")
    return out if ok else ""


def list_branches(path):
    """(locales, remotas) — listas de str sin prefijo origin/."""
    ok, out = _run(path, "branch", "--format=%(refname:short)")
    if not ok:
        return [], []
    local = [b for b in out.splitlines() if b and not b.startswith("remotes/")]
    ok, out = _run(path, "branch", "-r", "--format=%(refname:short)")
    remote = []
    if ok:
        remote = [b.split("/", 1)[1] for b in out.splitlines()
                  if b and "/" in b and "HEAD" not in b]
    return local, remote


def pull(path):
    return _run(path, "pull", "--ff-only", timeout=60)


def push(path):
    return _run(path, "push", timeout=60)


def checkout(path, branch):
    return _run(path, "checkout", branch, timeout=30)


def create_branch(path, name):
    return _run(path, "checkout", "-b", name, timeout=30)


def status_short(path):
    """Lista de (estado, archivo) o None si error."""
    ok, out = _run(path, "status", "--porcelain")
    if not ok:
        return None
    out2 = []
    for line in out.splitlines():
        if len(line) >= 4:
            out2.append((line[:2], line[3:]))
    return out2


def has_remote(path):
    ok, out = _run(path, "remote")
    return ok and bool(out.strip())


def clone_dest_name(url):
    """Nombre de carpeta que generaría `git clone <url>`."""
    name = url.rstrip("/").rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    if ":" in name:  # estilo scp: git@host:repo.git
        name = name.rsplit(":", 1)[-1]
    return name


def clone(url, dest_parent):
    """Clona url dentro de dest_parent. Devuelve (ok, dest_path | stderr)."""
    name = clone_dest_name(url)
    if not name:
        return False, "URL inválida"
    if not os.path.isdir(dest_parent):
        return False, f"No existe la carpeta destino: {dest_parent}"
    dest = os.path.join(dest_parent, name)
    if os.path.exists(dest):
        return False, f"Ya existe {dest}"
    ok, out = _run(dest_parent, "clone", url, timeout=600)
    return (True, dest) if ok else (False, out)
