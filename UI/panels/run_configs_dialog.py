# -*- coding: utf-8 -*-
"""Diálogo Run/Debug Configurations — estilo JetBrains (WebStorm/IntelliJ).

Layout del mockup:
- Izquierda: toolbar [＋ − ⧉], árbol agrupado por tipo con selección redondeada,
  link "Edit configuration templates…" abajo.
- Derecha: Name + checkboxes, tabs Configuration | Browser/Live Edit,
  formulario con labels a la izquierda e inputs de 26px, "Before launch"
  con panel vacío centrado.
- Abajo: línea divisoria, "?" a la izquierda, [Cancel] [Apply] [▶ Run] [OK].
"""
import copy
import os

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPainter, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QLineEdit, QComboBox, QCheckBox,
    QStackedWidget, QWidget, QFileDialog, QFrame, QTabWidget,
    QListWidget, QListWidgetItem,
)

from utils.run_configs import (
    load_configs, save_configs, npm_scripts, VALID_TYPES,
    FILE_TYPES, GOAL_TYPES,
)

ICONOS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "iconos")

TYPE_NAMES = {
    "node": "Node.js", "npm": "npm", "python": "Python", "java": "Java",
    "springboot": "Spring Boot", "quarkus": "Quarkus",
    "terminal": "Shell Script", "compound": "Compound",
}
BROWSERS = ["Sistema (default)", "Google Chrome", "Safari", "Firefox", "Arc"]

STYLE = """
QDialog { background:#1e1f22; color:#c7c7c7; }
QWidget { font-size:11px; color:#c7c7c7; }
QLabel { background:transparent; border:none; }
QLabel#field { color:#9da0a5; }
QLineEdit, QComboBox {
    background:#2b2d30; border:1px solid #3f4246; border-radius:4px;
    padding:4px 8px; min-height:24px; color:#ffffff; }
QLineEdit:focus, QComboBox:focus { border-color:#3574f0; }
QComboBox::drop-down { border:none; width:22px; }
QComboBox QAbstractItemView {
    background:#2b2d30; border:1px solid #3f4246;
    selection-background-color:#353b45; }
QPushButton {
    background:#353b45; border:1px solid #4e5259; border-radius:6px;
    padding:7px 16px; color:#c7c7c7; font-size:12px; }
QPushButton:hover { background:#434955; }
QPushButton#primary { background:#3574f0; color:#fff; font-weight:600; }
QPushButton#primary:hover { background:#2a5fd0; }
QPushButton#success { background:#3574f0; color:#fff; font-weight:600; }
QPushButton#success:hover { background:#2a5fd0; }
QPushButton#tb { min-width:26px; max-width:26px; min-height:24px;
    max-height:24px; padding:0; border-radius:4px; font-size:13px; }
QTreeWidget {
    background:#2b2d30; border:none; border-radius:6px;
    padding:6px; outline:none; }
QTreeWidget::item { height:26px; border-radius:4px; padding:0 6px; }
QTreeWidget::item:selected { background:#353b45; color:#fff; }
QTreeWidget::item:hover:!selected { background:rgba(53,59,69,0.5); }
QListWidget {
    background:#2b2d30; border:1px solid #3f4246; border-radius:4px;
    padding:4px; }
QListWidget::item { height:24px; border-radius:4px; padding:0 6px; }
QListWidget::item:selected { background:#353b45; color:#fff; }
QTabWidget::pane { border:none; border-top:1px solid #32363d; }
QTabWidget::tab-bar { alignment:left; }
QTabBar::tab {
    background:transparent; color:#9da0a5; padding:6px 14px;
    border-radius:4px; margin:4px 2px; }
QTabBar::tab:selected { background:#353b45; color:#fff; font-weight:600; }
QLineEdit:disabled { color:#6f7275; }
QCheckBox { color:#c7c7c7; spacing:6px; }
QCheckBox::indicator {
    width:14px; height:14px; border:1px solid #6f7275;
    border-radius:3px; background:#2b2d30; }
QCheckBox::indicator:checked { background:#3574f0; border-color:#3574f0; }
QFrame#sep { color:#32363d; }
QFrame#panel {
    background:#2b2d30; border:1px solid #3f4246; border-radius:4px; }
"""


def _type_icon(kind):
    """Icono SVG del tipo de configuración (iconos/<tipo>.svg)."""
    p = os.path.join(ICONOS_DIR, f"{kind}.svg")
    if os.path.exists(p):
        return QIcon(p)
    # Fallback: cuadradito gris
    pm = QPixmap(12, 12)
    pm.fill(Qt.transparent)
    pa = QPainter(pm)
    pa.setRenderHint(QPainter.Antialiasing)
    pa.setPen(Qt.NoPen)
    pa.setBrush(QColor("#8e8e93"))
    pa.drawRoundedRect(0, 0, 12, 12, 3, 3)
    pa.end()
    return QIcon(pm)


def _field_label(text):
    lbl = QLabel(text)
    lbl.setObjectName("field")
    return lbl


class RunConfigsDialog(QDialog):
    """Editor de run configs del proyecto (estilo JetBrains)."""

    def __init__(self, project_dir, current_name="", parent=None):
        super().__init__(parent)
        self.project_dir = project_dir or os.getcwd()
        self.setWindowTitle("Run/Debug Configurations")
        self.resize(880, 560)
        self.setStyleSheet(STYLE)
        self._loading = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        root = QHBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ============ IZQUIERDA: sidebar con toolbar + árbol ============
        side = QWidget()
        side.setFixedWidth(280)
        side.setStyleSheet("background:#2b2d30;")
        sv = QVBoxLayout(side)
        sv.setContentsMargins(10, 10, 10, 10)
        sv.setSpacing(8)
        # Toolbar
        tb = QHBoxLayout()
        tb.setSpacing(4)
        for label, tip, cb in (
                ("＋", "Agregar configuración", self._add),
                ("−", "Eliminar configuración", self._delete),
                ("⧉", "Duplicar configuración", self._duplicate)):
            b = QPushButton(label)
            b.setObjectName("tb")
            b.setToolTip(tip)
            b.clicked.connect(cb)
            tb.addWidget(b)
        tb.addStretch(1)
        sv.addLayout(tb)
        # Árbol agrupado por tipo
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.setIconSize(QSize(17, 17))
        self.tree.setAttribute(Qt.WA_MacShowFocusRect, False)
        self.tree.currentItemChanged.connect(self._on_tree_select)
        sv.addWidget(self.tree, 1)
        # Link inferior
        link = QLabel("<a href='#' style='color:#3574f0;'>"
                      "Edit configuration templates…</a>")
        link.setStyleSheet("font-size:11px;")
        sv.addWidget(link)
        root.addWidget(side)

        # ============ DERECHA: panel de configuración ============
        right = QVBoxLayout()
        right.setContentsMargins(16, 12, 16, 8)
        right.setSpacing(10)

        # Fila superior: Name + checkboxes
        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(_field_label("Name:"))
        self.ed_name = QLineEdit()
        self.ed_name.setFixedWidth(180)
        top.addWidget(self.ed_name)
        top.addSpacing(10)
        self.chk_multi = QCheckBox("Allow multiple instances")
        top.addWidget(self.chk_multi)
        self.chk_store = QCheckBox("Store as project file")
        self.chk_store.setChecked(True)
        top.addWidget(self.chk_store)
        top.addStretch(1)
        right.addLayout(top)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_cfg_tab(), "Configuration")
        self.tabs.addTab(self._build_browser_tab(), "Browser / Live Edit")
        right.addWidget(self.tabs, 1)

        # Before launch
        bl = QHBoxLayout()
        bl_lbl = _field_label("Before launch")
        bl.addWidget(bl_lbl)
        sep_bl = QFrame()
        sep_bl.setObjectName("sep")
        sep_bl.setFrameShape(QFrame.HLine)
        bl.addWidget(sep_bl, 1)
        right.addLayout(bl)
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setFixedHeight(64)
        pl = QVBoxLayout(panel)
        pl.addWidget(QLabel("There are no tasks to run before launch"),
                     0, Qt.AlignCenter)
        right.addWidget(panel)
        root.addLayout(right, 1)

        # ============ BARRA INFERIOR ============
        bottom_container = QVBoxLayout()
        sep = QFrame()
        sep.setObjectName("sep")
        sep.setFrameShape(QFrame.HLine)
        bottom_container.addWidget(sep)
        brow = QHBoxLayout()
        brow.setContentsMargins(10, 8, 10, 10)
        help_lbl = QLabel("?")
        help_lbl.setFixedSize(20, 20)
        help_lbl.setAlignment(Qt.AlignCenter)
        help_lbl.setStyleSheet(
            "border:1px solid #6f7275; border-radius:10px; color:#c7c7c7;")
        brow.addWidget(help_lbl)
        brow.addStretch(1)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply = QPushButton("Apply")
        self.btn_apply.clicked.connect(self._apply)
        self.btn_run = QPushButton("▶ Run")
        self.btn_run.setObjectName("primary")
        self.btn_run.clicked.connect(self._run)
        self.btn_ok = QPushButton("OK")
        self.btn_ok.clicked.connect(self.accept)
        for b in (self.btn_cancel, self.btn_apply, self.btn_run, self.btn_ok):
            b.setFixedWidth(95)
            brow.addWidget(b)
        bottom_container.addLayout(brow)

        outer.addLayout(root, 1)
        outer.addLayout(bottom_container)

        self._configs = load_configs(self.project_dir)
        self._relativize_paths()
        self._fill_tree(current_name)
        self.result_run = False      # True si apretó Run
        self.result_config = None    # config a ejecutar

    # ---- tabs del formulario ----

    @staticmethod
    def _row(label_text, field, label_w=110):
        """Fila label fijo + campo que se expande (estilo JetBrains).

        Evita QFormLayout: en macOS centra las filas y no expande los
        campos (FieldsStayAtSizeHint).
        """
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        lbl = _field_label(label_text)
        lbl.setFixedWidth(label_w)
        lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        row.addWidget(lbl)
        if isinstance(field, QHBoxLayout):
            row.addLayout(field, 1)
        else:
            row.addWidget(field, 1)
        return row

    @staticmethod
    def _with_browse(line_edit, on_browse):
        """Campo + botón '…' a la derecha."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(line_edit, 1)
        b = QPushButton("…")
        b.setFixedSize(30, 26)
        b.clicked.connect(on_browse)
        row.addWidget(b)
        return row

    def _build_cfg_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 14, 6, 4)
        v.setSpacing(14)

        self.combo_type = QComboBox()
        for t in VALID_TYPES:
            self.combo_type.addItem(_type_icon(t), TYPE_NAMES.get(t, t), t)
        self.combo_type.currentIndexChanged.connect(self._on_type)
        v.addLayout(self._row("Type:", self.combo_type))

        # --- páginas por tipo ---
        # 0: archivo (node/python/java) · 1: npm · 2: goal (spring/quarkus)
        # 3: terminal
        self.stack = QStackedWidget()
        # archivo (compartida por node/python/java)
        w_file = QWidget()
        vn = QVBoxLayout(w_file)
        vn.setContentsMargins(0, 0, 0, 0)
        vn.setSpacing(14)
        self.ed_path = QLineEdit()
        self.lbl_file = _field_label("JavaScript file:")
        self.lbl_file.setFixedWidth(110)
        row_file = QHBoxLayout()
        row_file.setContentsMargins(0, 0, 0, 0)
        row_file.setSpacing(10)
        row_file.addWidget(self.lbl_file)
        row_file.addLayout(
            self._with_browse(self.ed_path, self._browse), 1)
        vn.addLayout(row_file)
        vn.addStretch(1)
        self.stack.addWidget(w_file)
        # npm: package.json + Command + Scripts
        w_npm = QWidget()
        vm = QVBoxLayout(w_npm)
        vm.setContentsMargins(0, 0, 0, 0)
        vm.setSpacing(14)
        self.ed_pkg = QLineEdit()
        self.ed_pkg.setPlaceholderText("package.json")
        vm.addLayout(self._row(
            "package.json:",
            self._with_browse(self.ed_pkg, self._browse_pkg)))
        self.combo_cmd = QComboBox()
        self.combo_cmd.addItem("run")
        vm.addLayout(self._row("Command:", self.combo_cmd))
        self.combo_script = QComboBox()
        self.combo_script.setEditable(True)
        vm.addLayout(self._row("Scripts:", self.combo_script))
        vm.addStretch(1)
        self.stack.addWidget(w_npm)
        # goal (springboot/quarkus)
        w_goal = QWidget()
        vg = QVBoxLayout(w_goal)
        vg.setContentsMargins(0, 0, 0, 0)
        vg.setSpacing(14)
        self.ed_goal = QLineEdit()
        self.ed_goal.setPlaceholderText("mvn spring-boot:run")
        vg.addLayout(self._row("Goal:", self.ed_goal))
        vg.addStretch(1)
        self.stack.addWidget(w_goal)
        # terminal: script text
        w_term = QWidget()
        vt = QVBoxLayout(w_term)
        vt.setContentsMargins(0, 0, 0, 0)
        vt.setSpacing(14)
        self.ed_command = QLineEdit()
        self.ed_command.setPlaceholderText("npm run build && echo listo")
        vt.addLayout(self._row("Script text:", self.ed_command))
        vt.addStretch(1)
        self.stack.addWidget(w_term)
        # compound: lista de configs miembro + picker
        w_comp = QWidget()
        vc = QVBoxLayout(w_comp)
        vc.setContentsMargins(0, 0, 0, 0)
        vc.setSpacing(10)
        lbl_m = _field_label("Configurations to run:")
        vc.addWidget(lbl_m)
        self.list_members = QListWidget()
        vc.addWidget(self.list_members, 1)
        row_m = QHBoxLayout()
        row_m.setSpacing(6)
        self.combo_member = QComboBox()
        row_m.addWidget(self.combo_member, 1)
        for label, cb in (("＋", self._member_add), ("−", self._member_del)):
            b = QPushButton(label)
            b.setFixedSize(30, 26)
            b.clicked.connect(cb)
            row_m.addWidget(b)
        vc.addLayout(row_m)
        self.stack.addWidget(w_comp)
        v.addWidget(self.stack)

        # --- campos comunes ---
        self.ed_args = QLineEdit()
        self.ed_args.setPlaceholderText("argumentos extra (opcional)")
        v.addLayout(self._row("Arguments:", self.ed_args))

        self.ed_node = QLineEdit()
        self.ed_node.setEnabled(False)
        self.ed_node.setText(self._node_runtime())
        self.node_row = QWidget()
        nr = self._row("Node runtime:", self.ed_node)
        nr.setContentsMargins(0, 0, 0, 0)
        self.node_row.setLayout(nr)
        v.addWidget(self.node_row)

        self.ed_env = QLineEdit()
        self.ed_env.setPlaceholderText("Environment variables  (A=1 B=2)")
        v.addLayout(self._row("Environment:", self.ed_env))

        self.lbl_dir = QLabel(self._short_path(self.project_dir))
        self.lbl_dir.setStyleSheet("color:#6f7275;")
        self.lbl_dir.setFixedHeight(24)
        self.lbl_dir.setToolTip(self.project_dir)
        v.addLayout(self._row("Working dir:", self.lbl_dir))
        v.addStretch(1)
        return w

    def _build_browser_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 14, 6, 4)
        v.setSpacing(14)
        self.chk_browser = QCheckBox(
            "Abrir navegador cuando la salida muestre una URL "
            "(http://localhost:…)")
        v.addWidget(self.chk_browser)
        self.combo_browser = QComboBox()
        self.combo_browser.addItems(BROWSERS)
        v.addLayout(self._row("Browser:", self.combo_browser))
        v.addStretch(1)
        return w

    @staticmethod
    def _short_path(p):
        """~/… para display compacto."""
        home = os.path.expanduser("~")
        return "~" + p[len(home):] if p.startswith(home) else p

    @staticmethod
    def _node_runtime():
        """'node (/ruta) · vX.Y' como el mockup."""
        import shutil, subprocess
        path = shutil.which("node") or "node"
        ver = ""
        if path != "node":
            try:
                ver = subprocess.run(
                    [path, "--version"], capture_output=True,
                    text=True, timeout=5).stdout.strip()
            except Exception:
                pass
        txt = f"node ({path})"
        return f"{txt}  {ver}" if ver else txt

    # ---- árbol ----

    def _fill_tree(self, select_name=""):
        self.tree.blockSignals(True)
        self.tree.clear()
        for kind in VALID_TYPES:
            group = [c for c in self._configs if c["type"] == kind]
            if not group:
                continue
            parent = QTreeWidgetItem([TYPE_NAMES.get(kind, kind)])
            f = parent.font(0)
            f.setBold(True)
            parent.setFont(0, f)
            parent.setFlags(Qt.ItemIsEnabled)
            parent.setForeground(0, QColor("#9da0a5"))
            self.tree.addTopLevelItem(parent)
            for c in group:
                it = QTreeWidgetItem([c["name"]])
                it.setIcon(0, _type_icon(kind))
                it.setData(0, Qt.UserRole, c["name"])
                parent.addChild(it)
            parent.setExpanded(True)
        self.tree.blockSignals(False)
        if select_name:
            self._select_by_name(select_name)
        else:
            for i in range(self.tree.topLevelItemCount()):
                it = self.tree.topLevelItem(i).child(0)
                if it:
                    self.tree.setCurrentItem(it)
                    return

    def _select_by_name(self, name):
        for i in range(self.tree.topLevelItemCount()):
            for j in range(self.tree.topLevelItem(i).childCount()):
                it = self.tree.topLevelItem(i).child(j)
                if it.data(0, Qt.UserRole) == name:
                    self.tree.setCurrentItem(it)
                    return

    def _current_config(self):
        it = self.tree.currentItem()
        if not it:
            return None, -1
        name = it.data(0, Qt.UserRole)
        if not name:
            return None, -1
        for i, c in enumerate(self._configs):
            if c["name"] == name:
                return c, i
        return None, -1

    def _on_tree_select(self, cur, prev):
        # Guardar los edits de la config anterior (como Apply automático)
        if prev and not self._loading:
            prev_name = prev.data(0, Qt.UserRole)
            if prev_name:
                prev_cfg = next(
                    (x for x in self._configs if x["name"] == prev_name),
                    None)
                if prev_cfg:
                    self._collect_into(prev_cfg)
        if cur is None or not cur.data(0, Qt.UserRole):
            return
        c, _ = self._current_config()
        if c:
            self._load_form(c)

    def _stack_index(self, t):
        """Mapea tipo → página del stack."""
        if t in FILE_TYPES:
            return 0
        if t == "npm":
            return 1
        if t in GOAL_TYPES:
            return 2
        if t == "compound":
            return 4
        return 3

    def _type(self):
        """Tipo seleccionado (userData del combo)."""
        return self.combo_type.currentData() or "node"

    def _load_form(self, c):
        self._loading = True
        self.ed_name.setText(c["name"])
        idx = self.combo_type.findData(c["type"])
        if idx >= 0:
            self.combo_type.setCurrentIndex(idx)
        self.ed_path.setText(c.get("path", ""))
        self.ed_pkg.setText(c.get("package_json", "package.json"))
        self.ed_goal.setText(c.get("goal", GOAL_TYPES.get(c["type"], "")))
        self.ed_command.setText(c.get("command", ""))
        self.ed_args.setText(c.get("args", ""))
        self.ed_env.setText(c.get("env", ""))
        self.chk_multi.setChecked(bool(c.get("allow_multiple")))
        self.chk_browser.setChecked(bool(c.get("open_browser")))
        br = c.get("browser", BROWSERS[0])
        idx = self.combo_browser.findText(br)
        self.combo_browser.setCurrentIndex(idx if idx >= 0 else 0)
        if c["type"] == "npm":
            self._reload_scripts(c.get("script", "start"))
        if c["type"] == "compound":
            self._reload_members(c)
        self._update_file_label(c["type"])
        self.node_row.setVisible(c["type"] in ("node", "npm"))
        self.stack.setCurrentIndex(self._stack_index(c["type"]))
        self._loading = False

    def _reload_members(self, c):
        """Carga la lista de miembros y el picker de configs disponibles."""
        self.list_members.clear()
        for name in c.get("members", []):
            it = QListWidgetItem(name)
            sub = next((x for x in self._configs if x["name"] == name), None)
            it.setIcon(_type_icon(sub["type"] if sub else "terminal"))
            self.list_members.addItem(it)
        # Picker: todas las configs menos compounds y la actual
        self.combo_member.clear()
        for x in self._configs:
            if x["type"] != "compound" and x["name"] != c["name"]:
                self.combo_member.addItem(_type_icon(x["type"]), x["name"])

    def _member_add(self):
        name = self.combo_member.currentText()
        if not name:
            return
        for i in range(self.list_members.count()):
            if self.list_members.item(i).text() == name:
                return  # ya está
        sub = next((x for x in self._configs if x["name"] == name), None)
        it = QListWidgetItem(name)
        it.setIcon(_type_icon(sub["type"] if sub else "terminal"))
        self.list_members.addItem(it)

    def _member_del(self):
        row = self.list_members.currentRow()
        if row >= 0:
            self.list_members.takeItem(row)

    def _reload_scripts(self, selected=""):
        self.combo_script.clear()
        scripts = npm_scripts(self.project_dir)
        if scripts:
            self.combo_script.addItems(scripts)
        if selected:
            idx = self.combo_script.findText(selected)
            if idx >= 0:
                self.combo_script.setCurrentIndex(idx)
            else:
                self.combo_script.setCurrentText(selected)

    def _update_file_label(self, t):
        """Label + placeholder del campo archivo según el tipo."""
        names = {"node": "JavaScript file:", "python": "Python file:",
                 "java": "Java file:"}
        self.lbl_file.setText(names.get(t, "Archivo:"))
        ph = FILE_TYPES.get(t, ("", "", "archivo"))[2]
        self.ed_path.setPlaceholderText(ph)

    def _on_type(self, _idx):
        if self._loading:
            return
        t = self._type()
        self.stack.setCurrentIndex(self._stack_index(t))
        self.node_row.setVisible(t in ("node", "npm"))
        self._update_file_label(t)
        if t == "npm":
            self._reload_scripts()
        elif t == "compound":
            c, _ = self._current_config()
            if c:
                self._reload_members(c)
        elif t in GOAL_TYPES and not self.ed_goal.text().strip():
            self.ed_goal.setText(GOAL_TYPES[t])
        self._collect()
        c, _ = self._current_config()
        if c:
            self._fill_tree(c["name"])

    def _browse(self):
        t = self._type()
        flt = FILE_TYPES.get(t, FILE_TYPES["node"])[1]
        p, _ = QFileDialog.getOpenFileName(
            self, "Archivo a ejecutar", self.project_dir,
            f"{flt};;Todos (*)")
        if p:
            try:
                p = os.path.relpath(p, self.project_dir)
            except ValueError:
                pass
            self.ed_path.setText(p)

    def _browse_pkg(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "package.json", self.project_dir,
            "package.json (package.json);;Todos (*)")
        if p:
            try:
                p = os.path.relpath(p, self.project_dir)
            except ValueError:
                pass
            self.ed_pkg.setText(p)

    # ---- CRUD ----

    def _collect(self):
        """Guarda los campos del formulario en la config seleccionada."""
        c, _ = self._current_config()
        if c:
            self._collect_into(c)

    def _collect_into(self, c):
        c["name"] = self.ed_name.text().strip() or "config"
        c["type"] = self._type()
        if c["type"] in FILE_TYPES:
            c["path"] = self.ed_path.text().strip()
        elif c["type"] == "npm":
            c["script"] = self.combo_script.currentText().strip() or "start"
            c["package_json"] = self.ed_pkg.text().strip() or "package.json"
        elif c["type"] in GOAL_TYPES:
            c["goal"] = self.ed_goal.text().strip() or GOAL_TYPES[c["type"]]
        elif c["type"] == "compound":
            c["members"] = [self.list_members.item(i).text()
                            for i in range(self.list_members.count())]
        else:
            c["command"] = self.ed_command.text().strip()
        c["args"] = self.ed_args.text().strip()
        c["env"] = self.ed_env.text().strip()
        c["allow_multiple"] = self.chk_multi.isChecked()
        c["open_browser"] = self.chk_browser.isChecked()
        c["browser"] = self.combo_browser.currentText()

    def _apply(self):
        self._collect()
        save_configs(self.project_dir, self._configs)
        c, _ = self._current_config()
        self._fill_tree(c["name"] if c else "")

    def _add(self):
        self._collect()
        self._configs.append({
            "name": f"config-{len(self._configs) + 1}",
            "type": "node", "path": "", "args": "", "env": "",
            "open_browser": False, "browser": BROWSERS[0],
        })
        save_configs(self.project_dir, self._configs)
        self._fill_tree(self._configs[-1]["name"])

    def _delete(self):
        c, i = self._current_config()
        if c is None:
            return
        del self._configs[i]
        save_configs(self.project_dir, self._configs)
        self._fill_tree(self._configs[0]["name"] if self._configs else "")

    def _duplicate(self):
        c, _ = self._current_config()
        if not c:
            return
        self._collect()
        dup = copy.deepcopy(c)
        dup["name"] = f"{c['name']} (copy)"
        self._configs.append(dup)
        save_configs(self.project_dir, self._configs)
        self._fill_tree(dup["name"])

    def _run(self):
        self._collect()
        c, _ = self._current_config()
        if c:
            save_configs(self.project_dir, self._configs)
            self.result_run = True
            self.result_config = dict(c)
        self.accept()

    def accept(self):
        self._collect()
        save_configs(self.project_dir, self._configs)
        super().accept()

    def _relativize_paths(self):
        """Convierte paths absolutos bajo el proyecto a relativos."""
        for c in self._configs:
            p = c.get("path", "")
            if p and os.path.isabs(p):
                try:
                    rel = os.path.relpath(p, self.project_dir)
                    if not rel.startswith(".."):
                        c["path"] = rel
                except ValueError:
                    pass
