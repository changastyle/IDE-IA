# -*- coding: utf-8 -*-
"""MonitorPanel — monitor de tareas de NG-Studio.

Lista los servicios registrados en el ServiceManager con su estado,
edad del último heartbeat y botones de control (start / stop /
restart). Arriba muestra la boot queue: una barra de progreso con el
servicio que está arrancando.

Estados: running (verde), starting (amarillo), hung (rojo),
stopping (amarillo), stopped (gris), error (rojo).
"""
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
)

_STATE_COLOR = {
    "running": "#4caf50",
    "starting": "#e6b450",
    "hung": "#e05555",
    "stopping": "#e6b450",
    "stopped": "#8e8e93",
    "error": "#e05555",
}

_STATE_LABEL = {
    "running": "● running",
    "starting": "◌ starting",
    "hung": "✖ hung",
    "stopping": "◌ stopping",
    "stopped": "○ stopped",
    "error": "✖ error",
}


class MonitorPanel(QWidget):
    """Panel de servicios: estado, heartbeat y control individual."""

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        # ---- boot queue ----
        self.boot_lbl = QLabel("Servicios: esperando boot…")
        self.boot_lbl.setStyleSheet("color:#9aa0aa; font-size:11px;")
        v.addWidget(self.boot_lbl)
        self.boot_bar = QProgressBar()
        self.boot_bar.setFixedHeight(6)
        self.boot_bar.setTextVisible(False)
        self.boot_bar.setRange(0, 1)
        self.boot_bar.setValue(0)
        v.addWidget(self.boot_bar)

        # ---- tabla de servicios ----
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Servicio", "Estado", "Beat", "Acciones"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        v.addWidget(self.table, 1)

        # señales del manager
        manager.service_state.connect(self._on_state)
        manager.boot_progress.connect(self._on_boot_progress)
        manager.boot_finished.connect(self._on_boot_finished)

        # refresco de la columna "Beat" (edad del heartbeat)
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._refresh_beats)
        self._tick.start(1000)

        self._rebuild()

    # ---- tabla ----
    def _rebuild(self):
        self.table.setRowCount(0)
        for svc in self.manager.services():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(svc.name))
            st = QTableWidgetItem(_STATE_LABEL.get(svc.state, svc.state))
            st.setForeground(QColor(
                _STATE_COLOR.get(svc.state, "#8e8e93")))
            self.table.setItem(row, 1, st)
            self.table.setItem(row, 2, QTableWidgetItem("—"))
            self.table.setCellWidget(row, 3, self._actions(svc.name))
            self._update_row(row, svc)

    def _actions(self, name):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(2, 0, 2, 0)
        h.setSpacing(2)
        for label, tip, fn in (
                ("▶", "Start", self.manager.start),
                ("■", "Stop", self.manager.stop),
                ("↻", "Restart", self.manager.restart)):
            b = QPushButton(label)
            b.setFixedSize(24, 22)
            b.setToolTip(f"{tip} '{name}'")
            b.setStyleSheet(
                "QPushButton{background:transparent;border:none;"
                "color:#9aa0aa;font-size:12px;}"
                "QPushButton:hover{background:#2a2d33;border-radius:4px;"
                "color:#fff;}")
            b.clicked.connect(lambda _c=False, n=name, f=fn: f(n))
            h.addWidget(b)
        h.addStretch(1)
        return w

    def _row_of(self, name):
        for row in range(self.table.rowCount()):
            it = self.table.item(row, 0)
            if it and it.text() == name:
                return row
        return -1

    def _update_row(self, row, svc):
        st = self.table.item(row, 1)
        if st:
            st.setText(_STATE_LABEL.get(svc.state, svc.state))
            st.setForeground(
                QColor(_STATE_COLOR.get(svc.state, "#8e8e93")))
        self._update_beat_cell(row, svc)

    def _update_beat_cell(self, row, svc):
        it = self.table.item(row, 2)
        if it is None:
            return
        if svc.state in ("running", "hung") and svc.last_beat:
            age = time.monotonic() - svc.last_beat
            it.setText(f"hace {age:.0f}s")
        else:
            it.setText("—")

    # ---- señales ----
    def _on_state(self, name, _state):
        svc = self.manager.get(name)
        row = self._row_of(name)
        if svc is None:
            return
        if row < 0:
            self._rebuild()
        else:
            self._update_row(row, svc)

    def _on_boot_progress(self, name, done, total):
        self.boot_bar.setRange(0, total)
        self.boot_bar.setValue(done)
        self.boot_lbl.setText(
            f"Boot queue: iniciando '{name}' ({done}/{total})")

    def _on_boot_finished(self):
        self.boot_bar.setValue(self.boot_bar.maximum())
        self.boot_lbl.setText("Boot queue: servicios listos")

    def _refresh_beats(self):
        for svc in self.manager.services():
            row = self._row_of(svc.name)
            if row >= 0:
                self._update_beat_cell(row, svc)
