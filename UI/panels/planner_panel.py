# -*- coding: utf-8 -*-
"""Panel Planner: workflows con agentes IA (placeholder inicial)."""
import os

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICONS_DIR = os.path.join(APP_DIR, "iconos")


class PlannerPanel(QWidget):
    """AI Autonomous Workflow Planner: carriles con tareas secuenciales
    ejecutadas por agentes IA.

    Placeholder inicial mientras se implementa la UI de carriles
    (diseño de referencia: workflow_planner_mockup.svg)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.addStretch(1)
        p = os.path.join(ICONS_DIR, "planner.svg")
        if os.path.exists(p):
            icon = QLabel()
            icon.setPixmap(QIcon(p).pixmap(QSize(40, 40)))
            icon.setAlignment(Qt.AlignCenter)
            v.addWidget(icon)
        title = QLabel("Planner")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color:#e8eaed; font-size:15px; font-weight:bold;")
        v.addWidget(title)
        sub = QLabel(
            "Workflows con agentes IA — carriles y tareas secuenciales.\n"
            "(En construcción)")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color:#9aa0aa; font-size:11px;")
        v.addWidget(sub)
        v.addStretch(2)
