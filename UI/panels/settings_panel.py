# -*- coding: utf-8 -*-
"""Diálogo de Settings con pestaña de shortcuts configurables."""
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QKeySequenceEdit, QMessageBox,
)

from utils.shortcuts import (
    load_shortcuts, save_shortcuts, reset_shortcuts, DEFAULT_SHORTCUTS,
)


class ShortcutsTab(QWidget):
    """Pestaña de atajos de teclado: tabla con acción + secuencia editable."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shortcuts = load_shortcuts()
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        v.addWidget(QLabel("Atajos de teclado — clic en la secuencia para editar, "
                           "presioná la combinación nueva:"))

        # Tabla: Acción | Secuencia | Default
        self.table = QTableWidget(len(DEFAULT_SHORTCUTS), 3)
        self.table.setHorizontalHeaderLabels(["Acción", "Atajo", "Por defecto"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._fill_table()
        v.addWidget(self.table, 1)

        # Botones
        row = QHBoxLayout()
        self.btn_reset = QPushButton("Restaurar defaults")
        self.btn_reset.clicked.connect(self._reset)
        row.addWidget(self.btn_reset)
        row.addStretch(1)
        v.addLayout(row)

    def _fill_table(self):
        for i, (key, (desc, default)) in enumerate(DEFAULT_SHORTCUTS.items()):
            # Acción
            item_desc = QTableWidgetItem(desc)
            item_desc.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(i, 0, item_desc)
            # Secuencia editable (KeySequenceEdit como cellWidget)
            edit = QKeySequenceEdit(QKeySequence(self._shortcuts.get(key, default)))
            edit.keySequenceChanged.connect(
                lambda seq, k=key: self._on_change(k, seq))
            self.table.setCellWidget(i, 1, edit)
            # Default
            item_def = QTableWidgetItem(default)
            item_def.setFlags(Qt.ItemIsEnabled)
            item_def.setForeground(Qt.gray)
            self.table.setItem(i, 2, item_def)

    def _on_change(self, key, seq):
        """seq es un QKeySequence emitido por keySequenceChanged."""
        s = seq.toString() if hasattr(seq, "toString") else str(seq)
        if s:
            self._shortcuts[key] = s
        else:
            # Vacío = restaurar default
            self._shortcuts[key] = DEFAULT_SHORTCUTS[key][1]

    def _reset(self):
        self._shortcuts = reset_shortcuts()
        # Limpiar la tabla y reconstruir
        self.table.setRowCount(0)
        self.table.setRowCount(len(DEFAULT_SHORTCUTS))
        self._fill_table()

    def save(self):
        # Antes de guardar, leer los valores actuales de los widgets
        # por si algún cambio no disparó el signal
        for i, (key, (desc, default)) in enumerate(DEFAULT_SHORTCUTS.items()):
            edit = self.table.cellWidget(i, 1)
            if edit:
                s = edit.keySequence().toString()
                if s:
                    self._shortcuts[key] = s
        save_shortcuts(self._shortcuts)


class SettingsDialog(QDialog):
    """Diálogo de Settings con pestañas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(600, 480)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self.tabs = QTabWidget()
        self.shortcuts_tab = ShortcutsTab()
        self.tabs.addTab(self.shortcuts_tab, "Atajos")
        v.addWidget(self.tabs, 1)

        # Botones
        row = QHBoxLayout()
        row.setContentsMargins(12, 8, 12, 12)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Guardar")
        btn_save.setObjectName("success")
        btn_save.clicked.connect(self._save)
        row.addStretch(1)
        row.addWidget(btn_cancel)
        row.addWidget(btn_save)
        v.addLayout(row)

    def _save(self):
        self.shortcuts_tab.save()
        self.accept()
