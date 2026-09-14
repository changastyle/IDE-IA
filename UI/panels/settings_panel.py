# -*- coding: utf-8 -*-
"""Diálogo de Settings con pestaña de shortcuts configurables."""
import os
import re
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QKeySequenceEdit, QPlainTextEdit, QSplitter,
)

from UTILS.shortcuts import (
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


def _parse_commits(detail_text):
    """Parsea el changelog detallado: 'hash|fecha|autor|mensaje' + stat."""
    commits, cur = [], None
    for line in detail_text.splitlines():
        m = re.match(r"^([0-9a-f]{6,})\|(\d{4}-\d{2}-\d{2})\|([^|]*)\|(.*)$",
                     line)
        if m:
            cur = {"hash": m.group(1), "fecha": m.group(2),
                   "autor": m.group(3).strip(), "mensaje": m.group(4).strip(),
                   "stat": ""}
            commits.append(cur)
        elif cur is not None:
            cur["stat"] += line + "\n"
    for c in commits:
        c["stat"] = c["stat"].strip()
    return commits


def _parse_version_md(text):
    """Extrae los builds de un archivo OUT/version-*.md."""
    builds = []
    for block in re.split(r"(?=^## Build )", text, flags=re.M):
        head = block.splitlines()[0] if block else ""
        m = re.match(r"## Build (\d+)\s*-\s*(.*?)\s*(?:\[(\w+)\])?\s*$", head)
        if not m:
            continue

        def field(name, default="-"):
            f = re.search(r"\*\*" + re.escape(name) + r":\*\*\s*(.+)", block)
            return f.group(1).strip() if f else default

        cl = re.search(r"### Resumen de cambios[^\n]*\n+```[^\n]*\n(.*?)```",
                       block, re.S)
        det = re.search(r"### Changelog detallado[^\n]*\n+```[^\n]*\n(.*?)```",
                        block, re.S)
        plat = m.group(3) or field("Plataforma").split()[0].strip("()")

        if det:
            commits = _parse_commits(det.group(1))
        else:
            # formato viejo: solo oneline "hash mensaje" (sin stat guardado)
            oneline = cl.group(1) if cl else ""
            commits = [
                {"hash": mm.group(1), "fecha": "", "autor": "",
                 "mensaje": mm.group(2).strip(), "stat": ""}
                for line in oneline.splitlines()
                for mm in [re.match(r"^([0-9a-f]{6,})\s+(.*)", line)]
                if mm
            ]

        builds.append({
            "build": int(m.group(1)),
            "version": field("Versión", ""),
            "platform": plat,
            "fecha": field("Fecha", m.group(2).strip()),
            "commit": field("Commit"),
            "mensaje": field("Mensaje"),
            "commits": commits,
        })
    return builds


def _find_version_files():
    """Busca los version-*.md en OUT/ (bundle PyInstaller, raíz o cwd)."""
    roots = []
    meipass = getattr(sys, "_MEIPASS", None)  # dentro del .exe/.app empaquetado
    if meipass:
        roots.append(os.path.join(meipass, "OUT"))
    project_root = os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    roots.append(os.path.join(project_root, "OUT"))
    roots.append(os.path.join(os.getcwd(), "OUT"))

    files = []
    for d in dict.fromkeys(roots):
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.startswith("version-") and name.endswith(".md"):
                files.append(os.path.join(d, name))
    return files


def _load_builds():
    """Carga todos los builds de los version-*.md, ordenados por nº desc."""
    seen, builds = set(), []
    for path in _find_version_files():
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        for b in _parse_version_md(text):
            key = (b["build"], b["platform"], b["fecha"])
            if key not in seen:
                seen.add(key)
                builds.append(b)
    builds.sort(key=lambda x: x["build"], reverse=True)
    return builds


def _current_platform():
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    return "linux"


def _project_root():
    return os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))


class VersionsTab(QWidget):
    """Pestaña 'NG-Studio Versions': changelog de builds + versión actual."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._builds = _load_builds()
        self._commits = []

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        split = QSplitter(Qt.Vertical)

        # --- tabla de builds ---
        w1 = QWidget()
        l1 = QVBoxLayout(w1)
        l1.setContentsMargins(0, 0, 0, 0)
        l1.setSpacing(4)
        l1.addWidget(QLabel("Builds registrados — clic para ver sus commits:"))
        self.table = QTableWidget(len(self._builds), 6)
        self.table.setHorizontalHeaderLabels(
            ["Versión", "Build", "Fecha", "Plataforma", "Commit", "Mensaje"])
        for col in range(5):
            self.table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_build_select)
        self._fill_table()
        l1.addWidget(self.table)
        split.addWidget(w1)

        # --- tabla de commits del build seleccionado ---
        w2 = QWidget()
        l2 = QVBoxLayout(w2)
        l2.setContentsMargins(0, 0, 0, 0)
        l2.setSpacing(4)
        l2.addWidget(QLabel(
            "Commits del build — doble clic para ver el detalle:"))
        self.commit_table = QTableWidget(0, 4)
        self.commit_table.setHorizontalHeaderLabels(
            ["Commit", "Fecha", "Autor", "Mensaje"])
        for col in range(3):
            self.commit_table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeToContents)
        self.commit_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.Stretch)
        self.commit_table.verticalHeader().setVisible(False)
        self.commit_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.commit_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.commit_table.setSelectionMode(QTableWidget.SingleSelection)
        self.commit_table.itemDoubleClicked.connect(self._on_commit_open)
        l2.addWidget(self.commit_table)
        split.addWidget(w2)

        split.setSizes([200, 280])
        v.addWidget(split, 1)

        # --- footer: versión actual + última compilación ---
        self.lbl_version = QLabel()
        self.lbl_version.setAlignment(Qt.AlignCenter)
        self.lbl_version.setStyleSheet(
            "color:#FFD60A; font-weight:bold; font-size:14px; padding:6px;")
        v.addWidget(self.lbl_version)
        self._fill_footer()

        if self._builds:
            self.table.selectRow(0)

    def _fill_table(self):
        for i, b in enumerate(self._builds):
            ver = b["version"] or f"b{b['build']}"
            for col, val in enumerate(
                    (ver, str(b["build"]), b["fecha"], b["platform"],
                     b["commit"], b["mensaje"])):
                item = QTableWidgetItem(val)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.table.setItem(i, col, item)

    def _on_build_select(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        self._commits = self._builds[rows[0].row()]["commits"]
        self.commit_table.setRowCount(len(self._commits))
        for i, c in enumerate(self._commits):
            for col, val in enumerate(
                    (c["hash"], c["fecha"], c["autor"], c["mensaje"])):
                item = QTableWidgetItem(val)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.commit_table.setItem(i, col, item)

    def _on_commit_open(self, item):
        """Doble clic en un commit → popup con el detalle (stat, archivos)."""
        c = self._commits[item.row()]
        header = (f"commit {c['hash']}"
                  + (f"  ·  {c['fecha']}" if c["fecha"] else "")
                  + (f"  ·  {c['autor']}" if c["autor"] else "")
                  + f"\n{c['mensaje']}\n")
        stat = c["stat"] or self._git_show(c["hash"]) or "(sin detalle)"

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Commit {c['hash']}")
        dlg.resize(620, 480)
        lay = QVBoxLayout(dlg)
        txt = QPlainTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(header + "\n" + stat)
        lay.addWidget(txt, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        btn = QPushButton("Cerrar")
        btn.clicked.connect(dlg.accept)
        row.addWidget(btn)
        lay.addLayout(row)
        dlg.exec()

    def _git_show(self, commit_hash):
        """Fallback: si el build no guardó el stat, intentar git show en vivo."""
        try:
            import subprocess
            r = subprocess.run(
                ["git", "-C", _project_root(), "show", "--stat",
                 "--format=", commit_hash],
                capture_output=True, text=True, timeout=5)
            return r.stdout.strip() if r.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            return ""

    def _fill_footer(self):
        if not self._builds:
            self.lbl_version.setText(
                "Sin builds registrados — ejecutá un script de OUT/ "
                "para compilar y generar el historial.")
            return
        cur = _current_platform()
        mine = [b for b in self._builds if b["platform"] == cur]
        latest = mine[0] if mine else self._builds[0]
        ver = latest["version"] or f"Build {latest['build']}"
        self.lbl_version.setText(
            f"Versión actual: {ver}  ·  commit {latest['commit']}\n"
            f"Última compilación: {latest['fecha']}  [{latest['platform']}]")


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
        self.versions_tab = VersionsTab()
        self.tabs.addTab(self.versions_tab, "NG-Studio Versions")
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
