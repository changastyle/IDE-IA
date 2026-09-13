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
import json
import os
import re
import unicodedata

from PySide6.QtCore import Qt, QSize, QPointF, QRectF
from PySide6.QtGui import QIcon, QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QToolButton, QScrollArea, QSizePolicy, QInputDialog,
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
    """Ficha de adjunto: ícono doc/imagen + nombre en mono."""

    def __init__(self, kind, name, parent=None):
        super().__init__(parent)
        self.setObjectName("fileChip")
        self.setStyleSheet(
            "QFrame#fileChip { background:#1a1d22; border:1px solid #2a2d33;"
            " border-radius:6px; }"
            "QFrame#fileChip:hover { border-color:#4a4e57; }")
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
    """Tarjeta de tarea: cabecera + material + conversación + tests."""

    def __init__(self, num, data, parent=None):
        super().__init__(parent)
        self.setObjectName("plannerCard")
        status = data.get("status", "wait")
        border = ("rgba(255,69,58,0.45)" if status == "fail" else "#33363c")
        self.setStyleSheet(
            "QFrame#plannerCard { background:#22252b;"
            f" border:1px solid {border}; border-radius:10px; }}"
            "QFrame#plannerCard:hover { border-color:#0a84ff; }")
        self.setFixedWidth(300)
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
            t2 = QLabel(data.get("sub2", ""))
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
        cap = QLabel("MATERIAL EXTRA")
        cap.setStyleSheet(CAPTION)
        v.addWidget(cap)
        for kind, name in data.get("materials", []):
            v.addWidget(FileChip(kind, name))

        # ---- Historial de conversación ----
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
        badge = QWidget()
        badge.setStyleSheet(
            "background:rgba(124,228,149,0.08); border-top-left-radius:8px;"
            "border-top-right-radius:8px;")
        bh = QHBoxLayout(badge)
        bh.setContentsMargins(10, 4, 8, 4)
        bh.setSpacing(6)
        bic = QLabel()
        bic.setPixmap(_icon("check_w").pixmap(11, 11))
        bh.addWidget(bic)
        blb = QLabel("CONCLUSIÓN ACEPTADA")
        blb.setStyleSheet("color:#7ce495; font-size:9px; font-weight:bold;"
                          "letter-spacing:0.5px;")
        bh.addWidget(blb)
        bh.addStretch(1)
        cv.addWidget(badge)
        for role, text in data.get("messages", []):
            cv.addWidget(ConvRow(role, text))
        cv.addStretch(1)
        link = QLabel(f"Ver conversación completa ({data.get('conv_n', 0)})")
        link.setStyleSheet("color:#0a84ff; font-size:10px; padding-left:10px;")
        link.setCursor(Qt.PointingHandCursor)
        cv.addWidget(link)
        v.addWidget(conv, 1)

        # ---- Tests propuestos ----
        cap = QLabel("TESTS PROPUESTOS")
        cap.setStyleSheet(CAPTION)
        v.addSpacing(2)
        v.addWidget(cap)
        tests = QFrame()
        tests.setObjectName("testsBox")
        tests.setStyleSheet(
            "QFrame#testsBox, QFrame#testsBox { background:#1a1d22;"
            " border:1px solid #2a2d33; border-radius:8px; }")
        tv = QVBoxLayout(tests)
        tv.setContentsMargins(1, 2, 1, 4)
        tv.setSpacing(0)
        for name, result in data.get("tests", []):
            tv.addWidget(TestRow(name, result))
        tv.addStretch(1)
        summary = QLabel(data.get("summary", ""))
        summary.setStyleSheet(
            f"color:{data.get('summary_color', '#6b7280')}; font-size:10px;"
            "padding:6px 12px;")
        tv.addWidget(summary)
        v.addWidget(tests)


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

    def __init__(self, lane, on_play, on_pause, on_run, parent=None):
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
        h.addWidget(b_cfg)
        b_run = QPushButton("Ejecutar todo")
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


class Lane(QFrame):
    """Un carril: header + pipeline horizontal de tarjetas."""

    def __init__(self, lane, parent=None):
        super().__init__(parent)
        self.setObjectName("lane")
        self.setStyleSheet(
            "QFrame#lane { background:#1e2126; border:1px solid #2a2d33;"
            " border-radius:10px; }"
            "QFrame#lane QLabel { background:transparent; border:none; }"
            "QScrollArea { border:none; background:transparent; }"
            "QScrollBar:horizontal { height:0px; background:transparent; }"
            "QScrollBar:vertical { width:0px; background:transparent; }")
        self.lane = lane
        self.running = False
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 10)
        v.setSpacing(8)
        self.header = LaneHeader(
            lane, on_play=self._play, on_pause=self._pause,
            on_run=self._run_all)
        v.addWidget(self.header)
        # Pipeline horizontal
        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setFixedHeight(500)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        self.flow = QHBoxLayout(inner)
        self.flow.setContentsMargins(2, 2, 2, 2)
        self.flow.setSpacing(6)
        self._build_cards()
        self.area.setWidget(inner)
        v.addWidget(self.area)

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
            w = PlannerCard(i + 1, card)
            self.flow.addWidget(w, 0, Qt.AlignTop)
            prev_status = card.get("status", "wait")
        self.flow.addStretch(1)

    def _play(self):
        self.running = True
        self.header.dot.setStyleSheet("background:#7ce495; border-radius:4px;")
        done, total = self.lane.get("progress", (0, 0))
        self.header.set_state(True, done, total)

    def _pause(self):
        self.running = False
        self.header.dot.setStyleSheet("background:#eab308; border-radius:4px;")
        done, total = self.lane.get("progress", (0, 0))
        self.header.set_state(False, done, total)

    def _run_all(self):
        self._play()


class PlannerPanel(QWidget):
    """AI Autonomous Workflow Planner: carriles con tareas secuenciales
    ejecutadas por agentes IA, persistidos en <root>/ng-studio-stuff/planner/."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.root = ""
        self.planner_dir = ""
        self.setStyleSheet(
            "QWidget { background:#16181c; }"
            "QScrollArea { border:none; }"
            "QScrollBar:vertical { width:0px; background:transparent; }"
            "QScrollBar:horizontal { height:0px; background:transparent; }")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)
        page = QWidget()
        page.setStyleSheet("background:transparent;")
        pv = QVBoxLayout(page)
        pv.setContentsMargins(12, 12, 12, 12)
        pv.setSpacing(10)
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
        while self.lanes_box.count():
            it = self.lanes_box.takeAt(0)
            w = it.widget()
            if w is not None and w is not self._empty:
                w.deleteLater()
        lanes = self._load_lanes() if self.planner_dir else []
        for lane in lanes:
            self.lanes_box.addWidget(Lane(lane))
        if not lanes:
            self.lanes_box.insertWidget(0, self._empty)
            self._empty.show()

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
                "progress": (done, len(cards)), "dir": d, "cards": cards}

    def _load_step(self, sd, sname):
        meta = _read_json(os.path.join(sd, "step.json")) or {}
        card = {"title": meta.get("title") or _pretty_name(sname, STEP_PREFIX),
                "status": meta.get("status", "wait")}
        mats = []
        if os.path.exists(os.path.join(sd, "requerimientos.md")):
            mats.append(("doc", "requerimientos.md"))
        archivos = os.path.join(sd, "archivos")
        try:
            for f in sorted(os.listdir(archivos)):
                if not f.startswith("."):
                    kind = ("img" if os.path.splitext(f)[1].lower() in IMG_EXTS
                            else "doc")
                    mats.append((kind, f))
        except OSError:
            pass
        card["materials"] = mats
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
        if not mats and not conv and not tests:
            card["compact"] = True
            card["subtitle"] = meta.get("subtitle") or "Esperando definición de pasos"
        return card

    # ---- Acciones ----

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
