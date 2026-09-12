# -*- coding: utf-8 -*-
"""Panel de archivos estilo IntelliJ (vista Project).

Header con título + acciones, y árbol de archivos con iconos por extensión.
La fila de carpeta muestra nombre + ruta relativa, como IntelliJ.
"""
import os

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QKeyEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTreeWidget,
    QTreeWidgetItem, QHeaderView, QMenu, QMessageBox, QInputDialog,
)

APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICONS_DIR = os.path.join(APP_DIR, "iconos")

EXT_ICONS = {
    ".html": "html", ".htm": "html", ".css": "css", ".js": "js",
    ".py": "python", ".json": "json", ".md": "markdown", ".txt": "txt",
}

RUNNABLE_EXTS = {".py", ".js", ".java"}

IGNORED_DIRS = {".git", "__pycache__", ".idea", "node_modules", ".venv", "venv"}


def file_icon(name, is_dir):
    if is_dir:
        p = os.path.join(ICONS_DIR, "carpeta.svg")
    else:
        icon = EXT_ICONS.get(os.path.splitext(name)[1].lower(), "archivo")
        p = os.path.join(ICONS_DIR, icon + ".svg")
    return QIcon(p) if os.path.exists(p) else QIcon()


def play_icon():
    p = os.path.join(ICONS_DIR, "play.svg")
    return QIcon(p) if os.path.exists(p) else QIcon()


class FilesPanel(QWidget):
    """Panel izquierdo: árbol de archivos del workspace."""

    file_activated = Signal(str)   # doble clic / enter
    file_selected = Signal(str)    # clic simple
    root_changed = Signal(str)
    run_requested = Signal(str)    # ejecutar archivo (path completo)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.root_path = ""
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # ---- Header estilo IntelliJ ----
        head = QHBoxLayout()
        head.setContentsMargins(10, 6, 6, 6)
        head.setSpacing(4)
        self.title = QLabel("Project")
        self.title.setObjectName("panelTitle")
        self.title.setCursor(Qt.PointingHandCursor)
        head.addWidget(self.title)
        lbl_chev = QLabel("⌄")
        lbl_chev.setObjectName("panelChevron")
        head.addWidget(lbl_chev)
        head.addStretch(1)
        for icon, tip, cb in (
                ("＋", "Nuevo archivo", self._new_file),
                ("↻", "Refrescar", self.refresh),
                ("⇅", "Colapsar todo", self._collapse_all),
                ("✕", "Cerrar panel", lambda: self.setVisible(False))):
            b = QPushButton(icon)
            b.setObjectName("panelHeadBtn")
            b.setFixedSize(22, 22)
            b.setToolTip(tip)
            b.clicked.connect(cb)
            head.addWidget(b)
        v.addLayout(head)

        # ---- Árbol ----
        self.tree = QTreeWidget()
        self.tree.setObjectName("filesTree")
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(2)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.setIndentation(14)
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemDoubleClicked.connect(self._on_double)
        self.tree.itemClicked.connect(self._on_click)
        # Teclas: F2 = renombrar, Delete = eliminar
        self._orig_key_press = self.tree.keyPressEvent
        self.tree.keyPressEvent = self._tree_key_press
        v.addWidget(self.tree, 1)

    # ---- API pública ----
    def set_root(self, path):
        self.root_path = path or ""
        self.refresh()
        self.root_changed.emit(self.root_path)

    def refresh(self):
        self.tree.clear()
        if not self.root_path or not os.path.isdir(self.root_path):
            return
        top = QTreeWidgetItem()
        top.setText(0, os.path.basename(self.root_path) or self.root_path)
        top.setIcon(0, file_icon("", True))
        top.setData(0, Qt.UserRole, self.root_path)
        top.setData(0, Qt.UserRole + 1, "dir")
        # Ruta completa al lado del nombre (como IntelliJ)
        home = os.path.expanduser("~")
        disp = self.root_path.replace(home, "~")
        top.setToolTip(0, disp)
        self.tree.addTopLevelItem(top)
        self._fill(top, self.root_path)
        top.setExpanded(True)

    # ---- internals ----
    def _fill(self, parent_item, dir_path):
        try:
            entries = sorted(
                os.scandir(dir_path),
                key=lambda e: (not e.is_dir(), e.name.lower()))
        except OSError:
            return
        for e in entries:
            if e.name.startswith(".") and e.name not in (".gitignore",):
                continue
            if e.is_dir(follow_symlinks=False):
                if e.name in IGNORED_DIRS:
                    continue
                it = QTreeWidgetItem()
                it.setText(0, e.name)
                it.setIcon(0, file_icon(e.name, True))
                it.setData(0, Qt.UserRole, e.path)
                it.setData(0, Qt.UserRole + 1, "dir")
                parent_item.addChild(it)
                self._fill(it, e.path)
            else:
                it = QTreeWidgetItem()
                it.setText(0, e.name)
                it.setIcon(0, file_icon(e.name, False))
                it.setData(0, Qt.UserRole, e.path)
                it.setData(0, Qt.UserRole + 1, "file")
                it.setToolTip(0, e.path)
                parent_item.addChild(it)
                # Botón play verde para archivos ejecutables
                ext = os.path.splitext(e.name)[1].lower()
                if ext in RUNNABLE_EXTS:
                    btn = QPushButton()
                    btn.setIcon(play_icon())
                    btn.setIconSize(QSize(12, 12))
                    btn.setFixedSize(16, 16)
                    btn.setStyleSheet(
                        "QPushButton { background:transparent; border:none; }"
                        "QPushButton:hover { background:#22c55e33; border-radius:2px; }")
                    btn.setToolTip(f"Ejecutar {e.name}")
                    btn.clicked.connect(
                        lambda _, p=e.path: self.run_requested.emit(p))
                    self.tree.setItemWidget(it, 1, btn)

    def _on_double(self, item, _col):
        path = item.data(0, Qt.UserRole)
        kind = item.data(0, Qt.UserRole + 1)
        if kind == "dir":
            item.setExpanded(not item.isExpanded())
        elif path:
            self.file_activated.emit(path)

    def _on_click(self, item, _col):
        path = item.data(0, Qt.UserRole)
        if path and item.data(0, Qt.UserRole + 1) == "file":
            self.file_selected.emit(path)

    def _collapse_all(self):
        self.tree.collapseAll()
        if self.tree.topLevelItemCount():
            self.tree.topLevelItem(0).setExpanded(True)

    def _new_file(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Nuevo archivo", "Nombre:")
        if ok and name.strip() and self.root_path:
            p = os.path.join(self.root_path, name.strip())
            if not os.path.exists(p):
                try:
                    with open(p, "w", encoding="utf-8") as f:
                        f.write("")
                    self.refresh()
                except OSError:
                    pass

    def _context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        path = item.data(0, Qt.UserRole)
        kind = item.data(0, Qt.UserRole + 1)
        menu = QMenu(self)
        menu.setObjectName("filesCtx")
        if kind == "file":
            a_open = menu.addAction("Abrir")
            a_open.triggered.connect(lambda: self.file_activated.emit(path))
            menu.addSeparator()
        a_ren = menu.addAction("✏  Renombrar (F2)")
        a_ren.triggered.connect(lambda: self._rename_item(item))
        a_del = menu.addAction("🗑  Eliminar (Delete)")
        a_del.triggered.connect(lambda: self._delete_item(item))
        menu.addSeparator()
        a_ref = menu.addAction("↻ Refrescar")
        a_ref.triggered.connect(self.refresh)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    # ---- teclas ----
    def _tree_key_press(self, event):
        if event.key() == Qt.Key_F2:
            item = self.tree.currentItem()
            if item:
                self._rename_item(item)
                return
        elif event.key() == Qt.Key_Delete:
            item = self.tree.currentItem()
            if item:
                self._delete_item(item)
                return
        self._orig_key_press(event)

    def _rename_item(self, item):
        path = item.data(0, Qt.UserRole)
        if not path:
            return
        old_name = os.path.basename(path)
        new_name, ok = QInputDialog.getText(
            self, "Renombrar", "Nuevo nombre:", text=old_name)
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        new_path = os.path.join(os.path.dirname(path), new_name.strip())
        if os.path.exists(new_path):
            QMessageBox.warning(self, "Renombrar",
                                 f"Ya existe: {new_name}")
            return
        try:
            os.rename(path, new_path)
            self.refresh()
        except OSError as e:
            QMessageBox.warning(self, "Renombrar", f"Error: {e}")

    def _delete_item(self, item):
        path = item.data(0, Qt.UserRole)
        if not path:
            return
        name = os.path.basename(path)
        is_dir = item.data(0, Qt.UserRole + 1) == "dir"
        msg = f"¿Eliminar {'la carpeta' if is_dir else 'el archivo'} " \
              f"'{name}'?\n\nEsto no se puede deshacer."
        btn = QMessageBox.question(
            self, "Confirmar eliminación", msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if btn != QMessageBox.Yes:
            return
        try:
            if is_dir:
                import shutil
                shutil.rmtree(path)
            else:
                os.remove(path)
            self.refresh()
        except OSError as e:
            QMessageBox.warning(self, "Eliminar", f"Error: {e}")
