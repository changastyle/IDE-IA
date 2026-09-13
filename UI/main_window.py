"""UI.py — Nuevo layout experimental (estilo IntelliJ).

Estructura:
  ┌────────────────────────────────────────────────────────┐
  │ TopBar (50px, todo el ancho)                           │
  ├────┬───────────────────────────────────────────────────┤
  │ H  │  Body del body: 3 paneles intercambiables        │
  │ o  │  ┌──────────┬───────────────┬──────────┐          │
  │ t  │  │ Panel 1  │   Panel 2     │ Panel 3  │          │
  │ b  │  └──────────┴───────────────┴──────────┘          │
  │ a  │  ┌──────────────────────────────────────┐         │
  │ r  │  │ Terminal flotante semitransparente   │         │
  └────┴──└──────────────────────────────────────┘─────────┘

- Los paneles se intercambian arrastrando su barra de título sobre otro panel.
- Cada panel se colapsa a una franja vertical con su nombre (clic para expandir).
- La terminal flota DENTRO del body del body (overlay, no quita espacio).
- La hotbar (50px) tiene botones para mostrar/ocultar cada panel y la terminal.
"""

import os
import re
import sys
import shlex
import subprocess
import zlib

try:
    import pty as _pty
except ImportError:  # Windows: pty no existe
    _pty = None
import signal as _signal
from PySide6.QtCore import (Qt, QMimeData, QPoint, Signal, QProcess, QSize,
                            QTimer, QSocketNotifier)
from PySide6.QtGui import (QDrag, QColor, QPainter, QFont, QAction, QIcon,
                           QTextCursor, QKeySequence, QPixmap, QPen, QImage)
from PySide6.QtCore import QRectF, QPointF
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSplitter, QPlainTextEdit, QMenu, QFileDialog,
    QGraphicsDropShadowEffect, QSizePolicy, QTabWidget,
    QDialog, QListWidget, QListWidgetItem, QWidgetAction, QLineEdit,
    QMessageBox, QProgressBar, QStackedWidget, QSplashScreen,
)

from utils.git import (
    is_repo, get_current_branch, list_branches, pull, push,
    checkout, create_branch, has_remote,
)
from utils.git_utils import GitUtils

MIME_PANEL = "application/x-ui-panel"
SHOW_SPLASH = False  # splash + chime de inicio
TOPBAR_H = 50
HOTBAR_W = 50
TERMINAL_H = 300
COLLAPSED_W = 30

ICONOS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "iconos")
CHEVRON_SVG = os.path.join(ICONOS_DIR, "flecha_abajo.svg")


def _chevron_right(btn, size=13):
    """Chevron ▾ SVG a la derecha del texto (icono + layout RTL)."""
    if os.path.exists(CHEVRON_SVG):
        btn.setIcon(QIcon(CHEVRON_SVG))
        btn.setIconSize(QSize(size, size))
        btn.setLayoutDirection(Qt.RightToLeft)


def _process_tree_rss_mb():
    """RSS total (MB) del proceso y todos sus descendientes.

    Suma IDE + terminales/procesos lanzados (node, npm, python, etc).
    Usa `ps` — sin dependencias externas.
    """
    try:
        out = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,rss="],
            capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return 0.0
    children, rss = {}, {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            pid, ppid, r = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue
        rss[pid] = r
        children.setdefault(ppid, []).append(pid)
    total, stack, seen = 0.0, [os.getpid()], set()
    while stack:
        pid = stack.pop()
        if pid in seen or pid not in rss:
            continue
        seen.add(pid)
        total += rss[pid]
        stack.extend(children.get(pid, []))
    return total / 1024.0  # KB → MB

STYLE = """
QMainWindow, QWidget { background:#16181c; color:#d7dae0; font-size:13px; }
#TopBar { background:#1e2126; border-bottom:1px solid #2a2d33; }
#TopBar QLabel { color:#e8eaed; font-weight:bold; font-size:14px; }
#BottomBar { background:#1e2126; border-top:1px solid #2a2d33; }
#BottomBar QLabel { color:#9aa0aa; font-size:11px; }
QPushButton#tbFolder {
    background:#2a2d33; border:none; border-radius:8px; padding:6px 14px;
    color:#e8eaed; font-weight:bold; font-size:13px; text-align:left; }
QPushButton#tbFolder:hover { background:#33373e; }
QListWidget#projList {
    background:#22242a; border:1px solid #33363c; border-radius:8px;
    padding:4px; font-size:13px; outline:none; }
QListWidget#projList::item { padding:6px 10px; border-radius:6px; }
QListWidget#projList::item:selected { background:#2f6fdb; color:#fff; }
QListWidget#projList::item:hover { background:#2a2d33; }
QPushButton#success {
    background:#2f6fdb; border:none; border-radius:8px; padding:8px 18px;
    color:#fff; font-weight:bold; }
QPushButton#success:hover { background:#3d7fed; }
QTableWidget {
    background:#22242a; border:1px solid #33363c; border-radius:8px;
    gridline-color:#2a2d33; font-size:13px; outline:none; }
QTableWidget::item { padding:6px 10px; }
QTableWidget::item:selected { background:#2f6fdb; color:#fff; }
QHeaderView::section {
    background:#1e2126; color:#9aa0aa; border:none;
    padding:6px 10px; font-weight:bold; font-size:12px; }
QKeySequenceEdit {
    background:#22242a; border:1px solid #33363c; border-radius:6px;
    padding:4px 8px; color:#e8eaed; }
QPushButton#tbBranch {
    background:transparent; border:none; border-radius:8px; padding:6px 10px;
    color:#c8ccd4; font-weight:bold; font-size:13px; }
QPushButton#tbBranch:hover { background:#2a2d33; }
QPushButton#tbBranch:disabled { color:#555; }
QPushButton#tbGit, QPushButton#tbNav {
    background:transparent; border:none; border-radius:8px;
    color:#c8ccd4; font-size:15px; font-weight:bold; }
QPushButton#tbGit:hover, QPushButton#tbNav:hover { background:#2a2d33; color:#fff; }
QPushButton#tbGit:disabled, QPushButton#tbNav:disabled { color:#555; }
QPushButton#tbRunCfg {
    background:#2a2d33; border:none; border-radius:8px; padding:6px 14px;
    color:#e8eaed; font-weight:bold; font-size:13px; }
QPushButton#tbRunCfg:hover { background:#33373e; }
QPushButton#tbRunPlay {
    background:transparent; border:none; border-radius:8px;
    color:#4caf50; font-size:16px; font-weight:bold; }
QPushButton#tbRunPlay:hover { background:#1d3a1f; }
QPushButton#tbRunStop {
    background:transparent; border:none; border-radius:8px;
    color:#e5716f; font-size:14px; font-weight:bold; }
QPushButton#tbRunStop:hover:enabled { background:#3a1d1d; }
QPushButton#tbRunStop:disabled { color:#555; }
QMenu#runMenu {
    background:#22252b; border:1px solid #3a3e46; border-radius:10px;
    padding:6px; color:#d7dae0; font-size:13px; }
QMenu#runMenu::item { padding:6px 18px; border-radius:6px; }
QMenu#runMenu::item:selected { background:#2f6fdb; }
QLabel#panelTitle { color:#e8eaed; font-weight:bold; font-size:13px; }
QLabel#panelChevron { color:#9aa0aa; font-size:12px; }
QPushButton#panelHeadBtn {
    background:transparent; border:none; border-radius:5px;
    color:#9aa0aa; font-size:12px; }
QPushButton#panelHeadBtn:hover { background:#2a2d33; color:#fff; }
QTreeWidget#filesTree {
    background:transparent; border:none; font-size:13px; outline:none; }
QTreeWidget#filesTree::item { padding:2px 0; border-radius:0; }
QTreeWidget#filesTree::item:selected { background:#2f6fdb; border-radius:0; }
QTreeWidget#filesTree::item:selected:first {
    border-top-left-radius:5px; border-bottom-left-radius:5px; }
QTreeWidget#filesTree::item:selected:last {
    border-top-right-radius:5px; border-bottom-right-radius:5px; }
QTreeWidget#filesTree::item:hover { background:#2a2d33; border-radius:0; }
QFrame#centerEditor { background:#1a1c21; border:1px solid #2b2e34; border-radius:8px; }
QTabWidget::pane { border:none; background:transparent; }
QTabBar::tab {
    background:#22242a; border:none; border-bottom:2px solid transparent;
    padding:6px 10px 6px 14px; color:#9aa0aa; font-size:13px;
    border-radius:6px 6px 0 0; text-align:left;
    min-width:60px; max-width:200px; }
QTabBar::tab:selected { background:#1a1c21; color:#e8eaed; border-bottom:2px solid #2f6fdb; }
QTabBar::tab:hover:!selected { background:#2a2d33; color:#c8ccd4; }
QTabBar::close-button {
    image: url(iconos/close.svg);
    subcontrol-position:right; width:12px; height:12px;
    padding:2px; border-radius:3px; }
QTabBar::close-button:hover { background:#3a3e46; }
QTabBar::close-button:disabled { image:none; }
QLabel#editorStatus {
    background:#1e2126; color:#5c6370; font-size:11px;
    border-top:1px solid #2b2e34; }
QTextEdit#chatView, QScrollArea#chatView {
    background:#1a1c21; border:1px solid #2b2e34; border-radius:8px;
    padding:4px; font-size:13px; }
QScrollArea#chatView > QWidget > QWidget {
    background:transparent; }
QPlainTextEdit {
    background:#22242a; border:1px solid #33363c; border-radius:8px;
    padding:6px; color:#e8eaed; font-size:13px; }
QFrame#chatTopPanel, QFrame#chatMidPanel, QFrame#chatBottomPanel {
    background:transparent; border:none; }
QFrame#chatRightPanel {
    background:#1e2126; border-left:1px solid #2b2e34; }
QListWidget#promptNavList {
    background:#22242a; border:1px solid #33363c; border-radius:8px;
    padding:4px; font-size:12px; color:#b6bac1; }
QListWidget#promptNavList::item {
    padding:4px 6px; border-radius:4px; }
QListWidget#promptNavList::item:hover {
    background:#2a2d33; }
QListWidget#promptNavList::item:selected {
    background:#7c3aed; color:#fff; }
QMenu#branchMenu {
    background:#22252b; border:1px solid #3a3e46; border-radius:10px;
    padding:6px; color:#d7dae0; font-size:13px; }
QMenu#branchMenu::item { padding:6px 18px; border-radius:6px; }
QMenu#branchMenu::item:selected { background:#2f6fdb; }
QMenu#branchMenu::item:disabled { color:#666; }
QWidget#branchRow { background:transparent; border-radius:6px; }
QWidget#branchRow:hover { background:#33373e; }
QLabel#branchRowCheck {
    background:transparent; color:#7ce495; font-size:12px; }
QMenu#projMenu {
    background:#22252b; border:1px solid #3a3e46; border-radius:10px;
    padding:6px; color:#d7dae0; font-size:13px; }
QMenu#projMenu::item { padding:6px 14px; border-radius:6px; }
QMenu#projMenu::item:selected { background:#2f6fdb; }
QMenu#projMenu::item:disabled {
    color:#7d828c; font-size:11px; font-weight:bold; padding:6px 14px 2px; }
QMenu#projMenu::separator {
    height:1px; background:#33363c; margin:5px 10px; }
QWidget#projRow { background:transparent; border-radius:6px; }
QWidget#projRow:hover { background:#2f6fdb; }
QLabel#projRowName {
    background:transparent; color:#e8eaed; font-weight:bold; font-size:13px; }
QLabel#projRowPath {
    background:transparent; color:#9aa0aa; font-size:11px; }
QLabel#projRowDot {
    background:transparent; color:#4caf50; font-size:11px; }
QWidget#projRow:hover QLabel#projRowName { color:#fff; }
QWidget#projRow:hover QLabel#projRowPath { color:#cfe0ff; }
QWidget#projRow:hover QLabel#projRowDot { color:#7ce495; }
#HotBar { background:#1a1c21; border-right:1px solid #2a2d33; }
#HotBar QPushButton {
    background:transparent; border:none; border-radius:8px;
    color:#9aa0aa; font-weight:bold; font-size:14px;
}
#HotBar QPushButton:hover { background:#2a2d33; color:#fff; }
#HotBar QPushButton:checked { background:#2f6fdb; color:#fff; }
#Panel { background:#1a1c21; border:1px solid #2a2d33; border-radius:8px; }
#PanelHeader { background:#22252b; border-top-left-radius:8px;
    border-top-right-radius:8px; }
#PanelHeader QLabel { color:#c8ccd4; font-weight:bold; background:transparent; }
#PanelHeader QPushButton {
    background:transparent; border:none; color:#9aa0aa; font-size:12px; }
#PanelHeader QPushButton:hover { color:#fff; background:#2f333a; border-radius:4px; }
#PanelStrip { background:#22252b; border:1px solid #2a2d33; border-radius:6px; }
#TerminalOverlay {
    background:rgba(12,13,16,216);
    border:1px solid #3a3f47; border-radius:10px; }
#TerminalHeader { background:transparent; border:none; }
#TerminalOverlay QLabel { color:#c8ccd4; font-weight:bold; background:transparent; }
#TerminalOverlay QPlainTextEdit {
    background:rgba(8,9,11,160); border:1px solid #2a2d33; border-radius:6px;
    font-family:Menlo,monospace; font-size:12px; color:#c8f7c5; }
#TerminalOverlay QPushButton { background:transparent; border:none; color:#9aa0aa; }
#TerminalOverlay QPushButton:hover { color:#fff; background:#2f333a; border-radius:4px; }
QSplitter::handle { background:#2a2d33; width:4px; }
QSplitter::handle:hover { background:#2f6fdb; }
QToolTip {
    background:#1e2229; color:#d7dae0; font-size:11px;
    border:1px solid #3a3f47; border-radius:7px; padding:8px 11px; }
"""


class VerticalLabel(QWidget):
    """Etiqueta con texto rotado 90° (para paneles colapsados)."""

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text
        self.setToolTip(f"{text} — clic para expandir")
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, e):
        p = self.parent()
        while p is not None and not isinstance(p, Panel):
            p = p.parent()
        if isinstance(p, Panel):
            p.set_collapsed(False)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QColor("#9aa0aa"))
        f = QFont()
        f.setPointSize(11)
        f.setBold(True)
        p.setFont(f)
        p.translate(0, self.height())
        p.rotate(-90)
        p.drawText(0, 0, self.height(), self.height(),
                   Qt.AlignHCenter | Qt.AlignVCenter, self.text)
        p.end()


class PanelHeader(QFrame):
    """Barra de título del panel: draggable para intercambiar paneles."""

    def __init__(self, panel, parent=None):
        super().__init__(parent)
        self.setObjectName("PanelHeader")
        self.setFixedHeight(30)
        self.panel = panel
        self._press_pos = None
        self.h = QHBoxLayout(self)
        self.h.setContentsMargins(8, 2, 4, 2)
        self.h.setSpacing(4)
        self.lbl = QLabel(panel.title)
        self.h.addWidget(self.lbl)
        self.h.addStretch(1)

    def add_action(self, icon, tip, cb):
        """Agrega un botón chico a la derecha del título del panel."""
        b = QPushButton(icon)
        b.setObjectName("panelHeadBtn")
        b.setFixedSize(22, 22)
        b.setToolTip(tip)
        b.clicked.connect(cb)
        self.h.addWidget(b)
        return b

    def add_widget(self, w, stretch=0):
        """Inserta un widget antes del stretch (después del título)."""
        self.h.insertWidget(max(0, self.h.count() - 1), w, stretch)
        return w

    def add_right(self, w):
        """Agrega un widget pegado al borde derecho del header."""
        self.h.addWidget(w)
        return w

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press_pos = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._press_pos is not None and \
           (e.position().toPoint() - self._press_pos).manhattanLength() > 8:
            self._start_drag()
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._press_pos = None
        super().mouseReleaseEvent(e)

    def _start_drag(self):
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(MIME_PANEL, self.panel.title.encode())
        drag.setMimeData(mime)
        pix = QPixmapSafe.grab(self.panel)
        drag.setPixmap(pix.scaledToWidth(120, Qt.SmoothTransformation))
        drag.setHotSpot(self._press_pos)
        drag.exec(Qt.MoveAction)


class QPixmapSafe:
    """Namespace helper para grabar widgets a pixmap."""
    @staticmethod
    def grab(w):
        return w.grab()


class Panel(QFrame):
    """Panel colapsable e intercambiable."""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.title = title
        self.collapsed = False
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.header = PanelHeader(self)
        v.addWidget(self.header)
        self.body = QFrame()
        self.body.setObjectName("PanelBody")
        # Selector acotado: sin esto el borde punteado cascada a los hijos
        self.body.setStyleSheet(
            "QFrame#PanelBody { background:#202329; border-radius:6px;"
            " border:1px dashed #2f333a; }")
        v.addWidget(self.body, 1)
        # Franja vertical para estado colapsado
        self.strip = VerticalLabel(title)
        self.strip.hide()
        v.addWidget(self.strip, 1)
        self.setAcceptDrops(True)
        self.setMinimumWidth(120)

    def toggle_collapse(self):
        self.set_collapsed(not self.collapsed)

    def set_collapsed(self, c):
        self.collapsed = c
        self.header.setVisible(not c)
        self.body.setVisible(not c)
        self.strip.setVisible(c)
        if c:
            self.setFixedWidth(30)
        else:
            self.setMinimumWidth(120)
            self.setMaximumWidth(16777215)

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(MIME_PANEL):
            e.acceptProposedAction()

    def dropEvent(self, e):
        other_title = bytes(e.mimeData().data(MIME_PANEL)).decode()
        w = self.window()
        if hasattr(w, "swap_panels"):
            w.swap_panels(other_title, self.title)
        e.acceptProposedAction()


class HotBar(QFrame):
    """Barra vertical de 50px con botones para paneles y terminal.

    side: 'left' o 'right' (solo cambia el orden de los botones).
    """

    def __init__(self, side="left", buttons=None, checked=None,
                 pinned_bottom=(), parent=None):
        super().__init__(parent)
        self.setObjectName("HotBar")
        self.setFixedWidth(HOTBAR_W)
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 8, 4, 8)
        v.setSpacing(6)
        self.btns = {}
        checked = checked or set()
        pinned = set(pinned_bottom)
        # Definición de botones por defecto
        if buttons is None:
            buttons = (
                ("p0", "1", "Panel 1", None),
                ("p1", "2", "Panel 2", None),
                ("p2", "3", "Panel 3", None),
                ("term", "⌨", "Terminal (flotante)", None),
            )
        for btn_def in buttons:
            # Soporta (key, label, tip) o (key, label, tip, icon_path)
            if len(btn_def) == 4:
                key, label, tip, icon_path = btn_def
            else:
                key, label, tip = btn_def
                icon_path = None
            b = QPushButton(label)
            b.setCheckable(True)
            b.setChecked(key in checked)
            b.setFixedSize(38, 38)
            b.setToolTip(tip)
            if icon_path and os.path.exists(icon_path):
                b.setIcon(QIcon(icon_path))
                b.setIconSize(QSize(22, 22))
                b.setText("")
            if key not in pinned:
                v.addWidget(b)
            self.btns[key] = b
        v.addStretch(1)
        # Anclados abajo, en el orden dado por pinned_bottom
        for key in pinned_bottom:
            if key in self.btns:
                v.addWidget(self.btns[key])


_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][B0]|\r")


class TermEdit(QPlainTextEdit):
    """Editor de terminal: intercepta el teclado y lo manda al pty."""

    send_data = Signal(bytes)

    def keyPressEvent(self, e):
        key, text = e.key(), e.text()
        if e.matches(QKeySequence.Copy) or (e.modifiers() & Qt.ControlModifier
                                            and key == Qt.Key_C
                                            and self.textCursor().hasSelection()):
            super().keyPressEvent(e)
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self.send_data.emit(b"\r")
        elif key == Qt.Key_Backspace:
            self.send_data.emit(b"\x7f")
        elif key == Qt.Key_Up:
            self.send_data.emit(b"\x1b[A")
        elif key == Qt.Key_Down:
            self.send_data.emit(b"\x1b[B")
        elif key == Qt.Key_Right:
            self.send_data.emit(b"\x1b[C")
        elif key == Qt.Key_Left:
            self.send_data.emit(b"\x1b[D")
        elif key == Qt.Key_Home:
            self.send_data.emit(b"\x1b[H")
        elif key == Qt.Key_End:
            self.send_data.emit(b"\x1b[F")
        elif text:
            self.send_data.emit(text.encode("utf-8"))
        # teclas sin efecto (tab, etc. las maneja la shell vía pty)
        e.accept()


class TerminalTab(QWidget):
    """Una pestaña de terminal real: zsh sobre un pty, escribís directo."""

    text_received = Signal(str)
    finished = Signal(int)  # código de salida

    def __init__(self, cwd=None, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.out = TermEdit()
        self.out.setFont(QFont("Menlo", 12))
        self.out.setStyleSheet(
            "QPlainTextEdit{background:#141519;color:#d7dae0;border:none;}")
        self.out.setPlaceholderText("Terminal… (escribí acá)")
        self.out.send_data.connect(self.proc_write)
        v.addWidget(self.out)
        if _pty is None:
            # Sin pty (Windows): la terminal integrada no está disponible
            self._alive = False
            self.pid = self.fd = self.notifier = self._screen = None
            self._scrollback = []
            self.out.setReadOnly(True)
            self.out.setPlaceholderText(
                "Terminal no disponible en esta plataforma "
                "(pty solo existe en macOS/Linux).")
            return
        # Pty: shell real con edición de línea, historial y tab-completion
        self.pid, self.fd = _pty.fork()
        if self.pid == 0:  # hijo: zsh interactivo en el pty
            os.environ["TERM"] = "xterm-256color"
            if cwd and os.path.isdir(cwd):
                try:
                    os.chdir(cwd)
                except OSError:
                    pass
            try:
                os.execv("/bin/zsh", ["zsh", "-i"])
            except Exception:
                os._exit(1)
        try:
            import fcntl, termios, struct
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ,
                        struct.pack("HHHH", 30, 120, 0, 0))
        except OSError:
            pass
        # Emulación de terminal real (pyte): \r, cursor, clear, colores…
        try:
            import pyte
            self._screen = pyte.HistoryScreen(120, 30, history=2000)
            self._stream = pyte.ByteStream(self._screen)
        except ImportError:
            self._screen = None
        self._scrollback = []
        self.notifier = QSocketNotifier(self.fd, QSocketNotifier.Read, self)
        self.notifier.activated.connect(self._read)
        self._alive = True

    def update_winsize(self):
        """Ajusta cols/rows del pty al tamaño real del widget (para que ls
        y los prompts usen el ancho correcto)."""
        if not self._alive:
            return
        try:
            import fcntl, termios, struct
            fm = self.out.fontMetrics()
            cols = max(20, self.out.viewport().width()
                       // max(1, fm.horizontalAdvance("M")))
            rows = max(5, self.out.viewport().height() // max(1, fm.lineSpacing()))
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ,
                        struct.pack("HHHH", rows, cols, 0, 0))
            if self._screen is not None:
                self._screen.resize(rows, cols)
            os.killpg(os.getpgid(self.pid), _signal.SIGWINCH)
        except (OSError, ProcessLookupError):
            pass

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.update_winsize()

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self.update_winsize)

    def _read(self):
        try:
            data = os.read(self.fd, 65536)
        except OSError:
            data = b""
        if not data:
            # La shell cerró el pty → terminó
            if self._alive:
                self._alive = False
                self.notifier.setEnabled(False)
                self.out.appendPlainText("— shell terminada —")
                self.finished.emit(0)
            return
        text = _ANSI_RE.sub("", data.decode("utf-8", "replace"))
        if self._screen is not None:
            try:
                self._stream.feed(data)
                self._render()
            except Exception as ex:
                # nunca romper el loop de la terminal: va al hook global
                # (loguea a crash.log, status bar, y no repite el spam)
                sys.excepthook(type(ex), ex, ex.__traceback__)
        else:
            self.out.appendPlainText(text.rstrip())
        self.text_received.emit("")

    @staticmethod
    def _dict_line(d, cols):
        out = []
        for x in range(cols):
            c = d.get(x)
            if c is None:
                out.append(" ")
            else:
                out.append(getattr(c, "data", str(c)))
        return "".join(out).rstrip()

    def _render(self):
        """Vuelca scrollback + pantalla de pyte al widget."""
        s = self._screen
        while s.history.top:
            line = s.history.top.popleft()
            self._scrollback.append(self._dict_line(line, s.columns))
        visible = [s.display[y].rstrip() for y in range(s.lines)]
        while visible and not visible[-1].strip():
            visible.pop()
        self.out.setPlainText("\n".join(self._scrollback + visible))
        cur = self.out.textCursor()
        cur.movePosition(QTextCursor.End)
        self.out.setTextCursor(cur)

    def _on_fin(self, code, _status):
        self.out.appendPlainText(f"— shell terminada (código {code}) —")
        self.finished.emit(code)

    def run_command(self, cmd):
        self.proc_write(cmd + "\r")

    def proc_write(self, data):
        if not self._alive:
            return
        if isinstance(data, str):
            data = data.encode("utf-8")
        try:
            os.write(self.fd, data)
        except OSError:
            self._alive = False

    def is_running(self):
        return self._alive

    def kill(self):
        if self._alive:
            try:
                os.killpg(os.getpgid(self.pid), _signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            self._alive = False
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
        if self.notifier is not None:
            self.notifier.setEnabled(False)


class TerminalOverlay(QFrame):
    """Terminal flotante con múltiples pestañas (cada una su proceso)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TerminalOverlay")
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 4, 8, 8)
        v.setSpacing(4)
        h = QHBoxLayout()
        h.setSpacing(6)
        lbl = QLabel("Terminal")
        lbl.setStyleSheet("color:#9aa0aa; font-weight:bold; background:transparent;")
        h.addWidget(lbl)
        h.addStretch(1)
        btn_new = QPushButton("＋")
        btn_new.setFixedSize(22, 22)
        btn_new.setToolTip("Nueva terminal")
        btn_new.setStyleSheet(
            "QPushButton{background:transparent;border:none;color:#9aa0aa;"
            "font-size:14px;} QPushButton:hover{background:#2a2d33;"
            "border-radius:4px;color:#fff;}")
        btn_new.clicked.connect(lambda: self.new_tab(cwd=None))
        h.addWidget(btn_new)
        btn_hide = QPushButton("▼")
        btn_hide.setFixedSize(22, 22)
        btn_hide.setToolTip("Ocultar terminal")
        btn_hide.clicked.connect(self.hide)
        h.addWidget(btn_hide)
        v.addLayout(h)
        # Pestañas: Local, Local (2), … con + para nueva
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        v.addWidget(self.tabs, 1)
        self._counter = 0
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 170))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def new_tab(self, cwd=None, run_cmd=None, on_output=None, on_fin=None):
        """Crea una pestaña con shell nueva; opcionalmente corre un comando."""
        self._counter += 1
        title = "Local" if self._counter == 1 else f"Local ({self._counter})"
        tab = TerminalTab(cwd=cwd)
        idx = self.tabs.addTab(tab, title)
        self.tabs.setCurrentIndex(idx)
        if on_output:
            tab.text_received.connect(on_output)
        if on_fin:
            tab.finished.connect(on_fin)
        if run_cmd:
            tab.run_command(run_cmd)
        return tab

    def close_tab(self, idx):
        tab = self.tabs.widget(idx)
        if tab:
            tab.kill()
        self.tabs.removeTab(idx)
        if self.tabs.count() == 0:
            self.hide()

    def current_tab(self):
        return self.tabs.currentWidget()

    def stop_current(self):
        tab = self.current_tab()
        if tab:
            tab.kill()

    def kill_all(self):
        """Mata todas las shells (al cerrar la app)."""
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab:
                tab.kill()


class ProjectsDialog(QDialog):
    """Diálogo de proyectos previos: muestra sesiones abiertas y recientes,
    permite abrir una nueva instancia en cualquiera de ellos."""

    def __init__(self, parent, current_path, sessions, recents):
        super().__init__(parent)
        self.setWindowTitle("Open Previous Project")
        self.resize(560, 420)
        self.selected_path = None
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)
        home = os.path.expanduser("~")

        def _disp(p):
            return p.replace(home, "~")

        # ---- Sesiones abiertas ----
        if sessions:
            v.addWidget(QLabel("Abiertas (instancias activas)"))
            self.list_sessions = QListWidget()
            self.list_sessions.setObjectName("projList")
            for p in sessions:
                name = os.path.basename(p)
                mark = "● " if p == os.path.realpath(current_path or "") else "  "
                it = QListWidgetItem(f"{mark}{name}   —   {_disp(p)}")
                it.setData(Qt.UserRole, p)
                it.setToolTip(p)
                self.list_sessions.addItem(it)
            self.list_sessions.itemDoubleClicked.connect(self._open_item)
            v.addWidget(self.list_sessions, 2)
            v.addSpacing(4)

        # ---- Recientes ----
        v.addWidget(QLabel("Recientes"))
        self.list_recents = QListWidget()
        self.list_recents.setObjectName("projList")
        for p in recents:
            if p in sessions:
                continue
            name = os.path.basename(p)
            it = QListWidgetItem(f"  {name}   —   {_disp(p)}")
            it.setData(Qt.UserRole, p)
            it.setToolTip(p)
            self.list_recents.addItem(it)
        self.list_recents.itemDoubleClicked.connect(self._open_item)
        v.addWidget(self.list_recents, 3)

        # ---- Botones ----
        row = QHBoxLayout()
        self.btn_open_here = QPushButton("Abrir aquí")
        self.btn_open_here.setToolTip("Cambiar esta ventana a la carpeta elegida")
        self.btn_open_here.clicked.connect(self._open_here)
        self.btn_new_window = QPushButton("Abrir en nueva ventana")
        self.btn_new_window.setObjectName("success")
        self.btn_new_window.setToolTip("Abrir una nueva instancia del IDE en esa carpeta")
        self.btn_new_window.clicked.connect(self._open_new)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_cancel)
        row.addStretch(1)
        row.addWidget(self.btn_open_here)
        row.addWidget(self.btn_new_window)
        v.addLayout(row)

    def _current_item_path(self):
        for lst in (getattr(self, "list_sessions", None), self.list_recents):
            if lst and lst.currentItem():
                return lst.currentItem().data(Qt.UserRole)
        return None

    def _open_item(self, item):
        self.selected_path = item.data(Qt.UserRole)
        self.accept()

    def _open_here(self):
        p = self._current_item_path()
        if p:
            self.selected_path = p
            self.setProperty("open_here", True)
            self.accept()

    def _open_new(self):
        p = self._current_item_path()
        if p:
            self.selected_path = p
            self.setProperty("open_here", False)
            self.accept()


_BADGE_COLORS = ["#e8912d", "#57b64f", "#d75f9e", "#31a8a0",
                 "#9a5fd0", "#4a86e8", "#d9534f", "#c9a227"]


def _initials(name):
    """'battle-citi-5.3-flash' → 'BF'; 'languages' → 'LA'."""
    words = [w for w in re.split(r"[^A-Za-z0-9]+", name) if w]
    if len(words) >= 2:
        return (words[0][0] + words[-1][0]).upper()
    return (name[:2] or "?").upper()


class _ProjectRow(QWidget):
    """Fila del menú de proyectos: badge + nombre (+ padre si se repite)
    + path + ✕ para quitarla de la lista."""
    clicked = Signal()
    removed = Signal()

    def __init__(self, path, current=False, suffix="", parent=None):
        super().__init__(parent)
        self.setObjectName("projRow")
        self.setAttribute(Qt.WA_StyledBackground)  # que pinte el :hover
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(320)
        base = os.path.basename(path.rstrip("/")) or path
        # si el nombre se repite en la lista, se muestra con la carpeta
        # padre: "sub-carpeta-for-test — NG-STUDIO"
        name = f"{base} — {suffix}" if suffix else base
        disp = path.replace(os.path.expanduser("~"), "~")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 5, 12, 5)
        lay.setSpacing(10)

        badge = QLabel(_initials(base))
        badge.setFixedSize(26, 26)
        badge.setAlignment(Qt.AlignCenter)
        color = _BADGE_COLORS[
            zlib.crc32(base.encode()) % len(_BADGE_COLORS)]
        badge.setStyleSheet(
            f"background:{color}; color:#fff; border-radius:6px;"
            "font-weight:bold; font-size:11px;")
        lay.addWidget(badge)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        nl = QLabel(name)
        nl.setObjectName("projRowName")
        pl = QLabel(disp)
        pl.setObjectName("projRowPath")
        col.addWidget(nl)
        col.addWidget(pl)
        lay.addLayout(col, 1)

        if current:
            dot = QLabel("●")
            dot.setObjectName("projRowDot")
            lay.addWidget(dot)

        btn_x = QPushButton("✕")
        btn_x.setFixedSize(18, 18)
        btn_x.setCursor(Qt.PointingHandCursor)
        btn_x.setToolTip("Quitar de la lista")
        btn_x.setStyleSheet(
            "QPushButton{background:transparent; border:none; color:#6b7078;"
            "font-size:11px; border-radius:5px;}"
            "QPushButton:hover{background:#4a2c2c; color:#e05561;}")
        btn_x.clicked.connect(self.removed.emit)
        lay.addWidget(btn_x)

        # Las labels no capturan mouse: la fila entera es clicable/hover
        for w in self.findChildren(QLabel):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(e)


class _BranchRow(QWidget):
    """Fila del menú de ramas: píldora del color único de la rama
    (igual que el botón de la barra superior y el grafo), ✓ en la actual."""
    clicked = Signal()

    def __init__(self, name, color, current=False, parent=None):
        super().__init__(parent)
        self.setObjectName("branchRow")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(220)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 4, 12, 4)
        lay.setSpacing(9)

        pill = QLabel(name)
        pill.setStyleSheet(
            f"background:{color}; color:#fff; font-size:12px;"
            "font-weight:bold; border-radius:11px; padding:4px 12px;")
        lay.addWidget(pill)
        lay.addStretch(1)

        if current:
            chk = QLabel("✓")
            chk.setStyleSheet(
                "background:transparent; color:#7ce495; font-size:12px;")
            lay.addWidget(chk)

        for w in self.findChildren(QLabel):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(e)


class TopBar(QFrame):
    """Barra superior de 50px: carpeta, rama git, pull/push, navegación,
    y run configurations a la derecha."""

    folder_changed = Signal(str)
    navigate = Signal(str)      # 'back' | 'forward'
    git_action = Signal(str)    # 'pull' | 'push' | 'commit' | f'checkout:{b}'
    run_requested = Signal(str)  # nombre de la configuración a ejecutar
    stop_requested = Signal()
    edit_configs_requested = Signal()
    open_new_window = Signal(str)  # path → abrir nueva instancia
    settings_requested = Signal()  # engranaje → preferencias

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(TOPBAR_H)
        self.repo_path = ""
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 6, 10, 6)
        h.setSpacing(8)

        # Proyecto actual (botón único con dropdown integrado)
        self.btn_folder = QPushButton("Sin carpeta  ▾")
        self.btn_folder.setObjectName("tbFolder")
        self.btn_folder.setCursor(Qt.PointingHandCursor)
        self.btn_folder.setToolTip("Proyecto — clic para cambiar o clonar")
        self.btn_folder.clicked.connect(self._show_folder_menu)
        h.addWidget(self.btn_folder)

        h.addSpacing(10)

        # Rama git (botón con icono + nombre + chevron)
        self.btn_branch = QPushButton("⎇ —")
        self.btn_branch.setObjectName("tbBranch")
        self.btn_branch.setCursor(Qt.PointingHandCursor)
        self.btn_branch.setToolTip("Rama git — clic para ver ramas y acciones")
        self.btn_branch.clicked.connect(self._show_branch_menu)
        _chevron_right(self.btn_branch, 12)
        h.addWidget(self.btn_branch)

        # Pull / Push
        self.btn_pull = QPushButton("↙")
        self.btn_pull.setObjectName("tbGit")
        self.btn_pull.setFixedSize(30, 30)
        self.btn_pull.setToolTip("Git pull")
        self.btn_pull.clicked.connect(lambda: self.git_action.emit("pull"))
        h.addWidget(self.btn_pull)
        self.btn_push = QPushButton("↗")
        self.btn_push.setObjectName("tbGit")
        self.btn_push.setFixedSize(30, 30)
        self.btn_push.setToolTip("Git push")
        self.btn_push.clicked.connect(lambda: self.git_action.emit("push"))
        h.addWidget(self.btn_push)

        h.addSpacing(10)

        # Navegación atrás / adelante
        self.btn_back = QPushButton("↩")
        self.btn_back.setObjectName("tbNav")
        self.btn_back.setFixedSize(30, 30)
        self.btn_back.setEnabled(False)
        self.btn_back.setToolTip("Atrás (archivo anterior)")
        self.btn_back.clicked.connect(lambda: self.navigate.emit("back"))
        h.addWidget(self.btn_back)
        self.btn_fwd = QPushButton("↪")
        self.btn_fwd.setObjectName("tbNav")
        self.btn_fwd.setFixedSize(30, 30)
        self.btn_fwd.setEnabled(False)
        self.btn_fwd.setToolTip("Adelante (archivo siguiente)")
        self.btn_fwd.clicked.connect(lambda: self.navigate.emit("forward"))
        h.addWidget(self.btn_fwd)

        h.addStretch(1)

        # ---- Run configurations (derecha, estilo IntelliJ) ----
        self.run_configs = []  # lista de {name, path}
        self._run_current = None
        self.btn_run_cfg = QPushButton("▶ run")
        self.btn_run_cfg.setObjectName("tbRunCfg")
        self.btn_run_cfg.setCursor(Qt.PointingHandCursor)
        self.btn_run_cfg.setToolTip("Configuración de ejecución")
        self.btn_run_cfg.clicked.connect(self._show_run_menu)
        _chevron_right(self.btn_run_cfg)
        h.addWidget(self.btn_run_cfg)

        self.btn_run = QPushButton("▶")
        self.btn_run.setObjectName("tbRunPlay")
        self.btn_run.setFixedSize(30, 30)
        self.btn_run.setToolTip("Ejecutar la configuración seleccionada")
        self.btn_run.clicked.connect(
            lambda: self.run_requested.emit(self._run_current))
        h.addWidget(self.btn_run)

        self.btn_stop_run = QPushButton("⏹")
        self.btn_stop_run.setObjectName("tbRunStop")
        self.btn_stop_run.setFixedSize(30, 30)
        self.btn_stop_run.setEnabled(False)
        self.btn_stop_run.setToolTip("Detener el proceso")
        self.btn_stop_run.clicked.connect(self.stop_requested.emit)
        h.addWidget(self.btn_stop_run)

        # Engranaje → preferencias (mismo diálogo que 🔧 del chat)
        gear = os.path.join(ICONOS_DIR, "engranaje.svg")
        self.btn_settings = QPushButton()
        self.btn_settings.setObjectName("tbGit")
        self.btn_settings.setFixedSize(30, 30)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.setToolTip("Preferencias (modelos, voz, tokens)")
        if os.path.exists(gear):
            self.btn_settings.setIcon(QIcon(gear))
            self.btn_settings.setIconSize(QSize(18, 18))
        self.btn_settings.clicked.connect(self.settings_requested.emit)
        h.addWidget(self.btn_settings)

    # ---- run configurations ----
    def load_run_configs(self):
        """Carga las run configs del proyecto desde .run_configs.json."""
        from utils.run_configs import load_configs
        self.run_configs = load_configs(self.repo_path) if self.repo_path else []
        if self.run_configs:
            self._run_current = self.run_configs[0]["name"]
        else:
            self._run_current = None
        self._update_run_btn()

    def _update_run_btn(self):
        if self._run_current:
            self.btn_run_cfg.setText(f"▶ {self._run_current}")
        else:
            self.btn_run_cfg.setText("▶ run")

    def _show_run_menu(self):
        menu = QMenu(self)
        menu.setObjectName("runMenu")
        for c in self.run_configs:
            name = c["name"]
            label = ("▶  " if name == self._run_current else "    ") + name
            act = QAction(label, menu)
            act.triggered.connect(lambda _, n=name: self._select_run_cfg(n))
            menu.addAction(act)
        if self.run_configs:
            menu.addSeparator()
        a_cur = QAction("Current File", menu)
        a_cur.triggered.connect(lambda: self._select_run_cfg("(current file)"))
        menu.addAction(a_cur)
        menu.addSeparator()
        a_edit = QAction("Edit Configurations…", menu)
        a_edit.triggered.connect(self.edit_configs_requested.emit)
        menu.addAction(a_edit)
        menu.exec(self.btn_run_cfg.mapToGlobal(
            QPoint(0, self.btn_run_cfg.height())))

    def _select_run_cfg(self, name):
        self._run_current = name
        self._update_run_btn()

    def set_run_running(self, running):
        """Activa/desactiva el botón de stop."""
        self.btn_stop_run.setEnabled(running)

    # ---- carpeta ----
    def set_folder(self, path):
        from utils.recents import add_recent
        # normalizar: una "/" final dejaba basename()="" y el botón sin nombre
        self.repo_path = os.path.normpath(path) if path else ""
        name = os.path.basename(self.repo_path) if self.repo_path else "Sin carpeta"
        self.btn_folder.setText(f"{name}  ▾")
        self._refresh_git()
        if self.repo_path:
            add_recent(self.repo_path)
        self.load_run_configs()

    def _show_folder_menu(self):
        menu = self._build_projects_menu()
        menu.exec(self.btn_folder.mapToGlobal(
            QPoint(0, self.btn_folder.height())))

    def _build_projects_menu(self):
        """Dropdown único del proyecto: acciones arriba, luego las
        sesiones abiertas y los proyectos recientes (estilo Windsurf)."""
        from utils.recents import load_recents
        from utils.sessions import load_sessions
        menu = QMenu(self)
        menu.setObjectName("projMenu")

        a_new = QAction("＋  New Project…", menu)
        a_new.triggered.connect(self._new_project)
        menu.addAction(a_new)
        a_open = QAction("📂  Open…", menu)
        a_open.triggered.connect(self._pick_folder)
        menu.addAction(a_open)
        a_cl = QAction("⎇  Clone Repository…", menu)
        a_cl.triggered.connect(self._clone_repo)
        menu.addAction(a_cl)
        a_nw = QAction("🗔  Open in New Window…", menu)
        a_nw.triggered.connect(self._show_projects_popup)
        menu.addAction(a_nw)

        cur = os.path.realpath(self.repo_path or "")
        sessions = load_sessions()
        recents = [p for p in load_recents() if p not in sessions]

        # nombres repetidos → mostrar la carpeta padre para distinguirlas
        all_paths = sessions + recents
        counts = {}
        for p in all_paths:
            n = os.path.basename(p.rstrip("/")) or p
            counts[n] = counts.get(n, 0) + 1

        def _suffix(p):
            n = os.path.basename(p.rstrip("/")) or p
            if counts.get(n, 0) <= 1:
                return ""
            return os.path.basename(os.path.dirname(p.rstrip("/"))) or ""

        def _header(text):
            menu.addSeparator()
            h = menu.addAction(text)
            h.setEnabled(False)

        def _row(p):
            act = QWidgetAction(menu)
            row = _ProjectRow(p, current=(p == cur), suffix=_suffix(p))
            row.setToolTip(p)
            row.clicked.connect(
                lambda pp=p: (menu.close(), self._select_folder(pp)))
            row.removed.connect(
                lambda pp=p, a=act: self._remove_project(menu, a, pp))
            act.setDefaultWidget(row)
            menu.addAction(act)

        if sessions:
            _header("Open Projects")
            for p in sessions:
                _row(p)
        if recents:
            _header("Recent Projects")
            for p in recents:
                _row(p)

        return menu

    def _remove_project(self, menu, act, path):
        """✕ de una fila: quita la carpeta de recientes y sesiones."""
        from utils.recents import remove_recent
        from utils.sessions import remove_session
        remove_recent(path)
        remove_session(path)
        menu.removeAction(act)

    def _select_folder(self, path):
        self.set_folder(path)
        self.folder_changed.emit(self.repo_path)  # ya normalizado

    def _pick_folder(self):
        d = QFileDialog.getExistingDirectory(
            self, "Elegir carpeta de trabajo",
            os.path.expanduser("~/Desktop"))
        if d:
            self._select_folder(d)

    def _new_project(self):
        # El diálogo nativo de macOS permite crear la carpeta ahí mismo
        d = QFileDialog.getExistingDirectory(
            self, "New Project — elegir o crear carpeta",
            os.path.expanduser("~/Desktop"))
        if d:
            self._select_folder(d)

    def _clone_repo(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Clone Repository")
        dlg.setMinimumWidth(430)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(8)
        v.addWidget(QLabel("URL del repositorio:"))
        url_edit = QLineEdit()
        url_edit.setPlaceholderText("https://github.com/usuario/repo.git")
        v.addWidget(url_edit)
        v.addWidget(QLabel("Clonar dentro de:"))
        base = os.path.dirname(
            (self.repo_path or os.path.expanduser("~/Desktop")).rstrip("/"))
        dest_edit = QLineEdit(base)
        drow = QHBoxLayout()
        drow.addWidget(dest_edit, 1)
        btn_browse = QPushButton("…")
        btn_browse.setFixedWidth(32)
        btn_browse.clicked.connect(lambda: dest_edit.setText(
            QFileDialog.getExistingDirectory(
                dlg, "Carpeta destino") or dest_edit.text()))
        drow.addWidget(btn_browse)
        v.addLayout(drow)
        brow = QHBoxLayout()
        brow.addStretch(1)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(dlg.reject)
        btn_ok = QPushButton("Clonar")
        btn_ok.setObjectName("success")
        brow.addWidget(btn_cancel)
        brow.addWidget(btn_ok)
        v.addLayout(brow)

        def _do_clone():
            from utils.git import clone
            url = url_edit.text().strip()
            dest = os.path.expanduser(dest_edit.text().strip())
            if not url or not dest:
                return
            dlg.accept()
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                ok, res = clone(url, dest)
            finally:
                QApplication.restoreOverrideCursor()
            if ok:
                self._select_folder(res)
            else:
                QMessageBox.warning(
                    self, "Clone Repository",
                    f"No se pudo clonar:\n{res}")

        btn_ok.clicked.connect(_do_clone)
        url_edit.returnPressed.connect(_do_clone)
        dlg.exec()

    def _show_projects_popup(self):
        """Abre un diálogo con todos los proyectos previos y permite
        abrir una nueva instancia en cualquiera de ellos."""
        from utils.sessions import load_sessions
        from utils.recents import load_recents
        dlg = ProjectsDialog(self, self.repo_path, load_sessions(), load_recents())
        if dlg.exec() and dlg.selected_path:
            if dlg.property("open_here"):
                self._select_folder(dlg.selected_path)
            else:
                self.open_new_window.emit(dlg.selected_path)

    # ---- git ----
    def _refresh_git(self):
        if self.repo_path and is_repo(self.repo_path):
            branch = get_current_branch(self.repo_path)
            self.btn_branch.setText(branch or "detached")
            self.btn_branch.setEnabled(True)
            # Píldora con el color del carril de la rama en el grafo
            color = ""
            if branch:
                try:
                    color = GitUtils(self.repo_path).branch_color(branch)
                except Exception:
                    pass
            if color:
                self.btn_branch.setStyleSheet(
                    f"QPushButton{{background:{color}; color:#fff;"
                    "border-radius:12px; padding:5px 12px;"
                    "font-weight:bold;}"
                    f"QPushButton:hover{{background:{color};}}")
                chev = os.path.join(ICONOS_DIR, "flecha_abajo_w.svg")
                if os.path.exists(chev):
                    self.btn_branch.setIcon(QIcon(chev))
            else:
                self.btn_branch.setStyleSheet("")
                if os.path.exists(CHEVRON_SVG):
                    self.btn_branch.setIcon(QIcon(CHEVRON_SVG))
        else:
            # No es repo → el botón de rama pasa a ser "git init"
            self.btn_branch.setText("⎇  Initialize Git Project")
            self.btn_branch.setEnabled(True)
            self.btn_branch.setStyleSheet(
                "QPushButton{background:#2a2d33; color:#e8eaed;"
                "border-radius:12px; padding:5px 12px; font-weight:bold;}"
                "QPushButton:hover{background:#33373e;}")
            self.btn_branch.setIcon(QIcon())

    def _show_branch_menu(self):
        if not self.repo_path:
            return
        if not is_repo(self.repo_path):
            # el botón actúa como "git init" cuando no hay repo
            ok, out = GitUtils(self.repo_path).init()
            win = self.window()
            if hasattr(win, "statusBar"):
                win.statusBar().showMessage(
                    ("✔ " if ok else "✖ ") + (out or "git init")[:100], 5000)
            if ok:
                self.folder_changed.emit(self.repo_path)  # refrescar paneles
            return
        menu = QMenu(self)
        menu.setObjectName("branchMenu")
        a_new = QAction("＋  New Branch…", menu)
        a_new.triggered.connect(self._new_branch)
        menu.addAction(a_new)
        menu.addSeparator()
        # Ramas locales
        local, remote = list_branches(self.repo_path)
        cur = get_current_branch(self.repo_path)
        if local:
            head = menu.addAction("Local")
            head.setEnabled(False)
            colors = GitUtils(self.repo_path).branch_colors()
            for b in local:
                act = QWidgetAction(menu)
                row = _BranchRow(b, colors.get(b, "#9aa0aa"),
                                 current=(b == cur))
                row.setToolTip(f"checkout {b}")
                row.clicked.connect(
                    lambda br=b: (menu.close(),
                                  self.git_action.emit(f"checkout:{br}")))
                act.setDefaultWidget(row)
                menu.addAction(act)
        if remote:
            head = menu.addAction("Remote")
            head.setEnabled(False)
            for b in remote:
                act = QAction(f"☁  {b}", menu)
                act.setEnabled(False)
                menu.addAction(act)
        menu.exec(self.btn_branch.mapToGlobal(
            QPoint(0, self.btn_branch.height())))

    def _new_branch(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Nueva rama", "Nombre:")
        if ok and name.strip():
            self.git_action.emit(f"newbranch:{name.strip()}")


class ProcPopup(QDialog):
    """Popup tipo htop con los procesos corriendo en terminales (hijos
    del IDE): PID, usuario, CPU% y memoria con barritas, tiempo corriendo,
    comando y botón rojo para matarlo 1 a 1. Se refresca cada 2s.
    Se cierra con la ✕ de arriba a la derecha o Esc."""

    MONO = "font-family:'Menlo','SF Mono',monospace;"
    CARD = (
        "QFrame#procRow{background:#262b33;border:1px solid #2f3540;"
        "border-radius:6px;}"
        "QFrame#procRow:hover{background:#2d333d;border-color:#3d4552;}")

    def __init__(self, get_procs, parent=None):
        # Qt.Popup (y no Qt.Tool): se cierra solo al clickear afuera.
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setWindowTitle("Procesos")
        self.setObjectName("procPopup")
        # Ventana opaca y sin border-radius: con WA_TranslucentBackground
        # macOS componía el Qt.Tool semitransparente y se veía el fondo.
        self.setStyleSheet(
            "QDialog#procPopup{background:#1e2229;border:1px solid #343b46;}"
            "QDialog#procPopup QWidget{background:transparent;border:none;}")
        self._get_procs = get_procs
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(6)
        # ---- cabecera: título + stats + ✕ ----
        head = QHBoxLayout()
        head.setSpacing(8)
        ttl = QLabel("Procesos de terminales")
        ttl.setStyleSheet(
            "color:#e8eaed; font-weight:bold; font-size:12px;")
        head.addWidget(ttl)
        self._stats = QLabel()
        self._stats.setStyleSheet(
            f"color:#8e8e93; font-size:10px; {self.MONO}")
        head.addWidget(self._stats)
        head.addStretch(1)
        x = QPushButton("✕")
        x.setFixedSize(22, 22)
        x.setCursor(Qt.PointingHandCursor)
        x.setToolTip("Cerrar (Esc)")
        x.setStyleSheet(
            "QPushButton{background:transparent;color:#8e8e93;border:none;"
            "border-radius:4px;font-size:12px;font-weight:bold;}"
            "QPushButton:hover{background:#e5484d;color:#fff;}")
        x.clicked.connect(self.accept)
        head.addWidget(x)
        v.addLayout(head)
        # ---- encabezado de columnas ----
        cols = QHBoxLayout()
        cols.setContentsMargins(9, 0, 9, 0)
        cols.setSpacing(8)
        for text, w in (("PID", 52), ("USER", 60), ("CPU", 80),
                        ("MEM", 100), ("TIME", 64), ("COMMAND", 0)):
            lbl = QLabel(text)
            lbl.setStyleSheet(
                "color:#6e7480; font-size:9px; font-weight:bold;")
            if w:
                lbl.setFixedWidth(w)
            cols.addWidget(lbl, 0 if w else 1)
        cols.addSpacing(22)  # columna del botón kill
        v.addLayout(cols)
        # ---- filas ----
        self._rows = QVBoxLayout()
        self._rows.setSpacing(3)
        v.addLayout(self._rows)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(2000)
        self._refresh()

    def _cell(self, text, width, color="#d7dae0"):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{color}; font-size:11px; {self.MONO}")
        lbl.setFixedWidth(width)
        return lbl

    def _bar(self, value, color, width):
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(max(0, min(100, int(value))))
        bar.setTextVisible(False)
        bar.setFixedSize(width, 6)
        bar.setStyleSheet(
            "QProgressBar{background:#1a1d23;border:none;border-radius:3px;}"
            f"QProgressBar::chunk{{background:{color};border-radius:3px;}}")
        return bar

    def _clear_rows(self):
        while self._rows.count():
            it = self._rows.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                self._rows.removeItem(it.layout())

    def _refresh(self):
        procs = self._get_procs()
        total_mb = sum(p[1] for p in procs) / 1024
        self._stats.setText(
            f"  {len(procs)} proc  ·  {total_mb:.0f} MB")
        self._clear_rows()
        if not procs:
            empty = QLabel("No hay procesos corriendo")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color:#8e8e93; font-size:11px; padding:6px;")
            self._rows.addWidget(empty)
            return
        max_rss = max(p[1] for p in procs) or 1
        for pid, rss_kb, cpu, user, etime, cmd in procs:
            mb = rss_kb / 1024
            card = QFrame()
            card.setObjectName("procRow")
            card.setStyleSheet(self.CARD)
            row = QHBoxLayout(card)
            row.setContentsMargins(8, 4, 6, 4)
            row.setSpacing(8)
            row.addWidget(self._cell(str(pid), 52, "#8e8e93"))
            row.addWidget(self._cell(user[:10], 60, "#9aa3af"))
            # CPU: barrita + %
            cpu_color = ("#e5484d" if cpu >= 50 else
                         "#e8a13c" if cpu >= 15 else "#7ec97e")
            cw = QWidget()
            ch = QHBoxLayout(cw)
            ch.setContentsMargins(0, 0, 0, 0)
            ch.setSpacing(5)
            ch.addWidget(self._bar(cpu, cpu_color, 34))
            ch.addWidget(self._cell(f"{cpu:.0f}%", 38, cpu_color))
            ch.addStretch(1)
            cw.setFixedWidth(80)
            row.addWidget(cw)
            # MEM: barrita + valor (color por tamaño absoluto)
            mem_color = ("#4c9aff" if mb < 128 else
                         "#e8a13c" if mb < 512 else "#e5484d")
            mw = QWidget()
            mh = QHBoxLayout(mw)
            mh.setContentsMargins(0, 0, 0, 0)
            mh.setSpacing(5)
            mh.addWidget(self._bar(100 * rss_kb / max_rss, mem_color, 44))
            mem_lbl = self._cell(
                f"{mb/1024:.1f}G" if mb >= 1024 else f"{mb:.0f}M", 44)
            mh.addWidget(mem_lbl)
            mh.addStretch(1)
            mw.setFixedWidth(100)
            row.addWidget(mw)
            row.addWidget(self._cell(etime, 64, "#8e8e93"))
            short = cmd if len(cmd) <= 44 else cmd[:41] + "…"
            cmd_lbl = QLabel(short)
            cmd_lbl.setStyleSheet("color:#d7dae0; font-size:11px;")
            cmd_lbl.setToolTip(f"PID {pid}\n{cmd}")
            row.addWidget(cmd_lbl, 1)
            btn = QPushButton("■")
            btn.setFixedSize(22, 22)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(f"Matar proceso {pid}")
            btn.setStyleSheet(
                "QPushButton{background:#e5484d;color:#fff;border:none;"
                "border-radius:4px;font-size:10px;font-weight:bold;}"
                "QPushButton:hover{background:#ff5f5f;}")
            btn.clicked.connect(lambda _, p=pid: self._kill(p))
            row.addWidget(btn)
            self._rows.addWidget(card)

    def _kill(self, pid):
        subprocess.run(["kill", str(pid)], capture_output=True)
        self._refresh()


class BottomBar(QFrame):
    """Barra inferior de 30px, todo el ancho."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BottomBar")
        self.setFixedHeight(30)
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 2, 12, 2)
        h.addWidget(QLabel("Bottom bar (30px)"))
        h.addStretch(1)
        # RAM del IDE + procesos hijos (terminales, servers corriendo)
        self.lbl_ram = QLabel()
        self.lbl_ram.setStyleSheet("color:#8e8e93; font-size:11px;")
        self.lbl_ram.setToolTip(
            "RAM total: IDE + terminales y procesos abiertos\n"
            "Clic para ver y matar procesos 1 a 1")
        self.lbl_ram.setCursor(Qt.PointingHandCursor)
        h.addWidget(self.lbl_ram)
        self._ram_timer = QTimer(self)
        self._ram_timer.timeout.connect(self._update_ram)
        self._ram_timer.start(3000)
        self._update_ram()

    def _update_ram(self):
        mb = _process_tree_rss_mb()
        if mb >= 1024:
            self.lbl_ram.setText(f"🐏 {mb/1024:.1f} GB")
        else:
            self.lbl_ram.setText(f"🐏 {mb:.0f} MB")

    def mousePressEvent(self, e):
        """Clic en la barra → popup de procesos (si el clic fue sobre RAM)."""
        if self.lbl_ram.geometry().contains(e.position().toPoint()):
            self._show_proc_popup()
        super().mousePressEvent(e)

    def _child_processes(self):
        """Descendientes del IDE (excluyéndolo), ordenados por RSS desc:
        [(pid, rss_kb, cpu%, user, etime, cmd)]."""
        try:
            out = subprocess.run(
                ["ps", "-axo",
                 "pid=,ppid=,rss=,%cpu=,user=,etime=,command="],
                capture_output=True, text=True, timeout=5).stdout
        except Exception:
            return []
        children, info = {}, {}
        for line in out.splitlines():
            parts = line.split(None, 6)
            if len(parts) < 6:
                continue
            try:
                pid, ppid, r = int(parts[0]), int(parts[1]), int(parts[2])
                cpu = float(parts[3])
            except ValueError:
                continue
            info[pid] = (r, cpu, parts[4], parts[5],
                         parts[6] if len(parts) > 6 else "?")
            children.setdefault(ppid, []).append(pid)
        result, stack, seen = [], [os.getpid()], set()
        while stack:
            pid = stack.pop()
            if pid in seen or pid not in info:
                continue
            seen.add(pid)
            result.append((pid,) + info[pid])
            stack.extend(children.get(pid, []))
        me = os.getpid()
        result = [p for p in result if p[0] != me]
        result.sort(key=lambda p: p[1], reverse=True)
        return result

    def _show_proc_popup(self):
        dlg = ProcPopup(self._child_processes, self)
        dlg.adjustSize()
        pos = self.lbl_ram.mapToGlobal(QPoint(
            self.lbl_ram.width() - dlg.width(), -dlg.height() - 6))
        dlg.exec()


class SideZone(QSplitter):
    """Zona lateral (izquierda o derecha) con paneles independientes.

    Cada zona tiene su propio splitter vertical con paneles que se
    pueden mostrar/ocultar independientemente de la otra zona.
    """

    def __init__(self, side="left", parent=None):
        super().__init__(Qt.Vertical, parent)
        self.side = side
        self.setChildrenCollapsible(False)
        self.setHandleWidth(4)
        self.panels = []  # lista de Panel widgets
        self._panel_map = {}  # key → Panel

    def add_panel_widget(self, key, title, widget):
        """Agrega un Panel que contiene un widget personalizado."""
        p = Panel(title)
        lay = p.body.layout()
        if lay is None:
            from PySide6.QtWidgets import QVBoxLayout
            lay = QVBoxLayout(p.body)
            lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(widget)
        self.addWidget(p)
        self.panels.append(p)
        self._panel_map[key] = p
        self.setSizes([200] * len(self.panels))
        return p

    def toggle(self, key, show):
        p = self._panel_map.get(key)
        if p is None:
            return
        p.setVisible(show)
        if show:
            p.set_collapsed(False)

    def is_visible(self, key):
        p = self._panel_map.get(key)
        return p.isVisible() if p else False


class MainBody(QWidget):
    """Body del body: zona izq + centro + zona der + terminal flotante.

    - Zona izquierda: controlada por hotbar izquierda
    - Centro: editor (siempre visible)
    - Zona derecha: controlada por hotbar derecha
    - Terminal: flotante (overlay)
    Cada zona tiene sus propios paneles, independientes entre sí.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initial_sizes_done = False
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # Splitter horizontal principal: izq | centro | der
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(4)
        h.addWidget(self.main_splitter)

        # Zona izquierda
        self.left_zone = SideZone("left")
        self.main_splitter.addWidget(self.left_zone)

        # Centro: editor + panel de Diff (se intercambian en el mismo lugar)
        from UI.panels.editor_panel import EditorPanel
        from UI.panels.diff_panel import DiffPanel
        self.center = EditorPanel()
        self.diff_panel = DiffPanel()
        self.center_stack = QStackedWidget()
        self.center_stack.addWidget(self.center)
        self.center_stack.addWidget(self.diff_panel)
        self.main_splitter.addWidget(self.center_stack)

        # Zona derecha
        self.right_zone = SideZone("right")
        self.main_splitter.addWidget(self.right_zone)

        self.main_splitter.setSizes([260, 700, 260])

        # Panel de archivos en zona izquierda
        from UI.panels.files_panel import FilesPanel
        self.files_panel = FilesPanel()
        pf = self.left_zone.add_panel_widget(
            "files", "Project", self.files_panel)
        self._add_files_header_btns(pf, self.files_panel)

        # Panel de Changes (commit) en zona izquierda
        from UI.panels.changes_panel import ChangesPanel
        self.changes_panel = ChangesPanel()
        self.left_zone.add_panel_widget("p1", "Changes", self.changes_panel)
        self.left_zone.toggle("p1", False)
        self.changes_panel.diff_requested.connect(self._open_diff)
        self.changes_panel.committed.connect(self._on_committed)
        self.changes_panel.generate_requested.connect(self._generate_msg)
        # Panel de Diff ↔ Changes
        self.diff_panel.close_requested.connect(
            lambda: self.center_stack.setCurrentIndex(0))
        self.diff_panel.selection_changed.connect(self._diff_selection_changed)
        self.diff_panel.commit_requested.connect(
            self.changes_panel.commit_paths)

        # Panel de Stash (el bolsillo) en zona izquierda
        from UI.panels.stash_panel import StashPanel
        self.stash_panel = StashPanel()
        self.left_zone.add_panel_widget("p2", "Stash", self.stash_panel)
        self.left_zone.toggle("p2", False)
        self.stash_panel.stash_changed.connect(self.changes_panel.refresh)

        # Panel de chat IA en zona izquierda
        from UI.panels.chat_panel import ChatPanel
        self.chat_panel = ChatPanel()
        pc = self.left_zone.add_panel_widget("chat", "Chat IA", self.chat_panel)
        self._add_chat_header_ctrls(pc, self.chat_panel)
        self.left_zone.toggle("chat", False)

        # Panel Planner (workflows con agentes IA) en zona izquierda
        from UI.panels.planner_panel import PlannerPanel
        self.planner_panel = PlannerPanel()
        pp = self.left_zone.add_panel_widget(
            "planner", "Planner", self.planner_panel)
        pp.header.add_action("↻", "Refrescar", self.planner_panel.reload)
        pp.header.add_action("▤", "Log de ejecución",
                             self.planner_panel.toggle_log)
        self.left_zone.toggle("planner", False)

        # Panel de Git (ramas + grafo) en zona izquierda
        from UI.panels.git_panel import GitPanel
        self.git_panel = GitPanel()
        pg = self.left_zone.add_panel_widget("git", "Git", self.git_panel)
        pg.header.add_action("↻", "Refrescar", self.git_panel.refresh)
        self.left_zone.toggle("git", False)
        self.git_panel.branch_changed.connect(self._on_branch_changed)
        # El stash movió algo → refrescar grafo y lista de cambios
        self.stash_panel.stash_changed.connect(self.git_panel.refresh)

        # ---- Listener central del repo (listeners/git_listener.py) ----
        # Vigila la carpeta + .git y avisa a los componentes suscriptos
        # cuando cambia el status o la rama (incl. cambios externos).
        from listeners import GitListener
        self.git_listener = GitListener(self)
        for comp in (self.changes_panel.refresh,
                     self.git_panel.refresh,
                     self.stash_panel.refresh):
            self.git_listener.subscribe(comp)

        # Panel de archivos en zona derecha (independiente, oculto al inicio)
        self.files_panel_right = FilesPanel()
        pfr = self.right_zone.add_panel_widget(
            "files", "Project", self.files_panel_right)
        self._add_files_header_btns(pfr, self.files_panel_right)
        self.right_zone.toggle("files", False)

        # Paneles placeholder en zona derecha
        p1r = QLabel("Panel 2 (der)")
        p1r.setAlignment(Qt.AlignCenter)
        p1r.setStyleSheet("color:#666;")
        self.right_zone.add_panel_widget("p1", "Panel 2", p1r)
        self.right_zone.toggle("p1", False)
        p2r = QLabel("Panel 3 (der)")
        p2r.setAlignment(Qt.AlignCenter)
        p2r.setStyleSheet("color:#666;")
        self.right_zone.add_panel_widget("p2", "Panel 3", p2r)
        self.right_zone.toggle("p2", False)

        # Panel de chat IA en zona derecha
        self.chat_panel_right = ChatPanel()
        pcr = self.right_zone.add_panel_widget(
            "chat", "Chat IA", self.chat_panel_right)
        self._add_chat_header_ctrls(pcr, self.chat_panel_right)
        self.right_zone.toggle("chat", False)

        # Panel Planner en zona derecha
        self.planner_panel_right = PlannerPanel()
        ppr = self.right_zone.add_panel_widget(
            "planner", "Planner", self.planner_panel_right)
        ppr.header.add_action("↻", "Refrescar", self.planner_panel_right.reload)
        ppr.header.add_action("▤", "Log de ejecución",
                              self.planner_panel_right.toggle_log)
        self.right_zone.toggle("planner", False)

        # Los planners ejecutan pasos con el provider/modelo de su chat
        self.planner_panel.provider_fn = self.chat_panel._current_provider
        self.planner_panel_right.provider_fn = (
            self.chat_panel_right._current_provider)
        # Chip de modelo en el header del Planner (mismo combo del chat)
        self.planner_panel.chat = self.chat_panel
        self.planner_panel_right.chat = self.chat_panel_right
        pp.header.add_right(self.planner_panel.model_btn)
        ppr.header.add_right(self.planner_panel_right.model_btn)
        self.planner_panel._sync_model_chip()
        self.planner_panel_right._sync_model_chip()
        # La IA del planner toca archivos → refrescar árboles
        self.planner_panel.files_changed.connect(self.files_panel.refresh)
        self.planner_panel.files_changed.connect(
            self.files_panel_right.refresh)
        self.planner_panel_right.files_changed.connect(
            self.files_panel.refresh)
        self.planner_panel_right.files_changed.connect(
            self.files_panel_right.refresh)
        # Chips de archivos del planner → abrir en el editor (path absoluto)
        self.planner_panel.open_file_requested.connect(
            self.center.open_file)
        self.planner_panel_right.open_file_requested.connect(
            self.center.open_file)
        # Un planner que escribe en planner/ → el gemelo recarga en vivo
        self.planner_panel.mutated.connect(self.planner_panel_right.reload)
        self.planner_panel_right.mutated.connect(self.planner_panel.reload)

        # Terminal flotante (con pestañas)
        self.terminal = TerminalOverlay(self)
        self.terminal.hide()

        # Conectar play de ambos paneles → terminal
        self.files_panel.run_requested.connect(self._run_file)
        self.files_panel_right.run_requested.connect(self._run_file)
        # Conectar save_run_config de ambos paneles
        self.files_panel.save_run_config.connect(self._save_run_config)
        self.files_panel_right.save_run_config.connect(self._save_run_config)
        # Conectar files_changed del chat → refrescar árboles
        self.chat_panel.files_changed.connect(self.files_panel.refresh)
        self.chat_panel.files_changed.connect(self.files_panel_right.refresh)
        self.chat_panel_right.files_changed.connect(self.files_panel.refresh)
        self.chat_panel_right.files_changed.connect(
            self.files_panel_right.refresh)
        # Clic en un archivo tocado → abrir en el editor
        self.chat_panel.open_file_requested.connect(self._open_from_chat)
        self.chat_panel_right.open_file_requested.connect(
            self._open_from_chat)
        # Auto-abrir archivos que la IA toca → editor + scroll a la línea
        self.chat_panel.file_auto_open.connect(self._auto_open_from_chat)
        self.chat_panel_right.file_auto_open.connect(
            self._auto_open_from_chat)
        # Review inline de cambios de la IA (diff verde/rojo en el editor)
        self.chat_panel.file_review.connect(self._review_from_chat)
        self.chat_panel_right.file_review.connect(self._review_from_chat)
        # Card ✓/✗ → salir del modo review en el editor
        self.chat_panel.file_resolved.connect(self._end_review)
        self.chat_panel_right.file_resolved.connect(self._end_review)
        # Review bar del editor → marcar la card correspondiente
        self.center.review_accepted.connect(
            lambda p: self._resolve_from_editor(p, True))
        self.center.review_rejected.connect(
            lambda p: self._resolve_from_editor(p, False))

    def _on_branch_changed(self, branch):
        """Checkout desde el panel de Git → refrescar la top bar."""
        self.changes_panel.refresh()
        p = self.parent()
        while p and not hasattr(p, "top_bar"):
            p = p.parent()
        if p and hasattr(p, "top_bar"):
            p.top_bar.set_folder(p.top_bar.repo_path)

    def _open_diff(self, rel_path):
        """Abre el panel de Diff para un archivo del panel de Changes."""
        if not self.changes_panel.utils:
            return
        self.diff_panel.show_file(self.changes_panel.utils, rel_path)
        self.center_stack.setCurrentIndex(1)

    def _diff_selection_changed(self, path, included, total):
        """El diff cambió la selección de líneas → sincronizar la lista."""
        self.changes_panel.set_file_selection(
            path, self.diff_panel.canvas.selected_lines().keys())

    def _on_committed(self, push_after):
        """Tras un commit: refrescar top bar + git, y push si corresponde."""
        win = self.window()
        win.top_bar._refresh_git()
        self.git_panel.refresh()
        if push_after and win.top_bar.repo_path:
            ok, out = push(win.top_bar.repo_path)
            win.statusBar().showMessage(
                ("✔ " if ok else "✖ ") + out.replace("\n", " ")[:120], 5000)

    def _generate_msg(self):
        self.window().statusBar().showMessage(
            "✨ Generate: pendiente de conectar a la IA", 3000)

    def _add_chat_header_ctrls(self, panel, chat):
        """Controles de modelo en la fila del título 'Chat IA', a la derecha.
        (El combo de modelo vive en la fila inferior del chat.)"""
        for b in (chat.btn_pick, chat.btn_refresh):
            panel.header.add_right(b)

    def _add_files_header_btns(self, panel, files_panel):
        """Botones ＋ ↻ ⇅ ✕ en el header del panel, junto al título."""
        panel.header.add_action("＋", "Nuevo archivo", files_panel._new_file)
        panel.header.add_action("↻", "Refrescar", files_panel.refresh)
        panel.header.add_action("⇅", "Colapsar todo",
                                files_panel._collapse_all)
        panel.header.add_action(
            "✕", "Cerrar panel", lambda: panel.setVisible(False))

    def showEvent(self, e):
        super().showEvent(e)
        if not self._initial_sizes_done:
            self._initial_sizes_done = True
            QTimer.singleShot(0, self._apply_initial_widths)

    def _apply_initial_widths(self):
        """Panel de archivos (izq) arranca con 30% del ancho de la ventana."""
        sp = self.main_splitter
        total = sum(sp.sizes()) or sp.width()
        if total <= 50:
            QTimer.singleShot(50, self._apply_initial_widths)
            return
        left = max(int(total * 0.30), 240)
        sizes = sp.sizes()
        right = sizes[2] if len(sizes) > 2 else 0
        center = max(total - left - right, 300)
        sp.setSizes([left, center, right])

    def ensure_right_chat_width(self):
        """Al abrir el chat derecho, le garantiza ≥40% del ancho total."""
        sp = self.main_splitter
        sizes = sp.sizes()
        if len(sizes) < 3 or sum(sizes) <= 0:
            return
        left, center, right = sizes
        target = int(sum(sizes) * 0.4)
        if right >= target:
            return
        need = target - right
        take_l = min(left // 2, need // 2)
        take_c = need - take_l
        if take_c > center:
            take_c, take_l = center, need - center
        sp.setSizes([left - take_l, center - take_c, right + need])

    def ensure_git_width(self):
        """Al abrir el panel de Git, la zona izquierda ocupa 75% del ancho."""
        sp = self.main_splitter
        sizes = sp.sizes()
        if len(sizes) < 3 or sum(sizes) <= 0:
            return
        total = sum(sizes)
        target = int(total * 0.75)
        if sizes[0] >= target:
            return
        need = target - sizes[0]
        take_c = min(sizes[1], need)
        take_r = need - take_c
        if take_r > sizes[2]:
            take_r = sizes[2]
            take_c = need - take_r
        sp.setSizes([sizes[0] + need, sizes[1] - take_c, sizes[2] - take_r])

    def ensure_planner_width(self):
        """Al abrir el Planner (izq), su zona ocupa ≥70% del ancho total."""
        self._ensure_zone_width(0)

    def ensure_planner_width_right(self):
        """Al abrir el Planner (der), su zona ocupa ≥70% del ancho total."""
        self._ensure_zone_width(2)

    def _ensure_zone_width(self, idx):
        """Garantiza que la zona idx del splitter ocupe ≥70% del ancho."""
        sp = self.main_splitter
        sizes = sp.sizes()
        if len(sizes) < 3 or sum(sizes) <= 0:
            return
        target = int(sum(sizes) * 0.7)
        if sizes[idx] >= target:
            return
        need = target - sizes[idx]
        new_sizes = list(sizes)
        new_sizes[idx] = target
        for i in (0, 1, 2):
            if i == idx:
                continue
            take = min(new_sizes[i], need)
            new_sizes[i] -= take
            need -= take
            if need <= 0:
                break
        sp.setSizes(new_sizes)

    def _open_from_chat(self, rel_path):
        """Abre en el editor un archivo tocado por la IA (path relativo)."""
        panel = self.sender()
        root = getattr(getattr(panel, "tools", None), "root", None)
        full = os.path.join(root, rel_path) if root else rel_path
        if os.path.exists(full):
            self.center.open_file(os.path.realpath(full))

    def _auto_open_from_chat(self, rel_path, line):
        """Auto-abre el archivo que la IA acaba de tocar y scrollea a `line`."""
        panel = self.sender()
        root = getattr(getattr(panel, "tools", None), "root", None)
        full = os.path.join(root, rel_path) if root else rel_path
        if os.path.exists(full):
            self.center.open_file(os.path.realpath(full),
                                  goto_line=int(line or 1))

    def _review_from_chat(self, rel_path, before):
        """Abre el archivo tocado por la IA en modo review (diff inline)."""
        panel = self.sender()
        root = getattr(getattr(panel, "tools", None), "root", None)
        full = os.path.join(root, rel_path) if root else rel_path
        if os.path.exists(full):
            self.center.start_review(os.path.realpath(full), before)

    def _resolve_from_editor(self, full_path, accepted):
        """La review bar del editor resolvió un archivo → marca la card."""
        for panel in (self.chat_panel, self.chat_panel_right):
            root = getattr(getattr(panel, "tools", None), "root", None)
            if not root:
                continue
            rel = os.path.relpath(full_path, os.path.realpath(root))
            if panel.resolve_from_editor(rel, accepted):
                return

    def _end_review(self, rel_path, _accepted):
        """La card del chat resolvió el archivo → salir de review en editor."""
        panel = self.sender()
        root = getattr(getattr(panel, "tools", None), "root", None)
        full = os.path.join(root, rel_path) if root else rel_path
        full = os.path.realpath(full)
        if os.path.exists(full):
            self.center.end_review(full)
        else:
            self.center.close_path(full)

    def _run_file(self, path):
        """Ejecuta un archivo .py/.js/.java en la terminal flotante."""
        ext = os.path.splitext(path)[1].lower()
        if ext == ".py":
            runner = "python3"
        elif ext == ".js":
            runner = "node"
        elif ext == ".java":
            runner = "java"
        else:
            return
        fname = os.path.basename(path)
        file_dir = os.path.dirname(path)
        cmd = f"{runner} {shlex.quote(fname)}"
        self._run_command(cmd, file_dir, header=f"cd {file_dir} && {cmd}")

    def _run_command(self, cmd, cwd, open_browser=False, header=None,
                     browser=""):
        """Ejecuta un comando en una pestaña nueva de la terminal.

        Si open_browser y la salida muestra una URL http://localhost:…,
        abre el navegador automáticamente (una sola vez por ejecución).
        """
        self.toggle_terminal(True)
        self._open_browser = open_browser
        self._browser_name = browser or ""
        self._browser_opened = False
        tab = self.terminal.new_tab(
            cwd=cwd, run_cmd=header or cmd,
            on_output=self._on_tab_output,
            on_fin=lambda code: self._on_tab_finished(code))
        # Avisar al top_bar que hay un run corriendo
        p = self.parent()
        while p and not hasattr(p, "top_bar"):
            p = p.parent()
        if p and hasattr(p, "top_bar"):
            p.top_bar.set_run_running(True)

    def _on_tab_output(self, text):
        # Auto-abrir navegador si la salida muestra una URL local
        if getattr(self, "_open_browser", False) and not getattr(
                self, "_browser_opened", True):
            m = re.search(r"https?://(localhost|127\.0\.0\.1):\d+\S*", text)
            if m:
                self._browser_opened = True
                url = m.group(0)
                name = getattr(self, "_browser_name", "")
                if name and "default" not in name.lower():
                    subprocess.Popen(["open", "-a", name, url])
                else:
                    from PySide6.QtGui import QDesktopServices
                    from PySide6.QtCore import QUrl
                    QDesktopServices.openUrl(QUrl(url))
                self.terminal.current_tab().out.appendPlainText(
                    f"🌐 Navegador abierto: {name or 'sistema'}")

    def _stop_proc(self):
        self.terminal.stop_current()

    def _on_tab_finished(self, code):
        # Avisar al top_bar para desactivar el botón stop
        p = self.parent()
        while p and not hasattr(p, "top_bar"):
            p = p.parent()
        if p and hasattr(p, "top_bar"):
            p.top_bar.set_run_running(False)

    def _save_run_config(self, path):
        """Guarda el archivo como run config del proyecto y lo ejecuta."""
        # El project dir se obtiene del top bar via la ventana principal
        project = ""
        p = self.parent()
        while p and not hasattr(p, "top_bar"):
            p = p.parent()
        if p and hasattr(p, "top_bar"):
            project = p.top_bar.repo_path
        if not project:
            return
        from utils.run_configs import add_config
        name = os.path.splitext(os.path.basename(path))[0]
        add_config(project, name, path)
        # Recargar el menú del top bar
        if p and hasattr(p, "top_bar"):
            p.top_bar.load_run_configs()
            p.top_bar._select_run_cfg(name)
        # Ejecutar el archivo
        self._run_file(path)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_terminal()

    def _place_terminal(self):
        self.terminal.setGeometry(
            8, self.height() - 300 - 8, self.width() - 16, 300)

    def toggle_terminal(self, show=None):
        if show is None:
            show = not self.terminal.isVisible()
        if show:
            if self.terminal.tabs.count() == 0:
                root = self.files_panel.root_path or None
                self.terminal.new_tab(cwd=root)
            self._place_terminal()
            self.terminal.show()
            self.terminal.raise_()
        else:
            self.terminal.hide()

    def set_root(self, path):
        """Actualiza ambos paneles de archivos y chat con la nueva carpeta."""
        self.files_panel.set_root(path)
        self.files_panel_right.set_root(path)
        self.chat_panel.set_repo(path)
        self.chat_panel_right.set_repo(path)
        self.git_panel.set_repo(path)
        self.changes_panel.set_repo(path)
        self.stash_panel.set_repo(path)
        self.planner_panel.set_repo(path)
        self.planner_panel_right.set_repo(path)
        if hasattr(self, "git_listener"):
            self.git_listener.set_repo(path)


class UIMainWindow(QMainWindow):
    """Ventana principal del nuevo layout."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("NG-Studio")
        self.resize(1400, 860)
        # Icono de la ventana
        icon_path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "iconos", "app.svg")
        if os.path.exists(icon_path):
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        # Historial de navegación (archivos abiertos)
        self._nav_back = []
        self._nav_fwd = []
        self._nav_current = None
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        # Top bar (50px, todo el ancho)
        self.top_bar = TopBar()
        root.addWidget(self.top_bar)
        # Fila central: hotbar izq + body + hotbar der
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        _ia_icon = os.path.join(ICONOS_DIR, "ia.svg")
        _folder_icon = os.path.join(ICONOS_DIR, "carpeta_w.svg")
        self.hotbar_left = HotBar(
            side="left",
            buttons=(
                ("files", "", "Panel de archivos", _folder_icon),
                ("p1", "", "Changes — commit",
                 os.path.join(ICONOS_DIR, "commit.svg")),
                ("p2", "", "Stash — el bolsillo",
                 os.path.join(ICONOS_DIR, "stash.svg")),
                ("chat", "IA", "Panel 4 — Chat IA (izq)", _ia_icon),
                ("planner", "", "Planner — workflows con agentes IA",
                 os.path.join(ICONOS_DIR, "planner.svg")),
                ("git", "", "Ramas git — pull/push/checkout",
                 os.path.join(ICONOS_DIR, "git_branch.svg")),
                ("term", "", "Terminal (pestañas)",
                 os.path.join(ICONOS_DIR, "terminal_w.svg")),
            ),
            checked={"files"},
            pinned_bottom=("git", "term"))
        self.hotbar_right = HotBar(
            side="right",
            buttons=(
                ("files", "", "Panel de archivos", _folder_icon),
                ("p1", "2", "Panel 2 (der)", None),
                ("p2", "3", "Panel 3 (der)", None),
                ("chat", "4", "Panel 4 — Chat IA (der)", _ia_icon),
                ("planner", "5", "Planner (der)",
                 os.path.join(ICONOS_DIR, "planner.svg")),
                ("term", "⌨", "Terminal (flotante)", None),
            ),
            checked=set())
        self.body = MainBody()
        row.addWidget(self.hotbar_left)
        row.addWidget(self.body, 1)
        row.addWidget(self.hotbar_right)
        root.addLayout(row, 1)
        # Bottom bar (30px, todo el ancho)
        self.bottom_bar = BottomBar()
        root.addWidget(self.bottom_bar)
        # Hotbar izquierda → zona izquierda (independiente)
        self.hotbar_left.btns["files"].toggled.connect(
            lambda on: self.body.left_zone.toggle("files", on))
        self.hotbar_left.btns["p1"].toggled.connect(
            lambda on: self.body.left_zone.toggle("p1", on))
        self.hotbar_left.btns["p2"].toggled.connect(
            lambda on: self.body.left_zone.toggle("p2", on))
        self.hotbar_left.btns["chat"].toggled.connect(
            lambda on: self.body.left_zone.toggle("chat", on))
        self.hotbar_left.btns["planner"].toggled.connect(
            lambda on: (self.body.left_zone.toggle("planner", on),
                        QTimer.singleShot(0, self.body.ensure_planner_width)
                        if on else None))
        self.hotbar_left.btns["term"].toggled.connect(
            lambda on: self.body.toggle_terminal(on))
        # Git de la hotbar → panel de Git (ramas + grafo)
        self.hotbar_left.btns["git"].toggled.connect(
            lambda on: (self.body.left_zone.toggle("git", on),
                        QTimer.singleShot(0, self.body.ensure_git_width)
                        if on else None))
        # Hotbar derecha → zona derecha (independiente)
        self.hotbar_right.btns["files"].toggled.connect(
            lambda on: self.body.right_zone.toggle("files", on))
        self.hotbar_right.btns["p1"].toggled.connect(
            lambda on: self.body.right_zone.toggle("p1", on))
        self.hotbar_right.btns["p2"].toggled.connect(
            lambda on: self.body.right_zone.toggle("p2", on))
        self.hotbar_right.btns["chat"].toggled.connect(
            lambda on: (self.body.right_zone.toggle("chat", on),
                        QTimer.singleShot(0, self.body.ensure_right_chat_width)
                        if on else None))
        self.hotbar_right.btns["planner"].toggled.connect(
            lambda on: (self.body.right_zone.toggle("planner", on),
                        QTimer.singleShot(0, self.body.ensure_planner_width_right)
                        if on else None))
        self.hotbar_right.btns["term"].toggled.connect(
            lambda on: self.body.toggle_terminal(on))
        # Top bar → acciones
        self.top_bar.folder_changed.connect(self._on_folder_changed)
        self.top_bar.navigate.connect(self._on_navigate)
        self.top_bar.git_action.connect(self._on_git_action)
        self.top_bar.run_requested.connect(self._on_run_requested)
        self.top_bar.stop_requested.connect(self._on_stop_requested)
        # Checkout rechazado desde el panel de Git → popup de stash
        self.body.git_panel.checkout_failed.connect(self._on_checkout_failed)
        # El listener central avisa si cambia la rama (incl. externo) →
        # actualizar la píldora de la top bar
        self.body.git_listener.branch_changed.connect(
            lambda _b: self.top_bar._refresh_git())
        self.top_bar.edit_configs_requested.connect(self._open_run_configs)
        self.top_bar.open_new_window.connect(self._open_new_window)
        self.top_bar.settings_requested.connect(self._show_settings_menu)
        # Panel de archivos sigue a la carpeta de la top bar
        self.body.files_panel.file_activated.connect(self._on_file_activated)
        self.body.files_panel_right.file_activated.connect(self._on_file_activated)
        # Restaurar última carpeta usada (de recents; o ~/Desktop si no hay)
        from utils.sessions import add_session
        from utils.recents import load_recents
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        recents = load_recents()
        start_dir = (recents[0] if recents else
                     desktop if os.path.isdir(desktop)
                     else os.path.expanduser("~"))
        self.top_bar.set_folder(start_dir)
        self.body.set_root(start_dir)
        add_session(start_dir)
        # Matar shells de la terminal al cerrar
        app = QApplication.instance()
        app.aboutToQuit.connect(self.body.terminal.kill_all)

    # ---- navegación atrás/adelante ----
    def push_history(self, location):
        """Registra una ubicación (ej: archivo abierto) en el historial."""
        if location == self._nav_current:
            return
        if self._nav_current is not None:
            self._nav_back.append(self._nav_current)
            self._nav_fwd.clear()
        self._nav_current = location
        self._update_nav_btns()

    def _on_navigate(self, direction):
        if direction == "back" and self._nav_back:
            self._nav_fwd.append(self._nav_current)
            self._nav_current = self._nav_back.pop()
        elif direction == "forward" and self._nav_fwd:
            self._nav_back.append(self._nav_current)
            self._nav_current = self._nav_fwd.pop()
        self._update_nav_btns()
        self.statusBar().showMessage(f"Ubicación: {self._nav_current}", 2500)

    def _update_nav_btns(self):
        self.top_bar.btn_back.setEnabled(bool(self._nav_back))
        self.top_bar.btn_fwd.setEnabled(bool(self._nav_fwd))

    # ---- carpeta ----
    def _on_folder_changed(self, path):
        from utils.sessions import add_session
        self.body.set_root(path)
        add_session(path)
        self.statusBar().showMessage(f"Carpeta: {path}", 3000)

    def closeEvent(self, e):
        """Al cerrar esta ventana su carpeta deja de ser 'Open Project'.

        (Las sesiones listan solo instancias vivas; la carpeta queda en
        recents para restaurarla al próximo arranque.)
        """
        from utils.sessions import remove_session
        if self.top_bar.repo_path:
            remove_session(self.top_bar.repo_path)
        super().closeEvent(e)

    def _open_new_window(self, path):
        """Abre una nueva instancia del IDE en otra carpeta."""
        from utils.sessions import add_session
        add_session(path)
        w = UIMainWindow()
        w.top_bar.set_folder(path)
        w.body.set_root(path)
        w.show()
        # Mantener referencia para que no la recoja el GC
        if not hasattr(QApplication.instance(), "_windows"):
            QApplication.instance()._windows = []
        QApplication.instance()._windows.append(w)

    def _show_settings_menu(self):
        """Engranaje de la top bar → menú de opciones."""
        m = QMenu(self)
        m.setObjectName("runMenu")
        a_ai = QAction("Preferencias de IA…", m)
        a_ai.triggered.connect(self._open_ai_prefs)
        m.addAction(a_ai)
        a_st = QAction("Settings / Atajos…", m)
        a_st.triggered.connect(self._open_settings)
        m.addAction(a_st)
        b = self.top_bar.btn_settings
        m.exec(b.mapToGlobal(QPoint(0, b.height())))

    def _open_ai_prefs(self):
        """Preferencias de IA (el mismo diálogo de 🔧 del chat)."""
        body = self.body
        panel = (body.chat_panel_right
                 if body.right_zone.is_visible("chat") else body.chat_panel)
        panel._open_prefs()

    def _open_settings(self):
        """Abre el diálogo de Settings con la pestaña de shortcuts."""
        from UI.panels.settings_panel import SettingsDialog
        dlg = SettingsDialog(self)
        if dlg.exec():
            # Recargar shortcuts en el editor
            self.body.center.reload_shortcuts()
            self.statusBar().showMessage("Atajos guardados", 3000)

    # ---- archivos ----
    def _on_file_activated(self, path):
        self.push_history(path)
        self.body.center.open_file(path)
        self.statusBar().showMessage(f"Abierto: {os.path.basename(path)}", 3000)

    # ---- git ----
    def _is_dirty_conflict(self, out):
        out = (out or "").lower()
        return ("would be overwritten by checkout" in out
                or "untracked working tree files" in out
                or "please commit your changes" in out)

    def _try_checkout(self, repo, branch):
        """Checkout; si pisaría cambios locales, ofrece stash en un popup."""
        ok, out = checkout(repo, branch)
        if ok or not self._is_dirty_conflict(out):
            return ok, out
        files = [l.strip() for l in (out or "").splitlines()
                 if l.startswith("\t") and l.strip()]
        mb = QMessageBox(self)
        mb.setWindowTitle("Cambios sin commitear")
        mb.setIcon(QMessageBox.Warning)
        mb.setText(f"Estos archivos se pueden pisar al pasarte a {branch}:")
        mb.setInformativeText(
            "\n".join(f"•  {f}" for f in files[:12])
            + ("\n…" if len(files) > 12 else "")
            + "\n\n¿Querés guardarlos en el stash (el bolsillo)?")
        b_stash = mb.addButton("📥 Stash y cambiar de rama",
                               QMessageBox.AcceptRole)
        b_commit = mb.addButton("Commit…", QMessageBox.ActionRole)
        mb.addButton("Cancelar", QMessageBox.RejectRole)
        mb.exec()
        clicked = mb.clickedButton()
        if clicked is b_stash:
            g = GitUtils(repo)
            ok2, out2 = g.stash_push()
            if not ok2:
                return False, out2
            self.body.stash_panel.refresh()
            self.body.changes_panel.refresh()
            return checkout(repo, branch)
        if clicked.text() == "Commit…":
            self.hotbar_left.btns["p1"].setChecked(True)
        return False, out

    def _on_checkout_failed(self, branch):
        """Checkout desde el panel de Git que git rechazó → popup de stash."""
        repo = self.top_bar.repo_path
        if repo:
            self._try_checkout(repo, branch)
        self.body.git_panel.refresh()
        self.top_bar._refresh_git()

    def _on_git_action(self, action):
        repo = self.top_bar.repo_path
        if not repo:
            return
        if action == "pull":
            ok, out = pull(repo)
        elif action == "push":
            ok, out = push(repo)
        elif action == "commit":
            self.hotbar_left.btns["p1"].setChecked(True)
            self.statusBar().showMessage("Panel de Changes", 2500)
            return
        elif action.startswith("newbranch:"):
            ok, out = create_branch(repo, action.split(":", 1)[1])
        elif action.startswith("checkout:"):
            ok, out = self._try_checkout(repo, action.split(":", 1)[1])
        else:
            return
        self.statusBar().showMessage(
            ("✔ " if ok else "✖ ") + out.replace("\n", " ")[:120], 5000)
        self.top_bar._refresh_git()

    # ---- run configurations ----
    def _on_run_requested(self, name):
        if name == "(current file)":
            # Ejecutar el archivo de la tab actual del editor
            tab = self.body.center.tabs.currentWidget()
            if tab and hasattr(tab, "path"):
                self.body._run_file(tab.path)
                self.top_bar.set_run_running(True)
            return
        # Buscar la config seleccionada (dict con type/path/script/command)
        from utils.run_configs import get_config, build_command
        cfg = get_config(self.top_bar.repo_path, name)
        if not cfg:
            self.statusBar().showMessage(f"⚠ Config '{name}' no encontrada", 3000)
            return
        project = self.top_bar.repo_path
        cmd = build_command(cfg, project)
        if not cmd:
            self.statusBar().showMessage(
                f"⚠ Config '{name}' sin comando (revisá el formulario)", 3000)
            return
        self.body._run_command(
            cmd, project, open_browser=bool(cfg.get("open_browser")),
            browser=cfg.get("browser", ""))
        self.top_bar.set_run_running(True)

    def _open_run_configs(self):
        """Abre el diálogo Run/Debug Configurations estilo JetBrains."""
        from UI.panels.run_configs_dialog import RunConfigsDialog
        project = self.top_bar.repo_path or os.getcwd()
        dlg = RunConfigsDialog(project, self.top_bar._run_current or "", self)
        if dlg.exec():
            self.top_bar.load_run_configs()
            if dlg.result_run and dlg.result_config:
                self.top_bar._select_run_cfg(dlg.result_config["name"])
                self._on_run_requested(dlg.result_config["name"])

    def _on_stop_requested(self):
        self.body._stop_proc()
        self.top_bar.set_run_running(False)
        self.statusBar().showMessage("⏹ Detenido", 3000)


_SEEN_ERRORS = set()


def _excepthook(exc_type, exc, tb):
    """Red de seguridad global: ninguna excepción suelta puede crashear
    ni spammear la app — se loguea a ng-studio/crash.log, se muestra en
    la status bar, y el mismo error solo se imprime una vez."""
    import traceback
    try:
        log = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "ng-studio", "crash.log")
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write("".join(traceback.format_exception(exc_type, exc, tb))
                    + "\n")
    except OSError:
        pass
    last = traceback.extract_tb(tb)[-1] if tb else None
    key = (exc_type.__name__, str(exc)[:120],
           (last.filename, last.lineno) if last else None)
    if key in _SEEN_ERRORS:
        return                      # mismo error repetido → silencio
    _SEEN_ERRORS.add(key)
    sys.__excepthook__(exc_type, exc, tb)   # una vez a consola (debug)
    try:
        w = QApplication.activeWindow()
        if w is not None and hasattr(w, "statusBar"):
            w.statusBar().showMessage(
                f"⚠ {exc_type.__name__}: {exc}", 8000)
    except Exception:
        pass


def _splash_font(pref):
    """Primera familia 'de diseñador' disponible en el sistema; si no, default."""
    from PySide6.QtGui import QFontDatabase
    fams = set(QFontDatabase.families())
    for fam in pref:
        if fam in fams:
            return fam
    return QFont().family()


def _splash_pixmap():
    """Splash de inicio: arte Thor generado por IA (splash/ng-studio-logo.png);
    si falta el PNG, cae a la escena SVG dorada pintada a mano."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hero = os.path.join(root, "splash", "ng-studio-logo.png")
    if os.path.exists(hero):
        img = QImage(hero)
        if not img.isNull():
            pm = QPixmap.fromImage(img.scaled(
                540, 360, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
            if pm.size() != QSize(540, 360):
                pm = pm.copy((pm.width() - 540) // 2,
                             (pm.height() - 360) // 2, 540, 360)
            return pm

    pm = QPixmap(520, 360)
    pm.fill(QColor("#0a0a0c"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    gold = QColor("#d4af37")
    design = _splash_font(("Futura", "Avenir Next", "Optima", "Gill Sans"))
    serif = _splash_font(("Didot", "Hoefler Text", "Baskerville", "Optima"))

    # Marco dorado tenue
    p.setPen(QPen(QColor(212, 175, 55, 60), 1))
    p.drawRect(pm.rect().adjusted(1, 1, -2, -2))

    # Emblema Thor desde el SVG (Thor en la roca + anillo de rayos)
    logo_path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "splash", "ng-logo.svg")
    if os.path.exists(logo_path):
        from PySide6.QtSvg import QSvgRenderer
        QSvgRenderer(logo_path).render(p, QRectF(100, 26, 320, 160))
    else:  # fallback pintado si falta el SVG
        f = QFont(serif)
        f.setBold(True)
        f.setPixelSize(96)
        p.setFont(f)
        p.setPen(gold)
        p.drawText(QRectF(0, 40, 520, 130), Qt.AlignCenter, "NG")

    # "NG Studio" en tipografía de diseñador, tracking amplio
    f = QFont(design)
    f.setPixelSize(30)
    f.setLetterSpacing(QFont.PercentageSpacing, 165)
    p.setFont(f)
    p.setPen(gold)
    p.drawText(QRectF(0, 214, 520, 42), Qt.AlignCenter, "NG Studio")

    # Firma en serif itálica (estilo editorial)
    f = QFont(serif)
    f.setItalic(True)
    f.setPixelSize(14)
    f.setLetterSpacing(QFont.PercentageSpacing, 110)
    p.setFont(f)
    p.setPen(QColor(212, 175, 55, 170))
    p.drawText(QRectF(0, 318, 520, 22), Qt.AlignCenter,
               "Design by Nicolas Grossi")
    p.end()
    return pm


def _play_startup_sound():
    """Chime de inicio: splash/sonido.mp3 (o chime.aiff) o sonido del sistema."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for path in (os.path.join(root, "splash", "sonido.mp3"),
                 os.path.join(root, "splash", "chime.aiff"),
                 "/System/Library/Sounds/Glass.aiff",
                 "/System/Library/Sounds/Ping.aiff"):
        if os.path.exists(path):
            try:
                subprocess.Popen(["afplay", "-v", "0.55", path],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            except Exception:
                pass
            return


def main():
    sys.excepthook = _excepthook
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    # Icono de la app
    from PySide6.QtGui import QIcon
    icon_path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "iconos", "app.svg")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    # Splash: negro con dorado, sobre la ventana principal
    if SHOW_SPLASH:
        _play_startup_sound()
        splash = QSplashScreen(_splash_pixmap())
        splash.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        splash.show()
        app.processEvents()
    w = UIMainWindow()
    w.show()
    if SHOW_SPLASH:
        QTimer.singleShot(1500, lambda: splash.finish(w))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
