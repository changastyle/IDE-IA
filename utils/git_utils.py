# -*- coding: utf-8 -*-
"""GitUtils: utilidades de git para el panel de Git.

- Log de todas las ramas con refs, parents, fecha y autor.
- Cálculo de "lanes" (carriles) para dibujar el grafo estilo IntelliJ.
"""
import difflib
import datetime
import subprocess
import os

from utils.branch_colors import PALETTE, get_colors


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
                capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=10)
            return r.stdout if r.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired):
            return ""

    def _git_ok(self, *args):
        """(ok, salida+error) — para acciones que reportan resultado."""
        try:
            r = subprocess.run(
                ["git", "-C", self.repo, *args],
                capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=30)
            return r.returncode == 0, (r.stderr or r.stdout or "").strip()
        except (OSError, subprocess.TimeoutExpired) as ex:
            return False, str(ex)

    def _git_stdin(self, *args, data=""):
        try:
            r = subprocess.run(
                ["git", "-C", self.repo, *args],
                input=data, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=30)
            return r.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

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
        out = self._git("log", "--all", "--topo-order", f"-n{limit}",
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
        lane_of_branch = {}
        colors = self.branch_colors()  # persistentes, compartidos
        next_lane = 0
        # main/master primero (carril 0), luego el resto por fecha del tip
        # (la rama con tip más antiguo va primero, la más nueva al final)
        main_names = {"main", "master"}
        main_branches = [b for b in tips if b in main_names]
        other_branches = [b for b in tips if b not in main_names]
        # Fecha del tip de cada rama para ordenar por antigüedad
        date_of = {c["hash"]: c["date"] for c in commits}
        tip_date = {b: date_of.get(h, "") for b, h in tips.items()}
        other_branches.sort(key=lambda b: tip_date.get(b, ""))
        ordered = main_branches + other_branches
        for b in ordered:
            if b not in lane_of_branch:
                lane_of_branch[b] = next_lane
                next_lane += 1
        # Tronco: main/master, si no la rama actual, si no la primera.
        trunk = next((b for b in tips if b in ("main", "master")),
                     current if current in tips
                     else next(iter(tips), None))
        trunk_lane = lane_of_branch.get(trunk, 0)
        trunk_tip = tips.get(trunk, "")
        # Commits exclusivos de cada rama (alcanzables desde su tip pero
        # no desde el tronco): van al carril de la rama. La historia
        # compartida queda en el carril del tronco — así main corre de
        # punta a punta como en IntelliJ. Si un commit lo reclaman varias
        # ramas (tips compartidos), gana la primera en `ordered`.
        claimed = {}
        for b in ordered:
            if b == trunk or not trunk_tip:
                continue
            tip_h = tips.get(b)
            if not tip_h:
                continue
            out = self._git("rev-list", tip_h, "--not", trunk_tip)
            for hh in out.splitlines():
                hh = hh.strip()
                if hh and hh not in claimed:
                    claimed[hh] = lane_of_branch[b]
        lane_of = {}
        edges = []
        for c in commits:
            h = c["hash"]
            lane_of[h] = claimed.get(h, trunk_lane)
            for p in c["parents"]:
                edges.append((h, p))
        # Fila base de cada rama (merge-base con el tronco) para dibujar
        # el rail de ramas que aún no tienen commits propios.
        row_of_c = {cc["hash"]: i for i, cc in enumerate(commits)}
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
                "branch_base": branch_base,
                "head_hash": tips.get(current)}

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

    def _branch_births(self):
        """{rama: ts de creación} vía reflog — distingue ramas recreadas."""
        births = {}
        for b in self.branches():
            out = self._git("reflog", "show", b, "--format=%ct")
            ts = out.strip().splitlines()[-1].strip() if out.strip() else ""
            if not ts:
                ts = self._git("log", "-1", "--format=%ct", b).strip()
            births[b] = ts or "0"
        return births

    def branch_colors(self):
        """{rama: color} persistente y único (ng-studio/colores-branches/)."""
        return get_colors(self.repo, self._branch_births())

    def branch_color(self, branch):
        """Color persistente de la rama."""
        return self.branch_colors().get(branch, PALETTE[0])

    # ---- changes / commit parcial ----
    def status(self):
        """(cambiados, sin trackear) — paths relativos al repo."""
        out = self._git("status", "--porcelain", "-uall")
        changed, untracked = [], []
        for line in out.splitlines():
            if len(line) < 4:
                continue
            st, path = line[:2], line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            if "__pycache__" in path or path.endswith(".pyc"):
                continue  # basura de python: no mostrar
            if st.strip() == "??":
                untracked.append(path)
            elif st.strip():
                changed.append(path)
        return changed, untracked

    def head_content(self, path):
        """Contenido del archivo en HEAD ("" si no existe)."""
        return self._git("show", f"HEAD:{path}")

    def work_content(self, path):
        """Contenido actual del archivo en el working tree."""
        try:
            with open(os.path.join(self.repo, path), "r",
                      encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""

    def diff_rows(self, path):
        """Filas lado a lado HEAD vs working tree.

        [{kind, left_n, left, right_n, right}] — kind: 'ctx'|'mod'|'add'|'del'.
        Las filas 'add' y 'mod' son las seleccionables (checkboxes).
        """
        a = self.head_content(path).splitlines()
        b = self.work_content(path).splitlines()
        if "\x00" in "".join(a[:40]) or "\x00" in "".join(b[:40]):
            return []  # binario (pyc, imagen, etc.): no hay diff de líneas
        sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
        rows = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for k in range(i2 - i1):
                    rows.append({"kind": "ctx", "left_n": i1 + k + 1,
                                 "left": a[i1 + k], "right_n": j1 + k + 1,
                                 "right": b[j1 + k]})
            elif tag == "replace":
                li, ri = i1, j1
                while li < i2 or ri < j2:
                    if li < i2 and ri < j2:
                        rows.append({"kind": "mod", "left_n": li + 1,
                                     "left": a[li], "right_n": ri + 1,
                                     "right": b[ri]})
                        li += 1
                        ri += 1
                    elif li < i2:
                        rows.append({"kind": "del", "left_n": li + 1,
                                     "left": a[li], "right_n": None,
                                     "right": ""})
                        li += 1
                    else:
                        rows.append({"kind": "add", "left_n": None,
                                     "left": "", "right_n": ri + 1,
                                     "right": b[ri]})
                        ri += 1
            elif tag == "delete":
                for i in range(i1, i2):
                    rows.append({"kind": "del", "left_n": i + 1,
                                 "left": a[i], "right_n": None, "right": ""})
            elif tag == "insert":
                for j in range(j1, j2):
                    rows.append({"kind": "add", "left_n": None, "left": "",
                                 "right_n": j + 1, "right": b[j]})
        return rows

    def blame(self, path, rev=None):
        """{nro_de_línea: (fecha dd/mm/yy, autor)} — del working tree o de `rev`."""
        args = ["blame", "--porcelain"]
        if rev:
            args.append(rev)
        args += ["--", path]
        out = self._git(*args)
        meta = {}  # sha → (fecha, autor)
        rows = {}
        cur_sha = cur_final = None
        for line in out.splitlines():
            if line.startswith("\t"):
                if cur_final is not None:
                    rows[cur_final] = meta.get(cur_sha, ("", ""))
                    cur_final = None
                continue
            parts = line.split(" ", 3)
            if len(parts) >= 3 and len(parts[0]) == 40 \
               and parts[1].isdigit() and parts[2].isdigit():
                cur_sha, cur_final = parts[0], int(parts[2])
            elif line.startswith("author "):
                a, d = meta.get(cur_sha, ("", ""))
                meta[cur_sha] = (a or line[7:], d)
            elif line.startswith("author-time "):
                try:
                    ts = int(line[12:])
                except ValueError:
                    continue
                ds = datetime.datetime.fromtimestamp(ts).strftime("%d/%m/%y")
                a, _ = meta.get(cur_sha, ("", ""))
                meta[cur_sha] = (a, ds)
        return rows

    def file_last_mod(self, path):
        """(fecha dd/mm/yy, hash corto) del último commit que tocó el archivo."""
        out = self._git("log", "-1", "--format=%h %ad",
                        "--date=format:%d/%m/%y", "--", path)
        parts = out.strip().split(" ", 1)
        return (parts[1], parts[0]) if len(parts) == 2 else ("", "")

    def reset_index(self):
        self._git("reset", "--mixed", "-q")

    def stage_files(self, paths):
        if paths:
            self._git("add", "--", *paths)

    def stage_content(self, path, content):
        """Stagea `content` para `path` (commit parcial: solo líneas elegidas).

        Las borradas del HEAD se aplican siempre; las agregadas/modificadas
        según `content`. Genera un patch y lo aplica al index.
        """
        a = self.head_content(path).splitlines(keepends=True)
        b = content.splitlines(keepends=True)
        if a and not a[-1].endswith("\n"):
            a[-1] += "\n"
        if b and not b[-1].endswith("\n"):
            b[-1] += "\n"
        patch = "".join(difflib.unified_diff(
            a, b, fromfile=f"a/{path}", tofile=f"b/{path}"))
        if patch:
            self._git_stdin("apply", "--cached", "--whitespace=nowarn",
                            data=patch)

    def commit(self, message, amend=False):
        """Commit del index. Con amend y mensaje vacío → --no-edit."""
        if amend and not message:
            return self._git_ok("commit", "--amend", "--no-edit")
        args = ["commit", "-m", message]
        if amend:
            args.append("--amend")
        return self._git_ok(*args)

    # ---- stash (el bolsillo) ----
    def stash_list(self):
        """[{index, sel, msg, date, files}] — entradas del stash, 0 = última."""
        out = self._git("stash", "list", "--format=%gd%x1f%gs%x1f%ct")
        entries = []
        for line in out.splitlines():
            parts = line.split("\x1f")
            if len(parts) != 3:
                continue
            sel, msg, ts = parts
            idx = sel.split("{", 1)[1].rstrip("}") if "{" in sel else sel
            date = ""
            try:
                date = datetime.datetime.fromtimestamp(
                    int(ts)).strftime("%d/%m %H:%M")
            except (ValueError, OSError):
                pass
            files = [f.strip() for f in self._git(
                "stash", "show", "--include-untracked", "--name-only",
                sel).splitlines() if f.strip()]
            entries.append({"index": int(idx), "sel": sel, "msg": msg,
                            "date": date, "files": files})
        return entries

    def stash_push(self):
        """Guarda todos los cambios (incluye sin trackear) en el stash."""
        return self._git_ok("stash", "push", "-u")

    def stash_restore(self, index, paths):
        """Recupera del stash los archivos dados (los untracked vienen de ^3)."""
        sel = f"stash@{{{index}}}"
        ok_all = True
        for p in paths:
            ok = self._git_stdin("checkout", sel, "--", p)
            if not ok:
                ok = self._git_stdin("checkout", f"{sel}^3", "--", p)
            ok_all = ok_all and ok
        return ok_all

    def stash_drop(self, index):
        return self._git_ok("stash", "drop", f"stash@{{{index}}}")

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
