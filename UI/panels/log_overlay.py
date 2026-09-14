# -*- coding: utf-8 -*-
"""LogOverlay — panel flotante con el log de NG-Studio.

Misma mecánica que TerminalOverlay (QFrame flotante sobre el body,
con sombra y botón de ocultar) pero en lugar de shells muestra las
líneas del AppLog central: eventos de servicios, boot queue,
excepciones capturadas por el excepthook, etc.
"""
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QGraphicsDropShadowEffect,
)

from UTILS.core_services.app_log import AppLog


class LogOverlay(QFrame):
    """Overlay flotante que muestra el log interno de la app."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TerminalOverlay")  # mismo estilo que la terminal
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 4, 8, 8)
        v.setSpacing(4)
        h = QHBoxLayout()
        h.setSpacing(6)
        lbl = QLabel("NG-Studio Log")
        lbl.setStyleSheet(
            "color:#9aa0aa; font-weight:bold; background:transparent;")
        h.addWidget(lbl)
        h.addStretch(1)
        btn_clear = QPushButton("⌫")
        btn_clear.setFixedSize(22, 22)
        btn_clear.setToolTip("Limpiar log")
        btn_clear.setStyleSheet(
            "QPushButton{background:transparent;border:none;color:#9aa0aa;"
            "font-size:14px;} QPushButton:hover{background:#2a2d33;"
            "border-radius:4px;color:#fff;}")
        btn_clear.clicked.connect(self._clear)
        h.addWidget(btn_clear)
        btn_hide = QPushButton("▼")
        btn_hide.setFixedSize(22, 22)
        btn_hide.setToolTip("Ocultar log")
        btn_hide.clicked.connect(self.hide)
        h.addWidget(btn_hide)
        v.addLayout(h)

        self.out = QPlainTextEdit()
        self.out.setReadOnly(True)
        self.out.setFont(QFont("Menlo", 11))
        self.out.setStyleSheet(
            "QPlainTextEdit{background:#141519;color:#d7dae0;"
            "border:none;}")
        self.out.setPlaceholderText("Log de NG-Studio…")
        v.addWidget(self.out, 1)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 170))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        # poblar con lo ya logueado y seguir en vivo
        self.out.setPlainText("\n".join(AppLog.instance().lines()))
        self._scroll_bottom()
        AppLog.instance().line.connect(self._append)

    def _append(self, line):
        self.out.appendPlainText(line)
        self._scroll_bottom()

    def _scroll_bottom(self):
        sb = self.out.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear(self):
        AppLog.instance().clear()
        self.out.clear()
