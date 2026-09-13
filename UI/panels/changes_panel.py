# -*- coding: utf-8 -*-
"""Panel de Changes: commit estilo IntelliJ + historial de la rama.

- Arriba: input de mensaje con 3 botones (✨ generate, ✓ commit, ↑ push).
- Medio: Changes / Unversioned Files con checkboxes por archivo
  (parcial = rayita, se eligen líneas en el panel de Diff).
- Abajo: commits de la rama actual con la pill de la rama en su color único.
"""
import os

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton,
    QLineEdit, QCheckBox, QScrollArea, QTreeWidget, QTreeWidgetItem,
)

from utils.git_utils import GitUtils
from utils.git import push

ICONOS = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "iconos")

BTN_GEN = "#a78bfa"
BTN_COMMIT = "#3574f0"
BTN_PUSH = "#22c55e"


def _icon(name):
    p = os.path.join(ICONOS, name)
    return QIcon(p) if os.path.exists(p) else QIcon()


class _Tri(QCheckBox):
    """Checkbox tri-estado: el usuario solo cicla ✓/☐ (parcial es interno)."""

    def nextCheckState(self):
        self.setCheckState(
            Qt.Unchecked if self.checkState() == Qt.Checked else Qt.Checked)


# Indicator con ✓/rayita blancas dentro del cuadro azul
_CHK_SS = (
    "QCheckBox::indicator{width:16px;height:16px;border-radius:4px;"
    "border:1px solid #555a63;background:#1e1f22;}"
    f"QCheckBox::indicator:checked{{background:#3574f0;border-color:#3574f0;"
    f"image:url({os.path.join(ICONOS, 'check_w.svg')});}}"
    f"QCheckBox::indicator:indeterminate{{background:#3574f0;"
    f"border-color:#3574f0;"
    f"image:url({os.path.join(ICONOS, 'rayita_w.svg')});}}"
)


class _Elide(QLabel):
    """QLabel que recorta el texto con … para entrar en el ancho disponible."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._raw = text

    def setText(self, t):
        self._raw = t
        super().setText(t)

    def resizeEvent(self, e):
        super().setText(self.fontMetrics().elidedText(
            self._raw, Qt.ElideRight, max(24, self.width() - 2)))
        super().resizeEvent(e)


class _GroupRow(QFrame):
    """Header de grupo: ▸/▾ + checkbox tri-estado + nombre + contador."""

    toggled = Signal(object)   # Qt.CheckState
    collapsed_changed = Signal(bool)

    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.setObjectName("groupRow")
        self.setAttribute(Qt.WA_StyledBackground)
        self.expanded = True
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 3, 10, 3)
        h.setSpacing(8)
        self.btn_arrow = QPushButton("▾")
        self.btn_arrow.setFixedSize(18, 18)
        self.btn_arrow.setCursor(Qt.PointingHandCursor)
        self.btn_arrow.setStyleSheet(
            "QPushButton{background:transparent;border:none;color:#8e8e93;"
            "font-size:11px;}")
        self.btn_arrow.clicked.connect(self.toggle_collapse)
        h.addWidget(self.btn_arrow)
        self.lbl = QLabel(name)
        self.lbl.setStyleSheet(
            "color:#d7dae0; font-size:13px; font-weight:bold;"
            "background:transparent;")
        h.addWidget(self.lbl)
        h.addStretch(1)
        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet(
            "color:#8e8e93; font-size:12px; background:transparent;")
        h.addWidget(self.lbl_count)
        self.chk = _Tri()
        self.chk.setStyleSheet(_CHK_SS)
        self.chk.setCheckState(Qt.Checked)
        self.chk.toggled.connect(
            lambda _: self.toggled.emit(self.chk.checkState()))
        h.addWidget(self.chk)

    def toggle_collapse(self):
        self.expanded = not self.expanded
        self.btn_arrow.setText("▾" if self.expanded else "▸")
        self.collapsed_changed.emit(not self.expanded)


class _FileRow(QFrame):
    """Fila de archivo: checkbox tri-estado + ícono + nombre (→ diff)."""

    state_changed = Signal(object)
    open_diff = Signal(str)

    def __init__(self, path, tracked, icon_path="", parent=None):
        super().__init__(parent)
        self.setObjectName("fileRow")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setFrameShape(QFrame.NoFrame)
        self.path = path
        self.setCursor(Qt.PointingHandCursor)
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 2, 8, 2)
        h.setSpacing(8)
        name = os.path.basename(path)
        self.lbl_name = _Elide(name)
        self.lbl_name.setStyleSheet(
            "color:#d7dae0; font-size:12px; background:transparent;"
            "border:none;")
        self.lbl_name.setToolTip(path)
        h.addWidget(self.lbl_name, 1)
        self.lbl_part = QLabel("")
        self.lbl_part.setStyleSheet(
            "color:#6b7078; font-size:11px; font-style:italic;"
            "background:transparent; border:none;")
        h.addWidget(self.lbl_part)
        folder = os.path.dirname(path)
        if folder:
            fl = _Elide(folder)
            fl.setStyleSheet(
                "color:#e8c97a; font-size:10px; background:"
                "rgba(240,200,120,0.13); border-radius:4px; padding:1px 6px;"
                "border:none;")
            fl.setMaximumWidth(160)
            h.addWidget(fl)
        self.chk = _Tri()
        self.chk.setStyleSheet(_CHK_SS)
        self.chk.setCheckState(Qt.Checked)
        self.chk.toggled.connect(
            lambda _: self.state_changed.emit(self.chk.checkState()))
        h.addWidget(self.chk)

    def mouseReleaseEvent(self, e):
        # clic en el nombre (no en el checkbox) → abrir el diff
        if self.chk.geometry().contains(
                self.chk.mapFrom(self, e.position().toPoint())):
            return super().mouseReleaseEvent(e)
        if e.button() == Qt.LeftButton:
            self.open_diff.emit(self.path)
        super().mouseReleaseEvent(e)


class ChangesPanel(QWidget):
    """Panel de Changes completo."""

    diff_requested = Signal(str)      # path relativo → abrir panel de Diff
    committed = Signal(bool)          # True si hay que pushear después
    generate_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo = ""
        self.utils = None
        self._files = []          # [{path, tracked, state, lines, total}]
        self._rows = {}           # path → _FileRow
        self._groups = {}
        # El auto-refresco lo maneja listeners.GitListener (watcher + poll
        # central que avisa a todos los componentes suscriptos).

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # ---- input de mensaje + 3 botones ----
        top = QFrame()
        top.setStyleSheet("background:transparent;")
        th = QHBoxLayout(top)
        th.setContentsMargins(8, 8, 8, 6)
        th.setSpacing(6)
        self.inp_msg = QLineEdit()
        self.inp_msg.setPlaceholderText("Message (⌘Ent…)")
        self.inp_msg.setStyleSheet(
            "QLineEdit{background:#26282e; border:1px solid #3a3d45;"
            "border-radius:8px; padding:6px 10px; font-size:12px;"
            "color:#e8eaed;}"
            "QLineEdit:focus{border-color:#3574f0;}")
        self.inp_msg.returnPressed.connect(lambda: self.do_commit())
        th.addWidget(self.inp_msg, 1)
        for tip, color, svg, cb in (
                ("Generate (IA)", BTN_GEN, "generar_w.svg",
                 self.generate_requested.emit),
                ("Commit", BTN_COMMIT, "check_w.svg",
                 lambda: self.do_commit()),
                ("Commit and Push", BTN_PUSH, "flecha_arriba_w.svg",
                 lambda: self.do_commit(push_after=True))):
            b = QPushButton()
            b.setFixedSize(32, 32)
            b.setIcon(_icon(svg))
            b.setIconSize(QSize(17, 17))
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:{color}; border:none;"
                "border-radius:8px;}"
                "QPushButton:hover{background:"
                + color + ";}")
            b.clicked.connect(cb)
            th.addWidget(b)
        v.addWidget(top)

        # ---- lista de cambios ----
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}")
        self.list_host = QWidget()
        self.list_lay = QVBoxLayout(self.list_host)
        self.list_lay.setContentsMargins(0, 0, 0, 0)
        self.list_lay.setSpacing(0)
        self.scroll.setWidget(self.list_host)
        v.addWidget(self.scroll, 3)

        # ---- amend + stats ----
        amend_row = QFrame()
        ah = QHBoxLayout(amend_row)
        ah.setContentsMargins(10, 4, 10, 4)
        self.btn_amend = QPushButton("Amend")
        self.btn_amend.setCheckable(True)
        self.btn_amend.setFixedHeight(22)
        self.btn_amend.setCursor(Qt.PointingHandCursor)
        self.btn_amend.setToolTip(
            "Amend: suma lo tildado al último commit en vez de crear uno\n"
            "nuevo (si escribís mensaje, también lo corrige).\n"
            "Solo sirve si todavía no hiciste push de ese commit.")
        self.btn_amend.setStyleSheet(
            "QPushButton{color:#d7dae0; font-size:11px; background:#26282e;"
            "border:1px solid #3a3d45; border-radius:6px; padding:0 10px;}"
            "QPushButton:checked{background:#e8804a; color:#fff;"
            "border-color:#e8804a; font-weight:bold;}")
        ah.addWidget(self.btn_amend)
        ah.addStretch(1)
        self.lbl_stats = QLabel("")
        self.lbl_stats.setStyleSheet(
            "color:#22c55e; font-size:11px; background:transparent;")
        ah.addWidget(self.lbl_stats)
        v.addWidget(amend_row)

        # ---- historial de la rama ----
        hist_head = QFrame()
        hist_head.setStyleSheet(
            "background:transparent;border-top:1px solid #2b2e34;")
        hh = QHBoxLayout(hist_head)
        hh.setContentsMargins(10, 6, 10, 4)
        t = QLabel("Historial")
        t.setStyleSheet(
            "color:#d7dae0; font-size:13px; font-weight:bold;"
            "background:transparent;")
        hh.addWidget(t)
        self.pill_branch = QLabel("")
        self.pill_branch.setStyleSheet(
            "background:#3574f0; color:#fff; font-size:11px;"
            "font-weight:bold; border-radius:10px; padding:2px 10px;")
        hh.addWidget(self.pill_branch)
        hh.addStretch(1)
        v.addWidget(hist_head)

        self.tree_hist = QTreeWidget()
        self.tree_hist.setHeaderHidden(True)
        self.tree_hist.setRootIsDecorated(False)
        self.tree_hist.setColumnCount(4)
        self.tree_hist.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tree_hist.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tree_hist.setStyleSheet(
            "QTreeWidget{background:transparent;border:none;outline:none;"
            "font-size:11px;}"
            "QTreeWidget::item{padding:2px 2px;}")
        self.tree_hist.header().setStretchLastSection(False)
        v.addWidget(self.tree_hist, 2)

    # ---- repo ----
    def set_repo(self, path):
        self.repo = path or ""
        self.utils = GitUtils(self.repo) if self.repo else None
        self.refresh()

    def showEvent(self, e):
        # al abrir el panel, refrescar de una
        self.refresh()
        super().showEvent(e)

    def _git_init(self):
        """Botón 'Create git project': git init + rearmar el watcher."""
        ok, out = self.utils.init()
        self._status(("✔ " if ok else "✖ ") + (out or "git init")[:100])
        if ok:
            self.set_repo(self.repo)   # ahora existe .git → watcher + refresh

    # ---- construcción de la lista ----
    def refresh(self):
        # limpiar
        while self.list_lay.count():
            it = self.list_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._rows.clear()
        self._groups.clear()
        if not self.utils or not self.utils.is_repo():
            empty = QWidget()
            ev = QVBoxLayout(empty)
            ev.setSpacing(10)
            ev.addStretch(1)
            lbl = QLabel("No es un repo git")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                "color:#666; font-size:13px; background:transparent;")
            ev.addWidget(lbl)
            if self.repo:
                btn = QPushButton("⎇  Initialize Git Project")
                btn.setCursor(Qt.PointingHandCursor)
                btn.setToolTip(f"git init en {self.repo}")
                btn.setStyleSheet(
                    "QPushButton{background:#3574f0; color:#fff; border:none;"
                    "border-radius:8px; padding:7px 18px; font-size:12px;"
                    "font-weight:bold;}"
                    "QPushButton:hover{background:#4a86f8;}")
                btn.clicked.connect(self._git_init)
                ev.addWidget(btn, alignment=Qt.AlignCenter)
            ev.addStretch(1)
            self.list_lay.addWidget(empty)
            self._refresh_history()
            return

        changed, untracked = self.utils.status()
        prev = {f["path"]: f for f in self._files}
        self._files = []
        for group, paths, tracked in (
                ("Changes", changed, True),
                ("Unversioned Files", untracked, False)):
            if not paths:
                continue
            # el grupo "Changes" no lleva header: los archivos van directo
            # debajo del input; solo "Unversioned Files" queda como grupo
            g = _GroupRow(group) if group != "Changes" else None
            if g:
                self.list_lay.addWidget(g)
            rows = []
            for p in paths:
                try:
                    total = sum(1 for r in self.utils.diff_rows(p)
                                if r["kind"] in ("add", "mod"))
                except Exception:
                    total = 0
                old = prev.get(p)
                if old and old["total"] == total:
                    f = dict(old)
                else:
                    f = {"path": p, "tracked": tracked, "total": total,
                         "state": Qt.Checked,
                         "lines": None}  # None = todas
                self._files.append(f)
                row = _FileRow(p, tracked)
                row.chk.setCheckState(f["state"])
                row.chk.toggled.connect(
                    lambda _c, fp=p: self._on_file_toggle(fp))
                row.state_changed.connect(
                    lambda st, fp=p: self._on_file_state(fp, st))
                row.open_diff.connect(self.diff_requested.emit)
                self._rows[p] = row
                self.list_lay.addWidget(row)
                rows.append(row)
                self._update_file_labels(f)
            if g is None:
                continue
            g.toggled.connect(
                lambda st, rs=rows: self._set_group(st, rs))
            g.collapsed_changed.connect(
                lambda hide, rs=rows: [r.setVisible(not hide) for r in rs])
            self._groups[group] = (g, rows)
            g.chk.blockSignals(True)
            g.chk.setCheckState(self._group_state(rows))
            g.chk.blockSignals(False)
        self.list_lay.addStretch(1)
        self._update_stats()
        self._refresh_history()

    def _group_state(self, rows):
        states = [r.chk.checkState() for r in rows]
        if all(s == Qt.Checked for s in states):
            return Qt.Checked
        if all(s == Qt.Unchecked for s in states):
            return Qt.Unchecked
        return Qt.PartiallyChecked

    def _set_group(self, state, rows):
        for r in rows:
            if r.chk.checkState() != state:
                r.chk.setCheckState(state)

    def _on_file_toggle(self, path):
        # el usuario tocó el checkbox → sincronizar modelo
        row = self._rows.get(path)
        f = self._file(path)
        if row and f:
            f["state"] = row.chk.checkState()
            if f["state"] == Qt.Checked:
                f["lines"] = None

    def _on_file_state(self, path, state):
        f = self._file(path)
        if f:
            f["state"] = state
            if state == Qt.Checked:
                f["lines"] = None
            elif state == Qt.Unchecked:
                f["lines"] = set()
            self._update_labels(path)

    def _file(self, path):
        return next((f for f in self._files if f["path"] == path), None)

    def _update_labels(self, path):
        f = self._file(path)
        if f:
            self._update_file_labels(f)

    def _update_file_labels(self, f):
        row = self._rows.get(f["path"])
        if not row:
            return
        if f["state"] == Qt.PartiallyChecked and f["lines"] is not None:
            n = len(f["lines"])
            row.lbl_part.setText(f"{n} of {f['total']} changes")
        else:
            row.lbl_part.setText("")

    def _update_stats(self):
        added = removed = 0
        for f in self._files:
            if f["state"] == Qt.Unchecked:
                continue
            for r in self.utils.diff_rows(f["path"]):
                if f["state"] == Qt.PartiallyChecked \
                   and r["kind"] in ("add", "mod") \
                   and r["right_n"] not in (f["lines"] or set()):
                    continue
                if r["kind"] in ("add", "mod"):
                    added += 1
                elif r["kind"] == "del":
                    removed += 1
        self.lbl_stats.setText(f"+{added} −{removed}" if added or removed
                               else "")

    # ---- sync con el panel de Diff ----
    def set_file_selection(self, path, lines):
        """El diff cambió la selección de líneas de `path`."""
        f = self._file(path)
        if not f:
            return
        f["lines"] = set(lines)
        if f["total"] and len(f["lines"]) >= f["total"]:
            f["state"] = Qt.Checked
            f["lines"] = None
        elif not f["lines"]:
            f["state"] = Qt.Unchecked
        else:
            f["state"] = Qt.PartiallyChecked
        row = self._rows.get(path)
        if row:
            row.chk.blockSignals(True)
            row.chk.setCheckState(f["state"])
            row.chk.blockSignals(False)
        self._update_file_labels(f)

    # ---- commit ----
    def _staged_content(self, f):
        """Contenido a stagear para un archivo parcial."""
        out = []
        for r in self.utils.diff_rows(f["path"]):
            if r["kind"] == "ctx":
                out.append(r["left"])
            elif r["kind"] == "del":
                continue  # las borradas se aplican siempre
            elif r["kind"] == "mod":
                out.append(r["right"] if r["right_n"] in (f["lines"] or set())
                           else r["left"])
            elif r["kind"] == "add":
                if r["right_n"] in (f["lines"] or set()):
                    out.append(r["right"])
        return "\n".join(out) + ("\n" if out else "")

    def do_commit(self, push_after=False, only=None):
        if not self.utils or not self.utils.is_repo():
            return
        msg = self.inp_msg.text().strip()
        amend = self.btn_amend.isChecked()
        if not msg and not amend:
            self._status("✖ Escribí un mensaje (o tildá Amend)")
            return
        sel = [f for f in self._files
               if f["state"] != Qt.Unchecked
               and (only is None or f["path"] in only)]
        if not sel:
            self._status("✖ No hay archivos tildados")
            return
        # parcial sin líneas concretas = archivo entero
        for f in sel:
            if f["state"] == Qt.PartiallyChecked and f["lines"] is None:
                f["state"] = Qt.Checked
        self.utils.reset_index()
        full = [f["path"] for f in sel if f["state"] == Qt.Checked]
        self.utils.stage_files(full)
        for f in sel:
            if f["state"] == Qt.PartiallyChecked:
                lines = []
                for r in self.utils.diff_rows(f["path"]):
                    if r["kind"] == "ctx":
                        lines.append(r["left"])
                    elif r["kind"] == "del":
                        continue
                    elif r["kind"] == "mod":
                        lines.append(
                            r["right"]
                            if r["right_n"] in (f["lines"] or set())
                            else r["left"])
                    elif r["kind"] == "add":
                        if r["right_n"] in (f["lines"] or set()):
                            lines.append(r["right"])
                self.utils.stage_content(f["path"], "\n".join(lines) + "\n")
        ok, out = self.utils.commit(msg, amend=amend)
        if ok:
            self.inp_msg.clear()
            self.btn_amend.setChecked(False)
            self.refresh()
            self._status("✔ " + out.replace("\n", " ")[:100])
        else:
            self._status("✖ " + out.replace("\n", " ")[:100])
        self.committed.emit(push_after)

    def commit_paths(self, paths):
        """Commit solo de los archivos dados (botón del panel de Diff)."""
        self.do_commit(only=set(paths))

    def _status(self, txt):
        win = self.window()
        if hasattr(win, "statusBar"):
            win.statusBar().showMessage(txt, 5000)

    # ---- historial ----
    def _refresh_history(self):
        self.tree_hist.clear()
        if not self.utils or not self.utils.is_repo():
            self.pill_branch.setText("")
            return
        cur = self.utils.current_branch()
        try:
            color = self.utils.branch_color(cur)
        except Exception:
            color = "#3574f0"
        self.pill_branch.setText(cur or "detached")
        self.pill_branch.setStyleSheet(
            f"background:{color}; color:#fff; font-size:11px;"
            "font-weight:bold; border-radius:10px; padding:2px 10px;")
        for c in self.utils.branch_commits(cur or "HEAD", limit=40):
            it = QTreeWidgetItem(
                [c["date"], c["subject"], c["author"], c["short"]])
            it.setForeground(0, QColor("#8e8e93"))
            it.setForeground(1, QColor("#d7dae0"))
            it.setForeground(2, QColor("#8e8e93"))
            it.setForeground(3, QColor("#8e8e93"))
            it.setToolTip(1, c["subject"])
            self.tree_hist.addTopLevelItem(it)
        self.tree_hist.resizeColumnToContents(0)
        self.tree_hist.setColumnWidth(1, 220)
        self.tree_hist.resizeColumnToContents(2)
        self.tree_hist.resizeColumnToContents(3)
