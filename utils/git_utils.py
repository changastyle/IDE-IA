# -*- coding: utf-8 -*-
"""GitUtils: utilidades de git para el panel de Git.

- Log de todas las ramas con refs, parents, fecha y autor.
- Cálculo de "lanes" (carriles) para dibujar el grafo estilo IntelliJ.
"""
import subprocess
import os

PALETTE = ["#3574f0", "#2ec4a5", "#e8804a", "#a78bfa", "#e05561",
           "#32ade6", "#22c55e", "#eab308"]


def find_repo_root(path):
    """Sube directorios hasta encontrar el .git (como IntelliJ)."""
    p = os.path.realpath(path or "")
    while p and p != os.path.dirname(p):
        if os.path.isdir(os.path.join(p, ".git")):
            return p
        p = os.path.dirname(p)
    return ""


class GitUtils:
    def __init__(self, repo_path):
        # Si el workspace es una subcarpeta, usar la raíz del repo
        self.repo = find_repo_root(repo_path) or (repo_path or "")

    def _git(self, *args):
        try:
            r = subprocess.run(
                ["git", "-C", self.repo, *args],
                capture_output=True, text=True, timeout=10)
            return r.stdout if r.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired):
            return ""

    def is_repo(self):
        return bool(self.repo) and os.path.isdir(
            os.path.join(self.repo, ".git"))

    def current_branch(self):
        return self._git("rev-parse", "--abbrev-ref", "HEAD").strip()

    def branches(self):
        """Ramas locales (sin remotos): main/master primero, luego alfabético."""
        out = self._git("for-each-ref",
                        "--format=%(refname:short)", "refs/heads")
        names = [b.strip() for b in out.splitlines() if b.strip()]
        main_names = {"main", "master"}
        main_b = [b for b in names if b in main_names]
        other = sorted([b for b in names if b not in main_names])
        return main_b + other

    def log_all(self, limit=300):
        """Commits de todas las ramas, más nuevos primero.

        Devuelve [{hash, short, parents, refs, branch, date, author, subject}]
        donde `branch` es la rama local de la que este commit es tip.
        """
        fmt = "%H%x1f%h%x1f%P%x1f%d%x1f%ad%x1f%an%x1f%s"
        out = self._git("log", "--all", f"-n{limit}",
                        "--date=format:%d/%m/%y, %H:%M",
                        f"--pretty=format:{fmt}")
        commits = []
        branch_of_tip = {}
        for line in out.splitlines():
            parts = line.split("\x1f")
            if len(parts) != 7:
                continue
            full, short, parents_s, refs_s, date, author, subject = parts
            parents = [p for p in parents_s.split() if p]
            refs = []
            local_branches = []  # todas las ramas locales de este commit
            branch = None
            if refs_s.strip():
                inner = refs_s.strip().strip("()")
                for ref in inner.split(","):
                    ref = ref.strip()
                    if not ref:
                        continue
                    if ref.startswith("HEAD -> "):
                        branch = ref[8:]
                        refs.append(branch)
                        if branch not in local_branches:
                            local_branches.append(branch)
                    elif ref.startswith("origin/"):
                        continue  # solo ramas locales en el grafo
                    elif not ref.startswith("tag: "):
                        refs.append(ref)
                        if not branch:
                            branch = ref
                        if ref not in local_branches:
                            local_branches.append(ref)
            for b in local_branches:
                branch_of_tip[b] = full
            commits.append({
                "hash": full, "short": short, "parents": parents,
                "refs": refs, "branch": branch,
                "branches": local_branches, "date": date,
                "author": author, "subject": subject,
            })
        return commits, branch_of_tip

    def graph(self, limit=300):
        """Calcula lanes y edges para dibujar el grafo.

        Devuelve {commits, lane_of, edges, lane_of_branch, colors, current}.
        - lane_of: hash → carril (x)
        - edges: [(hash, parent_hash)] conexiones del grafo
        - colors: branch → color

        Orden de carriles: main/master siempre a la izquierda (carril 0),
        el resto por antigüedad (la rama más nueva a la derecha).
        """
        commits, tips = self.log_all(limit)
        current = self.current_branch()
        lane_of_branch, colors = {}, {}
        next_lane = 0
        # main/master primero (carril 0), luego el resto por fecha del tip
        # (la rama con tip más antiguo va primero, la más nueva al final)
        main_names = {"main", "master"}
        main_branches = [b for b in tips if b in main_names]
        other_branches = [b for b in tips if b not in main_names]
        # Fecha del tip de cada rama para ordenar por antigüedad
        tip_date = {}
        for c in commits:
            if c["hash"] in tips.values() and c["branch"]:
                tip_date[c["branch"]] = c["date"]
        other_branches.sort(key=lambda b: tip_date.get(b, ""))
        ordered = main_branches + other_branches
        for b in ordered:
            if b not in lane_of_branch:
                lane_of_branch[b] = next_lane
                colors[b] = PALETTE[next_lane % len(PALETTE)]
                next_lane += 1
        # Un commit puede ser tip de varias ramas (p. ej. dev y puto en el
        # mismo hash): el nodo se dibuja en el carril de la rama actual si
        # participa; si no, de la primera en orden (main, luego por fecha).
        lane_at_tip = {}
        for b in ordered:
            h = tips.get(b)
            if h is None:
                continue
            if h not in lane_at_tip or b == current:
                lane_at_tip[h] = lane_of_branch[b]
        lane_of = {}
        edges = []
        for c in commits:
            h = c["hash"]
            if h in lane_at_tip:
                lane_of[h] = lane_at_tip[h]
            elif h not in lane_of:
                lane = None
                for p in c["parents"]:
                    if p in lane_of:
                        lane = lane_of[p]
                        break
                if lane is None:
                    # heredar de un hijo (fork): el commit es parent de otro
                    for other in commits:
                        if h in other["parents"] and other["hash"] in lane_of:
                            lane = lane_of[other["hash"]]
                            break
                if lane is None:
                    lane = next_lane
                    next_lane += 1
                lane_of[h] = lane
            for p in c["parents"]:
                edges.append((h, p))
            if c["branch"] and c["branch"] not in colors:
                colors[c["branch"]] = colors.get(
                    current, PALETTE[0])
        # Fila base de cada rama (merge-base con el tronco) para dibujar
        # el rail de ramas que aún no tienen commits propios.
        row_of_c = {cc["hash"]: i for i, cc in enumerate(commits)}
        trunk = next((b for b in tips if b in ("main", "master")),
                     current if current in tips
                     else next(iter(tips), None))
        branch_base = {}
        for b, tip_h in tips.items():
            if b == trunk or tip_h not in row_of_c:
                continue
            mb = self._git("merge-base", tip_h,
                           tips.get(trunk, tip_h)).strip()
            branch_base[b] = row_of_c.get(mb, row_of_c[tip_h])
        return {"commits": commits, "lane_of": lane_of, "edges": edges,
                "lane_of_branch": lane_of_branch, "colors": colors,
                "current": current, "tips": tips,
                "branch_base": branch_base}

    def branch_commits(self, branch, limit=50):
        """Commits alcanzables desde una rama (más nuevos primero)."""
        fmt = "%h%x1f%ad%x1f%an%x1f%s"
        out = self._git("log", branch, f"-n{limit}",
                        "--date=format:%d/%m/%y, %H:%M",
                        f"--pretty=format:{fmt}")
        rows = []
        for line in out.splitlines():
            parts = line.split("\x1f")
            if len(parts) == 4:
                rows.append({"short": parts[0], "date": parts[1],
                             "author": parts[2], "subject": parts[3]})
        return rows

    def checkout(self, branch):
        return self._git("checkout", branch)

    def commit_files(self, commit_hash):
        """Archivos cambiados en un commit con stats de líneas.

        Devuelve [{path, status, added, removed, lines: [{type, text}]}]
        donde type es '+' (añadida), '-' (borrada), ' ' (contexto).
        """
        # Stats por archivo
        out = self._git("show", "--no-color", "--name-status",
                        "--format=", commit_hash)
        files = []
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            status, path = parts
            files.append({"path": path, "status": status[:1],
                          "added": 0, "removed": 0, "lines": []})
        # Numstat para added/removed
        out2 = self._git("show", "--no-color", "--numstat", "--format=",
                         commit_hash)
        for i, line in enumerate(out2.splitlines()):
            if i < len(files):
                p = line.split("\t")
                if len(p) >= 3:
                    files[i]["added"] = int(p[0]) if p[0] != "-" else 0
                    files[i]["removed"] = int(p[1]) if p[1] != "-" else 0
        # Diff por archivo (líneas cambiadas)
        out3 = self._git("show", "--no-color", "--unified=3",
                         "--format=", commit_hash)
        cur_file = None
        for line in out3.splitlines():
            if line.startswith("diff --git"):
                cur_file = None
            elif line.startswith("+++ b/"):
                cur_file = line[6:]
                for f in files:
                    if f["path"] == cur_file:
                        cur_file = f
                        break
                else:
                    cur_file = None
            elif line.startswith("--- "):
                continue
            elif line.startswith("@@"):
                continue
            elif cur_file is not None:
                if line.startswith("+") and not line.startswith("+++"):
                    cur_file["lines"].append({"type": "+", "text": line[1:]})
                elif line.startswith("-") and not line.startswith("---"):
                    cur_file["lines"].append({"type": "-", "text": line[1:]})
        return files
