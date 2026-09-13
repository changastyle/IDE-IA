# -*- coding: utf-8 -*-
"""Panel Planner: AI Autonomous Workflow Planner.

Carriles horizontales con tareas secuenciales ejecutadas por agentes IA.
Diseño de referencia: workflow_planner_mockup.svg (paleta del app).

Persistencia en el workspace abierto:

    <root>/ng-studio-stuff/planner/
        tarea-001-slug/            ← un carril
            lane.json              ← {"name": str, "cron": str|null}
            paso-001-slug/         ← una tarjeta (step)
                step.json          ← {"title": str, "status": ok|fail|wait|blocked}
                conversacion.json  ← [{"role": user|ia|sys, "text": str}, ...]
                tests.json         ← [{"name": str, "result": pass|fail|queue}, ...]
                requerimientos.md  ← doc libre (aparece como adjunto)
                archivos/          ← adjuntos (chips doc/img según extensión)
        tarea-002-...
"""
import html
import json
import os
import re
import shutil
import time
import unicodedata

from PySide6.QtCore import Qt, QSize, QPointF, QRectF, QThread, Signal, QSettings
from PySide6.QtGui import QIcon, QColor, QPainter, QPen, QPolygonF, QTextCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QToolButton, QScrollArea, QSizePolicy, QInputDialog, QDialog,
    QLineEdit, QPlainTextEdit, QFileDialog, QMessageBox,
    QTextEdit, QListWidget, QListWidgetItem,
)

APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICONS_DIR = os.path.join(APP_DIR, "iconos")

STUFF_DIR = "ng-studio-stuff"   # carpeta interna del workspace abierto
PLANNER_SUBDIR = "planner"
LANE_PREFIX = "tarea-"          # tarea-001-slug/
STEP_PREFIX = "paso-"           # paso-001-slug/
IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".heic"}

CAPTION = "color:#6b7280; font-size:9px; font-weight:bold; letter-spacing:1px;"
MUTED = "color:#9aa0aa; font-size:11px;"
FAINT = "color:#6b7280; font-size:10px;"

STATUS = {  # key → (texto, color)
    "ok": ("OK", "#7ce495"),
    "fail": ("FAIL", "#ff6b63"),
    "wait": ("EN ESPERA", "#eab308"),
    "blocked": ("BLOQUEADO", "#8e8e93"),
}
TEST_TAG = {
    "pass": ("PASS", "#7ce495"),
    "fail": ("FAIL", "#ff6b63"),
    "queue": ("EN COLA", "#8e8e93"),
}
ROLE_DOT = {"user": "#eab308", "ia": "#0a84ff", "sys": "#8e8e93"}


def _icon(name):
    return QIcon(os.path.join(ICONS_DIR, name + ".svg"))


def _rgba(hex_color, alpha):
    c = QColor(hex_color)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _pretty_name(dirname, prefix):
    """'tarea-001-refactor-ui' → 'Refactor Ui' (nombre por el dir si no hay lane.json)."""
    n = dirname[len(prefix):] if dirname.startswith(prefix) else dirname
    n = re.sub(r"^\d+[-_]?", "", n) or dirname
    return n.replace("-", " ").replace("_", " ").strip().title()


def _slugify(text):
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()[:40]


# ---- Piezas de la tarjeta ----

class StatusPill(QLabel):
    """Pill de estado: OK / FAIL / EN ESPERA / BLOQUEADO."""

    def __init__(self, key, parent=None):
        txt, color = STATUS[key]
        super().__init__(txt, parent)
        self.setStyleSheet(
            f"color:{color}; font-size:9px; font-weight:bold;"
            f"background:{_rgba(color, 0.12)};"
            f"border:1px solid {_rgba(color, 0.35)};"
            "border-radius:9px; padding:2px 8px;")


class FileChip(QFrame):
    """Ficha de adjunto: ícono doc/imagen + nombre en mono.
    Si tiene open_path + panel, clic → abre el archivo en el editor."""

    def __init__(self, kind, name, panel=None, open_path="", parent=None):
        super().__init__(parent)
        self._panel = panel
        self._open_path = open_path
        self.setObjectName("fileChip")
        self.setStyleSheet(
            "QFrame#fileChip { background:#1a1d22; border:1px solid #2a2d33;"
            " border-radius:6px; }"
            "QFrame#fileChip:hover { border-color:#4a4e57; }")
        if open_path and panel is not None:
            self.setCursor(Qt.PointingHandCursor)
            self.setToolTip("Clic para abrir en el editor")
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 3, 10, 8)
        h.setSpacing(6)
        ic = QLabel()
        ic.setPixmap(_icon("archivo" if kind == "doc" else "imagen").pixmap(12, 12))
        h.addWidget(ic)
        lb = QLabel(name)
        lb.setStyleSheet("color:#b6bac1; font-size:10px;"
                         "font-family:Menlo,'SF Mono',monospace;")
        h.addWidget(lb)

    def mousePressEvent(self, e):
        if (e.button() == Qt.LeftButton and self._open_path
                and self._panel is not None):
            self._panel.open_step_file(self._open_path)
            e.accept()
            return
        super().mousePressEvent(e)


class ConvRow(QWidget):
    """Fila del historial: punto de rol + texto."""

    def __init__(self, role, text, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 2, 10, 2)
        h.setSpacing(8)
        dot = QLabel()
        dot.setFixedSize(6, 6)
        dot.setStyleSheet(f"background:{ROLE_DOT[role]}; border-radius:3px;")
        h.addWidget(dot, 0, Qt.AlignVCenter)
        lb = QLabel(text)
        lb.setStyleSheet(MUTED if role == "sys" else "color:#c8ccd4; font-size:11px;")
        h.addWidget(lb, 1)


class TestRow(QWidget):
    """Fila de test: ícono resultado + nombre mono + tag PASS/FAIL/EN COLA."""

    TAGS = {"pass": ("PASS", "#7ce495"), "fail": ("FAIL", "#ff6b63"),
            "queue": ("EN COLA", "#8e8e93")}

    def __init__(self, name, result, parent=None):
        super().__init__(parent)
        label, color = self.TAGS[result]
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 4, 12, 4)
        h.setSpacing(8)
        ic = QLabel()
        icname = "check_w" if result == "pass" else (
            "close" if result == "fail" else "reloj")
        ic.setPixmap(_icon(icname).pixmap(12, 12))
        h.addWidget(ic)
        lb = QLabel(name)
        lb.setStyleSheet(f"color:{color if result != 'pass' else '#c8ccd4'};"
                         "font-size:11px; font-family:Menlo,'SF Mono',monospace;")
        h.addWidget(lb, 1)
        tag = QLabel(label)
        tag.setStyleSheet(
            f"color:{color}; font-size:8.5px; font-weight:bold;"
            f"background:{_rgba(color, 0.12)}; border-radius:4px; padding:2px 7px;")
        h.addWidget(tag)


class PlannerCard(QFrame):
    """Tarjeta de tarea: cabecera + material + conversación + tests.
    Clic → editor del paso (step.json + requerimientos.md + archivos/)."""

    def __init__(self, num, data, panel=None, parent=None):
        super().__init__(parent)
        self.data = data
        self.panel = panel
        self.setObjectName("plannerCard")
        status = data.get("status", "wait")
        border = ("rgba(255,69,58,0.45)" if status == "fail" else "#33363c")
        self.setStyleSheet(
            "QFrame#plannerCard { background:#22252b;"
            f" border:1px solid {border}; border-radius:10px; }}"
            "QFrame#plannerCard:hover { border-color:#0a84ff; }")
        self.setFixedWidth(300)
        if panel is not None:
            self.setCursor(Qt.PointingHandCursor)
            self.setToolTip("Clic para definir/editar este paso")
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(6)

        # ---- Cabecera ----
        head = QHBoxLayout()
        head.setSpacing(8)
        num = QLabel(str(num))
        num.setFixedSize(22, 22)
        num.setAlignment(Qt.AlignCenter)
        num.setStyleSheet("color:#e8eaed; font-size:11px; font-weight:bold;"
                          "background:#1a1d22; border:1px solid #4a4e57;"
                          "border-radius:11px;")
        head.addWidget(num)
        title = QLabel(data["title"])
        title.setStyleSheet("color:#e8eaed; font-size:12.5px; font-weight:bold;")
        head.addWidget(title, 1)
        head.addWidget(StatusPill(status))
        v.addLayout(head)
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background:#2a2d33;")
        v.addWidget(line)

        if data.get("compact"):
            v.addSpacing(4)
            ic = QLabel()
            icname = "reloj" if status == "wait" else "pausa"
            ic.setPixmap(_icon(icname).pixmap(20, 20))
            h = QHBoxLayout()
            h.addWidget(ic, 0, Qt.AlignTop)
            col = QVBoxLayout()
            col.setSpacing(2)
            t1 = QLabel(data["subtitle"])
            t1.setStyleSheet(MUTED)
            col.addWidget(t1)
            t2 = QLabel(data.get("sub2", "clic para escribir las instrucciones"))
            t2.setStyleSheet("color:#6b7280; font-size:10px;")
            col.addWidget(t2)
            t3 = QLabel("0 adjuntos · 0 tests")
            t3.setStyleSheet("color:#4a4e57; font-size:10px;"
                             "font-family:Menlo,monospace;")
            col.addWidget(t3)
            h.addLayout(col, 1)
            v.addLayout(h)
            v.addStretch(1)
            return

        # ---- Material extra ----
        mats = data.get("materials", [])
        if mats:
            cap = QLabel("MATERIAL EXTRA")
            cap.setStyleSheet(CAPTION)
            v.addWidget(cap)
            for kind, name, ap in mats:
                v.addWidget(FileChip(kind, name, panel=self.panel,
                                     open_path=ap))

        # ---- Resultado: conclusión + archivos tocados ----
        concl = (data.get("conclusion") or "").strip()
        changed = data.get("changed_files", [])
        if concl or changed:
            cap = QLabel("RESULTADO")
            cap.setStyleSheet(CAPTION)
            v.addWidget(cap)
            rbox = QFrame()
            rbox.setObjectName("resBox")
            rbox.setStyleSheet(
                "QFrame#resBox { background:#1a1d22; border:1px solid #2a2d33;"
                " border-radius:8px; }")
            rv = QVBoxLayout(rbox)
            rv.setContentsMargins(10, 8, 10, 8)
            rv.setSpacing(6)
            if concl:
                t = concl if len(concl) <= 500 else concl[:500] + "…"
                lb = QLabel(t)
                lb.setWordWrap(True)
                lb.setStyleSheet("color:#c8ccd4; font-size:11px;")
                rv.addWidget(lb)
            if changed:
                cap2 = QLabel("ARCHIVOS MODIFICADOS")
                cap2.setStyleSheet(CAPTION)
                rv.addWidget(cap2)
                for f in changed:
                    rel = f.get("path", "")
                    kind = ("img" if os.path.splitext(rel)[1].lower()
                            in IMG_EXTS else "doc")
                    rv.addWidget(FileChip(kind, rel, panel=self.panel,
                                          open_path=rel))
            v.addWidget(rbox)

        # ---- Historial de conversación ----
        msgs = data.get("messages", [])
        if msgs or data.get("conv_n"):
            cap = QLabel("HISTORIAL DE CONVERSACIÓN")
            cap.setStyleSheet(CAPTION)
            v.addSpacing(6)
            v.addWidget(cap)
            conv = QFrame()
            conv.setObjectName("convBox")
            conv.setStyleSheet(
                "QFrame#convBox { background:#1a1d22; border:1px solid #2a2d33;"
                " border-radius:8px; }")
            cv = QVBoxLayout(conv)
            cv.setContentsMargins(1, 1, 1, 6)
            cv.setSpacing(0)
            badge_txt, badge_color = {
                "ok": ("CONCLUSIÓN ACEPTADA", "#7ce495"),
                "fail": ("ÚLTIMO INTENTO FALLÓ", "#ff6b63"),
            }.get(status, ("CONVERSACIÓN", "#9aa0aa"))
            badge = QWidget()
            badge.setStyleSheet(
                f"background:{_rgba(badge_color, 0.08)};"
                "border-top-left-radius:8px; border-top-right-radius:8px;")
            bh = QHBoxLayout(badge)
            bh.setContentsMargins(10, 4, 8, 4)
            bh.setSpacing(6)
            bic = QLabel()
            bic.setPixmap(_icon(
                "check_w" if status == "ok" else "reloj").pixmap(11, 11))
            bh.addWidget(bic)
            blb = QLabel(badge_txt)
            blb.setStyleSheet(f"color:{badge_color}; font-size:9px;"
                              "font-weight:bold; letter-spacing:0.5px;")
            bh.addWidget(blb)
            bh.addStretch(1)
            cv.addWidget(badge)
            for role, text in msgs:
                cv.addWidget(ConvRow(role, text))
            cv.addStretch(1)
            link = QLabel(f"Ver conversación completa ({data.get('conv_n', 0)})")
            link.setStyleSheet("color:#0a84ff; font-size:10px; padding-left:10px;")
            link.setCursor(Qt.PointingHandCursor)
            cv.addWidget(link)
            v.addWidget(conv, 1)

        # ---- Tests propuestos ----
        tests = data.get("tests", [])
        if tests or data.get("summary"):
            cap = QLabel("TESTS PROPUESTOS")
            cap.setStyleSheet(CAPTION)
            v.addSpacing(2)
            v.addWidget(cap)
            tbox = QFrame()
            tbox.setObjectName("testsBox")
            tbox.setStyleSheet(
                "QFrame#testsBox { background:#1a1d22;"
                " border:1px solid #2a2d33; border-radius:8px; }")
            tv = QVBoxLayout(tbox)
            tv.setContentsMargins(1, 2, 1, 4)
            tv.setSpacing(0)
            for name, result in tests:
                tv.addWidget(TestRow(name, result))
            tv.addStretch(1)
            summary = QLabel(data.get("summary", ""))
            summary.setStyleSheet(
                f"color:{data.get('summary_color', '#6b7280')}; font-size:10px;"
                "padding:6px 12px;")
            tv.addWidget(summary)
            v.addWidget(tbox)

    def mousePressEvent(self, e):
        # refs antes de super(): el editor modal puede disparar un reload
        # que destruye esta card → el C++ ya no existe al volver
        panel, data = self.panel, self.data
        super().mousePressEvent(e)
        if e.button() == Qt.LeftButton and panel is not None:
            panel.edit_step(data)


class _Arrow(QWidget):
    """Flecha pintada entre tarjetas del pipeline."""

    def __init__(self, color="#4a4e57", dashed=False, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.dashed = dashed
        self.setFixedSize(36, 20)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        y = self.height() / 2
        pen = QPen(self.color, 2)
        if self.dashed:
            pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.drawLine(2, y, self.width() - 9, y)
        p.setPen(Qt.NoPen)
        p.setBrush(self.color)
        p.drawPolygon(QPolygonF([QPointF(self.width() - 9, y - 5),
                                 QPointF(self.width() - 1, y),
                                 QPointF(self.width() - 9, y + 5)]))


class LaneHeader(QFrame):
    """Cabecera de carril: estado, nombre, cron/progreso y controles."""

    def __init__(self, lane, on_play, on_pause, on_run, on_config=None,
                 on_log=None, on_collapse=None, collapsed=False, parent=None):
        super().__init__(parent)
        self.setObjectName("laneHeader")
        self.setStyleSheet(
            "QFrame#laneHeader { background:#1e2126; border:1px solid #2a2d33;"
            " border-radius:10px; }"
            "QToolButton { background:#26292f; border:none; border-radius:6px; }"
            "QToolButton:hover { background:#34383f; }")
        self.setFixedHeight(44)
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 8, 12, 10)
        h.setSpacing(10)
        if on_collapse is not None:
            self.btn_collapse = QToolButton()
            self.btn_collapse.setFixedSize(20, 20)
            self.btn_collapse.setText("▸" if collapsed else "▾")
            self.btn_collapse.setToolTip("Colapsar/expandir el carril")
            self.btn_collapse.setCursor(Qt.PointingHandCursor)
            self.btn_collapse.setStyleSheet(
                "QToolButton { background:transparent; color:#9aa0aa;"
                " border:none; font-size:12px; }"
                "QToolButton:hover { color:#e8eaed; }")
            self.btn_collapse.clicked.connect(on_collapse)
            h.addWidget(self.btn_collapse)
        self.dot = QLabel()
        self.dot.setFixedSize(8, 8)
        self.dot.setStyleSheet(
            f"background:{'#7ce495' if lane.get('cron') else '#8e8e93'};"
            "border-radius:4px;")
        h.addWidget(self.dot)
        name = QLabel(lane["name"])
        name.setStyleSheet("color:#e8eaed; font-size:13px; font-weight:bold;")
        h.addWidget(name)
        h.addSpacing(8)
        if lane.get("cron"):
            chip = QFrame()
            chip.setObjectName("cronChip")
            chip.setStyleSheet(
                "QFrame#cronChip { background:#16181c; border:1px solid #2a2d33;"
                " border-radius:11px; }")
            ch = QHBoxLayout(chip)
            ch.setContentsMargins(10, 2, 10, 8)
            ch.setSpacing(5)
            cic = QLabel()
            cic.setPixmap(_icon("reloj").pixmap(12, 12))
            ch.addWidget(cic)
            ctl = QLabel(lane["cron"])
            ctl.setStyleSheet("color:#9aa0aa; font-size:10px;"
                              "font-family:Menlo,monospace;")
            ch.addWidget(ctl)
            h.addWidget(chip)
        else:
            manual = QLabel("Manual · esperando turno")
            manual.setStyleSheet("color:#9aa0aa; font-size:11px;")
            h.addWidget(manual)
        h.addStretch(1)
        self.progress_lbl = QLabel("")
        self.progress_lbl.setStyleSheet(MUTED)
        h.addWidget(self.progress_lbl)
        self.bar = QFrame()
        self.bar.setFixedSize(90, 8)
        self.bar.setStyleSheet("background:#2a2d33; border-radius:4px;")
        self.bar_fill = QFrame(self.bar)
        self.bar_fill.setStyleSheet("background:#7ce495; border-radius:4px;")
        h.addWidget(self.bar)
        for icon, tip, cb in (("play", "Play", on_play),
                              ("pausa", "Pausa", on_pause)):
            b = QToolButton()
            b.setFixedSize(28, 28)
            b.setIcon(_icon(icon))
            b.setIconSize(QSize(14, 14))
            b.setToolTip(tip)
            b.clicked.connect(cb)
            h.addWidget(b)
            setattr(self, "btn_" + icon, b)
        b_cfg = QToolButton()
        b_cfg.setFixedSize(28, 28)
        b_cfg.setIcon(_icon("engranaje"))
        b_cfg.setIconSize(QSize(14, 14))
        b_cfg.setToolTip("Configuración del carril")
        if on_config is not None:
            b_cfg.clicked.connect(on_config)
        h.addWidget(b_cfg)
        if on_log is not None:
            b_log = QToolButton()
            b_log.setFixedSize(28, 28)
            b_log.setIcon(_icon("archivo"))
            b_log.setIconSize(QSize(14, 14))
            b_log.setToolTip("Ver log del carril (ejecucion.log de sus pasos)")
            b_log.clicked.connect(on_log)
            h.addWidget(b_log)
        done0, total0 = lane.get("progress", (0, 0))
        b_run = QPushButton(
            "Relanzar lane" if total0 and done0 == total0
            else "Ejecutar lane")
        b_run.setIcon(_icon("play"))
        b_run.setFixedHeight(28)
        b_run.setCursor(Qt.PointingHandCursor)
        b_run.setStyleSheet(
            "QPushButton { background:#0a84ff; color:#fff; font-size:11px;"
            " font-weight:bold; border:none; border-radius:6px;"
            " padding:0 14px; }"
            "QPushButton:hover { background:#2f95ff; }")
        b_run.clicked.connect(on_run)
        h.addWidget(b_run)
        self.set_progress(*lane.get("progress", (0, 0)), running=False)

    def set_progress(self, done, total, running):
        if not total:
            self.progress_lbl.setText("")
            self.bar.hide()
            return
        self.bar.show()
        self.progress_lbl.setText(
            "en ejecución…" if running else f"{done}/{total} pasos OK")
        self.bar_fill.setGeometry(0, 0, max(6, int(90 * done / total)), 8)

    def set_state(self, running, done, total):
        self.set_progress(done, total, running)


class _CardsArea(QScrollArea):
    """Scroll horizontal del pipeline: la rueda mueve en X cuando hay
    overflow horizontal (vertical y horizontal del trackpad); si no,
    scrollea en Y normal."""

    def wheelEvent(self, e):
        hbar = self.horizontalScrollBar()
        if hbar.maximum() > 0:
            # Trackpad manda pixelDelta (x e y); rueda común manda angleDelta
            pd = e.pixelDelta()
            if pd is not None and not pd.isNull():
                delta = pd.y() + pd.x()
            else:
                ad = e.angleDelta()
                delta = ad.y() + ad.x()
            hbar.setValue(hbar.value() - delta)
            e.accept()
        else:
            super().wheelEvent(e)


class Lane(QFrame):
    """Un carril: header + pipeline horizontal de tarjetas."""

    def __init__(self, lane, panel=None, parent=None):
        super().__init__(parent)
        self.setObjectName("lane")
        self.setStyleSheet(
            "QFrame#lane { background:#1e2126; border:1px solid #2a2d33;"
            " border-radius:10px; }"
            "QFrame#lane QLabel { background:transparent; border:none; }"
            "QScrollArea { border:none; background:transparent; }"
            "QScrollBar:horizontal { height:7px; background:transparent; }"
            "QScrollBar::handle:horizontal { background:#33363c;"
            " border-radius:3px; min-width:24px; }"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal"
            " { width:0px; }"
            "QScrollBar:vertical { width:7px; background:transparent; }"
            "QScrollBar::handle:vertical { background:#33363c;"
            " border-radius:3px; min-height:24px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical"
            " { height:0px; }")
        self.lane = lane
        self.panel = panel
        self.running = False
        self.collapsed = lane.get("collapsed", False)
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 10)
        v.setSpacing(8)
        self.header = LaneHeader(
            lane, on_play=self._play, on_pause=self._pause,
            on_run=self._run_all,
            on_config=(lambda: self.panel.edit_lane(self.lane))
            if panel is not None else None,
            on_log=(lambda: self.panel.show_lane_log(self.lane))
            if panel is not None else None,
            on_collapse=self._toggle_collapse,
            collapsed=self.collapsed)
        v.addWidget(self.header)
        # Pipeline horizontal (alto ajustado al contenido, con tope)
        self.area = _CardsArea()
        self.area.setWidgetResizable(True)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        self.flow = QHBoxLayout(inner)
        self.flow.setContentsMargins(2, 2, 2, 2)
        self.flow.setSpacing(6)
        self._build_cards()
        self.area.setWidget(inner)
        self._fit_area_height(inner)
        self.area.setVisible(not self.collapsed)
        v.addWidget(self.area)

    def _fit_area_height(self, inner):
        """El área de tarjetas se ajusta al contenido (tope 560px)."""
        inner.adjustSize()
        h = inner.sizeHint().height()
        self.area.setFixedHeight(max(90, min(560, h + 6)))

    def _toggle_collapse(self):
        """▾/▸ del header: pliega el pipeline; persiste en lane.json."""
        self.collapsed = not self.collapsed
        self.area.setVisible(not self.collapsed)
        self.header.btn_collapse.setText("▸" if self.collapsed else "▾")
        if self.panel is not None:
            self.panel.set_lane_collapsed(self.lane, self.collapsed)

    def _build_cards(self):
        while self.flow.count():
            it = self.flow.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        prev_status = None
        for i, card in enumerate(self.lane["cards"]):
            if i:
                color = "#ff453a" if prev_status == "fail" else "#4a4e57"
                dashed = prev_status in ("wait", "blocked")
                self.flow.addWidget(_Arrow(color, dashed))
            w = PlannerCard(i + 1, card, panel=self.panel)
            self.flow.addWidget(w, 0, Qt.AlignTop)
            prev_status = card.get("status", "wait")
        if self.panel is not None:
            add = QPushButton("＋\nPaso")
            add.setFixedSize(64, 64)
            add.setCursor(Qt.PointingHandCursor)
            add.setToolTip("Agregar un paso a este carril")
            add.setStyleSheet(
                "QPushButton { background:transparent; color:#9aa0aa;"
                " border:1px dashed #33363c; border-radius:10px;"
                " font-size:10px; }"
                "QPushButton:hover { color:#e8eaed; border-color:#0a84ff; }")
            add.clicked.connect(lambda: self.panel.add_step(self.lane))
            self.flow.addWidget(add, 0, Qt.AlignTop)
        self.flow.addStretch(1)

    def _play(self):
        if self.panel is not None:
            self.panel.run_lane(self)

    def _pause(self):
        self.running = False
        self.header.dot.setStyleSheet("background:#eab308; border-radius:4px;")
        done, total = self.lane.get("progress", (0, 0))
        self.header.set_state(False, done, total)
        if self.panel is not None:
            self.panel.pause_lane(self)

    def _run_all(self):
        self._play()


_DLG_STYLE = (
    "QDialog { background:#1e2126; color:#d7dae0; }"
    "QLineEdit, QPlainTextEdit, QComboBox { background:#16181c; color:#d7dae0;"
    " border:1px solid #33363c; border-radius:6px; padding:5px; }"
    "QLabel { color:#9aa0aa; }"
    "QPushButton { background:#26292f; color:#d7dae0; border:none;"
    " border-radius:6px; padding:6px 16px; }"
    "QPushButton:hover { background:#34383f; }"
    "QPushButton#primary { background:#0a84ff; color:#fff; font-weight:bold; }"
    "QPushButton#primary:hover { background:#2f95ff; }")


class _DropList(QListWidget):
    """Lista de adjuntos: acepta drag&drop de archivos desde el Finder,
    con thumbnails para imágenes."""

    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setIconSize(QSize(30, 30))
        self.setStyleSheet(
            "QListWidget { background:#16181c; border:1px dashed #33363c;"
            " border-radius:8px; }"
            "QListWidget::item { color:#c8ccd4; font-size:11px;"
            " padding:3px; }"
            "QListWidget::item:selected { background:#26292f; }")

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        files = [u.toLocalFile() for u in e.mimeData().urls()
                 if u.isLocalFile() and os.path.isfile(u.toLocalFile())]
        if files:
            self.files_dropped.emit(files)
            e.acceptProposedAction()
        else:
            super().dropEvent(e)


class _TitleGen(QThread):
    """Genera un título corto para el paso a partir de las instrucciones,
    con el provider/modelo activo del chat."""

    done = Signal(str)

    def __init__(self, base, model, key, provider_name, text, parent=None):
        super().__init__(parent)
        self.base, self.model, self.key = base, model, key
        self.provider_name = provider_name or ""
        self.text = text

    def run(self):
        try:
            import requests
            from UI.panels.chat_panel import api_url
            headers = {"Content-Type": "application/json",
                       "User-Agent": "cli-ia/1.0"}
            if self.key:
                headers["Authorization"] = f"Bearer {self.key}"
            if "opencode" in self.provider_name.lower():
                import uuid
                headers["x-opencode-session"] = str(uuid.uuid4())
            r = requests.post(
                api_url(self.base, "/chat/completions"),
                json={"model": self.model, "stream": False,
                      "messages": [{"role": "user", "content":
                        "Generá un título corto (máximo 6 palabras, sin "
                        "comillas ni punto final) para esta tarea:\n\n"
                        + self.text[:4000]}],
                      "temperature": 0.2, "max_tokens": 40},
                timeout=(10, 60), headers=headers)
            r.encoding = "utf-8"
            r.raise_for_status()
            title = (r.json().get("choices") or [{}])[0] \
                .get("message", {}).get("content", "")
            self.done.emit(str(title))
        except Exception:
            self.done.emit("")


class StepDialog(QDialog):
    """Editor de un paso (tarjeta): escribir instrucciones directo
    (requerimientos.md), título por IA/primera línea y adjuntos con
    drag&drop en el panel lateral."""

    def __init__(self, card, parent=None):
        super().__init__(parent)
        self.card = card
        self.panel = parent          # PlannerPanel → provider_fn
        self.step_dir = card["dir"]
        self._title_thread = None
        self.setWindowTitle(f"Paso — {card.get('title', '')}")
        self.setModal(True)
        self.resize(760, 440)
        self.setStyleSheet(_DLG_STYLE)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(8)

        cap = QLabel("TÍTULO DEL PASO")
        cap.setStyleSheet(CAPTION)
        v.addWidget(cap)
        tr = QHBoxLayout()
        tr.setSpacing(6)
        self.title = QLineEdit(card.get("title", ""))
        tr.addWidget(self.title, 1)
        self.b_ai = QPushButton("✨ Generar")
        self.b_ai.setToolTip(
            "Generar el título con IA a partir de las instrucciones")
        self.b_ai.setCursor(Qt.PointingHandCursor)
        self.b_ai.clicked.connect(self._gen_title)
        tr.addWidget(self.b_ai)
        v.addLayout(tr)

        cols = QHBoxLayout()
        cols.setSpacing(10)
        # Izquierda: instrucciones (foco principal del diálogo)
        left = QVBoxLayout()
        left.setSpacing(4)
        cap = QLabel("INSTRUCCIONES / REQUERIMIENTOS  (requerimientos.md)")
        cap.setStyleSheet(CAPTION)
        left.addWidget(cap)
        self.req = QPlainTextEdit()
        self.req.setPlaceholderText(
            "Qué tiene que hacer el agente en este paso…")
        left.addWidget(self.req, 1)
        lw = QWidget()
        lw.setLayout(left)
        cols.addWidget(lw, 1)
        # Derecha: adjuntos con drag&drop
        right = QVBoxLayout()
        right.setSpacing(4)
        cap = QLabel("ARCHIVOS  (arrastrá acá)")
        cap.setStyleSheet(CAPTION)
        right.addWidget(cap)
        self.files = _DropList()
        self.files.files_dropped.connect(self._add_files)
        right.addWidget(self.files, 1)
        fr = QHBoxLayout()
        fr.setSpacing(6)
        b_attach = QPushButton("Adjuntar…")
        b_attach.setCursor(Qt.PointingHandCursor)
        b_attach.clicked.connect(self._attach)
        fr.addWidget(b_attach)
        b_del = QPushButton("Quitar")
        b_del.setCursor(Qt.PointingHandCursor)
        b_del.clicked.connect(self._remove_files)
        fr.addWidget(b_del)
        right.addLayout(fr)
        rw = QWidget()
        rw.setLayout(right)
        rw.setFixedWidth(230)
        cols.addWidget(rw)
        v.addLayout(cols, 1)

        br = QHBoxLayout()
        br.addStretch(1)
        b_cancel = QPushButton("Cancelar")
        b_cancel.clicked.connect(self.reject)
        b_save = QPushButton("Guardar")
        b_save.setObjectName("primary")
        b_save.setDefault(True)
        b_save.clicked.connect(self._save)
        br.addWidget(b_cancel)
        br.addWidget(b_save)
        v.addLayout(br)

        # Carga inicial: requerimientos + adjuntos ya existentes
        try:
            with open(os.path.join(self.step_dir, "requerimientos.md"),
                      encoding="utf-8") as f:
                self.req.setPlainText(f.read())
        except OSError:
            pass
        self._refresh_files()
        self.req.setFocus()          # escribir instrucciones de una

    # ---- Título ----

    def _gen_title(self):
        text = self.req.toPlainText().strip()
        if not text:
            self.req.setFocus()
            return
        base = model = key = pname = None
        fn = getattr(self.panel, "provider_fn", None)
        if fn is not None:
            base, model, key, pname = fn()
        if not model:
            self._title_from_first_line()   # sin modelo → primera línea
            return
        self.b_ai.setEnabled(False)
        self.b_ai.setText("…")
        self._title_thread = _TitleGen(base, model, key, pname, text, self)
        self._title_thread.done.connect(self._on_title_done)
        self._title_thread.start()

    def _title_from_first_line(self):
        lines = self.req.toPlainText().strip().splitlines()
        if lines:
            t = lines[0].strip()
            self.title.setText(t[:60] + "…" if len(t) > 60 else t)

    def _on_title_done(self, title):
        self.b_ai.setEnabled(True)
        self.b_ai.setText("✨ Generar")
        title = (title or "").strip().strip('"').splitlines()
        if title and title[0].strip():
            self.title.setText(title[0].strip()[:80])

    # ---- Adjuntos (archivos/) ----

    def _attach(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Adjuntar al paso")
        if files:
            self._add_files(files)

    def _add_files(self, files):
        adir = os.path.join(self.step_dir, "archivos")
        try:
            os.makedirs(adir, exist_ok=True)
            for f in files:
                if os.path.isfile(f):
                    shutil.copy2(f, os.path.join(adir, os.path.basename(f)))
        except OSError:
            pass
        self._refresh_files()

    def _remove_files(self):
        for it in self.files.selectedItems():
            try:
                os.remove(it.data(Qt.UserRole))
            except OSError:
                pass
        self._refresh_files()

    def _refresh_files(self):
        self.files.clear()
        adir = os.path.join(self.step_dir, "archivos")
        try:
            names = sorted(f for f in os.listdir(adir)
                           if not f.startswith("."))
        except OSError:
            names = []
        for f in names:
            p = os.path.join(adir, f)
            it = QListWidgetItem(f)
            ic = QIcon(p)
            if not ic.isNull():
                it.setIcon(ic)          # thumbnail si es imagen
            it.setData(Qt.UserRole, p)
            it.setToolTip(p)
            self.files.addItem(it)

    def _save(self):
        try:
            os.makedirs(self.step_dir, exist_ok=True)
            title = self.title.text().strip()
            if not title:
                lines = self.req.toPlainText().strip().splitlines()
                title = (lines[0].strip()[:60] if lines else "") \
                    or "Nuevo paso"
            # Solo toca el título: el status lo maneja la pipeline
            meta = _read_json(os.path.join(self.step_dir, "step.json")) or {}
            meta["title"] = title
            meta.setdefault("status", "wait")
            _write_json(os.path.join(self.step_dir, "step.json"), meta)
            req_path = os.path.join(self.step_dir, "requerimientos.md")
            txt = self.req.toPlainText()
            if txt.strip():
                with open(req_path, "w", encoding="utf-8") as f:
                    f.write(txt)
            elif os.path.exists(req_path):
                os.remove(req_path)
        except OSError:
            pass
        self.accept()


class LaneDialog(QDialog):
    """Config del carril: nombre + cron (vacío = manual) → lane.json."""

    def __init__(self, lane, parent=None):
        super().__init__(parent)
        self.lane = lane
        self.setWindowTitle(f"Carril — {lane.get('name', '')}")
        self.setModal(True)
        self.setFixedWidth(380)
        self.setStyleSheet(_DLG_STYLE)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(8)

        cap = QLabel("NOMBRE DE LA TAREA")
        cap.setStyleSheet(CAPTION)
        v.addWidget(cap)
        self.name = QLineEdit(lane.get("name", ""))
        v.addWidget(self.name)

        cap = QLabel("CRON  (ej: 02:00 AM — vacío = ejecución manual)")
        cap.setStyleSheet(CAPTION)
        v.addWidget(cap)
        self.cron = QLineEdit(lane.get("cron_raw", ""))
        self.cron.setPlaceholderText("vacío = manual")
        v.addWidget(self.cron)

        br = QHBoxLayout()
        br.addStretch(1)
        b_cancel = QPushButton("Cancelar")
        b_cancel.clicked.connect(self.reject)
        b_save = QPushButton("Guardar")
        b_save.setObjectName("primary")
        b_save.setDefault(True)
        b_save.clicked.connect(self._save)
        br.addWidget(b_cancel)
        br.addWidget(b_save)
        v.addLayout(br)

    def _save(self):
        try:
            _write_json(os.path.join(self.lane["dir"], "lane.json"), {
                "name": self.name.text().strip() or self.lane["name"],
                "cron": self.cron.text().strip() or None})
        except OSError:
            pass
        self.accept()


class LogDialog(QDialog):
    """Visor de ejecucion.log de un carril (todos sus pasos concatenados)."""

    def __init__(self, title, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(660, 480)
        self.setStyleSheet(_DLG_STYLE)
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)
        view = QTextEdit()
        view.setReadOnly(True)
        view.setStyleSheet(
            "QTextEdit { background:#0c0e11; color:#c8ccd4;"
            " border:1px solid #2a2d33; border-radius:6px;"
            " font-family:Menlo,'SF Mono',monospace; font-size:10.5px; }")
        view.setPlainText(text)
        v.addWidget(view, 1)
        br = QHBoxLayout()
        br.addStretch(1)
        b = QPushButton("Cerrar")
        b.setDefault(True)
        b.clicked.connect(self.accept)
        br.addWidget(b)
        v.addLayout(br)


class LaneRunner(QThread):
    """Ejecuta los pasos pendientes de un carril (status wait/fail), uno tras
    otro, con el Worker/Tools del chat. Persiste por paso:

        conversacion.json  ← historial completo del run
        step.json          ← status: ok / fail / wait (si se pausó)
    """

    step_started = Signal(str, str)   # step_dir, título
    step_done = Signal(str, str)      # step_dir, status
    lane_done = Signal()              # terminó (o se pausó) el carril
    files_changed = Signal()          # la IA tocó archivos del workspace
    log = Signal(str, str)            # kind, texto → consola de logs

    def __init__(self, root, lane_name, steps, base, model, key,
                 session_id="", parent=None):
        super().__init__(parent)
        self.root = root
        self.lane_name = lane_name
        self.steps = steps            # card dicts con dir/title/status
        self.base, self.model, self.key = base, model, key
        self.session_id = session_id  # x-opencode-session (providers Go/Zen)
        self._stop = False
        self._worker = None

    def stop(self):
        self._stop = True
        if self._worker is not None:
            self._worker.stop()

    def _step_prompt(self, card):
        """Prompt del paso: título + requerimientos.md + lista de adjuntos."""
        sd = card["dir"]
        req = ""
        try:
            with open(os.path.join(sd, "requerimientos.md"),
                      encoding="utf-8") as f:
                req = f.read().strip()
        except OSError:
            pass
        archivos = []
        try:
            archivos = [f for f in sorted(os.listdir(
                os.path.join(sd, "archivos"))) if not f.startswith(".")]
        except OSError:
            pass
        if not req:
            req = ("(sin instrucciones — interpretá el título del paso "
                   "y hacé el trabajo correspondiente)")
        prompt = (f'PASO DE LA TAREA «{self.lane_name}»: {card["title"]}\n\n'
                  f'Instrucciones:\n{req}')
        if archivos:
            prompt += ("\n\nArchivos adjuntos del paso "
                       "(dentro de ng-studio-stuff/planner/…/archivos/):\n"
                       + "\n".join("- " + f for f in archivos))
        return prompt

    @staticmethod
    def _conv_entry(role, content):
        """Historial OpenAI-style → {"role","text"} de conversacion.json."""
        if role == "assistant":
            r = "ia"
        elif role == "system" or content.startswith("[RESULTADO"):
            r = "sys"
        else:
            r = "user"
        return {"role": r, "text": content}

    _LOG_KIND = {"assistant": "ia", "tool": "tool", "error": "error",
                 "stats": "sys"}

    def run(self):
        # Import lazy: chat_panel es pesado y así el panel funciona sin él
        from UI.panels.chat_panel import (Tools, Worker, parse_actions,
                                          strip_tool_json)
        try:
            prefs = json.loads(
                QSettings("ChatIA", "ChatIA").value("prefs", "{}")) or {}
        except (ValueError, TypeError):
            prefs = {}
        tools = Tools(self.root)
        logf = None

        def log(kind, text, to_file=True):
            """Emite a la consola del panel y persiste en ejecucion.log."""
            self.log.emit(kind, text)
            if logf is not None and to_file:
                try:
                    ts = time.strftime("%H:%M:%S")
                    logf.write(f"[{ts}] {text}\n")
                    logf.flush()
                except OSError:
                    pass

        log("lane", f"══ Ejecutando «{self.lane_name}» — "
                    f"{len(self.steps)} paso(s) ══", to_file=False)
        for i, card in enumerate(self.steps):
            if self._stop:
                break
            step_dir = card["dir"]
            prompt = self._step_prompt(card)
            history = [{"role": "user", "content": prompt}]
            worker = Worker(
                self.base, self.model, tools, history, self.key,
                session_id=self.session_id,
                max_tools=int(prefs.get("max_tools", 50)),
                tool_limit_enabled=bool(prefs.get("tool_limit_enabled", True)),
                request_timeout=int(prefs.get("request_timeout", 600)),
                ctx_parts=dict(prefs.get("ctx_parts", {})),
                ctx_skip={k: dict(v) for k, v in
                          prefs.get("ctx_skip", {}).items()})
            roles = []
            touched = {}    # path → {"path","tool"} de lo que tocó la IA
            try:
                logf = open(os.path.join(step_dir, "ejecucion.log"),
                            "a", encoding="utf-8")
            except OSError:
                logf = None
            worker.msg.connect(
                lambda t, role, acc=roles: (
                    acc.append(role),
                    log(self._LOG_KIND.get(role, "sys"), t)))
            worker.chunk.connect(lambda c: log("stream", c))
            worker.files_changed.connect(self.files_changed)
            worker.file_changed.connect(
                lambda pth, tool, *_a, acc=touched: acc.__setitem__(
                    pth, {"path": pth, "tool": tool}))
            self._worker = worker
            log("step", f"── Paso {i + 1}: {card['title']} ──")
            log("sys", "prompt → " + prompt.replace("\n", " ")[:300])
            if logf is not None:
                try:
                    logf.write("════ PROMPT COMPLETO ════\n" + prompt + "\n\n")
                    logf.flush()
                except OSError:
                    pass
            self.step_started.emit(step_dir, card["title"])
            t0 = time.time()
            worker.run()              # síncrono dentro de este thread
            dt = time.time() - t0
            self._worker = None
            stopped = self._stop or worker._stop
            # ¿Terminó de verdad? Si el último mensaje es una respuesta final
            # del modelo (sin tool calls pendientes), el trabajo se completó
            # aunque el usuario haya pausado en el medio del cierre.
            last = history[-1] if history else {}
            finished_clean = (last.get("role") == "assistant"
                              and not parse_actions(
                                  last.get("content", "")))
            if stopped and not finished_clean:
                status = "wait"
            else:
                status = "fail" if "error" in roles else "ok"
            conclusion = ""
            if last.get("role") == "assistant":
                conclusion = strip_tool_json(
                    last.get("content", "")).strip()[:4000]
            mark = {"ok": "✓ OK", "fail": "✗ FAIL", "wait": "⏸ pausado"}
            u = worker.usage
            log("step" if status == "ok" else "error",
                f"── Paso {i + 1}: {mark[status]} "
                f"({dt:.1f}s · {u['completion']} tok generados) ──")
            if logf is not None:
                try:
                    logf.write("\n════ TRANSCRIPT COMPLETO ════\n")
                    for m in history:
                        logf.write(f"\n### [{m.get('role', '?').upper()}]\n"
                                   f"{m.get('content', '')}\n")
                    logf.flush()
                except OSError:
                    pass
            if logf is not None:
                try:
                    logf.close()
                except OSError:
                    pass
                logf = None
            try:
                conv = [self._conv_entry(m.get("role", "user"),
                                         m.get("content", ""))
                        for m in history]
                _write_json(os.path.join(step_dir, "conversacion.json"), conv)
                meta = _read_json(os.path.join(step_dir, "step.json")) or {}
                meta["status"] = status
                _write_json(os.path.join(step_dir, "step.json"), meta)
                _write_json(os.path.join(step_dir, "resultado.json"), {
                    "status": status,
                    "conclusion": conclusion,
                    "files": list(touched.values()),
                    "duration": round(dt, 1),
                    "tokens": u["completion"]})
            except OSError:
                pass
            self.step_done.emit(step_dir, status)
            if stopped:
                break
        log("lane", "══ Carril pausado ══" if self._stop
            else "══ Carril terminado ══", to_file=False)
        self.lane_done.emit()


class PlannerPanel(QWidget):
    """AI Autonomous Workflow Planner: carriles con tareas secuenciales
    ejecutadas por agentes IA, persistidos en <root>/ng-studio-stuff/planner/."""

    files_changed = Signal()   # la IA tocó archivos → refrescar panel Files
    open_file_requested = Signal(str)  # path absoluto → abrir en editor
    mutated = Signal()         # este panel escribió en planner/ → el gemelo recarga

    def __init__(self, parent=None):
        super().__init__(parent)
        self.root = ""
        self.planner_dir = ""
        self.provider_fn = None   # callable → (base, model, key, provider_name)
        self.chat = None          # ChatPanel de la misma zona (main_window)
        self._runner = None       # LaneRunner activo (un carril a la vez)
        self._running_lane = None # Lane widget del carril en ejecución
        self._queue = []          # dirs de carriles en cola (Ejecutar todo)
        self.setStyleSheet(
            "QWidget { background:#16181c; }"
            "QScrollArea { border:none; }"
            "QScrollBar:vertical { width:8px; background:transparent; }"
            "QScrollBar::handle:vertical { background:#2a2d33;"
            " border-radius:4px; min-height:24px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical"
            " { height:0px; }"
            "QScrollBar:horizontal { height:0px; background:transparent; }")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        outer.addWidget(scroll)
        page = QWidget()
        page.setStyleSheet("background:transparent;")
        pv = QVBoxLayout(page)
        pv.setContentsMargins(12, 12, 12, 12)
        pv.setSpacing(10)
        # Fila superior: título + Ejecutar todo (corre TODOS los carriles)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        cap = QLabel("CARRILES DE TAREAS")
        cap.setStyleSheet(CAPTION)
        top.addWidget(cap)
        top.addStretch(1)
        self.btn_run_all = QPushButton(" Ejecutar todo")
        self.btn_run_all.setIcon(_icon("play"))
        self.btn_run_all.setFixedHeight(28)
        self.btn_run_all.setCursor(Qt.PointingHandCursor)
        self.btn_run_all.setToolTip(
            "Ejecuta los pasos pendientes de todos los carriles")
        self.btn_run_all.setStyleSheet(
            "QPushButton { background:#0a84ff; color:#fff; font-size:11px;"
            " font-weight:bold; border:none; border-radius:6px;"
            " padding:0 14px; }"
            "QPushButton:hover { background:#2f95ff; }")
        self.btn_run_all.clicked.connect(self.run_all)
        top.addWidget(self.btn_run_all)
        pv.addLayout(top)
        self.lanes_box = QVBoxLayout()
        self.lanes_box.setSpacing(10)
        pv.addLayout(self.lanes_box)
        self._empty = QLabel("Sin tareas todavía — creá un carril abajo")
        self._empty.setStyleSheet("color:#4a4e57; font-size:12px; padding:18px;")
        self._empty.setAlignment(Qt.AlignCenter)
        self.btn_add = QPushButton(" Añadir nuevo carril de tareas")
        self.btn_add.setIcon(_icon("mas"))
        self.btn_add.setIconSize(QSize(14, 14))
        self.btn_add.setFixedHeight(44)
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.setStyleSheet(
            "QPushButton { background:transparent; color:#9aa0aa;"
            " border:1px dashed #33363c; border-radius:10px; font-size:12px; }"
            "QPushButton:hover { color:#e8eaed; border-color:#0a84ff; }")
        self.btn_add.clicked.connect(self._add_lane)
        pv.addWidget(self.btn_add)
        pv.addStretch(1)
        scroll.setWidget(page)

        # ---- Consola de logs de ejecución (oculta hasta que hay actividad) ----
        self.log_frame = QFrame()
        self.log_frame.setObjectName("plannerLog")
        self.log_frame.setStyleSheet(
            "QFrame#plannerLog { background:#101216;"
            " border-top:1px solid #2a2d33; }")
        lf = QVBoxLayout(self.log_frame)
        lf.setContentsMargins(10, 6, 10, 8)
        lf.setSpacing(4)
        lh = QHBoxLayout()
        lh.setContentsMargins(0, 0, 0, 0)
        t = QLabel("LOG DE EJECUCIÓN")
        t.setStyleSheet(CAPTION)
        lh.addWidget(t)
        lh.addStretch(1)
        b_clear = QPushButton("Limpiar")
        b_clear.setFixedHeight(20)
        b_clear.setCursor(Qt.PointingHandCursor)
        b_clear.setStyleSheet(
            "QPushButton { background:transparent; color:#6b7280;"
            " border:none; font-size:10px; padding:0 6px; }"
            "QPushButton:hover { color:#e8eaed; }")
        b_clear.clicked.connect(lambda: self.log_view.clear())
        lh.addWidget(b_clear)
        b_hide = QPushButton("✕")
        b_hide.setFixedSize(20, 20)
        b_hide.setCursor(Qt.PointingHandCursor)
        b_hide.setToolTip("Ocultar log")
        b_hide.setStyleSheet(
            "QPushButton { background:transparent; color:#6b7280;"
            " border:none; font-size:11px; }"
            "QPushButton:hover { color:#e8eaed; }")
        b_hide.clicked.connect(self.log_frame.hide)
        lh.addWidget(b_hide)
        lf.addLayout(lh)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(160)
        self.log_view.setStyleSheet(
            "QTextEdit { background:#0c0e11; color:#c8ccd4; border:none;"
            " font-family:Menlo,'SF Mono',monospace; font-size:10.5px; }")
        lf.addWidget(self.log_view)
        outer.addWidget(self.log_frame)
        self.log_frame.hide()

        # Chip del modelo activo (va al header del panel; clic abre el
        # mismo combo de modelos del chat)
        self.model_btn = QToolButton()
        self.model_btn.setToolTip(
            "Modelo de IA para ejecutar pasos — clic para elegir")
        self.model_btn.setCursor(Qt.PointingHandCursor)
        self.model_btn.setFixedHeight(22)
        self.model_btn.setStyleSheet(
            "QToolButton { background:#22252b; border:1px solid #33363c;"
            " border-radius:9px; padding:1px 10px; color:#e8e8ed;"
            " font-size:10.5px; }"
            "QToolButton:hover { border-color:#4a4e57; background:#2a2d34; }")
        self.model_btn.setText("(modelo)")
        self.model_btn.clicked.connect(self._pick_model)
        self.reload()

    # ---- Workspace / disco ----

    def set_repo(self, path):
        """Carpeta de trabajo abierta: crea ng-studio-stuff/planner/ y carga."""
        self.root = os.path.realpath(path) if path else ""
        self.planner_dir = (os.path.join(self.root, STUFF_DIR, PLANNER_SUBDIR)
                            if self.root else "")
        if self.planner_dir:
            try:
                os.makedirs(self.planner_dir, exist_ok=True)
            except OSError:
                pass
        self.reload()

    def reload(self):
        self._sync_model_chip()
        while self.lanes_box.count():
            it = self.lanes_box.takeAt(0)
            w = it.widget()
            if w is not None and w is not self._empty:
                w.deleteLater()
        lanes = self._load_lanes() if self.planner_dir else []
        for lane in lanes:
            self.lanes_box.addWidget(Lane(lane, panel=self))
        if not lanes:
            self.lanes_box.insertWidget(0, self._empty)
            self._empty.show()
        else:
            # fuera del layout pero sigue siendo hijo: ocultarla o flota
            # encima del botón "Añadir" y se come los clicks
            self._empty.hide()

    def _load_lanes(self):
        lanes = []
        try:
            names = sorted(os.listdir(self.planner_dir))
        except OSError:
            return lanes
        for name in names:
            d = os.path.join(self.planner_dir, name)
            if os.path.isdir(d) and name.startswith(LANE_PREFIX):
                lanes.append(self._load_lane(d, name))
        return lanes

    def _load_lane(self, d, dirname):
        meta = _read_json(os.path.join(d, "lane.json")) or {}
        cards = []
        try:
            steps = sorted(os.listdir(d))
        except OSError:
            steps = []
        for s in steps:
            sd = os.path.join(d, s)
            if os.path.isdir(sd) and s.startswith(STEP_PREFIX):
                cards.append(self._load_step(sd, s))
        done = sum(1 for c in cards if c.get("status") == "ok")
        cron = meta.get("cron")
        return {"name": meta.get("name") or _pretty_name(dirname, LANE_PREFIX),
                "cron": f"Cron {cron}" if cron else None,
                "cron_raw": cron or "",
                "collapsed": bool(meta.get("collapsed", False)),
                "progress": (done, len(cards)), "dir": d, "cards": cards}

    def _load_step(self, sd, sname):
        meta = _read_json(os.path.join(sd, "step.json")) or {}
        card = {"title": meta.get("title") or _pretty_name(sname, STEP_PREFIX),
                "status": meta.get("status", "wait"), "dir": sd}
        mats = []
        req_p = os.path.join(sd, "requerimientos.md")
        if os.path.exists(req_p):
            mats.append(("doc", "requerimientos.md", req_p))
        archivos = os.path.join(sd, "archivos")
        try:
            for f in sorted(os.listdir(archivos)):
                if not f.startswith("."):
                    kind = ("img" if os.path.splitext(f)[1].lower() in IMG_EXTS
                            else "doc")
                    mats.append((kind, f, os.path.join(archivos, f)))
        except OSError:
            pass
        card["materials"] = mats
        # Resultado del último run: conclusión + archivos que tocó la IA
        res = _read_json(os.path.join(sd, "resultado.json")) or {}
        card["conclusion"] = res.get("conclusion", "")
        card["changed_files"] = [f for f in res.get("files", [])
                                 if isinstance(f, dict) and f.get("path")]
        conv = _read_json(os.path.join(sd, "conversacion.json")) or []
        card["messages"] = [(m.get("role", "sys"), m.get("text", ""))
                            for m in conv if isinstance(m, dict)][-3:]
        card["conv_n"] = len(conv)
        tests = _read_json(os.path.join(sd, "tests.json")) or []
        card["tests"] = [(t.get("name", "test"), t.get("result", "queue"))
                         for t in tests if isinstance(t, dict)]
        if tests:
            ok = sum(1 for _, r in card["tests"] if r == "pass")
            card["summary"] = f"{ok}/{len(tests)} PASS"
            card["summary_color"] = "#7ce495" if ok == len(tests) else "#ff6b63"
        if not mats and not conv and not tests and not res:
            card["compact"] = True
            card["subtitle"] = meta.get("subtitle") or "Esperando definición de pasos"
        return card

    # ---- Selector de modelo (compartido con el chat de la zona) ----

    def _pick_model(self):
        """Clic en el chip → mismo popup de modelos del chat."""
        if self.chat is None:
            return
        self.chat._open_model_popup()
        self._sync_model_chip()

    def _sync_model_chip(self):
        ref = getattr(self.chat, "_current_ref", "") if self.chat else ""
        name = ref.partition("::")[2] or ref or "(sin modelo)"
        if len(name) > 22:
            name = name[:21] + "…"
        self.model_btn.setText(name)

    # ---- Consola de logs ----

    _LOG_COLOR = {"lane": "#0a84ff", "step": "#eab308", "ia": "#c8ccd4",
                  "tool": "#8e8e93", "error": "#ff6b63", "sys": "#6b7280",
                  "stream": "#c8ccd4"}

    def toggle_log(self):
        """Botón ▤ del header: muestra/oculta la consola de logs."""
        self.log_frame.setVisible(self.log_frame.isHidden())

    def _on_log(self, kind, text):
        """Una línea/chunk del LaneRunner → consola (con color por tipo)."""
        if self.log_frame.isHidden():
            self.log_frame.show()
        if kind == "stream":
            # chunks de la respuesta en vivo: texto crudo al final
            cur = self.log_view.textCursor()
            cur.movePosition(QTextCursor.End)
            self.log_view.setTextCursor(cur)
            self.log_view.insertPlainText(text)
        else:
            color = self._LOG_COLOR.get(kind, "#6b7280")
            ts = time.strftime("%H:%M:%S")
            self.log_view.append(
                f'<span style="color:#4a4e57;">[{ts}]</span> '
                f'<span style="color:{color};">'
                f'{html.escape(text).replace(chr(10), "<br>")}</span>')
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ---- Ejecución (▶ / Ejecutar lane / Ejecutar todo / Pausa) ----

    def run_lane(self, lane_w):
        """▶ / "Ejecutar lane" del carril: corre solo sus pasos pendientes."""
        self._queue = []
        self._start_run(lane_w)

    def run_all(self):
        """"Ejecutar todo" del panel: corre los carriles con pasos
        pendientes, uno tras otro (cola por lane_dir)."""
        if self._runner is not None and self._runner.isRunning():
            QMessageBox.information(
                self, "Planner", "Ya hay un carril ejecutándose.")
            return
        lanes = []
        for i in range(self.lanes_box.count()):
            w = self.lanes_box.itemAt(i).widget()
            if isinstance(w, Lane) and any(
                    c.get("status") in ("wait", "fail")
                    for c in w.lane["cards"]):
                lanes.append(w)
        if not lanes:
            QMessageBox.information(
                self, "Planner",
                "No hay pasos pendientes en ningún carril.")
            return
        self._queue = [w.lane.get("dir") for w in lanes[1:]]
        self._start_run(lanes[0])

    def _lane_widget_by_dir(self, lane_dir):
        for i in range(self.lanes_box.count()):
            w = self.lanes_box.itemAt(i).widget()
            if isinstance(w, Lane) and w.lane.get("dir") == lane_dir:
                return w
        return None

    def _start_run(self, lane_w):
        """Ejecuta los pasos pendientes del carril con la IA."""
        if not self.root or lane_w is None:
            return
        if self._runner is not None and self._runner.isRunning():
            QMessageBox.information(
                self, "Planner",
                "Ya hay un carril ejecutándose. Pausalo o esperá a que "
                "termine.")
            return
        if self.provider_fn is None:
            QMessageBox.information(
                self, "Planner",
                "No hay un chat conectado. Configurá un modelo en el panel "
                "de chat (⚙) para ejecutar pasos.")
            return
        base, model, key, pname = self.provider_fn()
        if not model:
            QMessageBox.information(
                self, "Planner",
                "Seleccioná un modelo de IA en el panel de chat para "
                "ejecutar pasos.")
            return
        self._sync_model_chip()
        # OpenCode Go/Zen requiere header x-opencode-session por sesión
        session_id = ""
        if pname and "opencode" in pname.lower():
            import uuid
            session_id = str(uuid.uuid4())
        steps = [c for c in lane_w.lane["cards"]
                 if c.get("status") in ("wait", "fail")]
        if not steps:
            # Sin pendientes → relanzar: confirmación + reset de estados
            cards = lane_w.lane["cards"]
            if not cards:
                return
            btn = QMessageBox.question(
                self, "Relanzar lane",
                f"«{lane_w.lane.get('name', '')}» ya ejecutó todos sus "
                "pasos.\n¿Relanzar el carril? Se vuelven a correr todos "
                "los pasos desde el primero.",
                QMessageBox.Yes | QMessageBox.No)
            if btn != QMessageBox.Yes:
                return
            for c in cards:
                try:
                    meta = _read_json(
                        os.path.join(c["dir"], "step.json")) or {}
                    meta["status"] = "wait"
                    _write_json(os.path.join(c["dir"], "step.json"), meta)
                    c["status"] = "wait"
                except OSError:
                    pass
            steps = list(cards)
            self.mutated.emit()  # los step.json quedaron en wait
        runner = LaneRunner(self.root, lane_w.lane.get("name", ""), steps,
                            base, model, key, session_id=session_id,
                            parent=self)
        runner.step_started.connect(self._step_started)
        runner.step_done.connect(self._step_done)
        runner.lane_done.connect(self._lane_finished)
        runner.files_changed.connect(self.files_changed)
        runner.log.connect(self._on_log)
        runner.finished.connect(runner.deleteLater)
        self._runner = runner
        self._running_lane = lane_w
        lane_w.running = True
        lane_w.header.dot.setStyleSheet(
            "background:#7ce495; border-radius:4px;")
        d, t = lane_w.lane.get("progress", (0, 0))
        lane_w.header.set_state(True, d, t)
        runner.start()

    def pause_lane(self, lane_w):
        """⏸: frena el run del carril (el paso actual queda EN ESPERA)
        y vacía la cola de "Ejecutar todo"."""
        if self._runner is not None and lane_w is self._running_lane:
            self._queue = []
            self._runner.stop()

    def _step_started(self, step_dir, title):
        w = self._running_lane
        if w is not None:
            try:
                w.header.progress_lbl.setText(f"ejecutando: {title}")
            except RuntimeError:
                pass  # un reload del panel gemelo destruyó el widget

    def _step_done(self, step_dir, status):
        # el runner ya escribió step/conversacion/resultado en disco:
        # avisar al panel gemelo para que refleje el avance en vivo
        self.mutated.emit()

    def _lane_finished(self):
        self._runner = None
        self._running_lane = None
        self.reload()
        self.mutated.emit()
        # "Ejecutar todo": encadenar el siguiente carril con pendientes
        while self._queue:
            d = self._queue.pop(0)
            w = self._lane_widget_by_dir(d)
            if w is not None and any(
                    c.get("status") in ("wait", "fail")
                    for c in w.lane["cards"]):
                self._start_run(w)
                return

    def set_lane_collapsed(self, lane, collapsed):
        """Persiste el estado plegado del carril en lane.json."""
        d = lane.get("dir")
        if not d:
            return
        try:
            meta = _read_json(os.path.join(d, "lane.json")) or {}
            meta["collapsed"] = bool(collapsed)
            _write_json(os.path.join(d, "lane.json"), meta)
        except OSError:
            pass
        self.mutated.emit()

    def open_step_file(self, p):
        """Chip de archivo de la tarjeta → abrir en el editor.
        `p` puede ser relativo al workspace o absoluto (adjuntos)."""
        if not p:
            return
        full = p if os.path.isabs(p) else os.path.join(self.root, p)
        full = os.path.realpath(full)
        if os.path.exists(full):
            self.open_file_requested.emit(full)

    def show_lane_log(self, lane):
        """▤ del carril: diálogo con los ejecucion.log de sus pasos."""
        parts = []
        lane_dir = lane.get("dir")
        if lane_dir:
            try:
                steps = sorted(os.listdir(lane_dir))
            except OSError:
                steps = []
            for s in steps:
                lp = os.path.join(lane_dir, s, "ejecucion.log")
                if s.startswith(STEP_PREFIX) and os.path.isfile(lp):
                    try:
                        with open(lp, encoding="utf-8", errors="replace") as f:
                            parts.append(f"════ {s} ════\n{f.read()}")
                    except OSError:
                        pass
        text = "\n".join(parts) or (
            "(sin ejecuciones todavía — el log aparece tras correr el "
            "carril)")
        LogDialog(f"Log — {lane.get('name', '')}", text, self).exec()

    # ---- Acciones ----

    def add_step(self, lane):
        """＋ Paso del carril: crea paso-NNN en disco y abre el editor
        directo (sin popup de título — se edita en el StepDialog)."""
        lane_dir = lane.get("dir")
        if not lane_dir:
            return
        title = "Nuevo paso"
        n = 1
        try:
            nums = [int(m.group(1)) for d in os.listdir(lane_dir)
                    if (m := re.match(STEP_PREFIX + r"(\d+)", d))]
            n = max(nums, default=0) + 1
        except OSError:
            pass
        sd = os.path.join(lane_dir, f"{STEP_PREFIX}{n:03d}")
        try:
            os.makedirs(os.path.join(sd, "archivos"), exist_ok=True)
            _write_json(os.path.join(sd, "step.json"),
                        {"title": title, "status": "wait"})
        except OSError:
            return
        self.edit_step({"title": title, "status": "wait", "dir": sd})

    def edit_step(self, card):
        """Clic en tarjeta: editor del paso (requerimientos.md, adjuntos)."""
        if not card.get("dir"):
            return
        if StepDialog(card, self).exec():
            self.reload()
            self.mutated.emit()

    def edit_lane(self, lane):
        """Engranaje del carril: nombre + cron → lane.json."""
        if not lane.get("dir"):
            return
        if LaneDialog(lane, self).exec():
            self.reload()
            self.mutated.emit()

    def _add_lane(self):
        if not self.planner_dir:
            return
        name, ok = QInputDialog.getText(
            self, "Nuevo carril de tareas", "Nombre de la tarea:")
        if not ok:
            return
        name = name.strip() or "Nueva tarea"
        n = 1
        try:
            nums = [int(m.group(1)) for d in os.listdir(self.planner_dir)
                    if (m := re.match(LANE_PREFIX + r"(\d+)", d))]
            n = max(nums, default=0) + 1
        except OSError:
            pass
        slug = _slugify(name)
        dname = f"{LANE_PREFIX}{n:03d}" + (f"-{slug}" if slug else "")
        lane_dir = os.path.join(self.planner_dir, dname)
        step_dir = os.path.join(lane_dir, STEP_PREFIX + "001")
        try:
            os.makedirs(step_dir, exist_ok=True)
            _write_json(os.path.join(lane_dir, "lane.json"), {"name": name})
            _write_json(os.path.join(step_dir, "step.json"),
                        {"title": name, "status": "wait"})
        except OSError:
            return
        self.reload()
        self.mutated.emit()
