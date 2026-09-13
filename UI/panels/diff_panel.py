# -*- coding: utf-8 -*-
"""Panel de Diff: HEAD (con blame) | working tree (con checkboxes de línea).

- Mitad izquierda: el archivo en el último commit, con gutter de blame
  (fecha + autor línea a línea; las más nuevas destacadas en azul).
- Mitad derecha: tu versión actual; las líneas cambiadas llevan checkbox
  para commitear parcialmente.
- Barra inferior: "N differences, M included" + commit de la selección.
"""
import os

from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QBrush, QFontMetrics
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QFrame,
)

ROW_H = 22
BLAME_W = 140
NUM_W = 34
CHK_W = 26
PAD = 10


class DiffCanvas(QWidget):
    """Lienzo pintado a mano: blame | código || checkbox | código."""

    selection_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.blame = {}
        self.recent_date = ""
        self.path = ""
        self.head_label = ""
        self.work_label = ""
        self.selected = set()   # índices de fila tildados
        self._checkable = set()  # índices de fila con checkbox
        self.setMinimumHeight(120)

    # ---- datos ----
    def set_data(self, path, rows, blame, head_label, work_label):
        self.path = path
        self.rows = rows
        self.blame = blame
        self.head_label = head_label
        self.work_label = work_label
        dates = [d for d, _a in blame.values() if d]
        self.recent_date = max(dates) if dates else ""
        self._checkable = {i for i, r in enumerate(rows)
                           if r["kind"] in ("add", "mod")}
        self.selected = set(self._checkable)
        self.setMinimumHeight(max(120, len(rows) * ROW_H + 2 * PAD + 8))
        self.update()

    def included(self):
        return len(self.selected)

    def total_changes(self):
        return len(self._checkable)

    def selected_lines(self):
        """{nro_de_línea_derecha: texto} de las filas tildadas."""
        out = {}
        for i in self.selected:
            r = self.rows[i]
            if r["right_n"]:
                out[r["right_n"]] = r["right"]
        return out

    def set_line_selected(self, right_n, on):
        for i, r in enumerate(self.rows):
            if r["right_n"] == right_n and i in self._checkable:
                (self.selected.add if on else self.selected.discard)(i)
        self.update()
        self.selection_changed.emit()

    # ---- geometría ----
    def _half(self):
        return self.width() / 2

    def _row_at(self, y):
        i = int((y - PAD) // ROW_H)
        return i if 0 <= i < len(self.rows) else None

    def _chk_rect(self, i):
        x = self._half() + 8
        y = PAD + i * ROW_H + (ROW_H - 14) // 2
        return QRectF(x, y, 14, 14)

    # ---- pintado ----
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#1a1c21"))
        half = self._half()

        # gutter de blame (izquierda)
        p.fillRect(QRectF(0, 0, BLAME_W, self.height()),
                   QColor("#23252b"))
        # divisor central
        p.fillRect(QRectF(half - 1, 0, 2, self.height()),
                   QColor("#3a3d45"))

        f_num = QFont("Menlo")
        f_num.setPointSizeF(9)
        f_code = QFont("Menlo")
        f_code.setPointSizeF(11)
        f_blame = QFont("Menlo")
        f_blame.setPointSizeF(8.5)

        fm = p.fontMetrics()
        for i, r in enumerate(self.rows):
            y = PAD + i * ROW_H
            cy = y + ROW_H // 2 + 4
            kind = r["kind"]

            # --- mitad izquierda: blame + nro + código HEAD ---
            bdate, bauth = self.blame.get(r["left_n"] or 0, ("", ""))
            if bdate and bdate == self.recent_date and kind == "ctx":
                p.fillRect(QRectF(0, y, BLAME_W, ROW_H),
                           QColor("#2c4a77"))
                p.setPen(QColor("#cfe0f5"))
            else:
                p.setPen(QColor("#6b7078"))
            p.setFont(f_blame)
            txt = f"{bdate}  {bauth}"
            p.drawText(QRectF(6, y, BLAME_W - 10, ROW_H), Qt.AlignVCenter,
                       QFontMetrics(f_blame).elidedText(
                           txt, Qt.ElideRight, BLAME_W - 14))

            if kind in ("del", "mod"):
                p.fillRect(QRectF(BLAME_W, y, half - BLAME_W, ROW_H),
                           QColor(239, 68, 68, 30))
            p.setFont(f_num)
            p.setPen(QColor("#6b7078"))
            if r["left_n"]:
                p.drawText(QRectF(BLAME_W + 4, y, NUM_W - 8, ROW_H),
                           Qt.AlignRight | Qt.AlignVCenter,
                           str(r["left_n"]))
            p.setFont(f_code)
            p.setPen(QColor("#e8a0a0" if kind in ("del", "mod")
                            else "#c8ccd4"))
            p.drawText(QRectF(BLAME_W + NUM_W + 4, y,
                              half - BLAME_W - NUM_W - 8, ROW_H),
                       Qt.AlignVCenter, r["left"])

            # --- mitad derecha: checkbox + nro + código working ---
            if kind in ("add", "mod"):
                p.fillRect(QRectF(half + 2, y, half - 2, ROW_H),
                           QColor(34, 197, 94, 28))
            p.setFont(f_num)
            p.setPen(QColor("#6b7078"))
            x_num = half + CHK_W + 6
            if r["right_n"]:
                p.drawText(QRectF(x_num, y, NUM_W - 8, ROW_H),
                           Qt.AlignRight | Qt.AlignVCenter,
                           str(r["right_n"]))
            p.setFont(f_code)
            p.setPen(QColor("#7ce495" if kind in ("add", "mod")
                            else "#c8ccd4"))
            p.drawText(QRectF(x_num + NUM_W, y,
                              self.width() - x_num - NUM_W - 6, ROW_H),
                       Qt.AlignVCenter, r["right"])

            # checkbox de las filas cambiadas
            if i in self._checkable:
                rc = self._chk_rect(i)
                if i in self.selected:
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor("#3574f0"))
                    p.drawRoundedRect(rc, 3, 3)
                    p.setPen(QPen(QColor("#fff"), 2))
                    p.drawLine(rc.left() + 3, rc.center().y(),
                               rc.center().x() - 1, rc.bottom() - 3)
                    p.drawLine(rc.center().x() - 1, rc.bottom() - 3,
                               rc.right() - 3, rc.top() + 3)
                else:
                    p.setBrush(Qt.NoBrush)
                    p.setPen(QPen(QColor("#555a63"), 1.4))
                    p.drawRoundedRect(rc, 3, 3)

        # sin cambios
        if not self.rows:
            p.setPen(QColor("#666"))
            f = p.font()
            f.setPointSizeF(11)
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignCenter,
                       "Sin diferencias con el último commit")

    def mouseReleaseEvent(self, e):
        i = self._row_at(e.position().y())
        if i is not None and i in self._checkable:
            rc = self._chk_rect(i)
            if rc.adjusted(-4, -4, 4, 4).contains(e.position()):
                (self.selected.discard if i in self.selected
                 else self.selected.add)(i)
                self.update()
                self.selection_changed.emit()
                return
        super().mouseReleaseEvent(e)


class DiffPanel(QWidget):
    """Panel completo: header + diff lado a lado + barra inferior."""

    close_requested = Signal()
    selection_changed = Signal(str, int, int)  # path, incluidas, total
    commit_requested = Signal(str)             # path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.utils = None
        self.path = ""
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # header: archivo | Commit: archivo | ✕
        head = QFrame()
        head.setObjectName("DiffHeader")
        head.setFixedHeight(34)
        head.setStyleSheet(
            "QFrame#DiffHeader{background:#23252b;"
            "border-bottom:1px solid #2b2e34;}")
        hh = QHBoxLayout(head)
        hh.setContentsMargins(10, 2, 6, 2)
        self.lbl_file = QLabel("")
        self.lbl_file.setStyleSheet(
            "color:#d7dae0; font-size:12px; font-weight:bold;"
            "background:transparent;")
        hh.addWidget(self.lbl_file)
        self.lbl_commit = QLabel("")
        self.lbl_commit.setStyleSheet(
            "color:#7aa2f7; font-size:12px; font-weight:bold;"
            "background:transparent;")
        hh.addWidget(self.lbl_commit, 1)
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(
            "QPushButton{background:transparent;border:none;color:#8e8e93;"
            "font-size:13px;} QPushButton:hover{color:#e8eaed;}")
        btn_close.clicked.connect(self.close_requested.emit)
        hh.addWidget(btn_close)
        v.addWidget(head)

        # sub-headers: qué es cada mitad
        sub = QFrame()
        sub.setFixedHeight(22)
        sub.setStyleSheet("background:#1e2025;border-bottom:1px solid #2b2e34;")
        sh = QHBoxLayout(sub)
        sh.setContentsMargins(6, 0, 6, 0)
        sh.setSpacing(0)
        self.lbl_head_side = QLabel("")
        self.lbl_head_side.setStyleSheet(
            "color:#8e8e93; font-size:10px; font-family:Menlo,monospace;"
            "background:transparent;")
        self.lbl_work_side = QLabel("")
        self.lbl_work_side.setStyleSheet(
            "color:#8e8e93; font-size:10px; background:transparent;")
        self.lbl_work_side.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sh.addWidget(self.lbl_head_side, 1)
        sh.addWidget(self.lbl_work_side, 1)
        v.addWidget(sub)

        # diff en scroll
        self.canvas = DiffCanvas()
        self.canvas.selection_changed.connect(self._emit_selection)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setWidget(self.canvas)
        self._scroll = sc
        v.addWidget(sc, 1)

        # barra inferior: stats + commit selección
        bar = QFrame()
        bar.setFixedHeight(36)
        bar.setStyleSheet("background:#202329;border-top:1px solid #2b2e34;")
        bh = QHBoxLayout(bar)
        bh.setContentsMargins(10, 4, 8, 4)
        self.lbl_stats = QLabel("")
        self.lbl_stats.setStyleSheet(
            "color:#8e8e93; font-size:11px; background:transparent;")
        bh.addWidget(self.lbl_stats)
        bh.addStretch(1)
        self.btn_commit = QPushButton("✓  Commit selección")
        self.btn_commit.setCursor(Qt.PointingHandCursor)
        self.btn_commit.setStyleSheet(
            "QPushButton{background:#3574f0; color:#fff; border:none;"
            "border-radius:6px; padding:5px 14px; font-size:12px;"
            "font-weight:bold;}"
            "QPushButton:hover{background:#2b63d8;}"
            "QPushButton:disabled{background:#2b2e34; color:#666;}")
        self.btn_commit.clicked.connect(
            lambda: self.commit_requested.emit(self.path))
        bh.addWidget(self.btn_commit)
        v.addWidget(bar)

    # ---- API ----
    def show_file(self, utils, path):
        """Carga el diff de `path` (path relativo al repo)."""
        self.utils = utils
        self.path = path
        if not utils or not path:
            return
        rows = utils.diff_rows(path)
        blame = utils.blame(path, rev="HEAD") if rows else {}
        date, short = utils.file_last_mod(path)
        head_lbl = (f"🔒 {short} · último commit"
                    + (f" · modificado {date}" if date else ""))
        work_lbl = "tu versión (sin commitear) ✏"
        self.lbl_file.setText(f"≡  {os.path.basename(path)}")
        self.lbl_file.setToolTip(path)
        self.lbl_commit.setText(f"⇄  Commit: {os.path.basename(path)}")
        self.canvas.set_data(path, rows, blame, head_lbl, work_lbl)
        self.lbl_head_side.setText(head_lbl)
        self.lbl_work_side.setText(work_lbl)
        self._update_stats()
        # saltar al primer cambio
        first = next((i for i, r in enumerate(rows)
                      if r["kind"] != "ctx"), None)
        if first:
            self._scroll.verticalScrollBar().setValue(
                max(0, first * ROW_H - 6))

    def set_line_selected(self, right_n, on):
        self.canvas.set_line_selected(right_n, on)

    def _emit_selection(self):
        self._update_stats()
        self.selection_changed.emit(self.path, self.canvas.included(),
                                    self.canvas.total_changes())

    def _update_stats(self):
        n = sum(1 for r in self.canvas.rows if r["kind"] != "ctx")
        m = self.canvas.included()
        self.lbl_stats.setText(f"{n} differences, {m} included")
        self.btn_commit.setEnabled(m > 0)
