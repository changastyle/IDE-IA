# -*- coding: utf-8 -*-
"""Lógica de IA para la nueva UI: providers, modelos, preferencias, voz.

Migrado desde chat_ia.py para separar la lógica de IA del panel de chat.
"""
import os
import json
import time
import subprocess
import sys

from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QIcon, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QCheckBox, QSpinBox, QListWidget, QListWidgetItem,
    QTabWidget, QWidget, QApplication,
)

APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICONS_DIR = os.path.join(APP_DIR, "iconos")

LMSTUDIO = os.environ.get("LMSTUDIO_URL", "http://172.27.247.113:1234")

CLOUD_PRESETS = [
    ("OpenCode Zen", "https://opencode.ai/zen/v1"),
    ("OpenCode Go", "https://opencode.ai/zen/go/v1"),
    ("OpenRouter", "https://openrouter.ai/api/v1"),
    ("Groq", "https://api.groq.com/openai/v1"),
    ("DeepSeek", "https://api.deepseek.com/v1"),
    ("Mistral", "https://api.mistral.ai/v1"),
    ("xAI (Grok)", "https://api.x.ai/v1"),
    ("Gemini (OpenAI-compat)", "https://generativelanguage.googleapis.com/v1beta/openai"),
    ("Ollama (local)", "http://localhost:11434/v1"),
]

AUDIO_KEYWORDS = ("whisper", "audio", "qwen2-audio", "voxtral", "belle-whisper")

SOUNDS = {
    "rec_start": "/System/Library/Sounds/Pop.aiff",
    "rec_stop": "/System/Library/Sounds/Glass.aiff",
    "send": "/System/Library/Sounds/Ping.aiff",
    "done": "/System/Library/Sounds/Hero.aiff",
}


# ---- Utilidades ----

def api_url(base, path):
    base = (base or "").rstrip("/")
    if base.endswith("/v1"):
        return base + path
    return base + "/v1" + path


def fetch_models(base, key=""):
    import requests
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    r = requests.get(api_url(base, "/models"), headers=headers, timeout=8)
    r.raise_for_status()
    r.encoding = "utf-8"
    return [m["id"] for m in r.json().get("data", []) if "embed" not in m["id"].lower()]


def is_audio_model(model_id):
    mid = model_id.lower()
    return any(k in mid for k in AUDIO_KEYWORDS)


def filter_audio_models(all_models):
    out = []
    for ref in all_models:
        _, _, model = ref.partition("::")
        if is_audio_model(model):
            out.append(ref)
    return out


def play_sound(name):
    path = SOUNDS.get(name)
    if not path or not os.path.exists(path):
        return
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["afplay", path],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


# ---- Diálogo: Añadir provider ----

class ProviderDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Añadir provider")
        self.resize(520, 340)
        v = QVBoxLayout(self)
        self.tabs = QTabWidget()
        v.addWidget(self.tabs, 1)

        local_w = QWidget()
        form = QFormLayout(local_w)
        self.local_name = QLineEdit()
        self.local_name.setPlaceholderText("ej: LM Studio oficina")
        self.local_base = QLineEdit()
        self.local_base.setPlaceholderText("http://localhost:1234")
        self.local_key = QLineEdit()
        self.local_key.setEchoMode(QLineEdit.Password)
        form.addRow("Nombre:", self.local_name)
        form.addRow("Base URL:", self.local_base)
        form.addRow("API key (opcional):", self.local_key)
        test_row = QHBoxLayout()
        self.test_dot = QLabel("⚪")
        self.test_dot.setFixedWidth(18)
        self.test_dot.setAlignment(Qt.AlignCenter)
        self.test_lbl = QLabel("Sin probar")
        self.test_lbl.setStyleSheet("color:#888;")
        self.test_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._last_error = ""
        self.b_copy_err = QPushButton("📋")
        self.b_copy_err.setFixedSize(24, 24)
        self.b_copy_err.setToolTip("Copiar error al portapapeles")
        self.b_copy_err.clicked.connect(self._copy_error)
        self.b_copy_err.setVisible(False)
        b_test = QPushButton("Test Connection")
        b_test.clicked.connect(self._test_connection)
        test_row.addWidget(self.test_dot)
        test_row.addWidget(self.test_lbl, 1)
        test_row.addWidget(self.b_copy_err)
        test_row.addWidget(b_test)
        form.addRow("", test_row)
        self.tabs.addTab(local_w, "Local")

        cloud_w = QWidget()
        cv = QVBoxLayout(cloud_w)
        cv.addWidget(QLabel("Elegí un provider — la Base URL se completa sola:"))
        self.cloud_list = QListWidget()
        for name, base in CLOUD_PRESETS:
            self.cloud_list.addItem(f"{name}   ({base})")
        cv.addWidget(self.cloud_list, 1)
        krow = QHBoxLayout()
        krow.addWidget(QLabel("API key:"))
        self.cloud_key = QLineEdit()
        self.cloud_key.setEchoMode(QLineEdit.Password)
        self.cloud_key.setPlaceholderText("pega tu API key aquí")
        krow.addWidget(self.cloud_key, 1)
        cv.addLayout(krow)
        self.tabs.addTab(cloud_w, "Providers")
        self.cloud_list.setCurrentRow(0)

        row = QHBoxLayout()
        b_ok = QPushButton("OK")
        b_ok.setDefault(True)
        b_ok.clicked.connect(self.accept)
        b_cancel = QPushButton("Cancelar")
        b_cancel.clicked.connect(self.reject)
        row.addStretch(1)
        row.addWidget(b_cancel)
        row.addWidget(b_ok)
        v.addLayout(row)

    def _test_connection(self):
        base = self.local_base.text().strip().rstrip("/")
        if not base:
            self._set_test_result("⚪", "Escribí una Base URL", "#888")
            return
        if "://" not in base:
            base = "http://" + base
        self._set_test_result("🟡", "Probando…", "#eab308")
        QApplication.processEvents()
        try:
            ids = fetch_models(base, self.local_key.text().strip())
            self._last_error = ""
            self.b_copy_err.setVisible(False)
            self._set_test_result("🟢", f"Conectado — {len(ids)} modelo(s)", "#22c55e")
        except Exception as e:
            full = f"URL probada: {base}/v1/models\n{type(e).__name__}: {e}"
            self._last_error = full
            msg = str(e)
            if "No route to host" in msg:
                msg = "Host inalcanzable (¿IP correcta? ¿misma red?)"
            elif "Connection refused" in msg:
                msg = "Conexión rechazada (¿puerto correcto? ¿server encendido?)"
            elif "timed out" in msg:
                msg = "Timeout (¿firewall?)"
            elif "404" in msg:
                msg = "404 Not Found — ¿falta el puerto? (ej: :1234)"
            self._set_test_result("🔴", msg, "#ef4444")
            self.b_copy_err.setVisible(True)

    def _copy_error(self):
        if self._last_error:
            QApplication.clipboard().setText(self._last_error)
            self.b_copy_err.setText("✓")
            QTimer.singleShot(1200, lambda: self.b_copy_err.setText("📋"))

    def _set_test_result(self, dot, text, color):
        self.test_dot.setText(dot)
        self.test_lbl.setText(text)
        self.test_lbl.setStyleSheet(f"color:{color};")

    def values(self):
        if self.tabs.currentIndex() == 0:
            base = self.local_base.text().strip().rstrip("/")
            if base and "://" not in base:
                base = "http://" + base
            return (self.local_name.text().strip(), base,
                    self.local_key.text().strip())
        row = self.cloud_list.currentRow()
        if row < 0:
            return "", "", ""
        name, base = CLOUD_PRESETS[row]
        return name, base, self.cloud_key.text().strip()


# ---- Diálogo: Modelos y providers (pin models) ----

class ModelPickerDialog(QDialog):
    def __init__(self, parent, providers, pinned):
        super().__init__(parent)
        self.setWindowTitle("Modelos y providers")
        self.resize(580, 480)
        self.providers = {k: dict(v) for k, v in providers.items()}
        self.pinned = list(pinned)
        self.cache = {}
        v = QVBoxLayout(self)
        prow = QHBoxLayout()
        prow.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.currentTextChanged.connect(lambda _: self._show_provider())
        prow.addWidget(self.provider_combo, 1)
        b_add = QPushButton("＋")
        b_add.setFixedWidth(32)
        b_add.setToolTip("Añadir provider")
        b_add.clicked.connect(self._add_provider)
        b_del = QPushButton("−")
        b_del.setFixedWidth(32)
        b_del.setToolTip("Quitar provider")
        b_del.clicked.connect(self._del_provider)
        prow.addWidget(b_add)
        prow.addWidget(b_del)
        v.addLayout(prow)
        self.picker_filter = QLineEdit()
        self.picker_filter.setPlaceholderText("🔍 filtrar modelos…")
        self.picker_filter.setClearButtonEnabled(True)
        self.picker_filter.textChanged.connect(lambda _: self._show_provider())
        v.addWidget(self.picker_filter)
        self.model_list = QListWidget()
        v.addWidget(self.model_list, 1)
        v.addWidget(QLabel("Marca (📌) los modelos que quieras fijar arriba del combo."))
        brow = QHBoxLayout()
        b_ref = QPushButton("↻ Re-descubrir")
        b_ref.clicked.connect(self._show_provider)
        b_ok = QPushButton("OK")
        b_ok.setDefault(True)
        b_ok.clicked.connect(self._ok)
        brow.addWidget(b_ref)
        brow.addStretch(1)
        brow.addWidget(b_ok)
        v.addLayout(brow)
        for name in self.providers:
            self.provider_combo.addItem(name)
        self._show_provider()

    def _discover_one(self, name):
        cfg = self.providers.get(name, {})
        base = cfg.get("base", "")
        if base and "://" not in base:
            base = "http://" + base
        try:
            return fetch_models(base, cfg.get("key", "")), None
        except Exception as e:
            return [], f"sin conexión con {name}: {e}"

    def _show_provider(self):
        self.model_list.clear()
        name = self.provider_combo.currentText()
        if not name:
            return
        ids, err = self.cache.get(name, (None, None))
        if ids is None:
            ids, err = self._discover_one(name)
            self.cache[name] = (ids, err)
        if err:
            self.model_list.addItem(f"⚠ {err}")
            return
        text = self.picker_filter.text().strip().lower()
        n = 0
        for mid in ids:
            if text and text not in mid.lower():
                continue
            ref = f"{name}::{mid}"
            it = QListWidgetItem(("📌 " if ref in self.pinned else "") + mid)
            it.setData(Qt.UserRole, ref)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if ref in self.pinned else Qt.Unchecked)
            self.model_list.addItem(it)
            n += 1
        if n == 0:
            self.model_list.addItem("(sin coincidencias)")

    def _add_provider(self):
        dlg = ProviderDialog(self)
        if dlg.exec():
            name, base, key = dlg.values()
            if not name or not base:
                return
            self.providers[name] = {"base": base, "key": key}
            if self.provider_combo.findText(name) < 0:
                self.provider_combo.blockSignals(True)
                self.provider_combo.addItem(name)
                self.provider_combo.blockSignals(False)
            self.provider_combo.setCurrentText(name)

    def _del_provider(self):
        name = self.provider_combo.currentText()
        if name and self.provider_combo.count() > 1:
            self.providers.pop(name, None)
            self.provider_combo.removeItem(self.provider_combo.currentIndex())
            self.pinned = [p for p in self.pinned if not p.startswith(name + "::")]

    def _ok(self):
        name = self.provider_combo.currentText()
        keep = [p for p in self.pinned if not p.startswith(name + "::")]
        for i in range(self.model_list.count()):
            it = self.model_list.item(i)
            ref = it.data(Qt.UserRole)
            if ref and it.checkState() == Qt.Checked:
                keep.append(ref)
        self.pinned = keep
        self.accept()


# ---- Diálogo: Preferencias ----

WHISPER_MODELS = [
    ("tiny",     "75 MB",  "Más rápido, menor calidad. Ideal para pruebas."),
    ("base",     "145 MB", "Balance bueno. Recomendado para uso diario."),
    ("small",    "480 MB", "Mejor calidad. Más lento en CPU."),
    ("medium",   "1.5 GB", "Alta calidad. Lento en CPU."),
    ("large-v3", "3 GB",   "Máxima calidad. Muy lento sin GPU."),
]

# Modelos de faster-whisper en HuggingFace: repo + subcarpetas
WHISPER_HF_REPOS = {
    "tiny":     "Systran/faster-whisper-tiny",
    "base":     "Systran/faster-whisper-base",
    "small":    "Systran/faster-whisper-small",
    "medium":   "Systran/faster-whisper-medium",
    "large-v3": "Systran/faster-whisper-large-v3",
}


def whisper_model_cache_dir(model_name):
    """Devuelve la ruta al cache del modelo en HuggingFace."""
    repo = WHISPER_HF_REPOS.get(model_name, "")
    if not repo:
        return None
    # HuggingFace guarda en ~/.cache/huggingface/hub/models--{org}--{name}
    safe = repo.replace("/", "--")
    return os.path.expanduser(f"~/.cache/huggingface/hub/models--{safe}")


def whisper_model_disk_size(model_name):
    """Devuelve el tamaño en disco del modelo descargado, o None si no existe."""
    d = whisper_model_cache_dir(model_name)
    if not d or not os.path.isdir(d):
        return None
    total = 0
    for root, dirs, files in os.walk(d):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def is_whisper_model_downloaded(model_name):
    """Verifica si un modelo de whisper está descargado."""
    d = whisper_model_cache_dir(model_name)
    if not d or not os.path.isdir(d):
        return False
    # Debe tener al menos un archivo .bin o .safetensors
    for root, dirs, files in os.walk(d):
        for f in files:
            if f.endswith((".bin", ".safetensors")):
                return True
    return False


def delete_whisper_model(model_name):
    """Borra un modelo de whisper del cache."""
    d = whisper_model_cache_dir(model_name)
    if d and os.path.isdir(d):
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def human_size(n):
    """Convierte bytes a formato legible."""
    if n is None:
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


class WhisperDownloadThread(QThread):
    """Descarga un modelo de faster-whisper en background."""
    progress = Signal(int, str)  # (porcentaje, mensaje)
    finished_ok = Signal(str)    # model_name
    failed = Signal(str)        # error

    def __init__(self, model_name, parent=None):
        super().__init__(parent)
        self.model_name = model_name

    def run(self):
        try:
            self.progress.emit(0, f"Descargando '{self.model_name}'…")
            from huggingface_hub import snapshot_download
            repo = WHISPER_HF_REPOS.get(self.model_name)
            if not repo:
                self.failed.emit(f"Modelo desconocido: {self.model_name}")
                return
            # snapshot_download descarga todos los archivos del repo
            # No hay progreso granular fácil, pero al menos sabemos que empezó
            self.progress.emit(10, f"Conectando a HuggingFace…")
            path = snapshot_download(
                repo_id=repo,
                allow_patterns=["*.bin", "*.safetensors", "*.json", "*.txt", "tokenizer/*"],
            )
            self.progress.emit(100, f"✅ Descarga completa")
            self.finished_ok.emit(self.model_name)
        except ImportError:
            self.failed.emit("huggingface_hub no instalado. Instalá con: pip install huggingface_hub")
        except Exception as e:
            self.failed.emit(str(e))


class PrefsDialog(QDialog):
    """Preferencias con pestañas: Modelos, Voz, Contexto."""
    def __init__(self, parent, prefs, all_models):
        super().__init__(parent)
        self.setWindowTitle("⚙ Preferencias")
        self.resize(620, 620)
        self.prefs = dict(prefs)
        self.all_models = all_models
        self._dl_thread = None
        self._selected_whisper = prefs.get("whisper_model", "base")
        v = QVBoxLayout(self)
        self.tabs = QTabWidget()
        v.addWidget(self.tabs, 1)

        # ---- Pestaña 1: Modelos ----
        models_w = QWidget()
        form = QFormLayout(models_w)
        self.combo_primary = QComboBox()
        self.combo_secondary = QComboBox()
        self.combo_vision = QComboBox()
        self.combo_polish = QComboBox()
        for c in (self.combo_primary, self.combo_secondary, self.combo_vision,
                  self.combo_polish):
            c.addItem("(usar el del combo)", "")
            for m in all_models:
                c.addItem(m)
        self._set_combo(self.combo_primary, prefs.get("primary_model", ""))
        self._set_combo(self.combo_secondary, prefs.get("secondary_model", ""))
        self._set_combo(self.combo_vision, prefs.get("vision_model", ""))
        self._set_combo(self.combo_polish, prefs.get("polish_model", ""))
        form.addRow("Modelo primario:", self.combo_primary)
        form.addRow("Modelo secundario:", self.combo_secondary)
        form.addRow("Modelo para imágenes:", self.combo_vision)
        self.combo_polish.setToolTip(
            "Modelo liviano (ideal local) que usa el botón ✨ para pulir texto.")
        form.addRow("Modelo para magia (✨ pulir):", self.combo_polish)
        self.tabs.addTab(models_w, "Modelos")

        # ---- Pestaña 2: Voz ----
        voice_w = QWidget()
        vv = QVBoxLayout(voice_w)
        vv.setSpacing(8)

        # Modo de transcripción
        mode_group = QFormLayout()
        self.combo_voice_mode = QComboBox()
        self.combo_voice_mode.addItem("Local (faster-whisper, offline)", "local")
        self.combo_voice_mode.addItem("IA (LM Studio / provider)", "ia")
        cur_mode = "ia" if prefs.get("voice_ia", False) else "local"
        idx = self.combo_voice_mode.findData(cur_mode)
        if idx >= 0:
            self.combo_voice_mode.setCurrentIndex(idx)
        self.combo_voice_mode.currentTextChanged.connect(self._on_voice_mode_change)
        mode_group.addRow("Modo de transcripción:", self.combo_voice_mode)
        vv.addLayout(mode_group)

        # ---- Sección: faster-whisper local ----
        self.local_group = QWidget()
        lg = QVBoxLayout(self.local_group)
        lg.setContentsMargins(0, 8, 0, 0)
        lg.setSpacing(6)
        lg.addWidget(QLabel(
            "<b>faster-whisper local</b> — transcripción offline, sin internet, sin Docker.\n"
            "Los modelos se guardan en ~/.cache/huggingface/ y se descargan una sola vez."))

        # Tabla de modelos whisper
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar
        self.whisper_table = QTableWidget()
        self.whisper_table.setColumnCount(5)
        self.whisper_table.setHorizontalHeaderLabels(
            ["", "Modelo", "Tamaño", "En disco", "Estado"])
        self.whisper_table.verticalHeader().setVisible(False)
        self.whisper_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.whisper_table.setSelectionMode(QTableWidget.SingleSelection)
        self.whisper_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.whisper_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.whisper_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.whisper_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.whisper_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.whisper_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.whisper_table.cellClicked.connect(self._on_whisper_row_click)
        lg.addWidget(self.whisper_table)
        self._refresh_whisper_table()

        # Botones de gestión de modelos
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self.btn_dl = QPushButton("⬇ Descargar")
        self.btn_dl.clicked.connect(self._download_whisper)
        btn_row.addWidget(self.btn_dl)
        self.btn_del_model = QPushButton("🗑 Borrar")
        self.btn_del_model.clicked.connect(self._delete_whisper)
        btn_row.addWidget(self.btn_del_model)
        self.btn_test_local = QPushButton("🔍 Probar")
        self.btn_test_local.clicked.connect(self._test_whisper_local)
        btn_row.addWidget(self.btn_test_local)
        btn_row.addStretch(1)
        lg.addLayout(btn_row)

        # Barra de progreso de descarga
        self.dl_progress = QProgressBar()
        self.dl_progress.setVisible(False)
        self.dl_progress.setTextVisible(True)
        lg.addWidget(self.dl_progress)

        # Label de estado
        self.lbl_test_local = QLabel("")
        self.lbl_test_local.setWordWrap(True)
        self.lbl_test_local.setStyleSheet("font-size:11px;")
        lg.addWidget(self.lbl_test_local)

        # Estado de faster-whisper
        self.lbl_whisper_status = QLabel("")
        self.lbl_whisper_status.setWordWrap(True)
        self.lbl_whisper_status.setStyleSheet("font-size:11px; color:#888;")
        lg.addWidget(self.lbl_whisper_status)
        self._check_whisper_status()
        vv.addWidget(self.local_group)

        # ---- Sección: IA provider ----
        self.ia_group = QWidget()
        ig = QVBoxLayout(self.ia_group)
        ig.setContentsMargins(0, 8, 0, 0)
        ig.setSpacing(4)
        ig.addWidget(QLabel(
            "<b>IA via provider</b> — usa /v1/audio/transcriptions de LM Studio u otro provider.\n"
            "Necesitás un modelo de audio (whisper, qwen2-audio) cargado en el provider."))
        ig_form = QFormLayout()
        self.combo_voice = QComboBox()
        self.combo_voice.addItem("(usar el del combo)", "")
        audio_models = filter_audio_models(all_models)
        if not audio_models:
            self.combo_voice.addItem("(ningún modelo de audio encontrado)")
            self.combo_voice.setItemData(1, "", Qt.UserRole)
        else:
            for m in audio_models:
                self.combo_voice.addItem(m)
        self._set_combo(self.combo_voice, prefs.get("voice_model", ""))
        self.combo_voice.setToolTip(
            "Solo aparecen modelos que soportan audio (whisper, qwen2-audio, etc.).")
        ig_form.addRow("Modelo para voz:", self.combo_voice)
        ig.addLayout(ig_form)
        test_ia_row = QHBoxLayout()
        self.btn_test_ia = QPushButton("🔍 Probar conexión IA")
        self.btn_test_ia.clicked.connect(self._test_voice_ia)
        test_ia_row.addWidget(self.btn_test_ia)
        self.lbl_test_ia = QLabel("")
        self.lbl_test_ia.setWordWrap(True)
        self.lbl_test_ia.setStyleSheet("font-size:11px;")
        test_ia_row.addWidget(self.lbl_test_ia, 1)
        ig.addLayout(test_ia_row)
        vv.addWidget(self.ia_group)

        # Auto-enviar
        self.chk_auto_send = QCheckBox("Auto-enviar voz al terminar transcripción")
        self.chk_auto_send.setChecked(bool(prefs.get("auto_send_voice", False)))
        self.chk_auto_send.setToolTip("Si está marcado, envía automáticamente después de transcribir.")
        vv.addWidget(self.chk_auto_send)

        self._on_voice_mode_change()
        self.tabs.addTab(voice_w, "🎙 Voz")

        # ---- Pestaña 3: Contexto ----
        ctx_w = QWidget()
        ctx_form = QFormLayout(ctx_w)
        self.spin_max_tokens = QSpinBox()
        self.spin_max_tokens.setRange(1000, 1000000)
        self.spin_max_tokens.setSingleStep(5000)
        self.spin_max_tokens.setValue(int(prefs.get("max_context_tokens", 50000)))
        ctx_form.addRow("Auto-resumir si el contexto pasa de (tokens):", self.spin_max_tokens)
        self.chk_auto_summarize = QCheckBox("Resumir automáticamente al superar el límite")
        self.chk_auto_summarize.setChecked(bool(prefs.get("auto_summarize", True)))
        ctx_form.addRow("", self.chk_auto_summarize)
        self.spin_budget = QSpinBox()
        self.spin_budget.setRange(1000, 10000000)
        self.spin_budget.setSingleStep(10000)
        self.spin_budget.setValue(int(prefs.get("token_budget", 50000)))
        ctx_form.addRow("Budget de tokens para esta carpeta:", self.spin_budget)
        self.tabs.addTab(ctx_w, "Contexto")

        # ---- Pestaña 4: Ejecución ----
        exec_w = QWidget()
        exec_form = QFormLayout(exec_w)
        # Límite de herramientas
        self.chk_tool_limit = QCheckBox("Habilitar límite de herramientas por respuesta")
        self.chk_tool_limit.setChecked(bool(prefs.get("tool_limit_enabled", True)))
        self.chk_tool_limit.setToolTip(
            "Si está marcado, la IA tiene un máximo de herramientas que puede usar\n"
            "en una sola respuesta. Si no, puede usar todas las que necesite.")
        exec_form.addRow("", self.chk_tool_limit)
        self.spin_max_tools = QSpinBox()
        self.spin_max_tools.setRange(1, 500)
        self.spin_max_tools.setSingleStep(5)
        self.spin_max_tools.setValue(int(prefs.get("max_tools", 50)))
        self.spin_max_tools.setToolTip(
            "Cantidad máxima de herramientas (read_file, save_file, edit_file, etc.)\n"
            "que la IA puede usar en una sola respuesta.")
        exec_form.addRow("Máximo de herramientas por respuesta:", self.spin_max_tools)
        # Timeout de request
        exec_form.addRow(QLabel(""))
        exec_form.addRow(QLabel(
            "<b>Timeout de requests</b>\n"
            "Si la IA tarda más de este tiempo en responder, la request se cancela."))
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(10, 3600)
        self.spin_timeout.setSingleStep(30)
        self.spin_timeout.setSuffix(" segundos")
        self.spin_timeout.setValue(int(prefs.get("request_timeout", 600)))
        self.spin_timeout.setToolTip(
            "Tiempo máximo de espera por una respuesta de la IA.\n"
            "Si pasa este tiempo sin respuesta, se cancela la request.\n"
            "Default: 600 segundos (10 minutos).")
        exec_form.addRow("Timeout máximo por request:", self.spin_timeout)
        self.tabs.addTab(exec_w, "⚙ Ejecución")

        # ---- Botones ----
        row = QHBoxLayout()
        btn_ok = QPushButton("Guardar")
        btn_ok.setObjectName("success")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        row.addStretch(1)
        row.addWidget(btn_cancel)
        row.addWidget(btn_ok)
        v.addLayout(row)

    # ---- Voz: faster-whisper ----

    def _on_voice_mode_change(self):
        mode = self.combo_voice_mode.currentData()
        self.local_group.setVisible(mode == "local")
        self.ia_group.setVisible(mode == "ia")

    def _check_whisper_status(self):
        try:
            import faster_whisper
            self.lbl_whisper_status.setText(
                f"✅ faster-whisper {faster_whisper.__version__} instalado")
        except ImportError:
            self.lbl_whisper_status.setText(
                "❌ faster-whisper no instalado. Instalá con: pip install faster-whisper")

    def _refresh_whisper_table(self):
        """Refresca la tabla de modelos whisper con estado de descarga."""
        from PySide6.QtWidgets import QTableWidgetItem, QRadioButton
        self.whisper_table.setRowCount(len(WHISPER_MODELS))
        for i, (name, size, desc) in enumerate(WHISPER_MODELS):
            # Radio button para seleccionar
            radio = QRadioButton()
            radio.setChecked(name == self._selected_whisper)
            radio.toggled.connect(lambda checked, n=name: self._on_whisper_radio(checked, n))
            self.whisper_table.setCellWidget(i, 0, radio)
            # Nombre + descripción
            self.whisper_table.setItem(i, 1, QTableWidgetItem(f"{name}\n{desc}"))
            # Tamaño esperado
            self.whisper_table.setItem(i, 2, QTableWidgetItem(size))
            # Tamaño en disco
            disk = whisper_model_disk_size(name)
            disk_str = human_size(disk) if disk else "—"
            self.whisper_table.setItem(i, 3, QTableWidgetItem(disk_str))
            # Estado
            if is_whisper_model_downloaded(name):
                status = QTableWidgetItem("✅ Descargado")
                status.setForeground(QColor("#22c55e"))
            else:
                status = QTableWidgetItem("⬇ No descargado")
                status.setForeground(QColor("#888"))
            self.whisper_table.setItem(i, 4, status)
        self.whisper_table.resizeRowsToContents()

    def _on_whisper_radio(self, checked, model_name):
        if checked:
            self._selected_whisper = model_name

    def _on_whisper_row_click(self, row, col):
        """Al clickear una fila, seleccionar el radio button."""
        from PySide6.QtWidgets import QRadioButton
        for i in range(self.whisper_table.rowCount()):
            w = self.whisper_table.cellWidget(i, 0)
            if w and isinstance(w, QRadioButton):
                w.setChecked(i == row)

    def _get_selected_whisper_row(self):
        """Devuelve la fila seleccionada o -1."""
        from PySide6.QtWidgets import QRadioButton
        for i in range(self.whisper_table.rowCount()):
            w = self.whisper_table.cellWidget(i, 0)
            if w and isinstance(w, QRadioButton) and w.isChecked():
                return i
        return -1

    def _download_whisper(self):
        """Descarga el modelo whisper seleccionado."""
        row = self._get_selected_whisper_row()
        if row < 0:
            self.lbl_test_local.setText("Seleccioná un modelo primero.")
            return
        model_name = WHISPER_MODELS[row][0]
        if is_whisper_model_downloaded(model_name):
            self.lbl_test_local.setText(f"El modelo '{model_name}' ya está descargado.")
            return
        self.dl_progress.setVisible(True)
        self.dl_progress.setValue(0)
        self.dl_progress.setFormat(f"Descargando {model_name}…")
        self.btn_dl.setEnabled(False)
        self.lbl_test_local.setText(f"Iniciando descarga de '{model_name}'…")
        self.lbl_test_local.setStyleSheet("font-size:11px; color:#eab308;")
        QApplication.processEvents()
        self._dl_thread = WhisperDownloadThread(model_name, self)
        self._dl_thread.progress.connect(self._on_dl_progress)
        self._dl_thread.finished_ok.connect(self._on_dl_done)
        self._dl_thread.failed.connect(self._on_dl_fail)
        self._dl_thread.start()

    def _on_dl_progress(self, pct, msg):
        self.dl_progress.setValue(pct)
        self.dl_progress.setFormat(msg)
        self.lbl_test_local.setText(msg)

    def _on_dl_done(self, model_name):
        self.dl_progress.setValue(100)
        self.dl_progress.setFormat(f"✅ {model_name} descargado")
        self.lbl_test_local.setText(f"✅ Modelo '{model_name}' descargado correctamente.")
        self.lbl_test_local.setStyleSheet("font-size:11px; color:#22c55e;")
        self.btn_dl.setEnabled(True)
        self.dl_progress.setVisible(False)
        self._refresh_whisper_table()

    def _on_dl_fail(self, err):
        self.dl_progress.setVisible(False)
        self.lbl_test_local.setText(f"❌ Error descargando: {err}")
        self.lbl_test_local.setStyleSheet("font-size:11px; color:#ef4444;")
        self.btn_dl.setEnabled(True)

    def _delete_whisper(self):
        """Borra el modelo whisper seleccionado del disco."""
        row = self._get_selected_whisper_row()
        if row < 0:
            self.lbl_test_local.setText("Seleccioná un modelo primero.")
            return
        model_name = WHISPER_MODELS[row][0]
        if not is_whisper_model_downloaded(model_name):
            self.lbl_test_local.setText(f"El modelo '{model_name}' no está descargado.")
            return
        from PySide6.QtWidgets import QMessageBox
        ret = QMessageBox.question(
            self, "Borrar modelo",
            f"¿Borrar el modelo '{model_name}' del disco?\n"
            f"Se liberará {human_size(whisper_model_disk_size(model_name))}.",
            QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            delete_whisper_model(model_name)
            self._refresh_whisper_table()
            self.lbl_test_local.setText(f"Modelo '{model_name}' borrado.")
            self.lbl_test_local.setStyleSheet("font-size:11px; color:#888;")

    def _test_whisper_local(self):
        """Prueba cargar faster-whisper con el modelo seleccionado."""
        row = self._get_selected_whisper_row()
        if row < 0:
            self.lbl_test_local.setText("Seleccioná un modelo primero.")
            return
        model_name = WHISPER_MODELS[row][0]
        if not is_whisper_model_downloaded(model_name):
            self.lbl_test_local.setText(
                f"El modelo '{model_name}' no está descargado. Clic en 'Descargar' primero.")
            self.lbl_test_local.setStyleSheet("font-size:11px; color:#eab308;")
            return
        self.lbl_test_local.setText(f"⏳ Cargando modelo '{model_name}'…")
        self.lbl_test_local.setStyleSheet("font-size:11px; color:#eab308;")
        QApplication.processEvents()
        try:
            from faster_whisper import WhisperModel
            import time
            t0 = time.time()
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
            dt = time.time() - t0
            self.lbl_test_local.setText(
                f"✅ Modelo '{model_name}' cargado en {dt:.1f}s. Listo para transcribir.")
            self.lbl_test_local.setStyleSheet("font-size:11px; color:#22c55e;")
        except Exception as e:
            self.lbl_test_local.setText(f"❌ Error: {e}")
            self.lbl_test_local.setStyleSheet("font-size:11px; color:#ef4444;")

    def _test_voice_ia(self):
        """Prueba conexión al provider de IA para audio."""
        self.lbl_test_ia.setText("⏳ Probando conexión…")
        self.lbl_test_ia.setStyleSheet("font-size:11px; color:#eab308;")
        QApplication.processEvents()
        self.lbl_test_ia.setText(
            "ℹ Para probar IA, necesitás un provider con modelo de audio cargado.\n"
            "Asegurate de que LM Studio tenga un modelo whisper/qwen2-audio cargado\n"
            "y que el servidor esté corriendo.")
        self.lbl_test_ia.setStyleSheet("font-size:11px; color:#888;")

    @staticmethod
    def _set_combo(combo, value):
        i = combo.findText(value)
        if i >= 0:
            combo.setCurrentIndex(i)

    def get_prefs(self):
        return {
            "primary_model": self.combo_primary.currentText(),
            "secondary_model": self.combo_secondary.currentText(),
            "vision_model": self.combo_vision.currentText(),
            "polish_model": self.combo_polish.currentText(),
            "voice_ia": self.combo_voice_mode.currentData() == "ia",
            "voice_model": self.combo_voice.currentText(),
            "whisper_model": self._selected_whisper,
            "auto_send_voice": self.chk_auto_send.isChecked(),
            "max_context_tokens": self.spin_max_tokens.value(),
            "auto_summarize": self.chk_auto_summarize.isChecked(),
            "token_budget": self.spin_budget.value(),
            "tool_limit_enabled": self.chk_tool_limit.isChecked(),
            "max_tools": self.spin_max_tools.value(),
            "request_timeout": self.spin_timeout.value(),
        }


# ---- Transcripción de voz ----

class VoiceTranscriber(QThread):
    done = Signal(str)
    error = Signal(str)

    def __init__(self, audio_path, parent=None, mode="local",
                 base=None, key="", model="", whisper_model="base"):
        super().__init__(parent)
        self.audio_path = audio_path
        self.mode = mode
        self.base = base
        self.key = key
        self.model = model
        self.whisper_model = whisper_model

    def run(self):
        if self.mode == "ia":
            self._transcribe_ia()
        else:
            self._transcribe_local()

    def _transcribe_local(self):
        """Transcripción local con faster-whisper (offline, sin Docker).
        Falla a speech_recognition (Google) si faster-whisper no está disponible."""
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel(self.whisper_model or "base",
                                 device="cpu", compute_type="int8")
            segments, info = model.transcribe(self.audio_path, language="es")
            text = " ".join(seg.text for seg in segments).strip()
            self.done.emit(text)
        except ImportError:
            try:
                import speech_recognition as sr
                r = sr.Recognizer()
                with sr.AudioFile(self.audio_path) as source:
                    r.adjust_for_ambient_noise(source, duration=0.3)
                    audio = r.record(source)
                try:
                    text = r.recognize_google(audio, language="es-ES")
                except sr.UnknownValueError:
                    text = ""
                except sr.RequestError as e:
                    self.error.emit(f"Error de Google Speech: {e}")
                    return
                self.done.emit(text)
            except Exception as e:
                self.error.emit(str(e))
        except Exception as e:
            self.error.emit(str(e))

    def _transcribe_ia(self):
        try:
            import requests
            url = api_url(self.base, "/audio/transcriptions")
            with open(self.audio_path, "rb") as f:
                files = {"file": (os.path.basename(self.audio_path), f, "audio/mpeg")}
                data = {"model": self.model or "whisper-1", "language": "es"}
                headers = {}
                if self.key:
                    headers["Authorization"] = f"Bearer {self.key}"
                resp = requests.post(url, files=files, data=data,
                                     headers=headers, timeout=120)
            if resp.status_code == 415:
                self.error.emit(
                    f"El modelo '{self.model}' no soporta audio (HTTP 415). "
                    f"Necesitás un modelo tipo Whisper.")
                return
            if resp.status_code == 404:
                self.error.emit(
                    f"El endpoint /v1/audio/transcriptions no existe. "
                    f"¿LM Studio con un modelo de audio cargado?")
                return
            if resp.status_code != 200:
                self.error.emit(f"HTTP {resp.status_code}: {resp.text[:200]}")
                return
            data = resp.json()
            text = data.get("text", "").strip()
            self.done.emit(text)
        except Exception as e:
            self.error.emit(f"Error transcripción IA: {e}")


# ---- AudioMeter (visualizador de grabación) ----

class AudioMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(8)
        self.setMaximumHeight(8)
        self._level = 0.0
        self._active = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._bars = [0.0] * 12

    def _tick(self):
        if not self._active:
            return
        import random
        base = random.uniform(0.3, 0.9) if self._active else 0.0
        self._bars = [max(0.1, min(1.0, base + random.uniform(-0.3, 0.3)))
                      for _ in range(12)]
        self.update()

    def start(self):
        self._active = True
        self._timer.start(80)

    def stop(self):
        self._active = False
        self._bars = [0.0] * 12
        self._timer.stop()
        self.update()

    def paintEvent(self, e):
        from PySide6.QtGui import QPainter, QColor
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#1a1a1a"))
        if not self._active:
            p.end()
            return
        n = len(self._bars)
        bar_w = max(2, (w - (n - 1) * 2) // n)
        gap = 2
        x = 0
        for i, level in enumerate(self._bars):
            bh = max(2, int(h * level))
            if level > 0.7:
                color = QColor("#ef4444")
            elif level > 0.4:
                color = QColor("#eab308")
            else:
                color = QColor("#22c55e")
            p.fillRect(x, h - bh, bar_w, bh, color)
            x += bar_w + gap
        p.end()
