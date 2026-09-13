# -*- coding: utf-8 -*-
"""Panel de Git estilo IntelliJ: ramas + grafo de commits.

- Izquierda: árbol de ramas con sus commits (hash, fecha, autor).
- Derecha: grafo pintado (carriles por rama, curvas de fork/merge),
  badges de rama:hash, fecha, mensaje y autor al margen.
"""
import os

from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QTimer
from PySide6.QtGui import (QColor, QPainter, QPen, QFont, QPixmap, QIcon,
                           QBrush, QPainterPath)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTreeWidget,
    QTreeWidgetItem, QScrollArea, QLabel, QPushButton, QSizePolicy,
    QFrame,
)

from utils.git_utils import GitUtils

ROW_H = 34
GRAPH_W = 110
COLLAPSED_W = 30


def _dot_icon(color, size=10):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawEllipse(1, 1, size - 2, size - 2)
    p.end()
    return QIcon(pm)


class GraphCanvas(QWidget):
    """Lienzo del grafo: carriles + badges + textos, pintado a mano."""

    commit_clicked = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = None
        self.setMinimumWidth(620)
        self.setMinimumHeight(200)
        self._rows_y = []
        self._expanded = {}  # hash → bool
        self._diffs = {}     # hash → [{path, added, removed, lines}]
        self._utils = None

    def set_utils(self, utils):
        self._utils = utils

    def set_data(self, data):
        self.data = data
        n = max(1, len(data["commits"])) if data else 1
        self.setMinimumHeight(max(200, n * ROW_H + 40))
        self.update()

    def _diff_height(self, commit_hash):
        """Altura en px del diff expandido de un commit."""
        if not self._expanded.get(commit_hash):
            return 0
        files = self._diffs.get(commit_hash)
        if files is None:
            if self._utils:
                files = self._utils.commit_files(commit_hash)
                self._diffs[commit_hash] = files
            else:
                files = []
        h = 8  # padding superior
        for f in files:
            h += 22  # header del archivo
            h += len(f["lines"]) * 16  # cada línea del diff
        return max(h, 30)

    def _row_offsets(self, commits):
        """Calcula el y de cada commit sumando las alturas de diffs expandidos."""
        ys = []
        y = 20 + ROW_H // 2
        for c in commits:
            ys.append(y)
            y += ROW_H + self._diff_height(c["hash"])
        return ys

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#1a1c21"))
        d = self.data
        if not d or not d["commits"]:
            p.setPen(QColor("#666"))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "Sin commits (¿es un repo git?)")
            return
        commits = d["commits"]
        lane_of, edges = d["lane_of"], d["edges"]
        colors = d["colors"]
        max_lane = max([lane_of.get(c["hash"], 0) for c in commits] or [0])
        lane_w = min(46, (GRAPH_W - 24) // max(1, max_lane + 1))
        x_of = lambda lane: 18 + lane * lane_w
        row_ys = self._row_offsets(commits)
        self._rows_y = row_ys

        # ---- Rails por rama (línea vertical continua) ----
        lane_rows = {}
        for i, c in enumerate(commits):
            ln = lane_of.get(c["hash"], 0)
            lane_rows.setdefault(ln, []).append(i)
        for ln, rows in lane_rows.items():
            if len(rows) < 1:
                continue
            top, bot = min(rows), max(rows)
            x = x_of(ln)
            color = QColor("#3574f0")
            for b, ln2 in d["lane_of_branch"].items():
                if ln2 == ln:
                    color = QColor(d["colors"].get(b, "#3574f0"))
            pen = QPen(color, 2)
            p.setPen(pen)
            y1 = row_ys[top] - ROW_H // 2 - 8
            y2 = row_ys[bot] + ROW_H // 2 + 8
            p.drawLine(x, max(4, y1), x, y2)

        # ---- Rails de ramas sin commits propios (tip compartido) ----
        # Cada rama debe tener su línea: curva desde el nodo tip hasta su
        # carril, y rail vertical hasta su merge-base con el tronco.
        row_of_pre = {c["hash"]: i for i, c in enumerate(commits)}
        for b, ln in d["lane_of_branch"].items():
            if ln in lane_rows:
                continue
            tip_h = d["tips"].get(b)
            if tip_h not in row_of_pre:
                continue
            x = x_of(ln)
            color = QColor(d["colors"].get(b, "#3574f0"))
            p.setPen(QPen(color, 2))
            y_tip = row_ys[row_of_pre[tip_h]]
            x_node = x_of(lane_of.get(tip_h, ln))
            y_start = y_tip + ROW_H // 2
            base_row = d.get("branch_base", {}).get(b)
            y_end = (row_ys[base_row] if base_row is not None
                     and base_row > row_of_pre[tip_h] else y_start)
            if x_node != x:
                path = QPainterPath(QPointF(x_node, y_tip))
                mid = y_tip + ROW_H // 2
                path.cubicTo(x_node, mid, x, mid, x, y_start)
                p.drawPath(path)
            if y_end > y_start:
                p.drawLine(x, y_start, x, y_end)

        # ---- Edges (rectas o curvas de fork/merge) ----
        row_of = {c["hash"]: i for i, c in enumerate(commits)}
        for h, parent in edges:
            if h not in lane_of or parent not in lane_of:
                continue
            i1, i2 = row_of.get(h), row_of.get(parent)
            if i1 is None or i2 is None or i2 <= i1:
                continue
            x1, y1 = x_of(lane_of[h]), row_ys[i1] + ROW_H // 2
            x2, y2 = x_of(lane_of[parent]), row_ys[i2] - ROW_H // 2
            color = QColor("#3574f0")
            for b, ln2 in d["lane_of_branch"].items():
                if ln2 == lane_of[h]:
                    color = QColor(d["colors"].get(b, "#3574f0"))
            p.setPen(QPen(color, 2))
            if x1 == x2:
                p.drawLine(x1, y1, x2, y2)
            else:
                path = QPainterPath(QPointF(x1, y1))
                mid = (y1 + y2) / 2
                path.cubicTo(x1, mid, x2, mid, x2, y2)
                p.drawPath(path)

        # ---- Filas: pills de rama, hash, fecha, mensaje, autor ----
        fm = p.fontMetrics()
        for i, c in enumerate(commits):
            y = row_ys[i]
            # círculo del commit
            ln = lane_of.get(c["hash"], 0)
            cx = x_of(ln)
            is_tip = bool(c.get("branches"))
            ring = QColor("#e8eaed") if c["hash"] == d.get(
                "head_hash") else QColor("#1a1c21")
            p.setPen(QPen(ring, 2))
            color = QColor("#3574f0")
            for b, ln2 in d["lane_of_branch"].items():
                if ln2 == ln:
                    color = QColor(d["colors"].get(b, "#3574f0"))
            p.setBrush(QColor("#1a1c21") if not is_tip else color)
            r = 5 if is_tip else 4
            p.drawEllipse(QPointF(cx, y), r, r)

            x = GRAPH_W + 6
            # pills apiladas: una por cada rama que apunta a este commit
            f = p.font()
            f.setPointSizeF(8.5)
            p.setFont(f)
            for b in c.get("branches") or []:
                bc = QColor(d["colors"].get(b, "#3574f0"))
                w = fm.horizontalAdvance(b) + 16
                p.setPen(QPen(bc, 1))
                p.setBrush(QBrush(bc))
                p.drawRoundedRect(QRectF(x, y - 10, w, 20), 10, 10)
                p.setPen(QColor("#fff"))
                p.drawText(QRectF(x, y - 10, w, 20), Qt.AlignCenter, b)
                x += w + 6
            # hash
            if c.get("branches"):
                p.setPen(QColor("#8e8e93"))
                p.drawText(QPointF(x, y + 4), c["short"])
                x += fm.horizontalAdvance(c["short"]) + 10
            # fecha
            p.setPen(QColor("#9da3ae"))
            f = p.font()
            f.setPointSizeF(8.5)
            p.setFont(f)
            p.drawText(QPointF(x, y + 4), c["date"])
            x += 118
            # mensaje
            p.setPen(QColor("#e8eaed"))
            f = p.font()
            f.setBold(True)
            f.setPointSizeF(9)
            p.setFont(f)
            msg = c["subject"]
            max_w = self.width() - x - 90
            if fm.horizontalAdvance(msg) > max_w and max_w > 40:
                while msg and fm.horizontalAdvance(msg + "…") > max_w:
                    msg = msg[:-1]
                msg += "…"
            p.drawText(QPointF(x, y + 4), msg)
            x += max(max_w, fm.horizontalAdvance(msg)) + 12
            # autor al margen derecho
            p.setPen(QColor("#8e8e93"))
            f = p.font()
            f.setBold(False)
            p.setFont(f)
            p.drawText(QPointF(self.width() - 10 - fm.horizontalAdvance(
                c["author"]), y + 4), c["author"])

            # ---- Diff expandido debajo del commit ----
            if self._expanded.get(c["hash"]):
                self._draw_diff(p, c["hash"], y + ROW_H // 2 + 4,
                                x_of(ln))

    def _draw_diff(self, p, commit_hash, y_top, lane_x):
        """Dibuja el diff expandido: archivos cambiados y líneas."""
        files = self._diffs.get(commit_hash)
        if files is None:
            if self._utils:
                files = self._utils.commit_files(commit_hash)
                self._diffs[commit_hash] = files
            else:
                files = []
        if not files:
            p.setPen(QColor("#666"))
            f = p.font()
            f.setPointSizeF(9)
            p.setFont(f)
            p.drawText(QPointF(GRAPH_W + 6, y_top + 16),
                       "Sin cambios detectados")
            return
        x0 = GRAPH_W + 6
        x1 = self.width() - 10
        y = y_top + 4
        f = p.font()
        f.setPointSizeF(9)
        for fi in files:
            # Header del archivo
            p.setPen(QColor("#9da3ae"))
            f.setBold(True)
            p.setFont(f)
            status_icon = {"A": "+", "M": "M", "D": "-",
                           "R": "R"}.get(fi["status"], "?")
            sc = {"A": "#22c55e", "D": "#ef4444",
                  "M": "#eab308"}.get(fi["status"], "#9da3ae")
            p.setPen(QColor(sc))
            p.drawText(QPointF(x0, y + 14), status_icon)
            p.setPen(QColor("#e8eaed"))
            p.drawText(QPointF(x0 + 14, y + 14), fi["path"])
            # stats
            stats = f"+{fi['added']}  -{fi['removed']}"
            p.setPen(QColor("#22c55e"))
            sw = p.fontMetrics().horizontalAdvance(
                f"+{fi['added']}")
            p.drawText(QPointF(x1 - sw - 60, y + 14),
                       f"+{fi['added']}")
            p.setPen(QColor("#ef4444"))
            p.drawText(QPointF(x1 - 30, y + 14),
                       f"-{fi['removed']}")
            y += 22
            # Líneas del diff
            f.setBold(False)
            f.setPointSizeF(8.5)
            p.setFont(f)
            for ln in fi["lines"][:50]:  # límite para no explotar
                if ln["type"] == "+":
                    p.setPen(QColor("#22c55e"))
                    p.fillRect(QRectF(x0, y - 12, x1 - x0, 16),
                               QColor(34, 197, 94, 30))
                    p.drawText(QPointF(x0 + 8, y + 2), "+ " + ln["text"])
                else:
                    p.setPen(QColor("#ef4444"))
                    p.fillRect(QRectF(x0, y - 12, x1 - x0, 16),
                               QColor(239, 68, 68, 30))
                    p.drawText(QPointF(x0 + 8, y + 2), "- " + ln["text"])
                y += 16
            if len(fi["lines"]) > 50:
                p.setPen(QColor("#666"))
                p.drawText(QPointF(x0 + 8, y + 2),
                           f"  … y {len(fi['lines']) - 50} líneas más")
                y += 16
            y += 4

    def mousePressEvent(self, e):
        if self.data:
            row_ys = self._rows_y
            for i, yy in enumerate(row_ys):
                # clic en la fila del commit (no en el diff)
                if abs(e.position().y() - yy) <= ROW_H // 2:
                    c = self.data["commits"][i]
                    h = c["hash"]
                    self._expanded[h] = not self._expanded.get(h, False)
                    if not self._expanded[h]:
                        self._diffs.pop(h, None)
                    # recalcular altura mínima
                    n = len(self.data["commits"])
                    total_h = 40
                    for j, cc in enumerate(self.data["commits"]):
                        total_h += ROW_H
                        if self._expanded.get(cc["hash"]):
                            total_h += self._diff_height(cc["hash"])
                    self.setMinimumHeight(max(200, total_h))
                    self.update()
                    self.commit_clicked.emit(c)
                    break
        super().mousePressEvent(e)


class GitPanel(QWidget):
    """Panel de Git: ramas + grafo."""

    branch_changed = Signal(str)  # tras checkout

    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo = ""
        self.utils = None
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        # Splitter: árbol de ramas | grafo
        # (el título y el ↻ viven en el header del panel contenedor)
        sp = QSplitter(Qt.Horizontal)
        sp.setChildrenCollapsible(False)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet(
            "QTreeWidget{background:transparent;border:none;outline:none;"
            "font-size:12px;}"
            "QTreeWidget::item{padding:3px 2px;border-radius:4px;}"
            "QTreeWidget::item:selected{background:#2f6fdb;}")
        self.tree.itemDoubleClicked.connect(self._on_double)
        self.tree.itemExpanded.connect(lambda _i: self._sync_sizes())
        self.tree.itemCollapsed.connect(lambda _i: self._sync_sizes())
        sp.addWidget(self.tree)
        # Grafo en scroll
        self.canvas = GraphCanvas()
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(self.canvas)
        sc.setStyleSheet(
            "QScrollArea{background:#1a1c21;border:none;}")
        sp.addWidget(sc)
        sp.setSizes([240, 420])
        v.addWidget(sp, 1)
        # Nota al pie
        foot = QLabel("Doble clic en una rama → checkout")
        foot.setStyleSheet(
            "color:#8e8e93; font-size:10px; padding:4px 8px;"
            "border-top:1px solid #2b2e34;")
        v.addWidget(foot)

    def set_repo(self, path):
        self.repo = path or ""
        self.utils = GitUtils(self.repo) if self.repo else None
        self.canvas.set_utils(self.utils)
        self.refresh()

    def refresh(self):
        self.tree.clear()
        self.canvas.set_data(None)
        if not self.utils or not self.utils.is_repo():
            it = QTreeWidgetItem(["No es un repo git"])
            self.tree.addTopLevelItem(it)
            # Botón para inicializar el repo
            btn = QPushButton("▸ git init")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton{background:#22c55e;color:#fff;border:none;"
                "border-radius:6px;padding:6px 12px;font-size:12px;font-weight:bold;}"
                "QPushButton:hover{background:#16a34a;}")
            btn.clicked.connect(self._init_repo)
            self.tree.setItemWidget(it, 0, btn)
            return
        data = self.utils.graph()
        self.canvas.set_data(data)
        current = data["current"]
        # Agrupar commits por carril → rama dueña
        lane_of_branch = data["lane_of_branch"]
        branch_by_lane = {ln: b for b, ln in lane_of_branch.items()}
        lane_of = data["lane_of"]
        by_branch = {}
        for c in data["commits"]:
            ln = lane_of.get(c["hash"], 0)
            b = branch_by_lane.get(ln, current)
            by_branch.setdefault(b, []).append(c)
        # Ramas que comparten tip (p. ej. puto = dev) heredan sus commits
        tips = data.get("tips", {})
        for b in self.utils.branches():
            if b in by_branch:
                continue
            tip = tips.get(b)
            for b2, lst in by_branch.items():
                if tips.get(b2) == tip:
                    by_branch[b] = lst
                    break
        for b in self.utils.branches():
            color = data["colors"].get(b, "#3574f0")
            # Tag coloreado con el nombre de la rama (estilo IntelliJ)
            top = QTreeWidgetItem([f"  {b}"])
            top.setIcon(0, _dot_icon(color))
            top.setData(0, Qt.UserRole, b)
            f = top.font(0)
            f.setBold(b == current)
            f.setPointSizeF(11)
            top.setFont(0, f)
            top.setForeground(0, QColor(color if b == current
                                        else "#c8ccd4"))
            top.setBackground(0, QBrush(QColor(color).darker(280)))
            self.tree.addTopLevelItem(top)
            for c in by_branch.get(b, [])[:30]:
                ch = QTreeWidgetItem(
                    [f"{c['short']}   {c['date']}   {c['author']}"])
                ch.setToolTip(0, c["subject"])
                ch.setForeground(0, QColor("#8e8e93"))
                ch.setData(0, Qt.UserRole, c["hash"])
                top.addChild(ch)
            top.setExpanded(b == current)
        self._sync_sizes()

    def _sync_sizes(self):
        self.tree.resizeColumnToContents(0)

    def _init_repo(self):
        if not self.repo:
            return
        import subprocess
        subprocess.run(["git", "init"], cwd=self.repo,
                       capture_output=True, text=True)
        self.utils = GitUtils(self.repo)
        self.refresh()
        self.branch_changed.emit("init")

    def _on_double(self, item, _col):
        branch = item.data(0, Qt.UserRole)
        if branch and self.utils and branch != self.utils.current_branch():
            self.utils.checkout(branch)
            self.refresh()
            self.branch_changed.emit(branch)
