# -*- coding: utf-8 -*-
"""Panel de archivos estilo IntelliJ (vista Project).

Header con título + acciones, y árbol de archivos con iconos por extensión.
La fila de carpeta muestra nombre + ruta relativa, como IntelliJ.
El watcher y el análisis de archivos corren en FileWatchService
(UTILS/CORE-SERVICES) — este panel es solo UI: se suscribe a
changed/diffs_ready/busy del servicio.
Muestra badges +N/-N de líneas cambiadas al lado de cada archivo.
"""
import os

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QKeyEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTreeWidget,
    QTreeWidgetItem, QHeaderView, QMenu, QMessageBox, QInputDialog,
)

# Lógica de análisis de archivos (filtros, walks, conteo de líneas)
# vive en UTILS/FILE-UTILS — este panel es solo UI.
from UTILS.file_utils import RUNNABLE_EXTS, list_entries

APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICONS_DIR = os.path.join(APP_DIR, "UI", "iconos")

EXT_ICONS = {
    ".html": "html", ".htm": "html", ".css": "css", ".js": "js",
    ".py": "python", ".json": "json", ".md": "markdown", ".txt": "txt",
}

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


def play_bookmark_icon():
    p = os.path.join(ICONS_DIR, "play_bookmark.svg")
    return QIcon(p) if os.path.exists(p) else QIcon()


class FilesPanel(QWidget):
    """Panel izquierdo: árbol de archivos del workspace."""

    file_activated = Signal(str)   # doble clic / enter
    file_selected = Signal(str)    # clic simple
    root_changed = Signal(str)
    run_requested = Signal(str)    # ejecutar archivo (path completo)
    save_run_config = Signal(str)  # guardar archivo como run config

    def __init__(self, parent=None):
        super().__init__(parent)
        self.root_path = ""
        # Tracking de líneas por archivo para mostrar diffs
        self._file_lines = {}    # path → line count (baseline)
        self._file_diffs = {}    # path → (added, removed) neto
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # ---- Árbol (2 columnas: nombre + acciones combinadas) ----
        # (los botones ＋ ↻ ⇅ ✕ viven en el header del panel contenedor)
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
        # Lazy loading: las subcarpetas se cargan al expandir
        self.tree.itemExpanded.connect(self._on_item_expanded)
        # Teclas: F2 = renombrar, Delete = eliminar
        self._orig_key_press = self.tree.keyPressEvent
        self.tree.keyPressEvent = self._tree_key_press
        v.addWidget(self.tree, 1)

        # Indicador de escaneo — lo maneja FileWatchService (señal busy)
        self.lbl_scan = QLabel("◌  Escaneando archivos…")
        self.lbl_scan.setStyleSheet(
            "color:#8e8e93; font-size:10px; padding:2px 6px; "
            "background:transparent;")
        self.lbl_scan.hide()
        v.addWidget(self.lbl_scan)

    # ---- API pública ----
    def set_root(self, path):
        self.root_path = path or ""
        self._file_lines = {}
        self._file_diffs = {}
        self.refresh()
        self.root_changed.emit(self.root_path)

    def set_scanning(self, on):
        """Slot para FileWatchService.busy — muestra/oculta el indicador."""
        self.lbl_scan.setVisible(bool(on))

    def repaint(self):
        """refresh() sin perder expansión ni selección.

        Slot público: lo llama FileWatchService.changed (hilo UI).
        """
        expanded = set()
        selected = None
        for i in range(self.tree.topLevelItemCount()):
            self._collect_expanded(self.tree.topLevelItem(i), expanded)
        cur = self.tree.currentItem()
        if cur:
            p = cur.data(0, Qt.UserRole)
            if p:
                selected = p
        self.refresh()
        for i in range(self.tree.topLevelItemCount()):
            self._restore_expanded(self.tree.topLevelItem(i), expanded)
        if selected:
            self._select_path(selected)

    def _collect_expanded(self, item, expanded_set):
        path = item.data(0, Qt.UserRole)
        if path and item.isExpanded():
            expanded_set.add(path)
        for i in range(item.childCount()):
            self._collect_expanded(item.child(i), expanded_set)

    def _restore_expanded(self, item, expanded_set):
        path = item.data(0, Qt.UserRole)
        if path and path in expanded_set:
            # setExpanded emite itemExpanded → _ensure_filled carga los
            # hijos antes de seguir bajando por el árbol
            item.setExpanded(True)
        for i in range(item.childCount()):
            self._restore_expanded(item.child(i), expanded_set)

    def _select_path(self, path):
        """Selecciona el item cuyo path coincide, cargando el camino
        nivel por nivel (el árbol es lazy: los hijos no existen hasta
        que la carpeta se expande)."""
        if not self.root_path or not path.startswith(self.root_path):
            return
        item = self.tree.topLevelItem(0)
        if item is None:
            return
        rel = os.path.relpath(path, self.root_path)
        if rel == ".":
            self.tree.setCurrentItem(item)
            return
        for part in rel.split(os.sep):
            self._ensure_filled(item)
            nxt = None
            for i in range(item.childCount()):
                c = item.child(i)
                if c.data(0, Qt.UserRole) == os.path.join(
                        item.data(0, Qt.UserRole), part):
                    nxt = c
                    break
            if nxt is None:
                return
            item = nxt
        self.tree.setCurrentItem(item)

    def apply_diffs(self, root, counts):
        """Slot para FileWatchService.diffs_ready (hilo UI).

        Vuelca los conteos del worker y repinta los badges +N/-N.
        """
        if root != self.root_path:
            return
        for fpath, lines in counts.items():
            old = self._file_lines.get(fpath)
            if old is not None:
                diff = lines - old
                if diff != 0:
                    self._file_diffs[fpath] = diff
        self._file_lines.update(counts)
        self.repaint()

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
        for name, path, is_dir in list_entries(dir_path):
            if is_dir:
                it = QTreeWidgetItem()
                it.setText(0, name)
                it.setIcon(0, file_icon(name, True))
                it.setData(0, Qt.UserRole, path)
                it.setData(0, Qt.UserRole + 1, "dir")
                # Lazy: marcar sin llenar + hijo dummy para la flecha
                it.setData(0, Qt.UserRole + 2, "unfilled")
                it.addChild(QTreeWidgetItem())
                parent_item.addChild(it)
            else:
                it = QTreeWidgetItem()
                it.setText(0, name)
                it.setIcon(0, file_icon(name, False))
                it.setData(0, Qt.UserRole, path)
                it.setData(0, Qt.UserRole + 1, "file")
                it.setToolTip(0, path)
                parent_item.addChild(it)
                # Columna de acciones: badge de diff + botones play/bookmark
                # en UN solo widget (evita columnas muertas)
                ext = os.path.splitext(name)[1].lower()
                runnable = ext in RUNNABLE_EXTS
                diff = self._file_diffs.get(path)
                has_badge = diff is not None and diff != 0
                if runnable or has_badge:
                    from PySide6.QtWidgets import QWidget, QHBoxLayout
                    btns = QWidget()
                    lo = QHBoxLayout(btns)
                    lo.setContentsMargins(0, 0, 2, 0)
                    lo.setSpacing(2)
                    if has_badge:
                        badge = QLabel()
                        if diff > 0:
                            badge.setText(f"+{diff}")
                            badge.setStyleSheet(
                                "background:rgba(34,197,94,0.15); color:#22c55e; "
                                "border-radius:4px; padding:1px 5px; "
                                "font-size:10px; font-weight:bold;")
                        else:
                            badge.setText(f"{diff}")
                            badge.setStyleSheet(
                                "background:rgba(239,68,68,0.15); color:#ef4444; "
                                "border-radius:4px; padding:1px 5px; "
                                "font-size:10px; font-weight:bold;")
                        lo.addWidget(badge)
                    if runnable:
                        btn = QPushButton()
                        btn.setIcon(play_icon())
                        btn.setIconSize(QSize(12, 12))
                        btn.setFixedSize(16, 16)
                        btn.setStyleSheet(
                            "QPushButton { background:transparent; border:none; }"
                            "QPushButton:hover { background:#22c55e33; border-radius:2px; }")
                        btn.setToolTip(f"Ejecutar {name}")
                        btn.clicked.connect(
                            lambda _, p=path: self.run_requested.emit(p))
                        lo.addWidget(btn)
                        # Play + Bookmark (guardar como run config)
                        btn_bm = QPushButton()
                        btn_bm.setIcon(play_bookmark_icon())
                        btn_bm.setIconSize(QSize(14, 14))
                        btn_bm.setFixedSize(16, 16)
                        btn_bm.setStyleSheet(
                            "QPushButton { background:transparent; border:none; }"
                            "QPushButton:hover { background:#2f6fdb33; border-radius:2px; }")
                        btn_bm.setToolTip(f"Guardar y ejecutar {name} como configuración")
                        btn_bm.clicked.connect(
                            lambda _, p=path: self.save_run_config.emit(p))
                        lo.addWidget(btn_bm)
                    self.tree.setItemWidget(it, 1, btns)

    def _ensure_filled(self, item):
        """Carga los hijos reales de una carpeta marcada 'unfilled'."""
        if item.data(0, Qt.UserRole + 2) == "unfilled":
            item.setData(0, Qt.UserRole + 2, None)
            item.takeChildren()  # quita el dummy
            self._fill(item, item.data(0, Qt.UserRole))

    def _on_item_expanded(self, item):
        self._ensure_filled(item)

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
