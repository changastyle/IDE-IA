# -*- coding: utf-8 -*-
"""Panel de chat IA para la nueva UI.

Contiene:
- Selector de provider + modelo
- Vista de chat (streaming)
- Input con Enter para enviar
- Botones: enviar, pulir, detener
- Checkbox "Sin contexto"
- Conexión streaming con OpenAI-compatible (LM Studio, etc.)
"""
import os
import re
import json
import time
import html
import shlex
import subprocess
import sys

from PySide6.QtCore import Qt, Signal, QThread, QTimer, QSettings, QSize
from PySide6.QtGui import QFont, QTextCursor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QPlainTextEdit, QComboBox, QLineEdit, QCheckBox, QMessageBox,
    QFileDialog, QInputDialog, QSplitter, QFrame, QListWidget, QListWidgetItem,
)

APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICONS_DIR = os.path.join(APP_DIR, "iconos")

LMSTUDIO = os.environ.get("LMSTUDIO_URL", "http://172.27.247.113:1234")
MAX_ITER = 10
MAX_RESULT = 8000
MAX_INDEX = 8000
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "conversaciones"}

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

SYSTEM_PROMPT = """Eres un agente que trabaja DIRECTAMENTE sobre los archivos de la carpeta de trabajo: {folder}

REGLA CRÍTICA: cuando el usuario pida crear, modificar o consultar archivos, NO expliques cómo hacerlo ni le des pasos a seguir: ejecútalo tú mismo con las herramientas. El usuario nunca copia y pega nada: tú escribes los archivos reales. Si el usuario reporta un error (por ejemplo de la consola del navegador), corrígelo tú: crea o edita los archivos que falten. NUNCA le digas al usuario que cree archivos, dé permisos o ejecute comandos.

Para usar una herramienta responde ÚNICAMENTE con un objeto JSON válido (sin texto antes ni después):
{{"tool": "list_files", "path": "."}}
{{"tool": "read_file", "path": "archivo.txt"}}
{{"tool": "save_file", "path": "archivo.txt", "content": "contenido completo del archivo"}}
{{"tool": "edit_file", "path": "archivo.txt", "old_text": "texto exacto existente", "new_text": "texto nuevo"}}
{{"tool": "run_skill", "name": "web_check", "args": "index.html"}}

Herramientas:
- list_files: lista el contenido de una carpeta (usa "." para la carpeta de trabajo).
- read_file: devuelve el contenido de un archivo.
- save_file: crea o sobrescribe un archivo con content.
- edit_file: reemplaza la primera aparición de old_text por new_text (lee el archivo antes).
- run_skill: ejecuta una skill de la carpeta Skills-py.

Tras cada herramienta recibirás un mensaje "[RESULTADO ...]". Cuando termines de trabajar, responde con 1-2 frases breves propias (sin JSON, sin repetir el RESULTADO).

Reglas: path siempre relativo a la carpeta de trabajo; no inventes contenido de archivos (léelos antes); si la consulta no requiere archivos, responde directamente.

Contexto del proyecto: existe un archivo "contexto.txt" en la carpeta de trabajo. Puedes leerlo y editarlo para guardar notas, decisiones, progreso o cualquier contexto importante del proyecto."""


# ---- Utilidades ----

def api_url(base, path):
    base = (base or "").rstrip("/")
    if base.endswith("/v1"):
        return base + path
    return base + "/v1" + path


def folder_snapshot(root, depth=2, max_entries=40):
    lines = []
    def walk(p, prefix, d):
        try:
            with os.scandir(p) as it:
                entries = sorted(it, key=lambda e: (not e.is_dir(), e.name.lower()))
        except OSError:
            return
        n = 0
        for e in entries:
            if n >= max_entries:
                lines.append(prefix + "…")
                return
            if e.is_dir():
                if e.name in SKIP_DIRS or e.name.startswith("."):
                    continue
                lines.append(prefix + e.name + "/")
                if d < depth:
                    walk(e.path, prefix + "  ", d + 1)
            else:
                lines.append(prefix + e.name)
            n += 1
    walk(root, "", 0)
    return "\n".join(lines) or "(carpeta vacía)"


def parse_actions(text):
    t = re.sub(r"```[a-zA-Z]*\s*", "", text or "").strip()
    t = re.sub(r"\s*```$", "", t).strip()
    actions = []
    dec = json.JSONDecoder()
    i = t.find("{")
    while i != -1:
        try:
            obj, end = dec.raw_decode(t[i:])
            if isinstance(obj, dict) and "tool" in obj:
                actions.append(obj)
                i += end
            else:
                i += 1
        except ValueError:
            i += 1
        i = t.find("{", i)
    return actions


def fetch_models(base, key=""):
    import requests
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    r = requests.get(api_url(base, "/models"), headers=headers, timeout=8)
    r.raise_for_status()
    r.encoding = "utf-8"
    return [m["id"] for m in r.json().get("data", []) if "embed" not in m["id"].lower()]


# ---- Tools (operaciones de archivos) ----

class Tools:
    def __init__(self, root):
        self.root = os.path.realpath(root)
        self.recent_changes = {}

    def _resolve(self, rel):
        p = os.path.realpath(os.path.join(self.root, str(rel or ".")))
        if p != self.root and not p.startswith(self.root + os.sep):
            raise ValueError("ruta fuera de la carpeta de trabajo")
        return p

    def run(self, tool, args):
        if tool == "list_files":
            return self._list(args.get("path", "."))
        if tool == "read_file":
            return self._read(args.get("path", ""))
        if tool == "save_file":
            return self._save(args.get("path", ""), args.get("content", ""))
        if tool == "edit_file":
            return self._edit(args.get("path", ""), args.get("old_text", ""), args.get("new_text", ""))
        if tool == "run_skill":
            return self._run_skill(args.get("name", ""), args.get("args", ""))
        return "ERROR: herramienta desconocida"

    def _list(self, rel):
        p = self._resolve(rel)
        if not os.path.isdir(p):
            return f"ERROR: '{rel}' no es una carpeta"
        items = []
        with os.scandir(p) as it:
            for e in sorted(it, key=lambda x: x.name):
                if e.is_dir():
                    items.append(f"dir   {e.name}/")
                else:
                    try:
                        size = e.stat().st_size
                    except OSError:
                        size = 0
                    items.append(f"file  {e.name}  ({size} B)")
        return "\n".join(items) or "(carpeta vacía)"

    def _read(self, rel):
        p = self._resolve(rel)
        with open(p, encoding="utf-8", errors="replace") as f:
            data = f.read(MAX_RESULT + 1)
        if len(data) > MAX_RESULT:
            return data[:MAX_RESULT] + f"\n…(truncado, {os.path.getsize(p)} bytes en total)"
        return data or "(archivo vacío)"

    def _save(self, rel, content):
        p = self._resolve(rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        content = str(content)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return f"OK: guardado {rel} ({len(content)} caracteres)"

    def _edit(self, rel, old, new):
        p = self._resolve(rel)
        with open(p, encoding="utf-8", errors="replace") as f:
            data = f.read()
        n = data.count(old)
        if n == 0:
            return "ERROR: old_text no encontrado en el archivo"
        new_data = data.replace(old, str(new), 1)
        with open(p, "w", encoding="utf-8") as f:
            f.write(new_data)
        return f"OK: editado {rel} ({n} coincidencia(s))"

    def _run_skill(self, name, args):
        skills_dir = os.path.realpath(os.path.join(APP_DIR, "Skills-py"))
        name = str(name or "").strip()
        if not name:
            return "ERROR: falta el nombre de la skill"
        script = os.path.realpath(os.path.join(skills_dir, name if name.endswith(".py") else name + ".py"))
        if not script.startswith(skills_dir + os.sep):
            return "ERROR: skill fuera de Skills-py"
        if not os.path.isfile(script):
            return f"ERROR: no existe la skill '{name}'"
        try:
            r = subprocess.run(
                [sys.executable, script] + shlex.split(str(args or "")),
                capture_output=True, text=True, timeout=180, cwd=self.root,
                encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        except subprocess.TimeoutExpired:
            return "ERROR: la skill tardó demasiado (180s)"
        out = r.stdout.strip()
        if r.stderr.strip():
            out += ("\n\nSTDERR:\n" + r.stderr.strip())
        return (out or "(sin salida)")[:MAX_RESULT]


# ---- Worker (thread de IA) ----

class Worker(QThread):
    msg = Signal(str, str)
    progress = Signal(str)
    files_changed = Signal()
    stream_start = Signal()
    chunk = Signal(str)
    stream_end = Signal(bool)
    finished_run = Signal()

    def __init__(self, base, model, tools, history, api_key="", no_context=False,
                 session_id="", max_tools=50, tool_limit_enabled=True,
                 request_timeout=600, parent=None):
        super().__init__(parent)
        self.base, self.model, self.tools, self.history = base, model, tools, history
        self.api_key = api_key
        self.no_context = no_context
        self.session_id = session_id
        self.max_tools = max_tools
        self.tool_limit_enabled = tool_limit_enabled
        self.request_timeout = request_timeout
        self._stop = False
        self.usage = {"prompt": 0, "completion": 0, "gen_time": 0.0}

    def stop(self):
        self._stop = True

    def _system_message(self):
        content = SYSTEM_PROMPT.format(folder=self.tools.root)
        content += ("\n\nArchivos actuales de la carpeta de trabajo:\n"
                    + folder_snapshot(self.tools.root))
        idx_path = os.path.join(self.tools.root, "indexado.txt")
        if os.path.exists(idx_path):
            try:
                with open(idx_path, encoding="utf-8", errors="replace") as f:
                    idx = f.read(MAX_INDEX)
                if idx.strip():
                    content += "\n\nMapa del proyecto (indexado.txt):\n" + idx
            except OSError:
                pass
        ctx_path = os.path.join(self.tools.root, "contexto.txt")
        if os.path.exists(ctx_path):
            try:
                with open(ctx_path, encoding="utf-8", errors="replace") as f:
                    ctx = f.read(MAX_INDEX)
                if ctx.strip():
                    content += "\n\nContexto guardado (contexto.txt):\n" + ctx
            except OSError:
                pass
        return {"role": "system", "content": content}

    def _chat(self):
        import requests
        if self.no_context:
            messages = [{"role": "system", "content": "Respondé en español. Usá las herramientas si es necesario."}]
            user_msgs = [m for m in self.history if m.get("role") == "user"]
            history = user_msgs[-1:] if user_msgs else []
        else:
            messages = [self._system_message()]
            history = self.history
        self._streamed = False
        t0 = time.time()
        headers = {"User-Agent": "cli-ia/1.0"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.session_id:
            headers["x-opencode-session"] = self.session_id
        try:
            r = requests.post(
                api_url(self.base, "/chat/completions"),
                json={"model": self.model, "messages": messages + history,
                      "temperature": 0.2, "max_tokens": 16384,
                      "stream": True, "stream_options": {"include_usage": True}},
                stream=True, timeout=(10, self.request_timeout), headers=headers,
            )
            r.raise_for_status()
        except Exception:
            raise
        r.encoding = "utf-8"
        content = ""
        usage = None
        started = False
        pending = ""
        last_emit = 0.0
        for line in r.iter_lines(decode_unicode=True):
            if self._stop:
                r.close()
                raise RuntimeError("detenido por el usuario")
            if not line or not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            try:
                chunk_data = json.loads(payload)
            except ValueError:
                continue
            choices = chunk_data.get("choices") or []
            if choices:
                delta = (choices[0].get("delta") or {}).get("content") or ""
                if delta:
                    if not started:
                        self.stream_start.emit()
                        self._streamed = True
                        started = True
                    content += delta
                    pending += delta
                    now = time.time()
                    if now - last_emit > 0.08:
                        self.chunk.emit(pending)
                        pending = ""
                        last_emit = now
            if chunk_data.get("usage"):
                usage = chunk_data["usage"]
        if pending:
            self.chunk.emit(pending)
        dt = time.time() - t0
        u = usage or {"prompt_tokens": 0, "completion_tokens": max(1, len(content) // 4)}
        self.usage["prompt"] += u.get("prompt_tokens", 0)
        self.usage["completion"] += u.get("completion_tokens", 0)
        self.usage["gen_time"] += dt
        return content

    def run(self):
        self.usage = {"prompt": 0, "completion": 0, "gen_time": 0.0}
        t_start = time.time()
        try:
            max_iter = self.max_tools if self.tool_limit_enabled else 999999
            for _ in range(max_iter):
                if self._stop:
                    self.msg.emit("(detenido por el usuario)", "error")
                    return
                reply = self._chat()
                actions = parse_actions(reply)
                if not actions:
                    if self._streamed:
                        self.stream_end.emit(True)
                    else:
                        self.msg.emit(reply.strip() or "(respuesta vacía)", "assistant")
                    self.history.append({"role": "assistant", "content": reply})
                    return
                if self._streamed:
                    self.stream_end.emit(False)
                self.history.append({"role": "assistant", "content": reply})
                for action in actions:
                    tool = str(action.get("tool", ""))
                    try:
                        result = self.tools.run(tool, action)
                    except Exception as e:
                        result = f"ERROR: {e}"
                    if tool in ("save_file", "edit_file"):
                        self.files_changed.emit()
                    info = json.dumps({k: v for k, v in action.items() if k == "path"}, ensure_ascii=False)
                    self.msg.emit(f"🔧 {tool} {info}\n{result[:600]}", "tool")
                    self.history.append({"role": "user", "content":
                        f"[RESULTADO {tool}]\n{result}\n"
                        "(Si faltan operaciones, usa otra herramienta. "
                        "Solo responde al usuario en texto normal SIN JSON cuando TODO esté resuelto.)"})
            if self.tool_limit_enabled:
                self.msg.emit(f"(límite de {self.max_tools} herramientas alcanzado)", "error")
        except Exception as e:
            self.msg.emit(self._friendly_error(e), "error")
        finally:
            self.finished_run.emit()

    def _friendly_error(self, e):
        if "ConnectionError" in type(e).__name__:
            return f"No se pudo conectar con {self.base}.\n¿Está el servidor encendido?"
        if "HTTPError" in type(e).__name__:
            # Extraer detalle del error HTTP
            detail = ""
            resp = getattr(e, "response", None)
            if resp is not None:
                try:
                    detail = resp.json().get("error", "") or resp.text[:300]
                except Exception:
                    detail = (resp.text or "")[:300]
                if isinstance(detail, dict):
                    detail = detail.get("message") or json.dumps(detail, ensure_ascii=False)
                code = resp.status_code
                if code in (401, 402, 403):
                    if "credit" in str(detail).lower() or "balance" in str(detail).lower():
                        return f"⚠ La cuenta no tiene créditos.\nDetalle: {detail}"
                    return f"⚠ API key inválida o vencida (código {code}).\nDetalle: {detail}"
                return f"⚠ El provider rechazó la petición (código {code}).\n" \
                       f"Detalle: {detail}\n\n" \
                       f"Revisá el modelo '{self.model}' o probá otro modelo."
            return f"Error HTTP del provider. Revisá el modelo y la API key."
        if isinstance(e, RuntimeError):
            return str(e)
        return f"Error: {e}"


# ---- Input con Enter para enviar ----

class ChatInput(QPlainTextEdit):
    sent = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not (e.modifiers() & Qt.ShiftModifier):
            self.sent.emit()
        else:
            super().keyPressEvent(e)


# ---- Panel de Chat IA ----

class ChatPanel(QWidget):
    """Panel 4: chat con IA (LM Studio y compatibles)."""

    files_changed = Signal()

    COLORS = {"user": "#eab308", "tool": "#8e8e93", "error": "#ff453a",
              "stats": "#32ade6", "assistant": "#e8eaed"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = []
        self.worker = None
        self._stream_active = False
        self._prompt_counter = 0
        self._current_prompt_id = ""
        self.tools = None
        self.repo_path = ""
        self.pinned = []
        self._rec_proc = None
        self._voice_thread = None
        self._rec_timer = None
        self._rec_wav = None

        # Providers y prefs desde QSettings
        self.settings = QSettings("ChatIA", "ChatIA")
        try:
            self.providers = json.loads(self.settings.value("providers", "null")) or {}
        except (ValueError, TypeError):
            self.providers = {}
        if not self.providers:
            self.providers = {"LM Studio": {"base": LMSTUDIO, "key": ""}}
        try:
            self.prefs = json.loads(self.settings.value("prefs", "{}")) or {}
        except (ValueError, TypeError):
            self.prefs = {}
        if not self.prefs:
            self.prefs = {"max_context_tokens": 50000, "auto_summarize": True,
                          "token_budget": 50000}
        try:
            self.pinned = json.loads(self.settings.value("pinned", "[]")) or []
        except (ValueError, TypeError):
            self.pinned = []

        # ---- Layout principal: splitter horizontal (main | right) ----
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.h_split = QSplitter(Qt.Horizontal)
        self.h_split.setChildrenCollapsible(False)
        self.h_split.setHandleWidth(4)
        outer.addWidget(self.h_split)

        # ---- Splitter vertical: top | middle | bottom ----
        self.v_split = QSplitter(Qt.Vertical)
        self.v_split.setChildrenCollapsible(False)
        self.v_split.setHandleWidth(4)
        self.h_split.addWidget(self.v_split)

        # ==== SUB-PANEL TOP: modelo + controles ====
        top = QFrame()
        top.setObjectName("chatTopPanel")
        top_l = QVBoxLayout(top)
        top_l.setContentsMargins(6, 6, 6, 6)
        top_l.setSpacing(4)
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        self.model_combo = QComboBox()
        self.model_combo.setToolTip("Modelo de IA")
        self.model_combo.setMinimumWidth(120)
        row1.addWidget(self.model_combo, 1)
        self.btn_pick = QPushButton("⚙")
        self.btn_pick.setFixedSize(28, 28)
        self.btn_pick.setToolTip("Modelos y providers")
        self.btn_pick.clicked.connect(self._open_model_picker)
        row1.addWidget(self.btn_pick)
        self.btn_prefs = QPushButton("🔧")
        self.btn_prefs.setFixedSize(28, 28)
        self.btn_prefs.setToolTip("Preferencias (modelos, voz, tokens)")
        self.btn_prefs.clicked.connect(self._open_prefs)
        row1.addWidget(self.btn_prefs)
        self.btn_refresh = QPushButton("↻")
        self.btn_refresh.setFixedSize(28, 28)
        self.btn_refresh.setToolTip("Re-descubrir modelos")
        self.btn_refresh.clicked.connect(self.refresh_models)
        row1.addWidget(self.btn_refresh)
        self.btn_toggle_right = QPushButton("▶")
        self.btn_toggle_right.setFixedSize(28, 28)
        self.btn_toggle_right.setCheckable(True)
        self.btn_toggle_right.setToolTip("Mostrar/ocultar panel lateral")
        self.btn_toggle_right.clicked.connect(self._toggle_right_panel)
        row1.addWidget(self.btn_toggle_right)
        top_l.addLayout(row1)
        self.v_split.addWidget(top)

        # ==== SUB-PANEL MIDDLE: chat ====
        mid = QFrame()
        mid.setObjectName("chatMidPanel")
        mid_l = QVBoxLayout(mid)
        mid_l.setContentsMargins(6, 0, 6, 0)
        mid_l.setSpacing(0)
        self.chat = QTextEdit()
        self.chat.setObjectName("chatView")
        self.chat.setReadOnly(True)
        mid_l.addWidget(self.chat)
        self.v_split.addWidget(mid)

        # ==== SUB-PANEL BOTTOM: checkboxes + audio + input + botones ====
        bot = QFrame()
        bot.setObjectName("chatBottomPanel")
        bot_l = QVBoxLayout(bot)
        bot_l.setContentsMargins(6, 0, 6, 6)
        bot_l.setSpacing(4)
        # Checkboxes
        ctx_row = QHBoxLayout()
        ctx_row.setSpacing(8)
        self.chk_no_ctx = QCheckBox("Sin contexto")
        self.chk_no_ctx.setToolTip("Envía SIN contexto del proyecto (ahorra tokens)")
        self.chk_no_ctx.setStyleSheet("font-size:11px; color:#888;")
        ctx_row.addWidget(self.chk_no_ctx)
        self.chk_auto_send = QCheckBox("Auto-enviar voz")
        self.chk_auto_send.setToolTip("Envía automáticamente al terminar la transcripción")
        self.chk_auto_send.setStyleSheet("font-size:11px; color:#888;")
        ctx_row.addWidget(self.chk_auto_send)
        ctx_row.addStretch(1)
        bot_l.addLayout(ctx_row)
        # Audio meter
        from utils.ia import AudioMeter
        self.audio_meter = AudioMeter()
        self.audio_meter.setVisible(False)
        bot_l.addWidget(self.audio_meter)
        # Label de transcripción (visible mientras transcribe)
        self.lbl_transcribing = QLabel("")
        self.lbl_transcribing.setStyleSheet(
            "font-size:12px; color:#a78bfa; font-weight:bold; padding:4px;")
        self.lbl_transcribing.setVisible(False)
        self.lbl_transcribing.setAlignment(Qt.AlignCenter)
        bot_l.addWidget(self.lbl_transcribing)
        # Timer para contar segundos de transcripción
        self._transcribe_timer = QTimer(self)
        self._transcribe_timer.timeout.connect(self._on_transcribe_tick)
        self._transcribe_seconds = 0
        # Input + botones
        input_row = QHBoxLayout()
        input_row.setSpacing(4)
        self.input = ChatInput()
        self.input.setFixedHeight(60)
        self.input.setPlaceholderText("Escribe aquí… (Enter envía, Shift+Enter salto)")
        self.input.sent.connect(self.send)
        input_row.addWidget(self.input, 1)
        col = QVBoxLayout()
        col.setSpacing(4)
        self.btn_send = self._icon_btn("enviar", "#0a84ff", "#fff", "Enviar")
        self.btn_send.clicked.connect(self.send)
        col.addWidget(self.btn_send)
        self.btn_polish = self._icon_btn("pulir", "#a855f7", "#fff", "Pulir texto")
        self.btn_polish.clicked.connect(self._polish_text)
        col.addWidget(self.btn_polish)
        self.btn_mic = self._icon_btn("mic", "#6b7280", "#fff", "Hablar: clic para grabar")
        self.btn_mic.clicked.connect(self._toggle_voice)
        col.addWidget(self.btn_mic)
        self.btn_stop = self._icon_btn("detener", "#ff453a", "#fff", "Detener")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop)
        col.addWidget(self.btn_stop)
        input_row.addLayout(col)
        bot_l.addLayout(input_row)
        self.v_split.addWidget(bot)

        # Tamaños iniciales del splitter vertical (top chico, medio grande, bottom chico)
        self.v_split.setSizes([40, 300, 120])

        # ==== SUB-PANEL RIGHT: lateral flotante ====
        self.right_panel = QFrame()
        self.right_panel.setObjectName("chatRightPanel")
        right_l = QVBoxLayout(self.right_panel)
        right_l.setContentsMargins(6, 6, 6, 6)
        right_l.setSpacing(4)
        # Header del panel lateral
        rhead = QHBoxLayout()
        rhead.setSpacing(4)
        rlbl = QLabel("Prompt Navigator")
        rlbl.setStyleSheet("font-weight:bold; color:#a78bfa;")
        rhead.addWidget(rlbl)
        rhead.addStretch(1)
        self.btn_right_close = QPushButton("◀")
        self.btn_right_close.setFixedSize(24, 24)
        self.btn_right_close.setToolTip("Ocultar panel lateral")
        self.btn_right_close.clicked.connect(lambda: self._toggle_right_panel(False))
        rhead.addWidget(self.btn_right_close)
        right_l.addLayout(rhead)
        # Lista de prompts (navigator)
        self.prompt_list = QListWidget()
        self.prompt_list.setObjectName("promptNavList")
        self.prompt_list.setToolTip("Clic para saltar a un prompt del chat")
        self.prompt_list.itemClicked.connect(self._on_prompt_nav_click)
        right_l.addWidget(self.prompt_list, 1)
        # Sección de info/stats
        rstats = QLabel("Sin actividad")
        rstats.setStyleSheet("font-size:11px; color:#888;")
        rstats.setWordWrap(True)
        right_l.addWidget(rstats)
        self._right_stats = rstats
        self.h_split.addWidget(self.right_panel)
        # Panel lateral oculto al inicio
        self.right_panel.setVisible(False)
        self.h_split.setSizes([400, 0])

        # Cargar modelos al inicio
        QTimer.singleShot(100, self.refresh_models)

    def _icon_btn(self, name, bg, fg, tip):
        p = os.path.join(ICONS_DIR, name + ".svg")
        b = QPushButton()
        b.setFixedSize(36, 36)
        if os.path.exists(p):
            b.setIcon(QIcon(p))
            b.setIconSize(QSize(24, 24))
        b.setToolTip(tip)
        b.setStyleSheet(
            f"QPushButton {{ background:{bg}; border:none; border-radius:8px; }}"
            f"QPushButton:hover {{ opacity:0.85; }}"
            f"QPushButton:disabled {{ background:#555; }}")
        return b

    def set_repo(self, path):
        """Cambia la carpeta de trabajo del chat."""
        self.repo_path = path or ""
        self.tools = Tools(path) if path else None

    def _toggle_right_panel(self, on=None):
        """Muestra/oculta el panel lateral derecho."""
        if on is None:
            on = not self.right_panel.isVisible()
        self.right_panel.setVisible(on)
        self.btn_toggle_right.setChecked(on)
        self.btn_toggle_right.setText("◀" if on else "▶")
        if on:
            # Darle tamaño al panel lateral
            sizes = self.h_split.sizes()
            if len(sizes) >= 2 and sizes[1] < 50:
                self.h_split.setSizes([350, 150])

    def _on_prompt_nav_click(self, item):
        """Salta a la posición del chat donde está el prompt seleccionado."""
        pos = item.data(Qt.UserRole)
        if pos is None:
            return
        cursor = self.chat.textCursor()
        cursor.setPosition(pos)
        self.chat.setTextCursor(cursor)
        self.chat.ensureCursorVisible()
        self.chat.setFocus()

    # ---- Providers / modelos ----

    def _current_provider(self):
        ref = self.model_combo.currentData()
        if not ref:
            return None, None, None, None
        provider, _, model = ref.partition("::")
        cfg = self.providers.get(provider, {})
        return cfg.get("base", LMSTUDIO), model, cfg.get("key", ""), provider

    def refresh_models(self):
        """Descubre modelos de todos los providers configurados."""
        self.model_combo.clear()
        all_models = []
        for pname, cfg in self.providers.items():
            base = cfg.get("base", LMSTUDIO)
            key = cfg.get("key", "")
            try:
                models = fetch_models(base, key)
            except Exception:
                continue
            for m in models:
                ref = f"{pname}::{m}"
                all_models.append(ref)
                self.model_combo.addItem(f"{pname} · {m}", ref)
        # Pinned models arriba (reordenar)
        if self.pinned:
            # Mover pinned al frente
            items = []
            for i in range(self.model_combo.count()):
                items.append((self.model_combo.itemText(i),
                              self.model_combo.itemData(i)))
            pinned_items = [it for it in items if it[1] in self.pinned]
            other_items = [it for it in items if it[1] not in self.pinned]
            self.model_combo.clear()
            for text, data in pinned_items + other_items:
                self.model_combo.addItem(text, data)
        # Aplicar modelo primario si está seteado
        primary = self.prefs.get("primary_model", "")
        if primary:
            idx = self.model_combo.findData(primary)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
        self._all_models = all_models

    def _open_model_picker(self):
        """Abre el diálogo de modelos y providers (pin models, add/del)."""
        from utils.ia import ModelPickerDialog
        dlg = ModelPickerDialog(self, self.providers, self.pinned)
        if dlg.exec():
            self.providers = dlg.providers
            self.pinned = dlg.pinned
            self.settings.setValue("providers", json.dumps(self.providers))
            self.settings.setValue("pinned", json.dumps(self.pinned))
            self.refresh_models()

    def _open_prefs(self):
        """Abre el diálogo de preferencias (modelos, voz, tokens)."""
        from utils.ia import PrefsDialog
        all_models = getattr(self, "_all_models", [])
        dlg = PrefsDialog(self, self.prefs, all_models)
        if dlg.exec():
            self.prefs = dlg.get_prefs()
            self.settings.setValue("prefs", json.dumps(self.prefs))

    # ---- Voz ----

    def _toggle_voice(self):
        if self._rec_proc is not None:
            self._stop_rec()
        else:
            # Si no hay configuración de voz válida, abrir preferencias
            if not self._voice_configured():
                self._open_prefs()
                return
            self._start_rec()

    def _voice_configured(self):
        """Verifica si la voz está configurada y lista para usar."""
        mode = "ia" if self.prefs.get("voice_ia", False) else "local"
        if mode == "local":
            # Local: necesita faster-whisper o speech_recognition
            try:
                import faster_whisper
                return True
            except ImportError:
                try:
                    import speech_recognition
                    return True
                except ImportError:
                    return False
        else:
            # IA: necesita un provider con modelo de audio
            ref = self.prefs.get("voice_model", "")
            if not ref or ref == "(usar el del combo)":
                base, model, key, _ = self._current_provider()
                return model is not None
            return "::" in ref
        return False

    def _start_rec(self):
        import subprocess
        voice_dir = os.path.join(APP_DIR, "Voice")
        os.makedirs(voice_dir, exist_ok=True)
        # MP3 en vez de WAV — mucho más liviano
        audio_path = os.path.join(voice_dir, "rec.mp3")
        if os.path.exists(audio_path):
            os.remove(audio_path)
        self._rec_wav = audio_path
        try:
            self._rec_proc = subprocess.Popen(
                ["ffmpeg", "-y", "-f", "avfoundation", "-i", ":0",
                 "-ar", "16000", "-ac", "1", "-b:a", "32k", audio_path],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            self.append_chat("ffmpeg no encontrado. Instálalo con: brew install ffmpeg", "error")
            self._rec_proc = None
            return
        self.btn_mic.setStyleSheet(
            "QPushButton { background:#ff453a; border:none; border-radius:8px; }"
            "QPushButton:hover { background:#ff453a; opacity:0.85; }")
        self.btn_mic.setToolTip("Grabando… clic para parar")
        self.audio_meter.setVisible(True)
        self.audio_meter.start()
        from utils.ia import play_sound
        play_sound("rec_start")
        self._rec_timer = QTimer(self)
        self._rec_timer.setSingleShot(True)
        self._rec_timer.timeout.connect(self._stop_rec)
        self._rec_timer.start(120000)

    def _stop_rec(self):
        if self._rec_proc is None:
            return
        if self._rec_timer is not None:
            self._rec_timer.stop()
            self._rec_timer = None
        try:
            self._rec_proc.stdin.write(b"q")
            self._rec_proc.stdin.close()
        except Exception:
            self._rec_proc.terminate()
        self._rec_proc.wait(timeout=5)
        self._rec_proc = None
        self.btn_mic.setStyleSheet(
            "QPushButton { background:#6b7280; border:none; border-radius:8px; }"
            "QPushButton:hover { background:#6b7280; opacity:0.85; }")
        self.btn_mic.setToolTip("Hablar: clic para grabar")
        self.audio_meter.stop()
        self.audio_meter.setVisible(False)
        from utils.ia import play_sound
        play_sound("rec_stop")
        audio = self._rec_wav
        if not audio or not os.path.exists(audio):
            return
        # Mostrar animación de transcripción
        self._transcribe_seconds = 0
        self.lbl_transcribing.setText("🎙 Transcribiendo voz… 0s")
        self.lbl_transcribing.setVisible(True)
        self._transcribe_timer.start(1000)
        from utils.ia import VoiceTranscriber
        whisper_model = self.prefs.get("whisper_model", "base")
        if self.prefs.get("voice_ia", False):
            ref = self.prefs.get("voice_model", "")
            if ref and "::" in ref:
                provider, _, model = ref.partition("::")
                cfg = self.providers.get(provider, {})
                base = cfg.get("base", LMSTUDIO)
                key = cfg.get("key", "")
            else:
                base, model, key, _ = self._current_provider()
            self._voice_thread = VoiceTranscriber(
                audio, mode="ia", base=base, key=key, model=model,
                whisper_model=whisper_model)
        else:
            self._voice_thread = VoiceTranscriber(
                audio, mode="local", whisper_model=whisper_model)
        self._voice_thread.done.connect(self._on_voice_done)
        self._voice_thread.error.connect(self._on_voice_error)
        self._voice_thread.start()

    def _on_transcribe_tick(self):
        """Cuenta los segundos que tarda la transcripción."""
        self._transcribe_seconds += 1
        self.lbl_transcribing.setText(f"🎙 Transcribiendo voz… {self._transcribe_seconds}s")

    def _on_voice_done(self, text):
        self._transcribe_timer.stop()
        self.lbl_transcribing.setVisible(False)
        secs = self._transcribe_seconds
        words = len(text.split()) if text else 0
        if text:
            current = self.input.toPlainText()
            if current and not current.endswith(" "):
                current += " "
            self.input.setPlainText(current + text)
            self.input.setFocus()
            cursor = self.input.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.input.setTextCursor(cursor)
            self.append_chat(
                f"🎙 Transcripción: {secs}s · {words} palabra(s)", "stats")
            if self.chk_auto_send.isChecked():
                self.send()
        else:
            self.append_chat(f"🎙 No se entendió el audio ({secs}s)", "error")

    def _on_voice_error(self, err):
        self._transcribe_timer.stop()
        self.lbl_transcribing.setVisible(False)
        self.append_chat(f"Error de transcripción: {err}", "error")

    # ---- Chat ----

    def append_chat(self, text, kind, prompt_id=None):
        if kind == "assistant" and self._stream_active:
            self._stream_active = False
            return
        body = html.escape(text).replace("\n", "<br>")
        if kind in ("tool", "stats"):
            body = f'<span style="font-family:Menlo,monospace; font-size:11px">{body}</span>'
        color = self.COLORS.get(kind, "")
        style = f"color:{color};" if color else ""
        if kind == "user":
            style += "font-weight:bold;"
            label = prompt_id or "Tú"
        elif kind == "assistant":
            label = f"response-{self._current_prompt_id or '?'}"
        else:
            label = {"tool": "🔧", "error": "✖", "stats": "⚙"}.get(kind, kind)
        # Guardar posición antes de append para el navigator
        pos_before = self.chat.textCursor().position()
        self.chat.append(f'<p style="{style}"><b>{label}:</b> {body}</p>')
        self.chat.moveCursor(QTextCursor.End)
        # Agregar al prompt navigator si es mensaje del usuario
        if kind == "user" and prompt_id:
            short = text.replace("\n", " ").strip()
            title = short[:60] + ("…" if len(short) > 60 else "")
            it = QListWidgetItem(f"{prompt_id}: {title}")
            it.setData(Qt.UserRole, pos_before)
            self.prompt_list.addItem(it)
        # Actualizar stats del panel lateral
        if kind == "stats":
            self._right_stats.setText(text)

    def send(self):
        if self.worker is not None and self.worker.isRunning():
            return
        text = self.input.toPlainText().strip()
        if not text:
            return
        if not self.tools:
            self.append_chat("Selecciona una carpeta de trabajo primero.", "error")
            return
        base, model, key, provider_name = self._current_provider()
        if not model:
            self.append_chat("Selecciona un modelo (⚙ para configurar providers).", "error")
            return
        # OpenCode Go/Zen requiere header x-opencode-session
        session_id = ""
        if provider_name and "opencode" in provider_name.lower():
            import uuid
            session_id = str(uuid.uuid4())
        self._prompt_counter += 1
        folder_name = os.path.basename(self.tools.root) or "proyecto"
        prompt_id = f"{folder_name}-prompt-{self._prompt_counter}"
        self._current_prompt_id = prompt_id
        user_msg = {"role": "user", "content": text}
        self.append_chat(text, "user", prompt_id=prompt_id)
        self.history.append(user_msg)
        self.input.clear()
        self.worker = Worker(base, model, self.tools, self.history, key,
                            no_context=self.chk_no_ctx.isChecked(),
                            session_id=session_id,
                            max_tools=int(self.prefs.get("max_tools", 50)),
                            tool_limit_enabled=bool(self.prefs.get("tool_limit_enabled", True)),
                            request_timeout=int(self.prefs.get("request_timeout", 600)))
        self.worker.msg.connect(self.append_chat)
        self.worker.progress.connect(lambda s: self.append_chat(s, "stats"))
        self.worker.files_changed.connect(self.files_changed.emit)
        self.worker.stream_start.connect(self._on_stream_start)
        self.worker.chunk.connect(self._on_stream_chunk)
        self.worker.stream_end.connect(self._on_stream_end)
        self.worker.finished_run.connect(self.on_done)
        self.btn_send.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.worker.start()

    def _on_stream_start(self):
        self._stream_active = True
        self.chat.append(f'<p style="color:#241f31"><b>response-{self._current_prompt_id}:</b> </p>')
        self.chat.moveCursor(QTextCursor.End)

    def _on_stream_chunk(self, text):
        self.chat.moveCursor(QTextCursor.End)
        self.chat.insertPlainText(text)
        self.chat.ensureCursorVisible()

    def _on_stream_end(self, ok):
        self._stream_active = False

    def on_done(self):
        self.btn_send.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if self.worker is not None:
            u = self.worker.usage
            tps = u["completion"] / u["gen_time"] if u["gen_time"] > 0 else 0
            self.append_chat(
                f"{u['completion']} tok · {tps:.1f} tok/s · prompt: {u['prompt']} tok · 🤖 {self.worker.model}",
                "stats")

    def stop(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()

    def _polish_text(self):
        """Pulir el texto del input antes de enviar."""
        text = self.input.toPlainText().strip()
        if not text:
            return
        # Prioridad: modelo para magia → secundario → el del combo
        ref = (self.prefs.get("polish_model", "")
               or self.prefs.get("secondary_model", ""))
        provider_name = ""
        if ref and "::" in ref:
            provider, _, model = ref.partition("::")
            provider_name = provider
            cfg = self.providers.get(provider, {})
            base = cfg.get("base", LMSTUDIO)
            key = cfg.get("key", "")
        else:
            base, model, key, provider_name = self._current_provider()
        if not model:
            self.append_chat("Configurá un modelo en Preferencias para pulir", "error")
            return
        # OpenCode requiere session_id
        session_id = ""
        if provider_name and "opencode" in provider_name.lower():
            import uuid
            session_id = str(uuid.uuid4())
        prompt = (
            "Sos un editor profesional experto en comunicación técnica. "
            "Reescribí el siguiente texto como si lo pidiera un experto del área. "
            "Reglas:\n"
            "1. Corregí ortografía y gramática.\n"
            "2. Usá MAYÚSCULAS donde corresponda (inicio de oración, nombres propios, siglas).\n"
            "3. Organizá en párrafos con sentido (una idea por párrafo).\n"
            "4. Sacá muletillas, repeticiones y coloquialismos.\n"
            "5. NO inventes requisitos que no estén implícitos.\n"
            "6. Mantené siempre la intención original.\n\n"
            f"Texto a pulir:\n{text}"
        )
        import requests
        try:
            headers = {}
            if key:
                headers["Authorization"] = f"Bearer {key}"
            if session_id:
                headers["x-opencode-session"] = session_id
            r = requests.post(
                api_url(base, "/chat/completions"),
                json={"model": model, "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.3, "max_tokens": 2048},
                headers=headers,
                timeout=30)
            r.encoding = "utf-8"
            r.raise_for_status()
            result = r.json()["choices"][0]["message"]["content"].strip()
            self.input.setPlainText(result)
            self.input.setFocus()
        except Exception as e:
            self.append_chat(f"Error al pulir: {e}", "error")
