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
import difflib

from PySide6.QtCore import Qt, Signal, QThread, QTimer, QSettings, QSize
from PySide6.QtGui import QFont, QTextCursor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QPlainTextEdit, QComboBox, QLineEdit, QCheckBox, QMessageBox,
    QFileDialog, QInputDialog, QSplitter, QFrame, QListWidget, QListWidgetItem,
    QScrollArea, QSizePolicy,
)

APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICONS_DIR = os.path.join(APP_DIR, "iconos")

LMSTUDIO = os.environ.get("LMSTUDIO_URL", "http://172.27.247.113:1234")
MAX_ITER = 10
MAX_RESULT = 8000
MAX_INDEX = 8000
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "conversaciones",
             "ns-code"}
NS_DIR = "ns-code"  # carpeta interna del workspace: contexto.txt, indexado.txt, resumen.txt, conversacion.json

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
{{"tool": "run_skill", "name": "move_file", "args": "viejo.js carpeta/nuevo.js"}}

Herramientas:
- list_files: lista el contenido de una carpeta (usa "." para la carpeta de trabajo).
- read_file: devuelve el contenido de un archivo.
- save_file: crea o sobrescribe un archivo con content.
- edit_file: reemplaza la primera aparición de old_text por new_text (lee el archivo antes).
- run_skill: ejecuta una skill de la carpeta Skills-py. Disponibles: "web_check" (verifica una web/HTML en navegador headless) y "move_file" (mueve/renombra archivos o carpetas: "move_file origen destino").

Tras cada herramienta recibirás un mensaje "[RESULTADO ...]". Cuando termines de trabajar, responde con 1-2 frases breves propias (sin JSON, sin repetir el RESULTADO).

Reglas: path siempre relativo a la carpeta de trabajo; no inventes contenido de archivos (léelos antes); si la consulta no requiere archivos, responde directamente.

Contexto del proyecto: existe una carpeta "ns-code/" en la carpeta de trabajo con archivos internos tuyos: "ns-code/contexto.txt" (notas, decisiones y progreso — podés leerlo y editarlo con save_file/edit_file), "ns-code/indexado.txt" (mapa del proyecto) y "ns-code/resumen.txt" (resumen de conversaciones anteriores). Usalos para recordar contexto entre sesiones."""


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


def strip_tool_json(text):
    """Quita los objetos {"tool": ...} del texto que se muestra al usuario.

    Las tool-calls ya se ven como chips; mostrar el JSON crudo (con todo el
    content escapado en \n) es ilegible. Si el stream cortó un JSON a la
    mitad, recorta desde ahí hasta el final.
    """
    dec = json.JSONDecoder()
    out = []
    i, n = 0, len(text or "")
    while i < n:
        if text[i] == "{":
            try:
                obj, end = dec.raw_decode(text[i:])
                if isinstance(obj, dict) and "tool" in obj:
                    i += end
                    continue
            except ValueError:
                if '"tool"' in text[i:i + 300]:
                    break  # tool-call JSON aún streameando
            out.append(text[i])
            i += 1
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def fmt_ai_text(raw):
    """Texto de la IA listo para mostrar: sin JSON de tools ni fences huérfanos."""
    t = strip_tool_json(raw or "")
    t = re.sub(r"^\s*```[a-zA-Z]*\s*$", "", t, flags=re.M)
    return t.strip()


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
    file_changed = Signal(str, str, int, int, int, int)  # path, tool, lines_b/a, bytes_b/a
    file_diff = Signal(str, str, list)  # path, tool, entries=[(sign, lineno, text)]
    file_backup = Signal(str, str, bool)  # path, contenido_antes, existía
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
        self._backed_up = set()  # paths ya respaldados en este run

    def stop(self):
        self._stop = True

    def _system_message(self):
        content = SYSTEM_PROMPT.format(folder=self.tools.root)
        content += ("\n\nArchivos actuales de la carpeta de trabajo:\n"
                    + folder_snapshot(self.tools.root))
        idx_path = os.path.join(self.tools.root, NS_DIR, "indexado.txt")
        if not os.path.exists(idx_path):
            idx_path = os.path.join(self.tools.root, "indexado.txt")  # legacy
        if os.path.exists(idx_path):
            try:
                with open(idx_path, encoding="utf-8", errors="replace") as f:
                    idx = f.read(MAX_INDEX)
                if idx.strip():
                    content += "\n\nMapa del proyecto (indexado.txt):\n" + idx
            except OSError:
                pass
        ctx_path = os.path.join(self.tools.root, NS_DIR, "contexto.txt")
        if not os.path.exists(ctx_path):
            ctx_path = os.path.join(self.tools.root, "contexto.txt")  # legacy
        if os.path.exists(ctx_path):
            try:
                with open(ctx_path, encoding="utf-8", errors="replace") as f:
                    ctx = f.read(MAX_INDEX)
                if ctx.strip():
                    content += "\n\nContexto guardado (contexto.txt):\n" + ctx
            except OSError:
                pass
        res_path = os.path.join(self.tools.root, NS_DIR, "resumen.txt")
        if os.path.exists(res_path):
            try:
                with open(res_path, encoding="utf-8", errors="replace") as f:
                    res = f.read(MAX_INDEX)
                if res.strip():
                    content += "\n\nResumen de la conversación (resumen.txt):\n" + res
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
                    path = str(action.get("path", ""))
                    # Leer líneas, bytes y contenido antes de modificar
                    lines_before = bytes_before = 0
                    text_before = ""
                    existed_before = False
                    full = os.path.join(self.tools.root, path) if path else ""
                    if tool in ("save_file", "edit_file") and full:
                        existed_before = os.path.exists(full)
                        if existed_before:
                            try:
                                with open(full, encoding="utf-8", errors="replace") as f:
                                    text_before = f.read()
                                lines_before = len(text_before.splitlines())
                                bytes_before = os.path.getsize(full)
                            except OSError:
                                pass
                    try:
                        result = self.tools.run(tool, action)
                    except Exception as e:
                        result = f"ERROR: {e}"
                    if tool in ("save_file", "edit_file"):
                        self.files_changed.emit()
                        lines_after = bytes_after = 0
                        text_after = ""
                        if os.path.exists(full):
                            try:
                                with open(full, encoding="utf-8", errors="replace") as f:
                                    text_after = f.read()
                                lines_after = len(text_after.splitlines())
                                bytes_after = os.path.getsize(full)
                            except OSError:
                                pass
                        # Backup del estado previo (una vez por archivo y run)
                        # para poder revertir con el botón ✗
                        if path not in self._backed_up:
                            self._backed_up.add(path)
                            self.file_backup.emit(
                                path, text_before, existed_before)
                        entries = self._diff_lines(text_before, text_after)
                        # file_diff primero: el bloque ya tiene el diff cuando refresca
                        self.file_diff.emit(path, tool, entries)
                        self.file_changed.emit(path, tool, lines_before,
                                               lines_after, bytes_before, bytes_after)
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

    @staticmethod
    def _diff_lines(before, after, limit=300):
        """Devuelve [(signo, lineno, texto)] del unified_diff, en orden y con nº de línea."""
        entries = []
        if before == after:
            return entries
        old_ln = new_ln = 0
        for ln in difflib.unified_diff(before.splitlines(), after.splitlines(),
                                       lineterm=""):
            if ln.startswith("+++") or ln.startswith("---"):
                continue
            if ln.startswith("@@"):
                m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", ln)
                if m:
                    old_ln, new_ln = int(m.group(1)), int(m.group(2))
                continue
            if len(entries) >= limit:
                break
            sign = ln[0]
            text = ln[1:]
            if sign == " ":
                old_ln += 1
                new_ln += 1
            elif sign == "+":
                entries.append(("+", new_ln, text))
                new_ln += 1
            elif sign == "-":
                entries.append(("-", old_ln, text))
                old_ln += 1
        return entries

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

def _rgba(hex_color, alpha=0.12):
    """Convierte #RRGGBB a rgba() (Qt interpreta #RRGGBBAA como #AARRGGBB)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


class CollapsibleSection(QFrame):
    """Sección colapsable con header y contenido."""
    def __init__(self, title, color="#8e8e93", expanded=False, parent=None):
        super().__init__(parent)
        self._expanded = expanded
        self._title = title
        self._color = color
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        # Header
        self.btn = QPushButton(f"{'▼' if expanded else '▶'} {title}")
        self.btn.setCheckable(True)
        self.btn.setChecked(expanded)
        self.btn.setStyleSheet(
            f"QPushButton {{ background:{_rgba(color, 0.10)}; color:{color}; "
            f"border:1px solid {_rgba(color, 0.25)}; border-radius:4px; "
            f"padding:4px 8px; font-size:11px; font-weight:bold; text-align:left; }}"
            f"QPushButton:hover {{ background:{_rgba(color, 0.18)}; }}"
            f"QPushButton:checked {{ background:{_rgba(color, 0.18)}; }}")
        self.btn.clicked.connect(self.toggle)
        v.addWidget(self.btn)
        # Content
        self.content = QFrame()
        self.content.setStyleSheet(
            "QFrame { background:#1e2126; border:1px solid #2b2e34; "
            "border-top:none; border-bottom-left-radius:6px; "
            "border-bottom-right-radius:6px; }")
        self.content_l = QVBoxLayout(self.content)
        self.content_l.setContentsMargins(8, 6, 8, 6)
        self.content_l.setSpacing(4)
        self.content.setVisible(expanded)
        v.addWidget(self.content)

    def toggle(self):
        self._expanded = not self._expanded
        self.btn.setText(f"{'▼' if self._expanded else '▶'} {self._title}")
        self.content.setVisible(self._expanded)

    def set_title(self, title):
        self._title = title
        self.btn.setText(f"{'▼' if self._expanded else '▶'} {title}")

    def add_text(self, text, color="#e8eaed", font_size=12, mono=False, rich=False):
        """Agrega un label de texto al contenido."""
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        if not rich:
            text = html.escape(text).replace("\n", "<br>")
        font_family = "Menlo,monospace" if mono else "sans-serif"
        lbl.setStyleSheet(
            f"color:{color}; font-size:{font_size}px; "
            f"font-family:{font_family}; background:transparent; border:none;")
        lbl.setTextFormat(Qt.RichText)
        lbl.setText(text)
        self.content_l.addWidget(lbl)
        return lbl

    def clear_content(self):
        while self.content_l.count():
            w = self.content_l.takeAt(0).widget()
            if w:
                w.deleteLater()


class ToolChip(QFrame):
    """Fila de tool-call estilo Windsurf: ▸ icono Verbo + path clickeable.

    - Clic en la fila expande/colapsa el resultado.
    - Clic en el path abre el archivo en el editor.
    """
    TOOL_STYLE = {
        "read_file":  ("📖", "Read",  "#0a84ff"),
        "save_file":  ("📝", "Write", "#22c55e"),
        "edit_file":  ("✏️", "Edit",  "#eab308"),
        "run_skill":  ("▶",  "Run",   "#a78bfa"),
        "list_files": ("📋", "List",  "#8e8e93"),
    }
    MAX_RESULT = 1200
    open_clicked = Signal(str)

    def __init__(self, tool, path, result, created=False, parent=None):
        super().__init__(parent)
        icon, name, color = self.TOOL_STYLE.get(
            tool, ("🔧", tool or "tool", "#8e8e93"))
        if tool == "save_file" and created:
            name = "Create"
        detail = (result or "").strip()
        self._expanded = False
        self._has_detail = bool(detail)

        self.setStyleSheet(
            "ToolChip { background:#1e2126; border:1px solid #2b2e34; "
            "border-radius:4px; }")
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Fila: ▸ | icono+verbo | path (link azul estilo Windsurf)
        self.header = _CardHeader()
        self.header.setCursor(
            Qt.PointingHandCursor if self._has_detail else Qt.ArrowCursor)
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(8, 3, 8, 3)
        hl.setSpacing(7)
        self.chevron = QLabel("▸" if self._has_detail else "")
        self.chevron.setStyleSheet(
            "color:#8e8e93; font-size:10px; background:transparent; border:none;")
        self.chevron.setFixedWidth(10)
        hl.addWidget(self.chevron)
        verb = QLabel(f"{icon} {name}")
        verb.setStyleSheet(
            f"color:{color}; font-size:11px; font-weight:600; "
            "font-family:Menlo,monospace; background:transparent; border:none;")
        hl.addWidget(verb)
        if path:
            link = _LinkLabel(path)
            link.setStyleSheet(
                "color:#7aa2f7; font-size:11px; font-family:Menlo,monospace; "
                "background:rgba(122,162,247,0.12); border:none; "
                "border-radius:3px; padding:1px 5px;")
            link.setCursor(Qt.PointingHandCursor)
            link.setToolTip("Abrir en el editor")
            link.clicked.connect(
                lambda _=None, p=path: self.open_clicked.emit(p))
            hl.addWidget(link)
        hl.addStretch(1)
        v.addWidget(self.header)
        if self._has_detail:
            self.header.setToolTip(detail[:300])
            self.header.clicked.connect(self.toggle)

        # Resultado expandible
        if self._has_detail:
            self.detail_lbl = QLabel()
            self.detail_lbl.setWordWrap(True)
            self.detail_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.detail_lbl.setTextFormat(Qt.RichText)
            self.detail_lbl.setText(
                html.escape(detail[:self.MAX_RESULT]).replace("\n", "<br>"))
            self.detail_lbl.setStyleSheet(
                "color:#c8ccd4; font-size:11px; font-family:Menlo,monospace; "
                "background:#16181c; border-top:1px solid #2b2e34; "
                "border-bottom-left-radius:4px; border-bottom-right-radius:4px; "
                "padding:6px 8px;")
            self.detail_lbl.setVisible(False)
            v.addWidget(self.detail_lbl)

    def toggle(self):
        if not self._has_detail:
            return
        self._expanded = not self._expanded
        self.chevron.setText("▾" if self._expanded else "▸")
        self.detail_lbl.setVisible(self._expanded)


class _CardHeader(QFrame):
    """Header clicable de una card."""
    clicked = Signal()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(e)


class _LinkLabel(QLabel):
    """QLabel clicable (emite clicked al presionar, no depende del hit-test
    de <a href>)."""
    clicked = Signal()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
            e.accept()
            return
        super().mousePressEvent(e)


class FileDiffCard(QFrame):
    """Card de archivo tocado: header (nombre + +N/−N + ✓/✗) y diff estilo editor.

    state: None → sin botones (sesión restaurada) · "pending" → ✓/✗
           "accepted" → ✓ Aceptado · "rejected" → ✗ Revertido
    """
    MAX_LINES = 60
    MAX_LINE_LEN = 300
    accept_clicked = Signal(str)
    reject_clicked = Signal(str)
    open_clicked = Signal(str)

    def __init__(self, path, info, diff=None, state=None, parent=None):
        super().__init__(parent)
        tool = info.get("tool", "")
        diff = diff or {}
        entries = diff.get("entries") or []
        added = [e for e in entries if e[0] == "+"]
        removed = [e for e in entries if e[0] == "-"]
        self._has_diff = bool(entries)
        self._expanded = self._has_diff

        self.setStyleSheet(
            "FileDiffCard { background:#16181c; border:1px solid #2b2e34; "
            "border-radius:6px; }")
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Header clicable
        self.header = _CardHeader()
        self.header.setCursor(Qt.PointingHandCursor if self._has_diff
                              else Qt.ArrowCursor)
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(8, 4, 8, 4)
        hl.setSpacing(6)
        self.chevron = QLabel("▾" if self._expanded else ("▸" if self._has_diff else ""))
        self.chevron.setStyleSheet(
            "color:#8e8e93; font-size:11px; background:transparent; border:none;")
        hl.addWidget(self.chevron)
        title = _LinkLabel()
        title.setTextFormat(Qt.RichText)
        title.setText(
            f'📄 <u>{html.escape(path)}</u> '
            f'<span style="color:#8e8e93">[{html.escape(tool)}]</span>'
            f'{self._counts_html(info, added, removed)}')
        title.setStyleSheet(
            "color:#e8eaed; font-size:11px; font-family:Menlo,monospace; "
            "background:transparent; border:none;")
        title.setCursor(Qt.PointingHandCursor)
        title.setToolTip("Abrir en el editor")
        title.clicked.connect(
            lambda _=None, p=path: self.open_clicked.emit(p))
        hl.addWidget(title, 1)
        # Botones ✓/✗ (estilo Windsurf) o etiqueta de estado
        if state == "pending":
            for txt, color, sig in (
                    ("✓", "#22c55e", self.accept_clicked),
                    ("✗", "#ef4444", self.reject_clicked)):
                b = QPushButton(txt)
                b.setFixedSize(22, 22)
                b.setCursor(Qt.PointingHandCursor)
                b.setToolTip("Aceptar cambio" if txt == "✓"
                             else "Rechazar (revertir archivo)")
                b.setStyleSheet(
                    f"QPushButton {{ background:#2b2e34; color:{color}; "
                    "border:1px solid #3a3d44; border-radius:4px; "
                    "font-size:12px; font-weight:bold; } "
                    f"QPushButton:hover {{ border-color:{color}; }}")
                b.clicked.connect(lambda _=False, s=sig, p=path: s.emit(p))
                hl.addWidget(b)
        elif state == "accepted":
            lbl = QLabel("✓ Aceptado")
            lbl.setStyleSheet(
                "color:#22c55e; font-size:10px; font-weight:bold; "
                "background:transparent; border:none;")
            hl.addWidget(lbl)
        elif state == "rejected":
            lbl = QLabel("✗ Revertido")
            lbl.setStyleSheet(
                "color:#8e8e93; font-size:10px; font-weight:bold; "
                "background:transparent; border:none;")
            hl.addWidget(lbl)
            self.setStyleSheet(
                "FileDiffCard { background:#16181c; border:1px solid #2b2e34; "
                "border-radius:6px; opacity:0.5; }")
        v.addWidget(self.header)
        if self._has_diff:
            self.header.clicked.connect(self.toggle)

        # Body: líneas del diff en orden, con nº de línea y fondo rojo/verde
        if self._has_diff:
            self.body = QWidget()
            bl = QVBoxLayout(self.body)
            bl.setContentsMargins(0, 0, 0, 2)
            bl.setSpacing(0)
            shown = 0
            for sign, lineno, text in entries:
                if shown >= self.MAX_LINES:
                    break
                bl.addWidget(self._diff_line(sign, lineno, text))
                shown += 1
            if len(entries) > shown:
                more = QLabel(f"… {len(entries) - shown} líneas más")
                more.setStyleSheet(
                    "color:#8e8e93; font-size:10px; font-family:Menlo,monospace; "
                    "padding:0 8px; background:transparent; border:none;")
                bl.addWidget(more)
            self.body.setVisible(self._expanded)
            v.addWidget(self.body)

    @staticmethod
    def _counts_html(info, added, removed):
        """Badges +N/−N: usa el diff real si existe, si no el fallback de líneas/bytes."""
        if added or removed:
            out = ""
            if added:
                out += f' <span style="color:#22c55e; font-weight:bold">+{len(added)}</span>'
            if removed:
                out += f' <span style="color:#ef4444; font-weight:bold">−{len(removed)}</span>'
            return out
        line_diff = info.get("diff", 0)
        byte_diff = info.get("bytes_after", 0) - info.get("bytes_before", 0)
        if line_diff > 0:
            return f' <span style="color:#22c55e; font-weight:bold">+{line_diff} líneas</span>'
        if line_diff < 0:
            return f' <span style="color:#ef4444; font-weight:bold">{line_diff} líneas</span>'
        if byte_diff != 0:
            sign = "+" if byte_diff > 0 else ""
            return (f' <span style="color:#eab308">±0 líneas · '
                    f'{sign}{byte_diff} caracteres</span>')
        return ' <span style="color:#8e8e93">sin cambios</span>'

    @staticmethod
    def _diff_line(sign, lineno, text):
        text = text if len(text) <= FileDiffCard.MAX_LINE_LEN \
            else text[:FileDiffCard.MAX_LINE_LEN] + "…"
        removed = sign == "-"
        num = str(lineno).rjust(4) if lineno else "    "
        lbl = QLabel(f"{sign} {num} │ {text}")
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        bg = "rgba(239,68,68,0.13)" if removed else "rgba(34,197,94,0.13)"
        fg = "#f09595" if removed else "#7ee2a8"
        lbl.setStyleSheet(
            f"background:{bg}; color:{fg}; font-family:Menlo,monospace; "
            "font-size:11px; padding:0 8px; border:none;")
        return lbl

    def toggle(self):
        if not self._has_diff:
            return
        self._expanded = not self._expanded
        self.chevron.setText("▾" if self._expanded else "▸")
        self.body.setVisible(self._expanded)


class PromptBlock(QFrame):
    """Bloque por prompt con 4 secciones colapsables:
    1. Respuesta completa de la IA (tool calls + texto)
    2. Resumen (solo texto final de la IA)
    3. Archivos tocados (path + diff de líneas)
    4. Stats (tokens, tiempo, modelo)
    """
    accept_requested = Signal(str)
    reject_requested = Signal(str)
    open_file = Signal(str)

    def __init__(self, prompt_id, prompt_text, timestamp, parent=None):
        super().__init__(parent)
        self.prompt_id = prompt_id
        self.prompt_text = prompt_text
        self.timestamp = timestamp
        self.files_touched = {}  # path → {tool, lines_b/a, bytes_b/a}
        self.file_diffs = {}     # path → {"added": [...], "removed": [...]}
        self.file_backups = {}   # path → (contenido_antes, existía)
        self.file_states = {}    # path → "accepted" | "rejected"
        self._stats_lines = []
        self._stream_label = None
        self._stream_text = ""
        self._summary_text = ""
        self._all_text = ""  # todo el texto de la respuesta
        self._done = False
        self._status_text = "Pensando"

        self.setObjectName("promptBlock")
        self.setStyleSheet(
            "QFrame#promptBlock { background:#22242a; border:1px solid #33363c; "
            "border-radius:8px; margin-bottom:6px; }")
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(4)

        # Header del prompt (siempre visible, clicable para expandir todo)
        self.header = QPushButton(
            f"📝 {timestamp}  {prompt_id}")
        self.header.setStyleSheet(
            "QPushButton { background:rgba(234,179,8,0.10); color:#fbbf24; "
            "border:1px solid rgba(234,179,8,0.30); border-radius:6px; "
            "padding:6px 10px; font-size:12px; font-weight:bold; "
            "text-align:left; }"
            "QPushButton:hover { background:rgba(234,179,8,0.18); }"
            "QPushButton:checked { background:rgba(234,179,8,0.18); }")
        self.header.setCheckable(True)
        self.header.setChecked(False)
        self.header.clicked.connect(self._toggle_all)
        v.addWidget(self.header)

        # Preview del prompt (siempre visible)
        short = prompt_text.replace("\n", " ").strip()
        if len(short) > 120:
            short = short[:120] + "…"
        self.preview = QLabel(short)
        self.preview.setWordWrap(True)
        self.preview.setStyleSheet(
            "color:#fcd34d; font-size:12px; padding:2px 10px 6px 10px; "
            "background:transparent; border:none;")
        self.preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(self.preview)

        # Indicador de estado ("Pensando… Ns" con timer)
        self.status_label = QLabel("⏳ Pensando… 0s")
        self.status_label.setStyleSheet(
            "color:#a78bfa; font-size:11px; font-weight:bold; "
            "padding:0 10px 2px 10px; background:transparent; border:none;")
        v.addWidget(self.status_label)
        self._elapsed = 0
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._tick_status)
        self._status_timer.start(1000)

        # Barra de carga indeterminada (visible mientras la IA trabaja)
        from PySide6.QtWidgets import QProgressBar
        self.busy_bar = QProgressBar()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setFixedHeight(4)
        self.busy_bar.setTextVisible(False)
        self.busy_bar.setStyleSheet(
            "QProgressBar { background:rgba(167,139,250,0.12); border:none; "
            "border-radius:2px; margin:0 10px; }"
            "QProgressBar::chunk { background:#a78bfa; border-radius:2px; }")
        v.addWidget(self.busy_bar)

        # Sección 1: Respuesta completa (visible desde el inicio)
        self.resp_section = CollapsibleSection("� Respuesta de la IA", "#a78bfa")
        v.addWidget(self.resp_section)

        # Sección 2: Archivos tocados (aparece cuando la IA toca un archivo,
        # siempre expandida)
        self.files_section = CollapsibleSection("📁 Archivos tocados (0)",
                                                "#0a84ff", expanded=True)
        self.files_section.setVisible(False)
        v.addWidget(self.files_section)

        # Sección 3: Resumen (aparece al final con el texto final de la IA)
        self.summary_section = CollapsibleSection("📋 Resumen", "#22c55e")
        self.summary_section.setVisible(False)
        v.addWidget(self.summary_section)

        # Stats: SIEMPRE visible, sin desplegable — pills en fila
        self.stats_frame = QFrame()
        self.stats_frame.setStyleSheet(
            "QFrame { background:#1e2126; border:1px solid #2b2e34; "
            "border-radius:6px; }")
        stats_v = QVBoxLayout(self.stats_frame)
        stats_v.setContentsMargins(8, 5, 8, 5)
        stats_v.setSpacing(3)
        self.stats_pills = QHBoxLayout()
        self.stats_pills.setContentsMargins(0, 0, 0, 0)
        self.stats_pills.setSpacing(6)
        stats_v.addLayout(self.stats_pills)
        # Líneas extra (add_stats / progress)
        self.stats_label = QLabel("")
        self.stats_label.setWordWrap(True)
        self.stats_label.setTextFormat(Qt.RichText)
        self.stats_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.stats_label.setStyleSheet(
            "color:#8e8e93; font-size:10px; font-family:Menlo,monospace; "
            "background:transparent; border:none;")
        self.stats_label.setVisible(False)
        stats_v.addWidget(self.stats_label)
        self.stats_frame.setVisible(False)
        v.addWidget(self.stats_frame)

    def _tick_status(self):
        self._elapsed += 1
        if not self._done:
            self.status_label.setText(f"⏳ {self._status_text}… {self._elapsed}s")

    def set_status(self, text):
        """Cambia el texto del indicador (Pensando / Trabajando / Escribiendo)."""
        self._status_text = text
        self.status_label.setText(f"⏳ {text}… {self._elapsed}s")

    def finish_status(self):
        """Marca el bloque como completado y detiene el timer."""
        self._done = True
        self._status_timer.stop()
        self.busy_bar.setVisible(False)
        self.status_label.setText(f"✓ Completado en {self._elapsed}s")
        self.status_label.setStyleSheet(
            "color:#22c55e; font-size:11px; font-weight:bold; "
            "padding:0 10px 2px 10px; background:transparent; border:none;")

    def _toggle_all(self):
        """Expande/colapsa las secciones (Archivos tocados queda siempre abierta)."""
        on = self.header.isChecked()
        for s in (self.resp_section, self.summary_section):
            if s._expanded != on:
                s.toggle()
        if not self.files_section._expanded:
            self.files_section.toggle()

    @staticmethod
    def _md(text):
        """Markdown → HTML para mostrar respuestas formateadas."""
        from utils.markdown_utils import md_to_html
        return md_to_html(text)

    def add_response_text(self, text, color="#e8eaed", mono=False):
        """Agrega texto a la sección de respuesta (renderiza markdown)."""
        self._all_text += text
        if mono:
            self.resp_section.add_text(text, color=color, font_size=11,
                                       mono=True)
        else:
            visible = fmt_ai_text(text)
            if visible:
                self.resp_section.add_text(self._md(visible), color=color,
                                           font_size=12, rich=True)

    def start_stream(self):
        """Prepara para streaming — crea un label acumulador con markdown."""
        self._stream_text = ""
        self._stream_label = QLabel("")
        self._stream_label.setWordWrap(True)
        self._stream_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._stream_label.setTextFormat(Qt.RichText)
        self._stream_label.setStyleSheet(
            "color:#e8eaed; font-size:12px; font-family:sans-serif; "
            "background:transparent; border:none;")
        self.resp_section.content_l.addWidget(self._stream_label)
        if not self.resp_section._expanded:
            self.resp_section.toggle()

    def append_stream_chunk(self, text):
        """Agrega un chunk al label de streaming (markdown + sin JSON)."""
        self._stream_text += text
        self._all_text += text
        if self._stream_label:
            visible = fmt_ai_text(self._stream_text)
            self._stream_label.setText(self._md(visible))

    def end_stream(self):
        """Finaliza el streaming."""
        self._stream_label = None

    def add_summary(self, text):
        """Agrega texto al resumen (respuesta final de la IA, en markdown)."""
        self._summary_text += text
        visible = fmt_ai_text(text)
        if visible:
            self.summary_section.add_text(
                self._md(visible), color="#22c55e", font_size=12, rich=True)
        self.summary_section.setVisible(True)

    def add_tool(self, tool, path, result):
        """Agrega una tool-call como chip visual en la sección de respuesta."""
        info = self.files_touched.get(path, {})
        created = tool == "save_file" and bool(path) and info.get("before", 1) == 0
        chip = ToolChip(tool, path, result, created=created)
        chip.open_clicked.connect(self.open_file.emit)
        self.resp_section.content_l.addWidget(chip)

    def add_file_changed(self, path, tool, lines_before, lines_after,
                         bytes_before=0, bytes_after=0):
        """Registra un archivo tocado y actualiza la sección."""
        diff = lines_after - lines_before
        self.files_touched[path] = {
            "tool": tool,
            "before": lines_before,
            "after": lines_after,
            "diff": diff,
            "bytes_before": bytes_before,
            "bytes_after": bytes_after,
        }
        self._refresh_files_section()

    def add_file_diff(self, path, tool, entries):
        """Guarda el diff real de un archivo tocado (emitido por el Worker)."""
        d = self.file_diffs.setdefault(path, {"entries": []})
        d["entries"].extend(entries)
        d["entries"] = d["entries"][:300]

    def add_file_backup(self, path, before, existed):
        """Guarda el estado previo del archivo para poder revertir."""
        if path not in self.file_backups:
            self.file_backups[path] = (before, existed)

    def _refresh_files_section(self):
        """Refresca la sección de archivos con FileDiffCards estilo editor."""
        self.files_section.setVisible(True)
        self.files_section.clear_content()
        count = len(self.files_touched)
        self.files_section.set_title(f"📁 Archivos tocados ({count})")
        for path, info in self.files_touched.items():
            if path in self.file_states:
                state = self.file_states[path]
            elif path in self.file_backups:
                state = "pending"
            else:
                state = None
            card = FileDiffCard(path, info, self.file_diffs.get(path),
                                state=state)
            card.accept_clicked.connect(self.accept_requested.emit)
            card.reject_clicked.connect(self.reject_requested.emit)
            card.open_clicked.connect(self.open_file.emit)
            self.files_section.content_l.addWidget(card)

    @staticmethod
    def _stat_pill(text, color):
        """Pill coloreada para un stat."""
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"background:{_rgba(color, 0.14)}; color:{color}; "
            f"border:1px solid {_rgba(color, 0.35)}; border-radius:9px; "
            "padding:2px 9px; font-size:11px; font-weight:600;")
        return lbl

    def add_stats(self, text):
        """Agrega una línea extra de stats (debajo de las pills)."""
        self._stats_lines.append(str(text))
        self.stats_frame.setVisible(True)
        self.stats_label.setText(
            "<br>".join(html.escape(l) for l in self._stats_lines))
        self.stats_label.setVisible(True)

    def set_final_stats(self, completion_tok, tps, prompt_tok, model, elapsed):
        """Stats finales como pills coloreadas en una fila."""
        while self.stats_pills.count():
            it = self.stats_pills.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for text, color in (
                (f"⏱ {elapsed:.0f}s", "#60a5fa"),
                (f"📤 {prompt_tok:,} enviados", "#f97316"),
                (f"📥 {completion_tok:,} recibidos", "#22c55e"),
                (f"⚡ {tps:.1f} tok/s", "#a78bfa"),
                (f"🤖 {model}", "#8e8e93")):
            self.stats_pills.addWidget(self._stat_pill(text, color))
        self.stats_pills.addStretch(1)
        self.stats_frame.setVisible(True)

    def add_error(self, text):
        """Agrega un error a la sección de respuesta."""
        self.resp_section.add_text(f"✖ {text}", color="#ff453a", font_size=11)


class ChatPanel(QWidget):
    """Panel 4: chat con IA (LM Studio y compatibles)."""

    files_changed = Signal()
    open_file_requested = Signal(str)  # path relativo al workspace
    file_auto_open = Signal(str, int)  # path relativo + línea a scrollear
    file_review = Signal(str, str)     # path relativo + contenido "antes"
    file_resolved = Signal(str, bool)  # path relativo + accepted? (desde card)

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
        self._file_block = {}  # path → PromptBlock que tiene su backup

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
        # Scroll area con bloques de prompt
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setObjectName("chatView")
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        chat_container = QWidget()
        self.chat_layout = QVBoxLayout(chat_container)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(6)
        self.chat_layout.addStretch(1)
        self.chat_scroll.setWidget(chat_container)
        mid_l.addWidget(self.chat_scroll)
        self.v_split.addWidget(mid)
        # Estado de bloques
        self._current_block = None
        self._blocks = []

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
        if self.tools:
            self._init_ns_code()
            self._load_conversation()

    # ---- Persistencia (ns-code/) ----

    def _ns_dir(self):
        """Crea y devuelve <workspace>/ns-code/."""
        d = os.path.join(self.tools.root, NS_DIR)
        os.makedirs(d, exist_ok=True)
        return d

    def _init_ns_code(self):
        """Crea ns-code/ y migra contexto.txt/indexado.txt desde la raíz."""
        d = self._ns_dir()
        for name in ("contexto.txt", "indexado.txt"):
            old = os.path.join(self.tools.root, name)
            new = os.path.join(d, name)
            if os.path.isfile(old) and not os.path.exists(new):
                try:
                    os.replace(old, new)
                except OSError:
                    pass

    def _save_conversation(self):
        """Guarda el historial en ns-code/conversacion.json."""
        if not self.tools:
            return
        try:
            p = os.path.join(self._ns_dir(), "conversacion.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=1)
        except OSError:
            pass

    def _append_resumen(self, block):
        """Agrega una entrada a ns-code/resumen.txt al terminar un prompt."""
        if not self.tools or not block:
            return
        files = ", ".join(
            f"{p} ({'+' if i['diff'] >= 0 else ''}{i['diff']})"
            for p, i in block.files_touched.items())
        entry = f"[{block.timestamp}] {block.prompt_id}\n"
        entry += f"Prompt: {block.prompt_text.strip()}\n"
        if block._summary_text.strip():
            entry += f"Respuesta: {block._summary_text.strip()}\n"
        if files:
            entry += f"Archivos: {files}\n"
        entry += "\n"
        try:
            with open(os.path.join(self._ns_dir(), "resumen.txt"),
                      "a", encoding="utf-8") as f:
                f.write(entry)
        except OSError:
            pass

    def _load_conversation(self):
        """Restaura historial desde ns-code/conversacion.json y reconstruye bloques."""
        p = os.path.join(self.tools.root, NS_DIR, "conversacion.json")
        if not os.path.isfile(p):
            return
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                history = json.load(f)
        except (OSError, ValueError):
            return
        if not isinstance(history, list):
            return
        self.history = history
        from datetime import datetime
        folder_name = os.path.basename(self.tools.root) or "proyecto"
        n = 0
        cur = None
        for m in history:
            role = m.get("role")
            text = m.get("content", "")
            if role == "user" and not text.startswith("[RESULTADO "):
                n += 1
                pid = f"{folder_name}-prompt-{n}"
                cur = PromptBlock(pid, text, "(sesión anterior)")
                cur.open_file.connect(self.open_file_requested.emit)
                cur.accept_requested.connect(
                    lambda p, b=cur: self._accept_file(b, p))
                cur.reject_requested.connect(
                    lambda p, b=cur: self._reject_file(b, p))
                cur._done = True
                cur.status_label.setText("✓ sesión anterior")
                cur.status_label.setStyleSheet(
                    "color:#8e8e93; font-size:11px; font-weight:bold; "
                    "padding:0 10px 2px 10px; background:transparent; border:none;")
                cur.busy_bar.setVisible(False)
                self._blocks.append(cur)
                self.chat_layout.insertWidget(self.chat_layout.count() - 1, cur)
                short = text.replace("\n", " ").strip()
                nav = short[:60] + ("…" if len(short) > 60 else "")
                it = QListWidgetItem(f"{pid}: {nav}")
                it.setData(Qt.UserRole, len(self._blocks) - 1)
                self.prompt_list.addItem(it)
            elif role == "assistant" and cur is not None:
                if '"tool"' in text:
                    cur.add_response_text(text, color="#8e8e93", mono=True)
                elif text.strip():
                    cur.add_summary(text.strip())
        self._prompt_counter = n
        if n:
            self._add_standalone_message(
                f"📂 Conversación restaurada: {n} prompt(s) anteriores", "stats")

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
        """Scroll al bloque de prompt seleccionado en el navigator."""
        idx = item.data(Qt.UserRole)
        if idx is None or not isinstance(idx, int):
            return
        if 0 <= idx < len(self._blocks):
            block = self._blocks[idx]
            self.chat_scroll.ensureWidgetVisible(block)
            # Resaltar brevemente
            block.header.setStyleSheet(
                "QPushButton { background:#eab30844; color:#eab308; border:none; "
                "border-radius:6px; padding:6px 10px; font-size:12px; font-weight:bold; "
                "text-align:left; }")
            from PySide6.QtCore import QTimer as _QTimer
            _QTimer.singleShot(1000, lambda: block.header.setStyleSheet(
                "QPushButton { background:#eab30822; color:#eab308; border:none; "
                "border-radius:6px; padding:6px 10px; font-size:12px; font-weight:bold; "
                "text-align:left; }"
                "QPushButton:hover { background:#eab30833; }"))

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
            self._add_standalone_message("ffmpeg no encontrado. Instálalo con: brew install ffmpeg", "error")
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
            self._add_standalone_message(
                f"🎙 Transcripción: {secs}s · {words} palabra(s)", "stats")
            if self.chk_auto_send.isChecked():
                self.send()
        else:
            self._add_standalone_message(f"🎙 No se entendió el audio ({secs}s)", "error")

    def _on_voice_error(self, err):
        self._transcribe_timer.stop()
        self.lbl_transcribing.setVisible(False)
        self._add_standalone_message(f"Error de transcripción: {err}", "error")

    # ---- Chat ----

    def append_chat(self, text, kind, prompt_id=None):
        """Enruta mensajes al PromptBlock actual o crea un mensaje suelto."""
        if kind == "assistant" and self._stream_active:
            self._stream_active = False
            return

        # Si hay un bloque actual, enrutar a sus secciones
        if self._current_block:
            block = self._current_block
            if kind == "tool":
                if not block._done:
                    block.set_status("Trabajando")
                # Extraer path del texto de la herramienta
                # Formato: "🔧 save_file {"path": "server.js"}\n<result>"
                lines = text.split("\n", 1)
                header = lines[0] if lines else ""
                result = lines[1] if len(lines) > 1 else ""
                path = ""
                try:
                    j = json.loads(header.split("🔧 ", 1)[1].split(" ", 1)[1])
                    path = j.get("path", "")
                except Exception:
                    pass
                tool_name = header.split("🔧 ", 1)[1].split(" ", 1)[0] if "🔧 " in header else ""
                block.add_tool(tool_name, path, result)
            elif kind == "assistant":
                block.add_response_text(text)
                block.add_summary(text)
            elif kind == "error":
                block.add_error(text)
            elif kind == "stats":
                block.add_stats(text)
                self._right_stats.setText(text)
            elif kind == "user":
                # No debería llegar aquí, el user se maneja en send()
                pass
        else:
            # Mensaje suelto (sin prompt block) — crear un mini-bloque
            self._add_standalone_message(text, kind)

        # Agregar al prompt navigator
        if kind == "user" and prompt_id:
            short = text.replace("\n", " ").strip()
            title = short[:60] + ("…" if len(short) > 60 else "")
            it = QListWidgetItem(f"{prompt_id}: {title}")
            it.setData(Qt.UserRole, len(self._blocks))
            self.prompt_list.addItem(it)

    def _add_standalone_message(self, text, kind):
        """Agrega un mensaje sin prompt block (errores, voz, etc.)."""
        color = self.COLORS.get(kind, "#e8eaed")
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lbl.setStyleSheet(
            f"color:{color}; font-size:12px; padding:4px 8px; "
            f"background:#22242a; border-radius:6px;")
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, lbl)

    def send(self):
        if self.worker is not None and self.worker.isRunning():
            return
        text = self.input.toPlainText().strip()
        if not text:
            return
        if not self.tools:
            self._add_standalone_message("Selecciona una carpeta de trabajo primero.", "error")
            return
        base, model, key, provider_name = self._current_provider()
        if not model:
            self._add_standalone_message("Selecciona un modelo (⚙ para configurar providers).", "error")
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
        # Crear PromptBlock
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        block = PromptBlock(prompt_id, text, timestamp)
        block.accept_requested.connect(
            lambda p, b=block: self._accept_file(b, p))
        block.reject_requested.connect(
            lambda p, b=block: self._reject_file(b, p))
        block.open_file.connect(self.open_file_requested.emit)
        self._blocks.append(block)
        self._current_block = block
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, block)
        # Agregar al prompt navigator
        short = text.replace("\n", " ").strip()
        nav_title = short[:60] + ("…" if len(short) > 60 else "")
        it = QListWidgetItem(f"{prompt_id}: {nav_title}")
        it.setData(Qt.UserRole, len(self._blocks) - 1)
        self.prompt_list.addItem(it)
        # Scroll al final
        self.chat_scroll.ensureWidgetVisible(block)
        # Enviar
        user_msg = {"role": "user", "content": text}
        self.history.append(user_msg)
        self._save_conversation()
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
        self.worker.file_diff.connect(self._on_file_diff)
        self.worker.file_backup.connect(self._on_file_backup)
        self.worker.file_changed.connect(self._on_file_changed)
        self.worker.stream_start.connect(self._on_stream_start)
        self.worker.chunk.connect(self._on_stream_chunk)
        self.worker.stream_end.connect(self._on_stream_end)
        self.worker.finished_run.connect(self.on_done)
        self.btn_send.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.worker.start()

    def _on_file_diff(self, path, tool, entries):
        """Guarda el diff real y abre el archivo en modo review."""
        if self._current_block:
            self._current_block.add_file_diff(path, tool, entries)
        backup = (self._current_block.file_backups.get(path)
                  if self._current_block else None)
        if path and backup:
            # Review inline: líneas verdes/rojas + navegación por hunks
            self.file_review.emit(path, backup[0])
        elif path:
            first = next((ln for sign, ln, _t in entries if sign == "+"), 0)
            if not first:
                first = next((ln for sign, ln, _t in entries if sign == "-"), 0)
            self.file_auto_open.emit(path, int(first or 1))

    def _on_file_changed(self, path, tool, lines_before, lines_after,
                         bytes_before, bytes_after):
        """Registra un archivo tocado por la IA."""
        if self._current_block:
            self._current_block.add_file_changed(
                path, tool, lines_before, lines_after, bytes_before, bytes_after)

    def _on_file_backup(self, path, before, existed):
        """Guarda el estado previo del archivo (para ✗ revertir)."""
        if self._current_block:
            self._current_block.add_file_backup(path, before, existed)
            self._file_block[path] = self._current_block

    def resolve_from_editor(self, rel_path, accepted):
        """El usuario resolvió el archivo desde la barra de review del editor."""
        block = self._file_block.get(rel_path)
        if not block:
            return False
        if accepted:
            self._accept_file(block, rel_path)
        else:
            self._reject_file(block, rel_path)
        return True

    def _accept_file(self, block, path):
        """✓ Aceptar: el cambio queda, la card pasa a 'accepted'."""
        if path in block.file_states:
            return
        block.file_states[path] = "accepted"
        block._refresh_files_section()
        self.file_resolved.emit(path, True)

    def _reject_file(self, block, path):
        """✗ Rechazar: restaura el archivo a su estado previo al run."""
        backup = block.file_backups.get(path)
        if not backup or path in block.file_states:
            return
        before, existed = backup
        full = os.path.join(self.tools.root, path)
        try:
            if existed:
                with open(full, "w", encoding="utf-8") as f:
                    f.write(before)
            elif os.path.exists(full):
                os.remove(full)
        except OSError:
            return
        block.file_states[path] = "rejected"
        block._refresh_files_section()
        self.files_changed.emit()  # refresca el árbol de archivos
        self.file_resolved.emit(path, False)

    def _on_stream_start(self):
        self._stream_active = True
        if self._current_block:
            self._current_block.set_status("Escribiendo")
            self._current_block.start_stream()
            self.chat_scroll.ensureWidgetVisible(self._current_block)

    def _on_stream_chunk(self, text):
        if self._current_block:
            self._current_block.append_stream_chunk(text)
            self.chat_scroll.ensureWidgetVisible(self._current_block)

    def _on_stream_end(self, ok):
        self._stream_active = False
        block = self._current_block
        if block:
            stream_text = block._stream_text
            block.end_stream()
            if ok:
                # Con streaming no llega msg "assistant": el stream es el resumen
                if stream_text.strip():
                    block.add_summary(stream_text.strip())
                # Colapsar la respuesta al terminar (queda limpia, expandible)
                if block.resp_section._expanded:
                    block.resp_section.toggle()

    def on_done(self):
        self.btn_send.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if self.worker is not None:
            u = self.worker.usage
            tps = u["completion"] / u["gen_time"] if u["gen_time"] > 0 else 0
            if self._current_block:
                self._current_block.set_final_stats(
                    u["completion"], tps, u["prompt"],
                    self.worker.model, self._current_block._elapsed)
                self._current_block.finish_status()
                self._append_resumen(self._current_block)
            self._save_conversation()
            self._right_stats.setText(
                f"{u['completion']} tok · {tps:.1f} tok/s · "
                f"prompt: {u['prompt']} tok · 🤖 {self.worker.model}")

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
            self._add_standalone_message("Configurá un modelo en Preferencias para pulir", "error")
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
            self._add_standalone_message(f"Error al pulir: {e}", "error")
