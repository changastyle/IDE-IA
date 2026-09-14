# -*- coding: utf-8 -*-
"""Visor de archivos Markdown con renderizado a HTML."""
import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextBrowser,
    QFileDialog,
)

from UTILS.markdown_utils.renderer import md_to_html

MD_EXTS = (".md", ".markdown")


class MarkdownViewerDialog(QDialog):
    """Muestra un .md renderizado, con toggle código/vista y abrir externa."""

    def __init__(self, parent, path, rel):
        super().__init__(parent)
        self.path = path
        self.rel = rel
        self.setWindowTitle(f"Markdown — {rel}")
        self.resize(760, 640)
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 10)
        v.setSpacing(6)

        size = os.path.getsize(path)
        head = QHBoxLayout()
        lbl = QLabel(f"{rel}  ·  {size:,} bytes  ·  {os.path.splitext(path)[1]}")
        lbl.setStyleSheet("color:#8a8f98;")
        head.addWidget(lbl, 1)
        v.addLayout(head)

        self.view = QTextBrowser()
        self.view.setObjectName("mdView")
        self.view.setOpenExternalLinks(True)
        self.view.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        v.addWidget(self.view, 1)

        row = QHBoxLayout()
        b_raw = QPushButton("Ver código")
        b_raw.setCheckable(True)
        b_raw.toggled.connect(self._toggle_raw)
        b_ext = QPushButton("Abrir externa")
        b_ext.clicked.connect(self._open_external)
        b_close = QPushButton("Cerrar")
        b_close.clicked.connect(self.accept)
        row.addWidget(b_raw)
        row.addWidget(b_ext)
        row.addStretch(1)
        row.addWidget(b_close)
        v.addLayout(row)

        self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError as e:
            text = f"**Error al leer el archivo:** {e}"
        html = md_to_html(text, base_dir=os.path.dirname(self.path))
        self.view.setHtml(
            f"<style>"
            "body{color:#d7dae0;font-size:14px;line-height:1.5;}"
            "h1,h2,h3,h4,h5,h6{color:#fff;margin:14px 0 6px;}"
            "code{background:#2a2d33;padding:1px 4px;border-radius:4px;"
            "font-family:Menlo,monospace;font-size:12px;}"
            "pre{background:#14161a;border:1px solid #2b2e34;border-radius:8px;"
            "padding:10px;overflow:auto;}"
            "pre code{background:transparent;padding:0;}"
            "table{border-collapse:collapse;margin:8px 0;}"
            "th,td{border:1px solid #3a3e46;padding:4px 10px;}"
            "th{background:#22252b;}"
            "blockquote{border-left:3px solid #2f6fed;margin:6px 0;"
            "padding:2px 10px;color:#a8adb6;background:#22252b66;}"
            "a{color:#5b9bff;}"
            "img{max-width:100%;}"
            "hr{border:none;border-top:1px solid #3a3e46;}"
            "</style>" + html)
        # Base URL para que links/images relativos funcionen
        self.view.document().setBaseUrl(
            QUrl.fromLocalFile(os.path.dirname(self.path) + os.sep))

    def _toggle_raw(self, on):
        if on:
            try:
                with open(self.path, "r", encoding="utf-8", errors="replace") as f:
                    raw = f.read()
            except OSError as e:
                raw = f"Error: {e}"
            self.view.setPlainText(raw)
        else:
            self._load()

    def _open_external(self):
        QFileDialog  # noqa: F821  (import ya usado arriba)
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.path))
