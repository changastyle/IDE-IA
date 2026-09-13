# -*- coding: utf-8 -*-
"""Panel de Stash — el bolsillo: cambios guardados sin commitear.

- 📥 Guardar todo en el stash (incluye sin trackear).
- Cada entrada stash@{N} se expande y muestra sus archivos con checkboxes.
- ⤴ Recuperar lo tildado (por archivo); si se recupera todo, la entrada
  se borra sola (como git stash pop).
- 🗑 Descartar la entrada expandida, con confirmación.
"""
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton,
    QScrollArea, QMessageBox,
)

from utils.git_utils import GitUtils
from UI.panels.changes_panel import _Tri, _CHK_SS


class _StashRow(QFrame):
    """Header de entrada: ▸/▾ + stash@{N} + mensaje + fecha."""

    toggled = Signal(int)

    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.setObjectName("stashRow")
        self.setAttribute(Qt.WA_StyledBackground)
        self.entry = entry
        self.expanded = False
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 3, 10, 3)
        h.setSpacing(8)
        self.btn_arrow = QPushButton("▸")
        self.btn_arrow.setFixedSize(18, 18)
        self.btn_arrow.setCursor(Qt.PointingHandCursor)
        self.btn_arrow.setStyleSheet(
            "QPushButton{background:transparent;border:none;color:#8e8e93;"
            "font-size:11px;}")
        self.btn_arrow.clicked.connect(
            lambda: self.toggled.emit(self.entry["index"]))
        h.addWidget(self.btn_arrow)
        lbl_idx = QLabel(f"stash@{{{entry['index']}}}")
        lbl_idx.setStyleSheet(
            "color:#d7dae0; font-size:13px; font-weight:bold;"
            "background:transparent;")
        h.addWidget(lbl_idx)
        lbl_msg = QLabel(entry["msg"])
        lbl_msg.setStyleSheet(
            "color:#8e8e93; font-size:11px; font-style:italic;"
            "background:transparent;")
        h.addWidget(lbl_msg, 1)
        lbl_date = QLabel(entry["date"])
        lbl_date.setStyleSheet(
            "color:#8e8e93; font-size:11px; background:transparent;")
        h.addWidget(lbl_date)

    def set_expanded(self, exp):
        self.expanded = exp
        self.btn_arrow.setText("▾" if exp else "▸")


class _StashFileRow(QFrame):
    """Archivo dentro de un stash, con checkbox para recuperar."""

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.setObjectName("stashFileRow")
        self.setAttribute(Qt.WA_StyledBackground)
        self.path = path
        h = QHBoxLayout(self)
        h.setContentsMargins(30, 2, 10, 2)
        h.setSpacing(8)
        self.lbl_name = QLabel(os.path.basename(path))
        self.lbl_name.setStyleSheet(
            "color:#d7dae0; font-size:12px; background:transparent;")
        self.lbl_name.setToolTip(path)
        h.addWidget(self.lbl_name)
        h.addStretch(1)
        folder = os.path.dirname(path)
        if folder:
            fl = QLabel(folder)
            fl.setStyleSheet(
                "color:#e8c97a; font-size:10px; background:"
                "rgba(240,200,120,0.13); border-radius:4px; padding:1px 6px;")
            h.addWidget(fl)
        self.chk = _Tri()
        self.chk.setStyleSheet(_CHK_SS)
        self.chk.setCheckState(Qt.Checked)
        h.addWidget(self.chk)


class StashPanel(QWidget):
    """Panel de Stash completo."""

    stash_changed = Signal()   # tras push/pop/drop → refrescar Changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo = ""
        self.utils = None
        self._open_index = None   # entrada expandida (para Descartar)
        self._rows = {}           # index → (_StashRow, [_StashFileRow...])

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # botón guardar todo
        top = QFrame()
        th = QHBoxLayout(top)
        th.setContentsMargins(8, 8, 8, 6)
        self.btn_stash = QPushButton("📥  Guardar todo en el stash")
        self.btn_stash.setCursor(Qt.PointingHandCursor)
        self.btn_stash.setStyleSheet(
            "QPushButton{background:#22c55e; color:#fff; border:none;"
            "border-radius:7px; padding:6px 14px; font-size:12px;"
            "font-weight:bold;}"
            "QPushButton:hover{background:#16a34a;}"
            "QPushButton:disabled{background:#2b2e34; color:#666;}")
        self.btn_stash.clicked.connect(self._stash_all)
        th.addWidget(self.btn_stash)
        hint = QLabel("guarda TODOS tus cambios sin commitear")
        hint.setStyleSheet(
            "color:#6b7078; font-size:11px; background:transparent;")
        th.addWidget(hint, 1)
        v.addWidget(top)

        # lista de entradas
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
        v.addWidget(self.scroll, 1)

        # barra inferior: pop + descartar
        bar = QFrame()
        bar.setStyleSheet("background:transparent;border-top:1px solid #2b2e34;")
        bh = QHBoxLayout(bar)
        bh.setContentsMargins(8, 6, 8, 8)
        self.btn_pop = QPushButton("⤴  Recuperar lo tildado (pop)")
        self.btn_pop.setCursor(Qt.PointingHandCursor)
        self.btn_pop.setStyleSheet(
            "QPushButton{background:#3574f0; color:#fff; border:none;"
            "border-radius:7px; padding:6px 14px; font-size:12px;"
            "font-weight:bold;}"
            "QPushButton:hover{background:#2b63d8;}"
            "QPushButton:disabled{background:#2b2e34; color:#666;}")
        self.btn_pop.clicked.connect(self._pop_checked)
        bh.addWidget(self.btn_pop)
        self.btn_drop = QPushButton("🗑  Descartar")
        self.btn_drop.setCursor(Qt.PointingHandCursor)
        self.btn_drop.setStyleSheet(
            "QPushButton{background:#2b2e34; color:#e05561; border:none;"
            "border-radius:7px; padding:6px 14px; font-size:12px;"
            "font-weight:bold;}"
            "QPushButton:hover{background:#3a3d45;}"
            "QPushButton:disabled{color:#666;}")
        self.btn_drop.clicked.connect(self._drop_open)
        bh.addWidget(self.btn_drop)
        bh.addStretch(1)
        self.lbl_hint = QLabel("")
        self.lbl_hint.setStyleSheet(
            "color:#6b7078; font-size:11px; background:transparent;")
        bh.addWidget(self.lbl_hint, 1)
        v.addWidget(bar)

    # ---- repo ----
    def set_repo(self, path):
        self.refresh()

    def refresh(self):
        self._open_index = None
        while self.list_lay.count():
            it = self.list_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._rows.clear()
        utils = self._utils()
        entries = utils.stash_list() if utils else []
        if not entries:
            empty = QLabel("El bolsillo está vacío\n\n"
                           "📥 Guardá cambios con el botón de arriba, o desde "
                           "el popup al cambiar de rama.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color:#666; font-size:12px; padding:24px;")
            empty.setWordWrap(True)
            self.list_lay.addWidget(empty)
        for e in entries:
            row = _StashRow(e)
            row.toggled.connect(self._toggle_entry)
            self.list_lay.addWidget(row)
            file_rows = []
            for p in e["files"]:
                fr = _StashFileRow(p)
                self.list_lay.addWidget(fr)
                file_rows.append(fr)
            self._rows[e["index"]] = (row, file_rows)
        self.list_lay.addStretch(1)
        has = bool(entries)
        self.btn_pop.setEnabled(has)
        self.btn_drop.setEnabled(has)
        self.btn_stash.setEnabled(utils is not None and utils.is_repo())

    def _utils(self):
        win = self.window()
        repo = getattr(getattr(win, "top_bar", None), "repo_path", "")
        return GitUtils(repo) if repo else None

    # ---- acciones ----
    def _stash_all(self):
        utils = self._utils()
        if not utils:
            return
        ok, out = utils.stash_push()
        self._status(("✔ " if ok else "✖ ") + out.replace("\n", " ")[:100])
        if ok:
            self.refresh()
            self.stash_changed.emit()

    def _toggle_entry(self, index):
        row, file_rows = self._rows.get(index, (None, []))
        if row is None:
            return
        opening = not row.expanded
        # cerrar la que estaba abierta
        if self._open_index is not None and self._open_index in self._rows:
            orow, ofiles = self._rows[self._open_index]
            orow.set_expanded(False)
            for fr in ofiles:
                fr.setVisible(False)
        row.set_expanded(opening)
        for fr in file_rows:
            fr.setVisible(opening)
        self._open_index = index if opening else None

    def _pop_checked(self):
        utils = self._utils()
        if not utils or self._open_index is None:
            self._status("✖ Abrí una entrada del stash primero")
            return
        row, file_rows = self._rows[self._open_index]
        checked = [fr.path for fr in file_rows
                   if fr.chk.checkState() != Qt.Unchecked]
        if not checked:
            self._status("✖ No hay archivos tildados")
            return
        entry = row.entry
        if not utils.stash_restore(entry["index"], checked):
            self._status("✖ No se pudo recuperar (¿se pisa con tus cambios?)")
            return
        if len(checked) >= len(entry["files"]):
            utils.stash_drop(entry["index"])  # pop completo → se borra
        self._status(f"✔ Recuperados {len(checked)} archivo(s) del stash")
        self.refresh()
        self.stash_changed.emit()

    def _drop_open(self):
        utils = self._utils()
        if not utils or self._open_index is None:
            self._status("✖ Abrí una entrada del stash primero")
            return
        row, _ = self._rows[self._open_index]
        ret = QMessageBox.question(
            self, "Descartar stash",
            f"¿Borrar {row.entry['sel']}?\n\n{row.entry['msg']}\n\n"
            "Se pierden esos cambios guardados para siempre.",
            QMessageBox.Yes | QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        ok, out = utils.stash_drop(row.entry["index"])
        self._status(("✔ " if ok else "✖ ") + out.replace("\n", " ")[:100])
        self.refresh()

    def _status(self, txt):
        win = self.window()
        if hasattr(win, "statusBar"):
            win.statusBar().showMessage(txt, 5000)
