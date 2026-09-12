#!/usr/bin/env python3
"""Chat con IA local (LM Studio) con herramientas de archivos.

Uso: .venv/bin/python chat_ia.py
"""
import html
import json
import os
import re
import shlex
import subprocess
import sys
import time

import requests
from PySide6.QtGui import QColor, QIcon, QTextCursor
from PySide6.QtCore import QSize, Qt, QProcess, QSettings, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QSpinBox, QTextEdit, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

LMSTUDIO = os.environ.get("LMSTUDIO_URL", "http://172.27.247.113:1234")
APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONV_DIR = os.path.join(APP_DIR, "conversaciones")
LAST_TXT = os.path.join(APP_DIR, "last-conversation.txt")
MAX_ITER = 10
MAX_RESULT = 8000
MAX_RECENT = 10
MAX_INDEX = 8000
INDEX_PROMPT = ("🧠 Indexa el proyecto: usa list_files y read_file para explorar los archivos, "
                "y crea o actualiza 'indexado.txt' con un mapa del proyecto: para cada archivo, "
                "su propósito, sus funciones/clases principales y cómo se relacionan, con comentarios "
                "breves. Guarda el resultado con save_file en 'indexado.txt'. "
                "No modifiques ningún otro archivo.")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "conversaciones"}
ICONS_DIR = os.path.join(APP_DIR, "iconos")


def svg_icon(name):
    """Carga un SVG de iconos/ como QIcon."""
    p = os.path.join(ICONS_DIR, name + ".svg")
    return QIcon(p) if os.path.exists(p) else QIcon()


def icon_btn(name, size=36, bg="#eab308", fg="#000", tooltip=""):
    """Crea un botón cuadrado con icono SVG, fondo de color y tooltip."""
    b = QPushButton()
    b.setFixedSize(size, size)
    b.setIcon(svg_icon(name))
    b.setIconSize(QSize(size - 12, size - 12))
    b.setToolTip(tooltip)
    b.setStyleSheet(
        f"QPushButton {{ background:{bg}; border:none; border-radius:8px; }}"
        f"QPushButton:hover {{ background:{bg}; opacity:0.85; }}"
        f"QPushButton:disabled {{ background:#555; }}")
    return b
EXT_ICONS = {".html": "html", ".htm": "html", ".css": "css", ".js": "js",
             ".py": "python", ".json": "json", ".md": "markdown", ".txt": "txt"}

APP_QSS = """
QMainWindow, QDialog { background-color: #17181c; }
QWidget { color: #e8eaed; font-size: 12px; }
QLabel { color: #b6bac1; background: transparent; }

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {
  background-color: #22242a;
  border: 1px solid #33363c;
  border-radius: 8px;
  padding: 4px 8px;
  selection-background-color: #2f6fed;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {
  border: 1px solid #2f6fed;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
  background-color: #222529;
  border: 1px solid #33363c;
  border-radius: 8px;
  selection-background-color: #2f6fed;
  outline: none;
}

QPushButton {
  background-color: #2a2d33;
  border: 1px solid #383c43;
  border-radius: 8px;
  padding: 5px 12px;
  color: #e8eaed;
}
QPushButton:hover { background-color: #34383f; }
QPushButton:pressed { background-color: #202329; }
QPushButton:disabled { color: #61666d; background-color: #232529; border-color: #2c2f35; }

QPushButton#primary { background-color: #2f6fed; border: none; font-weight: bold; }
QPushButton#primary:hover { background-color: #4a83f5; }
QPushButton#success { background-color: #2ea043; border: none; font-weight: bold; }
QPushButton#success:hover { background-color: #3fbf56; }
QPushButton#danger { background-color: #b6383a; border: none; }
QPushButton#danger:hover { background-color: #d24a48; }
QPushButton#accent { background-color: #7c3aed; border: none; }
QPushButton#accent:hover { background-color: #8f55f2; }

QListWidget, QTreeWidget {
  background-color: #1e2024;
  border: 1px solid #2b2e34;
  border-radius: 10px;
  padding: 4px;
  outline: none;
}
QListWidget::item { border-radius: 6px; padding: 3px; }
QListWidget::item:selected { background-color: #2f6fed; color: #fff; }
QListWidget::item:hover { background-color: #2a2d33; }
QTreeWidget::item { border-radius: 6px; padding: 2px; }
QTreeWidget::item:selected { background-color: #2f6fed; }

QTextEdit#chatView {
  background-color: #1e2024;
  border: 1px solid #2b2e34;
  border-radius: 10px;
  padding: 6px;
}

QTabWidget::pane {
  border: 1px solid #2b2e34;
  border-radius: 10px;
  background-color: #1e2024;
}
QTabBar::tab {
  background: #222529;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
  padding: 5px 12px;
  margin-right: 3px;
  color: #b6bac1;
}
QTabBar::tab:selected { background: #2f6fed; color: #fff; }

QStatusBar { background: transparent; color: #8b9097; }
QToolTip {
  background-color: #26282d;
  color: #e8eaed;
  border: 1px solid #3a3e45;
  border-radius: 6px;
  padding: 4px;
}
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #33363c; border-radius: 5px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def file_icon(name, is_dir):
    if is_dir:
        path = os.path.join(ICONS_DIR, "carpeta.svg")
    else:
        icon = EXT_ICONS.get(os.path.splitext(name)[1].lower(), "archivo")
        path = os.path.join(ICONS_DIR, icon + ".svg")
    return QIcon(path) if os.path.exists(path) else QIcon()

SYSTEM_PROMPT = """Eres un agente que trabaja DIRECTAMENTE sobre los archivos de la carpeta de trabajo: {folder}

REGLA CRÍTICA: cuando el usuario pida crear, modificar o consultar archivos, NO expliques cómo hacerlo ni le des pasos a seguir: ejecútalo tú mismo con las herramientas. El usuario nunca copia y pega nada: tú escribes los archivos reales. Si el usuario reporta un error (por ejemplo de la consola del navegador), corrígelo tú: crea o edita los archivos que falten. NUNCA le digas al usuario que cree archivos, dé permisos o ejecute comandos.

Para usar una herramienta responde ÚNICAMENTE con un objeto JSON válido (sin texto antes ni después):
{{"tool": "list_files", "path": "."}}
{{"tool": "read_file", "path": "archivo.txt"}}
{{"tool": "save_file", "path": "archivo.txt", "content": "contenido completo del archivo"}}
{{"tool": "edit_file", "path": "archivo.txt", "old_text": "texto exacto existente", "new_text": "texto nuevo"}}
{{"tool": "run_skill", "name": "web_check", "args": "index.html"}}

Ejemplos de comportamiento correcto:
- Usuario: "haz un juego index.html" → responde {{"tool": "save_file", "path": "index.html", "content": "<!DOCTYPE html>…"}} con el juego COMPLETO y funcional. Si lo divides en varios archivos (css, js), crea TODOS con save_file.
- Usuario: pega un error (ej: "styles.css net::ERR_FILE_NOT_FOUND") → usa save_file para crear el archivo que falta o edit_file para corregirlo.
- Usuario: "cambia el título de X" → usa read_file y luego edit_file.

Herramientas:
- list_files: lista el contenido de una carpeta (usa "." para la carpeta de trabajo).
- read_file: devuelve el contenido de un archivo.
- save_file: crea o sobrescribe un archivo con content.
- edit_file: reemplaza la primera aparición de old_text por new_text (lee el archivo antes).
- run_skill: ejecuta una skill de la carpeta Skills-py. La skill "web_check" abre una web o archivo HTML en un navegador headless y devuelve console logs, errores de JavaScript y recursos fallidos. Úsala para verificar que una página funciona, especialmente después de crear o editar HTML.

Tras cada herramienta recibirás un mensaje "[RESULTADO ...]". Cuando termines de trabajar, responde con 1-2 frases breves propias (sin JSON, sin repetir el RESULTADO).

Reglas: path siempre relativo a la carpeta de trabajo; no inventes contenido de archivos (léelos antes); si la consulta no requiere archivos, responde directamente.

Contexto del proyecto: existe un archivo "contexto.txt" en la carpeta de trabajo. Puedes leerlo y editarlo con save_file/edit_file para guardar notas, decisiones, progreso o cualquier contexto importante del proyecto que te ayude en futuras consultas. Si hacés algo importante, podés actualizar contexto.txt para recordarlo después."""


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


def parse_action(text):
    actions = parse_actions(text)
    return actions[0] if actions else None


def _salvage_save_file(text):
    """Intenta extraer un save_file de JSON truncado (path + content parcial)."""
    if '"tool"' not in text or 'save_file' not in text:
        return None
    m_path = re.search(r'"path"\s*:\s*"([^"]+)"', text)
    if not m_path:
        return None
    path = m_path.group(1)
    m_content = re.search(r'"content"\s*:\s*"', text)
    if m_content:
        start = m_content.end()
        content = text[start:]
        content = content.rstrip('"')
        content = content.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
        return {"tool": "save_file", "path": path, "content": content,
                "_truncated": True}
    return None


def parse_actions(text):
    """Extrae todos los objetos JSON con clave "tool" del texto (en orden)."""
    t = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    t = re.sub(r"^```[a-zA-Z]*\s*", "", t).strip()
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
            # JSON truncado: intentar salvar save_file con path y content parcial
            salvaged = _salvage_save_file(t[i:])
            if salvaged:
                actions.append(salvaged)
                break
            i += 1
        i = t.find("{", i)
    return actions


def render_message(m):
    """Convierte un mensaje del historial en (kind, texto visible para el chat)."""
    c = m.get("content", "")
    # Si el content es una lista (mensaje multimodal), extraer solo el texto
    if isinstance(c, list):
        parts = [p.get("text", "") for p in c if p.get("type") == "text"]
        imgs = [p for p in c if p.get("type") == "image_url"]
        text = " ".join(parts)
        if imgs:
            text += (" " if text else "") + " ".join(f"🖼️" for _ in imgs)
        c = text
    if m.get("role") == "assistant":
        a = parse_action(c)
        if a:
            info = json.dumps({k: v for k, v in a.items() if k == "path"}, ensure_ascii=False)
            return "tool", f"🔧 {a.get('tool')} {info}"
        return "assistant", c
    if c.startswith("[RESULTADO"):
        return "tool", c.split("\n(Si ya tienes")[0]
    return "user", c


class Tools:
    def __init__(self, root):
        self.root = os.path.realpath(root)
        self.recent_changes = {}  # rel_path -> {"kind": "created"/"modified", "preview": str}

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
        return "ERROR: herramienta desconocida; usa list_files, read_file, save_file, edit_file o run_skill"

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
        existed = os.path.exists(p)
        old_text = ""
        if existed:
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    old_text = f.read()
            except OSError:
                pass
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        self.recent_changes[rel] = self._build_change(
            rel, "modified" if existed else "created", old_text, content)
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
        self.recent_changes[rel] = self._build_change(rel, "modified", data, new_data)
        return f"OK: editado {rel} ({n} coincidencia(s), se reemplazó la primera)"

    def _build_change(self, rel, kind, old_text, new_text):
        """Construye el registro de cambio con diff de líneas (added/removed)."""
        import difflib
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        added = removed = 0
        diff_lines = []
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
                None, old_lines, new_lines, autojunk=False).get_opcodes():
            if tag == "equal":
                continue
            if tag in ("replace", "delete"):
                for ln in old_lines[i1:i2]:
                    diff_lines.append(("del", ln))
                    removed += 1
            if tag in ("replace", "insert"):
                for ln in new_lines[j1:j2]:
                    diff_lines.append(("add", ln))
                    added += 1
        # Limitar el diff guardado para no inflar memoria
        if len(diff_lines) > 200:
            diff_lines = diff_lines[:200] + [("ctx", f"… ({len(diff_lines) - 200} líneas más)")]
        return {
            "kind": kind,
            "added": added,
            "removed": removed,
            "diff": diff_lines,
            "old_text": old_text,
            "new_text": new_text,
        }

    def _run_skill(self, name, args):
        skills_dir = os.path.realpath(os.path.join(APP_DIR, "Skills-py"))
        name = str(name or "").strip()
        if not name:
            return "ERROR: falta el nombre de la skill"
        script = os.path.realpath(os.path.join(skills_dir, name if name.endswith(".py") else name + ".py"))
        if not script.startswith(skills_dir + os.sep):
            return "ERROR: skill fuera de Skills-py"
        if not os.path.isfile(script):
            disponibles = ", ".join(sorted(f[:-3] for f in os.listdir(skills_dir) if f.endswith(".py"))) or "(ninguna)"
            return f"ERROR: no existe la skill '{name}'. Disponibles: {disponibles}"
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


class Worker(QThread):
    msg = Signal(str, str)
    progress = Signal(str)
    files_changed = Signal()
    turn_usage = Signal(dict)  # {prompt, completion, total_time, model}
    stream_start = Signal()
    chunk = Signal(str)
    stream_end = Signal(bool)
    finished_run = Signal()

    def __init__(self, base, model, tools, history, api_key="", session_id="", images=None, no_context=False, prompt_id="", parent=None):
        super().__init__(parent)
        self.base, self.model, self.tools, self.history = base, model, tools, history
        self.api_key = api_key
        self.session_id = session_id
        self.images = images or []
        self.no_context = no_context
        self.prompt_id = prompt_id
        self._stop = False

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
                if len(idx) == MAX_INDEX:
                    idx += "\n…(indexado.txt truncado)"
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

    def _supports_vision(self):
        """Heurística: ¿el modelo soporta imágenes?"""
        m = (self.model or "").lower()
        # Modelos conocidos que soportan visión
        if any(k in m for k in ("vision", "-v", "vlm", "llava", "gpt-4o", "gpt-4-turbo",
                                "claude-3", "claude-4", "claude-5", "gemini",
                                "glm-4", "glm-5", "qwen2-vl", "qwen2.5-vl",
                                "qwen3", "kimi-k", "minimax", "grok-4")):
            return True
        return False

    def _chat(self):
        if self.no_context:
            messages = [{"role": "system", "content": "Respondé en español. Usá las herramientas si es necesario."}]
            # Sin contexto: mandar solo el último mensaje del usuario
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
        # Si hay imágenes pero el modelo probablemente no soporta visión, avisar
        if self.images and not self._supports_vision():
            raise RuntimeError(
                f"⚠ El modelo '{self.model}' probablemente no soporta imágenes. "
                "Elegí un modelo con visión (ej: glm-4.6v, gpt-4o, claude-3, gemini, qwen-vl).")
        try:
            r = requests.post(
                api_url(self.base, "/chat/completions"),
                json={"model": self.model, "messages": messages + history,
                      "temperature": 0.2, "max_tokens": 16384,
                      "stream": True, "stream_options": {"include_usage": True}},
                stream=True, timeout=(10, 180), headers=headers,
            )
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if e.response is not None and self.images:
                try:
                    detail = e.response.json().get("error", "") or e.response.text[:300]
                except Exception:
                    detail = (e.response.text or "")[:300]
                if any(k in str(detail).lower() for k in ("image", "vision", "multimodal", "unsupported")):
                    raise RuntimeError(
                        f"⚠ El modelo '{self.model}' no soporta imágenes. "
                        "Elegí un modelo con visión (ej: glm-4.6v, gpt-4o, claude-3, gemini).") from e
            raise
        r.encoding = "utf-8"  # los servers OpenAI-compatibles mandan UTF-8 sin declarar charset
        content = ""
        usage = None
        last_ping = t0
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
                chunk = json.loads(payload)
            except ValueError:
                continue
            choices = chunk.get("choices") or []
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
            if chunk.get("usage"):
                usage = chunk["usage"]
            now = time.time()
            if now - last_ping > 2:
                self.progress.emit(f"⏳ generando… {len(content) + len(pending)} chars ({now - t0:.0f}s)")
                last_ping = now
        if pending:
            self.chunk.emit(pending)
        dt = time.time() - t0
        u = usage or {"prompt_tokens": 0,
                      "completion_tokens": max(1, len(content) // 4)}
        self.usage["prompt"] += u.get("prompt_tokens", 0)
        self.usage["completion"] += u.get("completion_tokens", 0)
        self.usage["gen_time"] += dt
        return content

    def run(self):
        self.usage = {"prompt": 0, "completion": 0, "gen_time": 0.0}
        t_start = time.time()
        try:
            for _ in range(MAX_ITER):
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
                    self._emit_stats(time.time() - t_start)
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
                    truncated = action.get("_truncated", False)
                    info = json.dumps({k: v for k, v in action.items() if k == "path"}, ensure_ascii=False)
                    suffix = " ⚠️ JSON truncado — contenido parcial guardado" if truncated else ""
                    self.msg.emit(f"🔧 {tool} {info}{suffix}\n{result[:600]}{'…' if len(result) > 600 else ''}", "tool")
                    self.history.append({"role": "user", "content":
                        f"[RESULTADO {tool}]\n{result}\n"
                        "(Si aún faltan archivos, errores u operaciones pendientes, usa otra herramienta. "
                        "Solo responde al usuario en texto normal SIN JSON cuando TODO esté resuelto; "
                        "no repitas el RESULTADO.)"})
            self.msg.emit("(límite de herramientas por mensaje alcanzado)", "error")
        except Exception as e:
            self.msg.emit(self._friendly_error(e), "error")
        finally:
            self.finished_run.emit()

    def _friendly_error(self, e):
        if isinstance(e, requests.exceptions.ConnectionError):
            return (f"No se pudo conectar con LM Studio ({self.base}).\n"
                    "¿Está abierto y el servidor encendido?")
        if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
            try:
                detail = e.response.json().get("error", "") or e.response.text[:300]
            except Exception:
                detail = (e.response.text or "")[:300]
            if isinstance(detail, dict):
                detail = detail.get("message") or json.dumps(detail, ensure_ascii=False)
            code = e.response.status_code
            if code in (401, 402, 403):
                if "credit" in str(detail).lower() or "balance" in str(detail).lower():
                    return ("⚠ La cuenta del provider no tiene créditos.\n"
                            f"Detalle: {detail}\n\n"
                            "Cargá saldo en el panel de billing del provider.")
                return ("⚠ API key inválida o vencida.\n"
                        f"Detalle: {detail}\n\n"
                        "Revisá la key en ⚙ → ＋ → Providers (o generá una nueva).")
            if code in (400, 404, 500, 503):
                return (f"⚠ El provider rechazó la petición ({code}).\n"
                        f"Detalle: {detail}\n\n"
                        f"Revisa el modelo '{self.model}', los créditos de la cuenta "
                        "o prueba otro modelo del combo.")
        if isinstance(e, RuntimeError):
            return str(e)
        return f"Error: {e}"

    def _emit_stats(self, total_time):
        u = self.usage
        tps = u["completion"] / u["gen_time"] if u["gen_time"] > 0 else 0
        now = time.strftime("%H:%M:%S")
        pid = self.prompt_id or "?"
        self.msg.emit(
            f"response-{pid} · {now} · {total_time:.1f}s · "
            f"{u['completion']} tok · {tps:.1f} tok/s · prompt: {u['prompt']} tok · 🤖 {self.model}",
            "stats")
        self.turn_usage.emit({
            "prompt": u["prompt"],
            "completion": u["completion"],
            "total_time": total_time,
            "model": self.model,
        })


class FnThread(QThread):
    ok = Signal(object)
    fail = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        try:
            self.ok.emit(self._fn())
        except Exception as e:
            self.fail.emit(str(e))


class Input(QPlainTextEdit):
    sent = Signal()
    file_dropped = Signal(str)   # emite la ruta del archivo soltado (del árbol)
    image_dropped = Signal(str)  # emite la ruta de una imagen soltada (externa)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.source() is not None:
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dropEvent(self, e):
        # Si viene del file_tree (internal drag), el source es un QTreeWidget
        src = e.source()
        if src is not None and hasattr(src, "currentItem"):
            item = src.currentItem()
            if item is not None:
                path = item.data(0, Qt.UserRole)
                if path:
                    self.file_dropped.emit(path)
                    e.acceptProposedAction()
                    return
        # Si viene de afuera (finder), ver si es imagen o archivo
        if e.mimeData().hasUrls():
            for url in e.mimeData().urls():
                p = url.toLocalFile()
                if p:
                    ext = os.path.splitext(p)[1].lower()
                    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
                        self.image_dropped.emit(p)
                    else:
                        self.file_dropped.emit(p)
            e.acceptProposedAction()
            return
        super().dropEvent(e)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not (e.modifiers() & Qt.ShiftModifier):
            self.sent.emit()
        else:
            super().keyPressEvent(e)


class SkillsDialog(QDialog):
    def __init__(self, parent, skills_dir, cwd):
        super().__init__(parent)
        self.setWindowTitle("Skills")
        self.resize(640, 420)
        self.skills_dir = skills_dir
        self.cwd = cwd
        v = QVBoxLayout(self)
        v.addWidget(QLabel(f"Skills disponibles en {skills_dir}:"))
        self.listw = QListWidget()
        self.listw.currentRowChanged.connect(self._load)
        v.addWidget(self.listw, 1)
        form = QHBoxLayout()
        form.addWidget(QLabel("Argumentos:"))
        self.args_edit = QLineEdit()
        self.args_edit.setPlaceholderText("ej: index.html  (url o archivo, según la skill)")
        form.addWidget(self.args_edit, 1)
        v.addLayout(form)
        self.out = QPlainTextEdit()
        self.out.setReadOnly(True)
        self.out.setStyleSheet("font-family:Menlo,monospace; font-size:11px")
        self.out.setPlaceholderText("La salida de la skill aparecerá aquí…")
        v.addWidget(self.out, 1)
        row = QHBoxLayout()
        b_run = QPushButton("▶ Ejecutar")
        b_run.clicked.connect(self._run)
        b_close = QPushButton("Cerrar")
        b_close.clicked.connect(self.accept)
        row.addWidget(b_run)
        row.addStretch(1)
        row.addWidget(b_close)
        v.addLayout(row)
        self._reload()
        if self.listw.count():
            self.listw.setCurrentRow(0)

    def _skills(self):
        try:
            return sorted(f for f in os.listdir(self.skills_dir) if f.endswith(".py"))
        except OSError:
            return []

    def _reload(self):
        self.listw.clear()
        for f in self._skills():
            desc = ""
            try:
                with open(os.path.join(self.skills_dir, f), encoding="utf-8") as fh:
                    for ln in fh.read().split('"""')[1].splitlines():
                        if ln.strip():
                            desc = ln.strip()
                            break
            except Exception:
                pass
            self.listw.addItem(f"{f[:-3]}  —  {desc}" if desc else f[:-3])

    def _load(self, row):
        pass

    def _run(self):
        row = self.listw.currentRow()
        if row < 0:
            return
        script = os.path.join(self.skills_dir, self._skills()[row])
        args = self.args_edit.text().strip()
        self.out.appendPlainText(f"$ {self._skills()[row]} {args}")
        try:
            r = subprocess.run([sys.executable, os.path.join(self.skills_dir, self._skills()[row])]
                               + shlex.split(args), capture_output=True, text=True,
                               timeout=180, cwd=self.cwd)
            self.out.appendPlainText(r.stdout.strip() or "(sin salida)")
            if r.stderr.strip():
                self.out.appendPlainText("STDERR:\n" + r.stderr.strip())
        except subprocess.TimeoutExpired:
            self.out.appendPlainText("ERROR: timeout (180s)")
        self.out.appendPlainText("")


class ImageViewerDialog(QDialog):
    """Visor de imágenes: SVG, PNG, JPG, GIF, WEBP, BMP."""
    IMG_EXTS = {".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

    def __init__(self, parent, path, rel):
        super().__init__(parent)
        self.setWindowTitle(f"🖼️ {rel}")
        self.resize(900, 700)
        self.path = path
        v = QVBoxLayout(self)
        # Info
        size = os.path.getsize(path) if os.path.exists(path) else 0
        ext = os.path.splitext(path)[1].lower()
        info = QLabel(f"<b>{rel}</b>  ·  {size:,} bytes  ·  {ext}")
        info.setTextFormat(Qt.RichText)
        v.addWidget(info)
        # Visor con scroll
        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background:#2a2a2a;")
        self.img_lbl = QLabel()
        self.img_lbl.setAlignment(Qt.AlignCenter)
        self.img_lbl.setStyleSheet("background:#2a2a2a;")
        scroll.setWidget(self.img_lbl)
        v.addWidget(scroll, 1)
        self._scale = 1.0
        self._base_pixmap = None
        self._load_image(ext)
        # Botones
        row = QHBoxLayout()
        btn_open_ext = QPushButton("Abrir en app externa")
        btn_open_ext.setToolTip("Abrir con la aplicación predeterminada del sistema")
        btn_open_ext.clicked.connect(self._open_external)
        row.addWidget(btn_open_ext)
        btn_zoom_in = QPushButton("🔍+")
        btn_zoom_in.clicked.connect(lambda: self._zoom(1.25))
        row.addWidget(btn_zoom_in)
        btn_zoom_out = QPushButton("🔍-")
        btn_zoom_out.clicked.connect(lambda: self._zoom(0.8))
        row.addWidget(btn_zoom_out)
        btn_fit = QPushButton("Ajustar")
        btn_fit.clicked.connect(self._fit)
        row.addWidget(btn_fit)
        row.addStretch(1)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        row.addWidget(btn_close)
        v.addLayout(row)
        self._scale = 1.0

    def _load_image(self, ext):
        from PySide6.QtGui import QPixmap
        if ext == ".svg":
            from PySide6.QtSvg import QSvgRenderer
            from PySide6.QtGui import QImage, QPainter
            renderer = QSvgRenderer(self.path)
            if renderer.isValid():
                img = QImage(800, 600, QImage.Format_ARGB32)
                img.fill(0)
                p = QPainter(img)
                renderer.render(p)
                p.end()
                self._base_pixmap = QPixmap.fromImage(img)
            else:
                self.img_lbl.setText("No se pudo cargar el SVG")
                return
        else:
            self._base_pixmap = QPixmap(self.path)
        if self._base_pixmap.isNull():
            self.img_lbl.setText("No se pudo cargar la imagen")
            return
        self._fit()

    def _fit(self):
        if not self._base_pixmap:
            return
        avail = self.img_lbl.parent().size() if self.img_lbl.parent() else QSize(800, 600)
        pw, ph = self._base_pixmap.width(), self._base_pixmap.height()
        if pw == 0 or ph == 0:
            return
        sx = avail.width() / pw
        sy = avail.height() / ph
        self._scale = min(sx, sy, 1.0)
        self._apply_scale()

    def _zoom(self, factor):
        if not self._base_pixmap:
            return
        self._scale *= factor
        self._apply_scale()

    def _apply_scale(self):
        if not self._base_pixmap:
            return
        w = max(1, int(self._base_pixmap.width() * self._scale))
        h = max(1, int(self._base_pixmap.height() * self._scale))
        self.img_lbl.setPixmap(self._base_pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _open_external(self):
        import subprocess, sys
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", self.path])
            elif sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", self.path])
            else:
                subprocess.Popen(["start", "", self.path], shell=True)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo abrir: {e}")


class FileEditorDialog(QDialog):
    """Editor/visor de archivos del workspace. Muestra diff si la IA tocó el archivo."""
    def __init__(self, parent, path, rel, tools):
        super().__init__(parent)
        self.setWindowTitle(f"📄 {rel}")
        self.resize(760, 600)
        self.path = path
        self.rel = rel
        self.tools = tools
        v = QVBoxLayout(self)
        ch = tools.recent_changes.get(rel)
        added = ch.get("added", 0) if ch else 0
        removed = ch.get("removed", 0) if ch else 0
        kind = ch["kind"] if ch else None
        if kind == "created":
            badge = f'<span style="color:#22c55e">✨ Creado por la IA (+{added} líneas)</span>'
        elif kind == "modified":
            badge = (f'<span style="color:#22c55e">✏️ Modificado (+{added}</span> / '
                     f'<span style="color:#ef4444">-{removed} líneas)</span>')
        else:
            badge = f"{os.path.getsize(path)} bytes"
        info = QLabel(f"<b>{rel}</b>  ·  {badge}")
        info.setTextFormat(Qt.RichText)
        v.addWidget(info)

        # Vista de diff (solo lectura) si hay cambios, sino editor normal
        self.has_diff = bool(ch and ch.get("diff"))
        if self.has_diff:
            self.diff_view = QTextEdit()
            self.diff_view.setReadOnly(True)
            self.diff_view.setStyleSheet(
                "font-family:Menlo,monospace; font-size:12px; background:#1a1a1a;")
            self._render_diff(ch["diff"])
            v.addWidget(self.diff_view, 1)
            # También editor editable debajo, plegado
            toggle = QPushButton("▼ Editar archivo directamente")
            toggle.setObjectName("accent")
            toggle.setCheckable(True)
            toggle.toggled.connect(lambda on: (self.edit.setVisible(on),
                                  toggle.setText("▲ Ocultar editor" if on else "▼ Editar archivo directamente")))
            v.addWidget(toggle)
            self.edit = QPlainTextEdit()
            self.edit.setStyleSheet("font-family:Menlo,monospace; font-size:12px;")
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    self.edit.setPlainText(f.read())
            except Exception as e:
                self.edit.setPlainText(f"(no se pudo leer: {e})")
            self.edit.setVisible(False)
            v.addWidget(self.edit, 1)
        else:
            self.diff_view = None
            self.edit = QPlainTextEdit()
            self.edit.setStyleSheet("font-family:Menlo,monospace; font-size:12px;")
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    self.edit.setPlainText(f.read())
            except Exception as e:
                self.edit.setPlainText(f"(no se pudo leer: {e})")
            v.addWidget(self.edit, 1)

        row = QHBoxLayout()
        self.btn_save = QPushButton("💾 Guardar")
        self.btn_save.setObjectName("success")
        self.btn_save.clicked.connect(self._save)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        row.addWidget(self.btn_save)
        row.addStretch(1)
        row.addWidget(btn_close)
        v.addLayout(row)

    def _render_diff(self, diff_lines):
        """Pinta el diff con colores: rojo eliminado, verde agregado."""
        html = []
        for kind, text in diff_lines:
            esc = (text.replace("&", "&").replace("<", "<")
                   .replace(">", ">"))
            if kind == "del":
                html.append(f'<div style="background:#3b1414;color:#ff6b6b;">- {esc}</div>')
            elif kind == "add":
                html.append(f'<div style="background:#143b1e;color:#7cff6b;">+ {esc}</div>')
            else:
                html.append(f'<div style="color:#888;">{esc}</div>')
        self.diff_view.setHtml("<pre style='margin:0'>" + "".join(html) + "</pre>")

    def _save(self):
        try:
            self.tools._save(self.rel, self.edit.toPlainText())
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))


class PrefsDialog(QDialog):
    """Preferencias del usuario: modelos preferidos, límites de tokens, budget."""
    def __init__(self, parent, prefs, all_models):
        super().__init__(parent)
        self.setWindowTitle("⚙ Preferencias")
        self.resize(480, 440)
        self.prefs = dict(prefs)  # copia para no modificar hasta OK
        self.all_models = all_models
        form = QFormLayout(self)
        # Modelos preferidos
        self.combo_primary = QComboBox()
        self.combo_secondary = QComboBox()
        self.combo_vision = QComboBox()
        for c in (self.combo_primary, self.combo_secondary, self.combo_vision):
            c.addItem("(usar el del combo)", "")
            for m in all_models:
                c.addItem(m)
        self._set_combo(self.combo_primary, prefs.get("primary_model", ""))
        self._set_combo(self.combo_secondary, prefs.get("secondary_model", ""))
        self._set_combo(self.combo_vision, prefs.get("vision_model", ""))
        form.addRow("Modelo primario:", self.combo_primary)
        form.addRow("Modelo secundario:", self.combo_secondary)
        form.addRow("Modelo para imágenes:", self.combo_vision)
        # Max tokens de conversación (auto-resumir)
        self.spin_max_tokens = QSpinBox()
        self.spin_max_tokens.setRange(1000, 1000000)
        self.spin_max_tokens.setSingleStep(5000)
        self.spin_max_tokens.setValue(int(prefs.get("max_context_tokens", 50000)))
        form.addRow("Auto-resumir si el contexto pasa de (tokens):", self.spin_max_tokens)
        self.chk_auto_summarize = QCheckBox("Resumir automáticamente al superar el límite")
        self.chk_auto_summarize.setChecked(bool(prefs.get("auto_summarize", True)))
        form.addRow("", self.chk_auto_summarize)
        # Budget por carpeta
        self.spin_budget = QSpinBox()
        self.spin_budget.setRange(1000, 10000000)
        self.spin_budget.setSingleStep(10000)
        self.spin_budget.setValue(int(prefs.get("token_budget", 50000)))
        form.addRow("Budget de tokens para esta carpeta:", self.spin_budget)
        # Botones
        row = QHBoxLayout()
        btn_ok = QPushButton("Guardar")
        btn_ok.setObjectName("success")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        row.addStretch(1)
        row.addWidget(btn_cancel)
        row.addWidget(btn_ok)
        form.addRow(row)

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
            "max_context_tokens": self.spin_max_tokens.value(),
            "auto_summarize": self.chk_auto_summarize.isChecked(),
            "token_budget": self.spin_budget.value(),
        }


def api_url(base, path):
    """Une base + path sin duplicar /v1 (acepta bases con o sin /v1)."""
    base = (base or "").rstrip("/")
    if base.endswith("/v1"):
        return base + path
    return base + "/v1" + path


def fetch_models(base, key=""):
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    r = requests.get(api_url(base, "/models"), headers=headers, timeout=8)
    r.raise_for_status()
    r.encoding = "utf-8"
    return [m["id"] for m in r.json().get("data", []) if "embed" not in m["id"].lower()]


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

    def values(self):
        if self.tabs.currentIndex() == 0:
            return (self.local_name.text().strip(),
                    self.local_base.text().strip().rstrip("/"),
                    self.local_key.text().strip())
        row = self.cloud_list.currentRow()
        if row < 0:
            return "", "", ""
        name, base = CLOUD_PRESETS[row]
        return name, base, self.cloud_key.text().strip()


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
        b_add.setToolTip("Añadir provider (endpoint OpenAI-compatible)")
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
        try:
            return fetch_models(cfg.get("base", ""), cfg.get("key", "")), None
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
        text = self.picker_filter.text().strip().lower() if hasattr(self, "picker_filter") else ""
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


class RunDialog(QDialog):
    def __init__(self, parent, configs):
        super().__init__(parent)
        self.setWindowTitle("Running configs")
        self.resize(640, 340)
        self.configs = [dict(c) for c in configs]
        self._editing = -1

        h = QHBoxLayout(self)

        left = QVBoxLayout()
        tb = QHBoxLayout()
        b_add = QPushButton("＋")
        b_add.setFixedWidth(36)
        b_add.setToolTip("Añadir configuración")
        b_add.clicked.connect(self._add)
        b_del = QPushButton("−")
        b_del.setFixedWidth(32)
        b_del.setToolTip("Quitar configuración")
        b_del.clicked.connect(self._remove)
        tb.addWidget(b_add)
        tb.addWidget(b_del)
        tb.addStretch(1)
        left.addLayout(tb)
        self.listw = QListWidget()
        self.listw.currentRowChanged.connect(self._load_row)
        left.addWidget(self.listw, 1)
        h.addLayout(left, 0)

        right = QVBoxLayout()
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.cmd_edit = QLineEdit()
        self.cmd_edit.setPlaceholderText("ej: node server.js")
        form.addRow("Nombre:", self.name_edit)
        form.addRow("Comando:", self.cmd_edit)
        hint = QLabel("El comando se ejecuta con la carpeta de trabajo como directorio actual.")
        hint.setWordWrap(True)
        form.addRow(hint)
        right.addLayout(form, 1)

        btns = QHBoxLayout()
        b_run = QPushButton("▶ Ejecutar")
        b_run.clicked.connect(self._run)
        b_cancel = QPushButton("Cancelar")
        b_cancel.clicked.connect(self.reject)
        b_ok = QPushButton("OK")
        b_ok.setDefault(True)
        b_ok.clicked.connect(self._ok)
        btns.addWidget(b_run)
        btns.addStretch(1)
        btns.addWidget(b_cancel)
        btns.addWidget(b_ok)
        right.addLayout(btns)
        h.addLayout(right, 1)

        self._reload()
        if self.configs:
            self.listw.setCurrentRow(0)

    def _flush(self):
        if 0 <= self._editing < len(self.configs):
            self.configs[self._editing]["name"] = self.name_edit.text().strip() or "sin nombre"
            self.configs[self._editing]["cmd"] = self.cmd_edit.text().strip()
            self.listw.item(self._editing).setText(
                f'{self.configs[self._editing]["name"]}  —  {self.configs[self._editing]["cmd"]}')

    def _load_row(self, row):
        self._flush()
        self._editing = row
        if 0 <= row < len(self.configs):
            self.name_edit.setText(self.configs[row]["name"])
            self.cmd_edit.setText(self.configs[row]["cmd"])

    def _reload(self):
        self.listw.clear()
        for c in self.configs:
            self.listw.addItem(f'{c["name"]}  —  {c["cmd"]}')

    def _add(self):
        self._flush()
        self.configs.append({"name": "nueva", "cmd": ""})
        self._reload()
        self.listw.setCurrentRow(len(self.configs) - 1)

    def _remove(self):
        row = self.listw.currentRow()
        if row >= 0:
            self.listw.takeItem(row)
            self.configs.pop(row)
            self._editing = -1
            self.name_edit.clear()
            self.cmd_edit.clear()

    def selected_cmd(self):
        self._flush()
        row = self.listw.currentRow()
        if 0 <= row < len(self.configs):
            return self.configs[row]["cmd"]
        return None

    def _run(self):
        self._flush()
        row = self.listw.currentRow()
        if 0 <= row < len(self.configs):
            self._run_cmd = self.configs[row]["cmd"]
        self.accept()

    def _ok(self):
        self._flush()
        self.accept()


class BudgetBar(QWidget):
    """Barra de progreso del budget de tokens del proyecto."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(14)
        self.setMaximumHeight(14)
        self._used = 0
        self._budget = 50000

    def set_values(self, used, budget):
        self._used = used
        self._budget = max(1, budget)
        self.update()

    def paintEvent(self, e):
        from PySide6.QtGui import QPainter, QColor
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#222529"))
        ratio = min(1.0, self._used / self._budget)
        bw = int(w * ratio)
        if ratio < 0.5:
            color = QColor("#22c55e")
        elif ratio < 0.8:
            color = QColor("#eab308")
        else:
            color = QColor("#ef4444")
        p.fillRect(0, 0, bw, h, color)
        p.setPen(QColor("#fff"))
        from PySide6.QtGui import QFont
        f = QFont()
        f.setPointSize(7)
        p.setFont(f)
        p.drawText(self.rect(), 0x84, f"{self._used:,} / {self._budget:,} ({ratio*100:.0f}%)")
        p.end()


class TokenBar(QWidget):
    """Mini gráfico de barras: una barra por turno, altura = tokens del turno."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(28)
        self.setMaximumHeight(28)
        self.setMouseTracking(True)
        self._turns = []      # lista de dicts del token_log
        self._bar_rects = []  # lista de (x, w, info_dict) para hit-test

    def set_turns(self, turns):
        # turns = lista de dicts {label, prompt, completion, total_time, model}
        self._turns = turns
        self.update()

    def paintEvent(self, e):
        from PySide6.QtGui import QPainter, QColor
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#222529"))
        self._bar_rects = []
        if not self._turns:
            p.setPen(QColor("#555"))
            p.drawText(self.rect(), 0x84, "(sin uso todavía)")
            p.end()
            return
        max_t = max((t["prompt"] + t["completion"] for t in self._turns), default=1) or 1
        n = len(self._turns)
        bar_w = max(6, min(24, (w - 4) // max(n, 1)))
        gap = 2
        x = 2
        for t in self._turns:
            tot = t["prompt"] + t["completion"]
            ratio = tot / max_t
            if ratio < 0.4:
                color = "#22c55e"
            elif ratio < 0.75:
                color = "#eab308"
            else:
                color = "#ef4444"
            bh = max(2, int(h * 0.85 * tot / max_t))
            p.fillRect(x, h - bh - 2, bar_w, bh, QColor(color))
            self._bar_rects.append((x, bar_w, t))
            x += bar_w + gap
            if x + bar_w > w:
                break
        p.end()

    def event(self, ev):
        from PySide6.QtCore import QEvent
        if ev.type() == QEvent.ToolTip and self._bar_rects:
            mx = ev.position().x() if hasattr(ev, "position") else ev.pos().x()
            for bx, bw, info in self._bar_rects:
                if bx <= mx <= bx + bw:
                    tot = info["prompt"] + info["completion"]
                    tip = (f"<b>{info['label']}</b> — {tot:,} tokens<br>"
                           f"Prompt: {info['prompt']:,} tok<br>"
                           f"Completion: {info['completion']:,} tok<br>"
                           f"Modelo: {info.get('model', '?')}<br>"
                           f"Tiempo: {info.get('total_time', 0):.1f}s")
                    self.setToolTip(tip)
                    return super().event(ev)
            self.setToolTip("")
            return True
        return super().event(ev)


class VoiceTranscriber(QThread):
    """Transcribe un archivo WAV a texto usando speech_recognition."""
    done = Signal(str)
    error = Signal(str)

    def __init__(self, wav_path, parent=None):
        super().__init__(parent)
        self.wav_path = wav_path

    def run(self):
        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            with sr.AudioFile(self.wav_path) as source:
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


class AudioMeter(QWidget):
    """Barra visualizadora de nivel de audio mientras se graba."""
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
        # Simular niveles de audio con algo de variación
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


SOUNDS = {
    "rec_start": "/System/Library/Sounds/Pop.aiff",
    "rec_stop": "/System/Library/Sounds/Glass.aiff",
    "send": "/System/Library/Sounds/Ping.aiff",
    "done": "/System/Library/Sounds/Hero.aiff",
}


def play_sound(name):
    """Reproduce un sonido del sistema en un thread separado (no bloquea la UI)."""
    path = SOUNDS.get(name)
    if not path or not os.path.exists(path):
        return
    import subprocess, sys
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["afplay", path],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


class MainWindow(QMainWindow):
    COLORS = {"user": "#eab308", "tool": "#8e8e93", "error": "#ff453a", "stats": "#32ade6"}
    LABELS = {"user": "Tú", "assistant": "IA", "tool": "Herramienta", "error": "Error", "stats": "⚙"}

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chat IA local — LM Studio")
        self.resize(860, 640)
        self.history = []
        self.pinned = []
        self._bookmarks = []
        self.last_prompt = 0
        self.ctx_limits = {}
        self.worker = None
        self.token_log = []  # lista de {prompt, completion, total_time, model, label}
        self.pending_images = []  # lista de paths de imágenes pendientes de enviar
        self._stream_active = False
        self._threads = []
        self._prompt_counter = 0  # contador secuencial de prompts por carpeta
        self._current_prompt_id = None  # id del prompt actual (para la respuesta)
        self._excluded_turns = set()  # turnos excluidos del contexto (por número)
        self._rec_proc = None  # proceso de ffmpeg para grabación de voz
        self._voice_thread = None  # thread de transcripción
        self._rec_timer = None  # QTimer para timeout de grabación

        self.settings = QSettings("ChatIA", "ChatIA")
        # Preferencias del usuario
        try:
            self.prefs = json.loads(self.settings.value("prefs", "{}")) or {}
        except (ValueError, TypeError):
            self.prefs = {}
        if not self.prefs:
            self.prefs = {"max_context_tokens": 50000, "auto_summarize": True,
                          "token_budget": 50000}
        # Budget de tokens por carpeta
        try:
            budgets = json.loads(self.settings.value("token_budgets", "{}")) or {}
        except (ValueError, TypeError):
            budgets = {}
        self.token_budgets = budgets

        recent = self.settings.value("recent_folders", []) or []
        if isinstance(recent, str):
            recent = [recent]
        recent = [f for f in recent if os.path.isdir(f)]
        current = self.settings.value("workspace", "") or ""
        if not os.path.isdir(current):
            current = os.getcwd()
        self.tools = Tools(current)
        self.proc = None
        self._last_run_idx = 0
        self._stream_active = False
        try:
            self.providers = json.loads(self.settings.value("providers", "null")) or {}
        except (ValueError, TypeError):
            self.providers = {}
        if not self.providers:
            self.providers = {"LM Studio": {"base": LMSTUDIO, "key": ""}}
        try:
            self.pinned = json.loads(self.settings.value("pinned_models", "[]")) or []
        except (ValueError, TypeError):
            self.pinned = []
        try:
            self.custom_configs = json.loads(self.settings.value("custom_run_configs", "[]"))
        except (ValueError, TypeError):
            self.custom_configs = []

        central = QWidget()
        self.setCentralWidget(central)
        main_row = QHBoxLayout(central)

        fpanel = QVBoxLayout()
        fpanel.addWidget(QLabel("Carpeta:"))
        self.folder_combo = QComboBox()
        self.folder_combo.activated.connect(self.on_folder_selected)
        self.folder_combo.addItems(recent)
        i = self.folder_combo.findText(current)
        if i < 0:
            self.folder_combo.insertItem(0, current)
            i = 0
        self.folder_combo.setCurrentIndex(i)
        fpanel.addWidget(self.folder_combo)
        frow_folder = QHBoxLayout()
        btn_folder = QPushButton("Elegir…")
        btn_folder.setToolTip("Añadir carpeta a la lista")
        btn_folder.clicked.connect(self.choose_folder)
        btn_del = QPushButton("✕")
        btn_del.setToolTip("Quitar carpeta de la lista")
        btn_del.clicked.connect(self.remove_folder)
        frow_folder.addWidget(btn_folder, 1)
        frow_folder.addWidget(btn_del)
        fpanel.addLayout(frow_folder)
        fpanel.addSpacing(6)
        fpanel.addWidget(QLabel("Archivos"))
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setColumnCount(2)
        self.file_tree.header().setStretchLastSection(False)
        from PySide6.QtWidgets import QHeaderView
        self.file_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.file_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.file_tree.setDragEnabled(True)
        self.file_tree.itemDoubleClicked.connect(self.on_file_double)
        self.file_tree.setToolTip("Doble clic: abrir editor · Arrastrar al chat: pedir edición")
        fpanel.addWidget(self.file_tree, 1)
        frow = QHBoxLayout()
        btn_index = QPushButton("🧠 Indexar")
        btn_index.setToolTip("Genera/actualiza indexado.txt: mapa del proyecto con funciones y propósito")
        btn_index.clicked.connect(self.index_project)
        btn_files = QPushButton("↻")
        btn_files.setToolTip("Refrescar lista de archivos")
        btn_files.clicked.connect(self.refresh_files)
        btn_open = QPushButton("📄 Abrir")
        btn_open.setToolTip("Abrir el archivo seleccionado en el editor")
        btn_open.clicked.connect(self.open_selected_file)
        frow.addWidget(btn_index)
        frow.addWidget(btn_files)
        frow.addWidget(btn_open)
        fpanel.addLayout(frow)
        fw = QWidget()
        fw.setLayout(fpanel)
        fw.setFixedWidth(160)
        main_row.addWidget(fw)

        v = QVBoxLayout()
        rw = QWidget()
        rw.setLayout(v)
        main_row.addWidget(rw, 1)

        bpanel = QVBoxLayout()
        self.bm_list = QListWidget()
        self.bm_list.itemClicked.connect(self._goto_bookmark)
        self.bm_list.setToolTip("Clic para ir a ese punto de la conversación")
        bpanel.addWidget(self.bm_list, 1)

        panel = QVBoxLayout()
        self.conv_list = QListWidget()
        self.conv_list.itemClicked.connect(self.on_conv_clicked)
        panel.addWidget(self.conv_list, 1)
        btnrow = QHBoxLayout()
        btn_new = QPushButton("＋ Nueva")
        btn_new.clicked.connect(self.new_conv)
        btn_del_conv = QPushButton("🗑")
        btn_del_conv.setToolTip("Eliminar conversación")
        btn_del_conv.clicked.connect(self.delete_conv)
        btnrow.addWidget(btn_new)
        btnrow.addWidget(btn_del_conv)
        panel.addLayout(btnrow)

        panel.addWidget(QLabel("Notas guardadas"))
        self.pinned_list = QListWidget()
        self.pinned_list.setMaximumHeight(90)
        panel.addWidget(self.pinned_list)
        pinrow = QHBoxLayout()
        btn_pin = QPushButton("📌")
        btn_pin.setToolTip("Guardar el texto seleccionado del chat (sobrevive al resumir)")
        btn_pin.clicked.connect(self.pin_selected)
        btn_unpin = QPushButton("✕")
        btn_unpin.setToolTip("Quitar nota seleccionada")
        btn_unpin.clicked.connect(self.unpin)
        pinrow.addWidget(btn_pin)
        pinrow.addWidget(btn_unpin)
        panel.addLayout(pinrow)

        self.ctx_lbl = QLabel("Contexto: 0 KB")
        panel.addWidget(self.ctx_lbl)
        self.btn_sum = QPushButton("🗜 Resumir contexto")
        self.btn_sum.setToolTip("Resume la conversación; se conservan las notas guardadas")
        self.btn_sum.clicked.connect(self.summarize)
        panel.addWidget(self.btn_sum)

        runpanel = QVBoxLayout()
        # Fila 1: total de tokens + botón preferencias
        tok_row = QHBoxLayout()
        tok_row.addWidget(QLabel("🪙"))
        self.tok_total_lbl = QLabel("0")
        self.tok_total_lbl.setStyleSheet(
            "color:#7cff6b; font-weight:bold; font-family:Menlo,monospace;")
        tok_row.addWidget(self.tok_total_lbl)
        tok_row.addStretch(1)
        # Botón preferencias (tuerca)
        self.btn_prefs = icon_btn("tuerca", 28, "#3a3d44", "#fff", "Preferencias del usuario")
        self.btn_prefs.clicked.connect(self.open_prefs)
        tok_row.addWidget(self.btn_prefs)
        runpanel.addLayout(tok_row)
        # Fila 2: barra de budget del proyecto
        self.budget_lbl = QLabel("Budget: 0 / 50,000 (0%)")
        self.budget_lbl.setStyleSheet("font-size:10px; color:#888;")
        runpanel.addWidget(self.budget_lbl)
        self.budget_bar = BudgetBar()
        runpanel.addWidget(self.budget_bar)
        # Fila 3: barra de tokens por turno
        self.tok_bar = TokenBar()
        runpanel.addWidget(self.tok_bar)
        runpanel.addWidget(QLabel("Ejecutar:"))
        self.run_combo = QComboBox()
        self.run_combo.activated.connect(self.on_run_activated)
        runpanel.addWidget(self.run_combo)
        runbtns = QHBoxLayout()
        btn_play = QPushButton("▶")
        btn_play.setObjectName("success")
        btn_play.setToolTip("Ejecutar la configuración seleccionada")
        btn_play.clicked.connect(self.run_config)
        btn_stop_proc = QPushButton("⏹")
        btn_stop_proc.setObjectName("danger")
        btn_stop_proc.setToolTip("Detener el proceso")
        btn_stop_proc.clicked.connect(self.stop_config)
        btn_stop_proc.setEnabled(False)
        self.btn_stop_proc = btn_stop_proc
        btn_skills = QPushButton("🧩 Skills")
        btn_skills.setObjectName("accent")
        btn_skills.setToolTip("Ver y ejecutar skills (Skills-py)")
        btn_skills.clicked.connect(self.open_skills)
        runbtns.addWidget(btn_play, 1)
        runbtns.addWidget(btn_stop_proc, 1)
        runbtns.addWidget(btn_skills, 1)
        runpanel.addLayout(runbtns)
        run_w = QWidget()
        run_w.setLayout(runpanel)

        conv_w = QWidget()
        conv_w.setLayout(panel)
        bm_w = QWidget()
        bm_w.setLayout(bpanel)

        # Pestaña de cambios recientes de la IA
        chpanel = QVBoxLayout()
        chpanel.addWidget(QLabel("Archivos tocados por la IA:"))
        self.changes_list = QListWidget()
        self.changes_list.itemClicked.connect(self._on_change_clicked)
        self.changes_list.setToolTip("Clic para abrir el editor; verde = nuevo, naranja = editado")
        chpanel.addWidget(self.changes_list, 1)
        btn_clear_changes = QPushButton("Limpiar marcas")
        btn_clear_changes.setToolTip("Borra el registro de cambios (no borra los archivos)")
        btn_clear_changes.clicked.connect(self._clear_changes)
        chpanel.addWidget(btn_clear_changes)
        ch_w = QWidget()
        ch_w.setLayout(chpanel)

        # Pestaña de turnos con tokens y checkboxes
        turnpanel = QVBoxLayout()
        self.turn_list = QListWidget()
        self.turn_list.setStyleSheet("font-family:Menlo,monospace; font-size:11px;")
        self.turn_list.itemChanged.connect(self._on_turn_check_changed)
        turnpanel.addWidget(self.turn_list, 1)
        self.turn_summary_lbl = QLabel("0 turnos · 0 tok totales · 0 tok ahorrados")
        self.turn_summary_lbl.setStyleSheet("font-size:11px; color:#888; padding:4px;")
        turnpanel.addWidget(self.turn_summary_lbl)
        turn_w = QWidget()
        turn_w.setLayout(turnpanel)

        self.side_tabs = QTabWidget()
        self.side_tabs.addTab(conv_w, "Conversaciones")
        self.side_tabs.addTab(bm_w, "🔖 Mensajes")
        self.side_tabs.addTab(turn_w, "📊 Turnos")
        self.side_tabs.addTab(ch_w, "✏️ Cambios")

        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.addWidget(run_w)
        right_col.addWidget(self.side_tabs, 1)
        right_w = QWidget()
        right_w.setLayout(right_col)
        right_w.setFixedWidth(250)
        main_row.addWidget(right_w)

        # Terminal toggleable (reemplaza run_out)
        self.terminal = QPlainTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setMaximumHeight(150)
        self.terminal.setStyleSheet(
            "font-family:Menlo,monospace; font-size:12px; background:#0a0a0a; color:#e0e0e0;")
        self.terminal.setVisible(False)
        self.term_proc = None
        # Botón para toggle de terminal
        self.btn_term = QPushButton("▶ Terminal")
        self.btn_term.setFixedHeight(22)
        self.btn_term.setStyleSheet("font-size:11px; background:#2a2a2a; color:#888; border:none;")
        self.btn_term.setToolTip("Mostrar/ocultar la terminal")
        self.btn_term.clicked.connect(self._toggle_terminal)
        self.btn_term.setVisible(False)
        v.addWidget(self.btn_term)
        v.addWidget(self.terminal)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Modelo:"))
        self.model_combo = QComboBox()
        self._all_models = []
        btn_pick = QPushButton("⚙")
        btn_pick.setToolTip("Providers y pines de modelos")
        btn_pick.clicked.connect(self.open_model_picker)
        btn_refresh = QPushButton("↻")
        btn_refresh.setToolTip("Re-descubrir modelos de todos los providers")
        btn_refresh.clicked.connect(self.refresh_models)
        row2.addWidget(self.model_combo, 1)
        self.model_filter = QLineEdit()
        self.model_filter.setPlaceholderText("🔍 filtrar…")
        self.model_filter.setClearButtonEnabled(True)
        self.model_filter.setMaximumWidth(150)
        self.model_filter.textChanged.connect(self._apply_model_filter)
        row2.addWidget(self.model_filter)
        row2.addWidget(btn_pick)
        row2.addWidget(btn_refresh)
        v.addLayout(row2)

        self.chat = QTextEdit()
        self.chat.setObjectName("chatView")
        self.chat.setReadOnly(True)
        v.addWidget(self.chat, 1)

        row3 = QHBoxLayout()
        input_col = QVBoxLayout()
        input_col.setSpacing(2)
        # Zona de preview de imágenes adjuntas
        self.img_preview = QHBoxLayout()
        self.img_preview.setSpacing(4)
        self._img_thumbs = []  # lista de (path, QLabel, QPushButton)
        self.img_preview.addStretch(1)
        self.img_w = QWidget()
        self.img_w.setLayout(self.img_preview)
        self.img_w.setMaximumHeight(60)
        self.img_w.setStyleSheet("background: transparent;")
        self.img_w.setVisible(False)
        input_col.addWidget(self.img_w)
        # Checkbox: enviar sin contexto (ahorra tokens)
        ctx_row = QHBoxLayout()
        ctx_row.setSpacing(4)
        self.chk_no_ctx = QCheckBox("Sin contexto")
        self.chk_no_ctx.setToolTip(
            "Si marcás esto, el mensaje se envía SIN el contexto del proyecto\n"
            "(sin system prompt, sin snapshot de archivos, sin indexado.txt).\n"
            "Ahorra tokens. La IA igual puede usar las herramientas de archivos.\n"
            "El historial de la conversación se mantiene.")
        self.chk_no_ctx.setStyleSheet("font-size:11px; color:#888;")
        ctx_row.addWidget(self.chk_no_ctx)
        self.chk_auto_send = QCheckBox("Auto-enviar voz")
        self.chk_auto_send.setToolTip(
            "Si marcás esto, al terminar la transcripción de voz\n"
            "el mensaje se envía automáticamente al modelo.")
        self.chk_auto_send.setStyleSheet("font-size:11px; color:#888;")
        ctx_row.addWidget(self.chk_auto_send)
        ctx_row.addStretch(1)
        input_col.addLayout(ctx_row)
        # Visualizador de audio (visible solo mientras graba)
        self.audio_meter = AudioMeter()
        self.audio_meter.setVisible(False)
        input_col.addWidget(self.audio_meter)
        # Fila: input + botones
        input_row = QHBoxLayout()
        input_row.setSpacing(4)
        self.input = Input()
        self.input.setFixedHeight(70)
        self.input.setPlaceholderText("Escribe aquí… (Enter envía, Shift+Enter salto de línea)")
        self.input.sent.connect(self.send)
        self.input.file_dropped.connect(self._on_file_dropped)
        self.input.image_dropped.connect(self._on_image_dropped)
        input_row.addWidget(self.input, 1)
        # Botón adjuntar (clip amarillo, icono negro)
        self.btn_attach = icon_btn("clip", 36, "#eab308", "#000",
                                   "Adjuntar imagen (PNG, JPG, GIF, WEBP)")
        self.btn_attach.clicked.connect(self._attach_image)
        input_row.addWidget(self.btn_attach)
        # Botón micrófono
        self.btn_mic = icon_btn("mic", 36, "#6b7280", "#fff",
                                "Hablar: clic para grabar, clic para parar")
        self.btn_mic.clicked.connect(self._toggle_voice)
        input_row.addWidget(self.btn_mic)
        input_col.addLayout(input_row)
        row3.addLayout(input_col, 1)
        col = QVBoxLayout()
        col.setSpacing(4)
        self.btn_send = icon_btn("enviar", 36, "#0a84ff", "#fff", "Enviar mensaje")
        self.btn_send.clicked.connect(self.send)
        self.btn_stop = icon_btn("detener", 36, "#ff453a", "#fff", "Detener generación")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_polish = icon_btn("pulir", 36, "#a855f7", "#fff",
                                   "Pulir: resume y mejora el texto antes de enviar")
        self.btn_polish.clicked.connect(self._polish_text)
        col.addWidget(self.btn_send)
        col.addWidget(self.btn_polish)
        col.addWidget(self.btn_stop)
        row3.addLayout(col)
        v.addLayout(row3)

        self.statusBar().showMessage(f"Conectando a {LMSTUDIO}…")
        self.append_chat(
            "Escribe una consulta. Puedo listar, leer, crear y editar archivos de la carpeta de trabajo.", "tool")
        self._ensure_contexto_txt()
        self.refresh_models()
        self.refresh_run_combo()

        os.makedirs(CONV_DIR, exist_ok=True)
        files = sorted(
            (os.path.join(CONV_DIR, f) for f in os.listdir(CONV_DIR) if f.endswith(".json")),
            key=os.path.getmtime, reverse=True)
        # Cargar la conversación más reciente que coincida con la carpeta actual
        current_folder = os.path.realpath(self.tools.root)
        loaded = False
        for fpath in files:
            try:
                with open(fpath, encoding="utf-8") as f:
                    data = json.load(f)
                conv_folder = data.get("folder", "")
                if conv_folder and os.path.realpath(conv_folder) == current_folder:
                    self.load_conv(fpath)
                    loaded = True
                    break
            except (OSError, ValueError):
                continue
        if not loaded:
            self.conv_path = self._new_conv_path()
        self.refresh_conv_list()
        self.update_ctx_label()

    def _on_stream_start(self):
        self._stream_active = True
        pid = self._current_prompt_id or "?"
        self.chat.append(f'<p style="color:#241f31"><b>response-{pid}:</b> </p>')
        self.chat.moveCursor(QTextCursor.End)

    def _on_stream_chunk(self, delta):
        self.chat.moveCursor(QTextCursor.End)
        self.chat.insertHtml(html.escape(delta))
        self.chat.ensureCursorVisible()

    def _on_stream_end(self, keep):
        if not keep:
            cursor = self.chat.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.movePosition(QTextCursor.StartOfBlock, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            cursor.deletePreviousChar()
        self._stream_active = False

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
            label = prompt_id or self.LABELS["user"]
        elif kind == "assistant":
            label = f"response-{self._current_prompt_id or '?'}"
        else:
            label = self.LABELS[kind]
        self.chat.append(f'<p style="{style}"><b>{label}:</b> {body}</p>')
        self.chat.moveCursor(QTextCursor.End)
        if kind == "user":
            self._add_bookmark(text)

    def _add_bookmark(self, text):
        pos = self.chat.textCursor().position()
        self._bookmarks.append((pos, text))
        short = text.replace("\n", " ")[:32] + ("…" if len(text) > 32 else "")
        it = QListWidgetItem("🔖 " + short)
        it.setData(Qt.UserRole, pos)
        it.setToolTip(text)
        it.setForeground(QColor("#eab308"))
        self.bm_list.addItem(it)

    def _goto_bookmark(self, item):
        pos = int(item.data(Qt.UserRole) or 0)
        cursor = self.chat.textCursor()
        cursor.setPosition(min(pos, max(0, self.chat.document().characterCount() - 1)))
        self.chat.setTextCursor(cursor)
        self.chat.ensureCursorVisible()

    def _clear_bookmarks(self):
        self._bookmarks = []
        self.bm_list.clear()

    def refresh_models(self):
        self.model_combo.clear()
        self.model_combo.addItem("(cargando…)")
        self.model_combo.setEnabled(False)
        providers = {k: dict(v) for k, v in self.providers.items()}
        pinned = list(self.pinned)

        def fn():
            out = {}
            for name, cfg in providers.items():
                try:
                    out[name] = fetch_models(cfg.get("base", ""), cfg.get("key", ""))
                except Exception as e:
                    out[name] = e
            return out

        t = FnThread(fn)
        t.ok.connect(self._on_models_all)
        t.fail.connect(self.on_models_fail)
        self._threads.append(t)
        t.start()

    def _on_models_all(self, result):
        self.model_combo.setEnabled(True)
        ok = {k: v for k, v in result.items() if isinstance(v, list)}
        bad = [k for k, v in result.items() if not isinstance(v, list)]
        items = []
        added = set()
        for ref in self.pinned:
            prov, _, model = ref.partition("::")
            if prov in ok and model in ok[prov]:
                items.append((f"📌 {model} · {prov}", ref))
                added.add(ref)
        for prov, ids in ok.items():
            for mid in ids:
                ref = f"{prov}::{mid}"
                if ref not in added:
                    items.append((f"{mid} · {prov}", ref))
        self._all_models = items
        for prov in bad:
            items.append((f"(⚠ {prov}: sin conexión)", ""))
        self._apply_model_filter()
        n = sum(len(v) for v in ok.values())
        msg = f"Modelos: {n} disponible(s)"
        if bad:
            msg += f" · {len(bad)} provider sin conexión"
        self.statusBar().showMessage(msg)

    def _apply_model_filter(self):
        text = self.model_filter.text().strip().lower()
        current = self.model_combo.currentData()
        self.model_combo.clear()
        n = 0
        for label, ref in getattr(self, "_all_models", []):
            if not text or text in label.lower():
                self.model_combo.addItem(label, ref)
        if self.model_combo.count() == 0:
            self.model_combo.addItem("(sin coincidencias)", "")
        # Priorizar el modelo primario del usuario sobre cualquier otro
        pm = self.prefs.get("primary_model", "")
        if pm:
            i = self.model_combo.findData(pm)
            if i >= 0:
                self.model_combo.setCurrentIndex(i)
                return
        if current:
            i = self.model_combo.findData(current)
            if i >= 0:
                self.model_combo.setCurrentIndex(i)

    def open_model_picker(self):
        dlg = ModelPickerDialog(self, self.providers, self.pinned)
        if dlg.exec():
            self.providers = dlg.providers
            self.pinned = dlg.pinned
            self.settings.setValue("providers", json.dumps(self.providers))
            self.settings.setValue("pinned_models", json.dumps(self.pinned))
            self.refresh_models()

    def on_models_fail(self, err):
        self.model_combo.clear()
        self.model_combo.setEnabled(True)
        self.model_combo.addItem("(sin conexión)")
        self.statusBar().showMessage(f"Sin conexión con LM Studio: {err}")

    def choose_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta de trabajo", self.tools.root)
        if d:
            self.add_folder(d)

    def add_folder(self, path):
        items = [self.folder_combo.itemText(i) for i in range(self.folder_combo.count())]
        items = [i for i in items if i != path]
        items.insert(0, path)
        self.folder_combo.blockSignals(True)
        self.folder_combo.clear()
        self.folder_combo.addItems(items[:MAX_RECENT])
        self.folder_combo.setCurrentIndex(0)
        self.folder_combo.blockSignals(False)
        self.set_folder(path)

    def remove_folder(self):
        i = self.folder_combo.currentIndex()
        if i < 0:
            return
        self.folder_combo.removeItem(i)
        if self.folder_combo.count() == 0:
            self.folder_combo.addItem(os.getcwd())
        self.folder_combo.setCurrentIndex(0)
        self.set_folder(self.folder_combo.currentText())

    def on_folder_selected(self, _index):
        self.set_folder(self.folder_combo.currentText())

    def set_folder(self, path, clear=True):
        if not os.path.isdir(path):
            return
        self.tools = Tools(path)
        if clear:
            # Reset completo: otra carpeta = otro contexto
            self.history = []
            self.pinned = []
            self.token_log = []
            self._prompt_counter = 0
            self._current_prompt_id = None
            self._excluded_turns = set()
            self._update_tok_display()
            self.chat.clear()
            self._clear_bookmarks()
            self._refresh_changes()
            self.conv_path = self._new_conv_path()
            self.refresh_pins()
        self.settings.setValue("workspace", path)
        self.settings.setValue(
            "recent_folders",
            [self.folder_combo.itemText(i) for i in range(self.folder_combo.count())])
        self.append_chat(f"Carpeta de trabajo: {path}", "tool")
        self._ensure_contexto_txt()
        self.refresh_files()
        self.refresh_run_combo()
        self.stop_config()
        self._update_budget()
        if clear:
            self.refresh_conv_list()

    def _ensure_contexto_txt(self):
        """Crea contexto.txt si no existe en la carpeta de trabajo."""
        ctx_path = os.path.join(self.tools.root, "contexto.txt")
        if not os.path.exists(ctx_path):
            try:
                with open(ctx_path, "w", encoding="utf-8") as f:
                    f.write("# Contexto del proyecto\n")
                self.append_chat("📝 contexto.txt creado (vacío). La IA lo usará para guardar contexto.", "stats")
            except OSError as e:
                self.append_chat(f"No se pudo crear contexto.txt: {e}", "error")

    def index_project(self):
        if self.worker is not None and self.worker.isRunning():
            return
        self.input.setPlainText(INDEX_PROMPT)
        self.send()

    def refresh_files(self):
        self.file_tree.clear()
        self.file_tree.setIconSize(QSize(16, 16))
        root_item = QTreeWidgetItem([os.path.basename(self.tools.root) or self.tools.root])
        root_item.setIcon(0, file_icon("", True))
        self.file_tree.addTopLevelItem(root_item)
        self._fill_tree(root_item, self.tools.root, 0)
        root_item.setExpanded(True)

    def _fill_tree(self, parent_item, path, depth):
        if depth >= 3:
            return
        try:
            with os.scandir(path) as it:
                entries = sorted(it, key=lambda e: (not e.is_dir(), e.name.lower()))
        except OSError:
            return
        for e in entries:
            if e.is_dir():
                if e.name in SKIP_DIRS or e.name.startswith("."):
                    continue
                child = QTreeWidgetItem([e.name + "/"])
                child.setIcon(0, file_icon(e.name, True))
                child.setData(0, Qt.UserRole, e.path)
                parent_item.addChild(child)
                self._fill_tree(child, e.path, depth + 1)
            else:
                child = QTreeWidgetItem([e.name])
                child.setIcon(0, file_icon(e.name, False))
                child.setData(0, Qt.UserRole, e.path)
                rel = os.path.relpath(e.path, self.tools.root)
                ch = self.tools.recent_changes.get(rel)
                if ch:
                    added = ch.get("added", 0)
                    removed = ch.get("removed", 0)
                    if ch["kind"] == "created":
                        label = e.name + f"  +{added}" if added else e.name
                        child.setText(0, label)
                        child.setForeground(0, QColor("#22c55e"))
                        child.setToolTip(0, f"✨ Creado por la IA (+{added} líneas)")
                    else:
                        parts = [e.name]
                        if added:
                            parts.append(f"  +{added}")
                        if removed:
                            parts.append(f"  -{removed}")
                        child.setText(0, "".join(parts))
                        child.setForeground(0, QColor("#22c55e") if added and not removed
                                            else QColor("#f59e0b"))
                        child.setToolTip(0, f"✏️ Modificado (+{added} / -{removed} líneas)")
                parent_item.addChild(child)
                # Botón play verde para archivos ejecutables
                ext = os.path.splitext(e.name)[1].lower()
                if ext in (".py", ".js", ".java"):
                    btn = QPushButton()
                    btn.setIcon(svg_icon("play"))
                    btn.setIconSize(QSize(12, 12))
                    btn.setFixedSize(16, 16)
                    btn.setStyleSheet(
                        "QPushButton { background:transparent; border:none; }"
                        "QPushButton:hover { background:#22c55e33; border-radius:2px; }")
                    btn.setToolTip(f"Ejecutar {e.name}")
                    btn.clicked.connect(lambda _, p=e.path: self._run_file_in_terminal(p))
                    self.file_tree.setItemWidget(child, 1, btn)

    def on_file_double(self, item, _col):
        path = item.data(0, Qt.UserRole)
        if not path or os.path.isdir(path):
            return
        rel = os.path.relpath(path, self.tools.root)
        ext = os.path.splitext(path)[1].lower()
        if ext in ImageViewerDialog.IMG_EXTS:
            dlg = ImageViewerDialog(self, path, rel)
        else:
            dlg = FileEditorDialog(self, path, rel, self.tools)
        dlg.exec()
        self.refresh_files()
        self._refresh_changes()

    def _on_file_dropped(self, path):
        """Archivo arrastrado desde el árbol al input del chat."""
        if not path or os.path.isdir(path):
            return
        rel = os.path.relpath(path, self.tools.root)
        self.input.setPlainText(f'Edita el archivo "{rel}": ')
        self.input.setFocus()
        self.statusBar().showMessage(f"{rel}: escribe qué cambiar y envía")

    def _attach_image(self):
        """Botón 📎 — abre un diálogo para elegir imágenes."""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Adjuntar imágenes", "",
            "Imágenes (*.png *.jpg *.jpeg *.gif *.webp *.bmp);;Todos los archivos (*)")
        if paths:
            for p in paths:
                self._on_image_dropped(p)

    def _toggle_voice(self):
        """Inicia/detiene la grabación de voz."""
        if self._rec_proc is not None:
            self._stop_rec()
        else:
            self._start_rec()

    def _start_rec(self):
        """Inicia grabación con ffmpeg."""
        import subprocess
        voice_dir = os.path.join(APP_DIR, "Voice")
        os.makedirs(voice_dir, exist_ok=True)
        wav_path = os.path.join(voice_dir, "rec.wav")
        # Borrar grabación anterior si existe
        if os.path.exists(wav_path):
            os.remove(wav_path)
        self._rec_wav = wav_path
        try:
            self._rec_proc = subprocess.Popen(
                ["ffmpeg", "-y", "-f", "avfoundation", "-i", ":0",
                 "-ar", "16000", "-ac", "1", wav_path],
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
        self.statusBar().showMessage("🎙 Grabando… clic para parar")
        self.audio_meter.setVisible(True)
        self.audio_meter.start()
        play_sound("rec_start")
        # Timeout: cortar grabación a los 2 minutos
        self._rec_timer = QTimer(self)
        self._rec_timer.setSingleShot(True)
        self._rec_timer.timeout.connect(self._stop_rec)
        self._rec_timer.start(120000)

    def _stop_rec(self):
        """Detiene la grabación y transcribe."""
        if self._rec_proc is None:
            return
        if self._rec_timer is not None:
            self._rec_timer.stop()
            self._rec_timer = None
        # Enviar 'q' a ffmpeg para que finalize limpio
        try:
            self._rec_proc.stdin.write(b"q")
            self._rec_proc.stdin.close()
        except Exception:
            self._rec_proc.terminate()
        self._rec_proc.wait(timeout=5)
        self._rec_proc = None
        # Restaurar botón
        self.btn_mic.setStyleSheet(
            "QPushButton { background:#6b7280; border:none; border-radius:8px; }"
            "QPushButton:hover { background:#6b7280; opacity:0.85; }")
        self.btn_mic.setToolTip("Hablar: clic para grabar, clic para parar")
        self.audio_meter.stop()
        self.audio_meter.setVisible(False)
        play_sound("rec_stop")
        self.statusBar().showMessage("Transcribiendo…")
        # Transcribir en un thread
        wav = self._rec_wav
        if not os.path.exists(wav):
            self.statusBar().showMessage("Grabación vacía")
            return
        self._voice_thread = VoiceTranscriber(wav)
        self._voice_thread.done.connect(self._on_voice_done)
        self._voice_thread.error.connect(self._on_voice_error)
        self._voice_thread.start()

    def _on_voice_done(self, text):
        self.statusBar().showMessage("Listo", 2000)
        if text:
            current = self.input.toPlainText()
            if current and not current.endswith(" "):
                current += " "
            self.input.setPlainText(current + text)
            self.input.setFocus()
            cursor = self.input.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.input.setTextCursor(cursor)
            # Auto-enviar si el checkbox está marcado
            if self.chk_auto_send.isChecked():
                self.send()
        else:
            self.statusBar().showMessage("No se entendió el audio")

    def _on_voice_error(self, err):
        self.statusBar().showMessage(f"Error de voz: {err}", 5000)
        self.append_chat(f"Error de transcripción: {err}", "error")

    def _polish_text(self):
        """Toma el texto del input, lo manda a un modelo liviano para pulirlo,
        y lo devuelve al input."""
        text = self.input.toPlainText().strip()
        if not text:
            self.statusBar().showMessage("Escribí algo para pulir primero", 3000)
            return
        # Usar modelo secundario de prefs, o el actual si no hay
        sm = self.prefs.get("secondary_model", "")
        if sm and sm != "(usar el del combo)":
            provider, _, model = sm.partition("::")
            cfg = self.providers.get(provider, {})
            base = cfg.get("base", LMSTUDIO)
            key = cfg.get("key", "")
            session_id = os.path.basename(self.conv_path) if "opencode" in provider.lower() else ""
        else:
            base, model, key = self._current_provider()
            session_id = os.path.basename(self.conv_path)
        if not model:
            self.append_chat("Configurá un modelo en Preferencias para pulir", "error")
            return
        self.btn_polish.setEnabled(False)
        self.statusBar().showMessage("Puliendo texto…")
        self._polish_thread = FnThread(
            lambda: self._polish_request(base, model, key, text, session_id))
        self._polish_thread.ok.connect(self._on_polish_done)
        self._polish_thread.fail.connect(self._on_polish_error)
        self._polish_thread.finished.connect(lambda: self.btn_polish.setEnabled(True))
        self._polish_thread.start()

    def _polish_request(self, base, model, key, text, session_id=""):
        """Llama a la API para pulir el texto."""
        headers = {"User-Agent": "cli-ia/1.0"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        if session_id:
            headers["x-opencode-session"] = session_id
        msgs = [
            {"role": "system", "content":
             "Eres un asistente que mejora y pule textos en español. "
             "Corregí ortografía, gramática y claridad. "
             "Resumí si es muy largo. Mantené el significado original. "
             "Respondé SOLO con el texto mejorado, sin explicaciones ni comentarios."},
            {"role": "user", "content": text},
        ]
        r = requests.post(api_url(base, "/chat/completions"),
                          json={"model": model, "messages": msgs,
                                "temperature": 0.3, "max_tokens": 4096,
                                "stream": False},
                          timeout=(10, 60), headers=headers)
        r.raise_for_status()
        r.encoding = "utf-8"
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()

    def _on_polish_done(self, result):
        if result:
            self.input.setPlainText(result)
            self.input.setFocus()
            cursor = self.input.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.input.setTextCursor(cursor)
            self.statusBar().showMessage("Texto pulido ✓ revisá antes de enviar", 5000)
        else:
            self.statusBar().showMessage("No se pudo pulir el texto", 3000)

    def _on_polish_error(self, err):
        # Si el secundario falló, intentar con el modelo actual del combo
        if self._polish_thread is not None:
            base, model, key = self._current_provider()
            if model:
                self.statusBar().showMessage("Reintentando con modelo actual…")
                self._polish_thread = FnThread(
                    lambda: self._polish_request(base, model, key,
                                                  self.input.toPlainText().strip(),
                                                  os.path.basename(self.conv_path)))
                self._polish_thread.ok.connect(self._on_polish_done)
                self._polish_thread.fail.connect(lambda e: self._on_polish_error_final(e))
                self._polish_thread.start()
                return
        self._on_polish_error_final(err)

    def _on_polish_error_final(self, err):
        self.statusBar().showMessage(f"Error al pulir: {err}", 5000)
        self.append_chat(f"Error al pulir texto: {err}", "error")

    def _on_image_dropped(self, path):
        """Imagen arrastrada al input — la agrega como preview pendiente."""
        if not path or not os.path.isfile(path):
            return
        if path not in self.pending_images:
            self.pending_images.append(path)
        self._refresh_img_preview()

    def _refresh_img_preview(self):
        """Reconstruye la zona de thumbnails de imágenes pendientes."""
        # Limpiar thumbnails viejos
        for item in list(self._img_thumbs):
            w = item[3] if len(item) > 3 else None
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._img_thumbs = []
        if not self.pending_images:
            self.img_w.setVisible(False)
            return
        self.img_w.setVisible(True)
        from PySide6.QtGui import QPixmap
        for path in self.pending_images:
            pix = QPixmap(path)
            if pix.isNull():
                continue
            thumb = pix.scaledToHeight(48, Qt.SmoothTransformation)
            lbl = QLabel()
            lbl.setPixmap(thumb)
            lbl.setToolTip(os.path.basename(path))
            lbl.setStyleSheet("border:1px solid #555; border-radius:4px; padding:2px; background:#222;")
            btn = QPushButton("✕")
            btn.setFixedSize(20, 20)
            btn.setStyleSheet("background:#444; border-radius:10px; font-size:11px; padding:0;")
            btn.clicked.connect(lambda checked=False, p=path: self._remove_image(p))
            wrap = QVBoxLayout()
            wrap.setSpacing(0)
            wrap.setContentsMargins(0, 0, 0, 0)
            wrap.addWidget(lbl)
            wrap.addWidget(btn)
            w = QWidget()
            w.setLayout(wrap)
            self.img_preview.insertWidget(self.img_preview.count() - 1, w)
            self._img_thumbs.append((path, lbl, btn, w))

    def _remove_image(self, path):
        if path in self.pending_images:
            self.pending_images.remove(path)
        self._refresh_img_preview()

    def _clear_images(self):
        self.pending_images = []
        self._refresh_img_preview()

    def open_selected_file(self):
        item = self.file_tree.currentItem()
        if item is None:
            self.statusBar().showMessage("Seleccioná un archivo primero")
            return
        path = item.data(0, Qt.UserRole)
        if not path or os.path.isdir(path):
            self.statusBar().showMessage("Seleccioná un archivo (no una carpeta)")
            return
        rel = os.path.relpath(path, self.tools.root)
        dlg = FileEditorDialog(self, path, rel, self.tools)
        dlg.exec()
        self.refresh_files()
        self._refresh_changes()

    def _on_files_changed(self):
        """Se llama (vía señal) cuando la IA toca archivos durante el turno."""
        self.refresh_files()
        self._refresh_changes()

    def _refresh_changes(self):
        self.changes_list.clear()
        for rel, ch in self.tools.recent_changes.items():
            added = ch.get("added", 0)
            removed = ch.get("removed", 0)
            if ch["kind"] == "created":
                mark = "✨"
                label = f"{mark}  {rel}  (+{added})"
                color = "#22c55e"
            else:
                mark = "✏️"
                label = f"{mark}  {rel}  (+{added} / -{removed})"
                color = "#f59e0b"
            item = QListWidgetItem(label)
            item.setForeground(QColor(color))
            # Tooltip con las primeras líneas del diff
            diff = ch.get("diff", [])
            tip = "\n".join(
                f"{'-' if k=='del' else '+' if k=='add' else ''} {t[:100]}"
                for k, t in diff[:20])
            item.setToolTip(tip or "(sin diff)")
            item.setData(Qt.UserRole, rel)
            self.changes_list.addItem(item)
        n = self.changes_list.count()
        if n > 0:
            self.side_tabs.setTabText(2, f"✏️ Cambios ({n})")
        else:
            self.side_tabs.setTabText(2, "✏️ Cambios")

    def _on_change_clicked(self, item):
        rel = item.data(Qt.UserRole)
        path = os.path.join(self.tools.root, rel)
        if os.path.isfile(path):
            dlg = FileEditorDialog(self, path, rel, self.tools)
            dlg.exec()
            self.refresh_files()
            self._refresh_changes()

    def _clear_changes(self):
        self.tools.recent_changes.clear()
        self._refresh_changes()
        self.refresh_files()
        self.statusBar().showMessage("Marcas de cambios limpiadas")

    def open_skills(self):
        dlg = SkillsDialog(self, os.path.join(APP_DIR, "Skills-py"), self.tools.root)
        dlg.exec()

    def open_prefs(self):
        """Abre el diálogo de preferencias del usuario."""
        all_models = [self.model_combo.itemData(i) or self.model_combo.itemText(i)
                      for i in range(self.model_combo.count())]
        dlg = PrefsDialog(self, self.prefs, all_models)
        if dlg.exec():
            self.prefs = dlg.get_prefs()
            self.settings.setValue("prefs", json.dumps(self.prefs, ensure_ascii=False))
            # Guardar budget por carpeta
            self.token_budgets[self.tools.root] = self.prefs["token_budget"]
            self.settings.setValue("token_budgets",
                                    json.dumps(self.token_budgets, ensure_ascii=False))
            self._update_budget()
            # Aplicar modelo primario si está seteado
            pm = self.prefs.get("primary_model", "")
            if pm:
                i = self.model_combo.findData(pm)
                if i >= 0:
                    self.model_combo.setCurrentIndex(i)
            self.statusBar().showMessage("Preferencias guardadas", 3000)

    def _folder_budget(self):
        """Budget de tokens para la carpeta actual."""
        return self.token_budgets.get(self.tools.root,
                                     self.prefs.get("token_budget", 50000))

    def _update_budget(self):
        """Actualiza la barra de budget con el total de tokens usados."""
        total = sum(t["prompt"] + t["completion"] for t in self.token_log)
        saved = sum(t["prompt"] + t["completion"] for i, t in enumerate(self.token_log)
                    if (i + 1) in self._excluded_turns)
        budget = self._folder_budget()
        self.budget_bar.set_values(total - saved, budget)
        pct = ((total - saved) / budget * 100) if budget else 0
        extra = f" · 💰 {saved:,} ahorrados" if saved else ""
        self.budget_lbl.setText(f"Budget: {total - saved:,} / {budget:,} ({pct:.0f}%){extra}")

    def detect_run_configs(self):
        root = self.tools.root
        cfgs = []
        if os.path.exists(os.path.join(root, "index.html")):
            cfgs.append({"name": "index.html → navegador", "cmd": "open index.html"})
        if os.path.exists(os.path.join(root, "package.json")):
            cfgs.append({"name": "npm start", "cmd": "npm start"})
        for f in ("server.js", "app.js", "index.js"):
            if os.path.exists(os.path.join(root, f)):
                cfgs.append({"name": f"node {f}", "cmd": f"node {f}"})
        for f in ("main.py", "app.py", "server.py"):
            if os.path.exists(os.path.join(root, f)):
                cfgs.append({"name": f"python {f}", "cmd": f"python3 {f}"})
        return cfgs

    def refresh_run_combo(self):
        self.run_combo.blockSignals(True)
        self.run_combo.clear()
        for c in self.detect_run_configs() + self.custom_configs:
            self.run_combo.addItem(c["name"], c["cmd"])
        self.run_combo.addItem("⚙ Running configs…", "")
        self.run_combo.blockSignals(False)

    def on_run_activated(self, _index):
        if self.run_combo.currentData() == "":
            prev = max(0, self.run_combo.currentIndex() - 1)
            self.open_run_dialog()
            self.run_combo.blockSignals(True)
            self.run_combo.setCurrentIndex(min(self.run_combo.count() - 2, self._last_run_idx))
            self.run_combo.blockSignals(False)
        else:
            self._last_run_idx = self.run_combo.currentIndex()

    def open_run_dialog(self):
        dlg = RunDialog(self, self.custom_configs)
        if dlg.exec():
            self.custom_configs = dlg.configs
            self.settings.setValue("custom_run_configs", json.dumps(self.custom_configs))
            self.refresh_run_combo()
            if dlg._run_cmd:
                i = self.run_combo.findData(dlg._run_cmd)
                if i >= 0:
                    self.run_combo.setCurrentIndex(i)
                self.run_config()

    def run_config(self):
        cmd = self.run_combo.currentData()
        if not cmd:
            self.open_run_dialog()
            return
        if self.proc is not None and self.proc.state() != QProcess.NotRunning:
            self.append_chat("Ya hay un proceso corriendo — deténlo primero (⏹).", "error")
            return
        self.proc = QProcess()
        self.proc.setWorkingDirectory(self.tools.root)
        self.proc.readyReadStandardOutput.connect(
            lambda: self.terminal.appendPlainText(
                str(self.proc.readAllStandardOutput(), "utf-8", "replace").rstrip()))
        self.proc.readyReadStandardError.connect(
            lambda: self.terminal.appendPlainText(
                str(self.proc.readAllStandardError(), "utf-8", "replace").rstrip()))
        self.proc.finished.connect(self.on_proc_finished)
        self.terminal.clear()
        self.terminal.setVisible(True)
        self.btn_term.setVisible(True)
        self.btn_term.setText("▼ Terminal")
        self.proc.start("/bin/zsh", ["-c", cmd])
        self.btn_stop_proc.setEnabled(True)
        self.statusBar().showMessage(f"▶ {cmd}")

    def stop_config(self):
        if self.proc is not None and self.proc.state() != QProcess.NotRunning:
            self.proc.terminate()
            if not self.proc.waitForFinished(2000):
                self.proc.kill()
            self.statusBar().showMessage("⏹ proceso detenido")

    def on_proc_finished(self, code, _status):
        self.terminal.appendPlainText(f"— proceso terminado (código {code}) —")
        self.btn_stop_proc.setEnabled(False)
        self.statusBar().showMessage(f"⏹ terminado (código {code})")

    def _toggle_terminal(self):
        visible = not self.terminal.isVisible()
        self.terminal.setVisible(visible)
        self.btn_term.setText("▼ Terminal" if visible else "▶ Terminal")

    def _run_file_in_terminal(self, path):
        """Ejecuta un archivo .py/.js/.java en la terminal del workspace."""
        if self.proc is not None and self.proc.state() != QProcess.NotRunning:
            self.append_chat("Ya hay un proceso corriendo — deténlo primero (⏹).", "error")
            return
        ext = os.path.splitext(path)[1].lower()
        if ext == ".py":
            runner = "python3"
        elif ext == ".js":
            runner = "node"
        elif ext == ".java":
            runner = "java"
        else:
            return
        # cd a la carpeta del archivo + ejecutarlo
        fname = os.path.basename(path)
        file_dir = os.path.dirname(path)
        cmd = f"cd {shlex.quote(file_dir)} && {runner} {shlex.quote(fname)}"
        self.terminal.clear()
        self.terminal.setVisible(True)
        self.btn_term.setVisible(True)
        self.btn_term.setText("▼ Terminal")
        self.terminal.appendPlainText(f"$ cd {file_dir} && {runner} {fname}")
        self.proc = QProcess()
        self.proc.setWorkingDirectory(file_dir)
        self.proc.readyReadStandardOutput.connect(
            lambda: self.terminal.appendPlainText(
                str(self.proc.readAllStandardOutput(), "utf-8", "replace").rstrip()))
        self.proc.readyReadStandardError.connect(
            lambda: self.terminal.appendPlainText(
                str(self.proc.readAllStandardError(), "utf-8", "replace").rstrip()))
        self.proc.finished.connect(self.on_proc_finished)
        self.proc.start("/bin/zsh", ["-c", cmd])
        self.btn_stop_proc.setEnabled(True)
        self.statusBar().showMessage(f"▶ {runner} {fname}")

    def _new_conv_path(self):
        base = os.path.join(CONV_DIR, f"conv_{time.strftime('%Y%m%d_%H%M%S')}")
        path, n = f"{base}.json", 1
        while os.path.exists(path):
            n += 1
            path = f"{base}_{n}.json"
        return path

    def _transcript(self):
        lines = [f"Carpeta: {self.tools.root}",
                 f"Modelo: {self.model_combo.currentText()}", ""]
        for m in self.history:
            kind, text = render_message(m)
            lines += [f"--- {self.LABELS[kind]} ---", text, ""]
        return "\n".join(lines)

    def save_conv(self):
        try:
            os.makedirs(CONV_DIR, exist_ok=True)
            with open(self.conv_path, "w", encoding="utf-8") as f:
                json.dump({"folder": self.tools.root,
                           "model": self.model_combo.currentData() or self.model_combo.currentText(),
                           "history": self.history,
                           "pinned": self.pinned,
                           "token_log": self.token_log}, f, ensure_ascii=False, indent=1)
            with open(LAST_TXT, "w", encoding="utf-8") as f:
                f.write(self._transcript())
        except OSError as e:
            self.append_chat(f"No se pudo guardar la conversación: {e}", "error")

    def load_conv(self, path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.append_chat(f"No se pudo cargar la conversación: {e}", "error")
            return
        self.conv_path = path
        self.history = data.get("history", [])
        self.pinned = data.get("pinned", [])
        self.token_log = data.get("token_log", [])
        self._update_tok_display()
        self._write_usage_md()
        self.refresh_pins()
        folder = data.get("folder", "")
        if os.path.isdir(folder) and folder != self.tools.root:
            self.set_folder(folder, clear=False)
            i = self.folder_combo.findText(folder)
            if i >= 0:
                self.folder_combo.blockSignals(True)
                self.folder_combo.setCurrentIndex(i)
                self.folder_combo.blockSignals(False)
        # Modelo: priorizar el modelo primario del usuario sobre el de la conversación
        pm = self.prefs.get("primary_model", "")
        target = pm if pm else data.get("model", "")
        i = self.model_combo.findData(target)
        if i < 0:
            i = self.model_combo.findText(target)
        if i >= 0:
            self.model_combo.setCurrentIndex(i)
        self.chat.clear()
        self._clear_bookmarks()
        for m in self.history:
            kind, text = render_message(m)
            self.append_chat(text, kind)
        self.append_chat("Conversación cargada — puedes continuarla.", "stats")

    def new_conv(self):
        if self.worker is not None and self.worker.isRunning():
            return
        self.history = []
        self.pinned = []
        self.token_log = []
        self._update_tok_display()
        self.chat.clear()
        self._clear_bookmarks()
        self.tools.recent_changes.clear()
        self._refresh_changes()
        self.conv_path = self._new_conv_path()
        self.refresh_pins()
        self.append_chat("Nueva conversación.", "stats")
        self.refresh_conv_list()

    def delete_conv(self):
        it = self.conv_list.currentItem()
        if it is None:
            return
        path = it.data(Qt.UserRole)
        try:
            os.remove(path)
        except OSError as e:
            self.append_chat(f"No se pudo eliminar: {e}", "error")
            return
        if path == self.conv_path:
            self.history = []
            self.chat.clear()
            self._clear_bookmarks()
            self.conv_path = self._new_conv_path()
        self.refresh_conv_list()

    def on_conv_clicked(self, item):
        if self.worker is not None and self.worker.isRunning():
            return
        path = item.data(Qt.UserRole)
        if path != self.conv_path:
            self.load_conv(path)
            self.refresh_conv_list()

    def refresh_conv_list(self):
        self.conv_list.clear()
        files = sorted(
            (os.path.join(CONV_DIR, f) for f in os.listdir(CONV_DIR) if f.endswith(".json")),
            key=os.path.getmtime, reverse=True)
        for p in files:
            try:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                first = next((m["content"] for m in data.get("history", [])
                              if m.get("role") == "user"), "")
                label = time.strftime("%d/%m %H:%M", time.localtime(os.path.getmtime(p)))
                text = f"{label} · {first[:26]}"
            except Exception:
                text = os.path.basename(p)
            it = QListWidgetItem(text)
            it.setData(Qt.UserRole, p)
            it.setToolTip(p)
            if p == self.conv_path:
                it.setText("● " + text)
            self.conv_list.addItem(it)

    def pin_selected(self):
        sel = self.chat.textCursor().selectedText().replace("\u2029", "\n").strip()
        if not sel:
            self.append_chat("Selecciona texto en el chat para guardarlo como nota.", "error")
            return
        self.pinned.append(sel)
        self.refresh_pins()
        self.save_conv()
        self.append_chat(f"📌 nota guardada: {sel[:80]}{'…' if len(sel) > 80 else ''}", "stats")

    def unpin(self):
        row = self.pinned_list.currentRow()
        if row >= 0:
            self.pinned.pop(row)
            self.refresh_pins()
            self.save_conv()

    def refresh_pins(self):
        self.pinned_list.clear()
        for p in self.pinned:
            it = QListWidgetItem(p[:40] + ("…" if len(p) > 40 else ""))
            it.setToolTip(p)
            self.pinned_list.addItem(it)
        self.update_ctx_label()

    def update_ctx_label(self):
        n = len(json.dumps({"history": self.history, "pinned": self.pinned},
                           ensure_ascii=False).encode("utf-8"))
        est = max(1, n // 4)
        prompt = self.last_prompt or est
        limit = self.ctx_limits.get((self._current_provider() or (None, None, None))[1] or "", 0)
        if limit:
            pct = min(100, int(prompt * 100 / limit))
            self.ctx_lbl.setText(f"KV cache: {prompt:,} / {limit:,} tok ({pct}%)")
        else:
            self.ctx_lbl.setText(f"Contexto: ~{est:,} tok (estimado)")

    def _fetch_ctx_limit(self):
        base, model, key = self._current_provider()
        if not model or model in self.ctx_limits:
            self.update_ctx_label()
            return

        def fn():
            headers = {"Authorization": f"Bearer {key}"} if key else {}
            r = requests.get(base.rstrip("/") + "/api/v0/models", headers=headers, timeout=8)
            r.raise_for_status()
            for m in r.json().get("data", []):
                if m.get("id") == model:
                    return m.get("loaded_context_length") or m.get("max_context_length") or 0
            return 0

        t = FnThread(fn)
        t.ok.connect(lambda v: self._set_ctx_limit(model, v))
        t.fail.connect(lambda e: self._set_ctx_limit(model, 0))
        self._threads.append(t)
        t.start()

    def _set_ctx_limit(self, model, value):
        self.ctx_limits[model] = value or 0
        self.update_ctx_label()

    def _strip_history_for_summary(self, history):
        """Reemplaza contenidos grandes de save_file/edit_file con placeholders."""
        stripped = []
        for m in history:
            c = m.get("content", "")
            if isinstance(c, list):
                stripped.append(m)
                continue
            role = m.get("role", "")
            # Reemplazar save_file con content grande
            if role == "assistant" and '"save_file"' in c:
                def _replace_save(m_obj):
                    path_match = re.search(r'"path"\s*:\s*"([^"]+)"', m_obj.group(0))
                    path = path_match.group(1) if path_match else "?"
                    content_match = re.search(r'"content"\s*:\s*"(.+?)"', m_obj.group(0), re.S)
                    if content_match and len(content_match.group(1)) > 200:
                        return f'[save_file: {path} — {len(content_match.group(1))} chars, ya guardado en disco]'
                    return m_obj.group(0)
                c = re.sub(r'\{"tool"\s*:\s*"save_file".*?\}', _replace_save, c, flags=re.S)
            # Reemplazar RESULTADO con contenido de archivo grande
            if role == "user" and c.startswith("[RESULTADO"):
                if len(c) > 500:
                    c = c[:200] + f"\n…({len(c)} chars total, contenido del archivo ya en disco)…"
            stripped.append({"role": role, "content": c})
        return stripped

    def summarize(self):
        if self.worker is not None and self.worker.isRunning():
            return
        if not self.history:
            self.append_chat("No hay nada que resumir.", "error")
            return
        base, model, key = self._current_provider()
        if not model:
            self.append_chat("Sin modelo disponible.", "error")
            return
        msgs = [{"role": "system",
                 "content": "Eres un asistente que resume conversaciones de programación de forma concisa. "
                            "NUNCA incluyas el contenido de archivos (SVG, código, etc.) en el resumen — "
                            "esos archivos ya están guardados en disco. Solo mencioná el nombre del archivo "
                            "y qué se hizo con él."},
                *self._strip_history_for_summary(self.history),
                {"role": "user", "content":
                 "Resume esta conversación de forma concisa: puntos clave, decisiones, "
                 "archivos creados o modificados (solo nombres, NO el contenido) y tareas pendientes."}]

        def fn():
            headers = {"User-Agent": "cli-ia/1.0",
                       "x-opencode-session": os.path.basename(self.conv_path)}
            if key:
                headers["Authorization"] = f"Bearer {key}"
            r = requests.post(api_url(base, "/chat/completions"),
                              json={"model": model, "messages": msgs,
                                    "temperature": 0.2, "max_tokens": 2000,
                                    "stream": True, "stream_options": {"include_usage": True}},
                              stream=True, timeout=(10, 180), headers=headers)
            r.raise_for_status()
            r.encoding = "utf-8"
            out = ""
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except ValueError:
                    continue
                choices = chunk.get("choices") or []
                if choices:
                    out += (choices[0].get("delta") or {}).get("content") or ""
            return out

        self.btn_sum.setEnabled(False)
        self.append_chat("Resumiendo conversación…", "stats")
        t = FnThread(fn)
        t.ok.connect(self.on_summary)
        t.fail.connect(lambda e: self.append_chat(f"Error al resumir: {e}", "error"))
        t.finished.connect(lambda: self.btn_sum.setEnabled(True))
        self._threads.append(t)
        t.start()

    def on_summary(self, summary):
        before = len(json.dumps(self.history, ensure_ascii=False)) // 1024
        keep = self.history[-2:]
        pins = "\n".join(f"- {p}" for p in self.pinned) or "(ninguna)"
        self.history = [
            {"role": "user", "content":
             f"[RESUMEN DE CONVERSACIÓN ANTERIOR]\n{summary}\n\n[NOTAS GUARDADAS]\n{pins}"},
            {"role": "assistant", "content": "Entendido, continúo con ese contexto."}] + keep
        self.chat.clear()
        self._clear_bookmarks()
        for m in self.history:
            kind, text = render_message(m)
            self.append_chat(text, kind)
        self.append_chat(
            f"🗜 contexto comprimido: {before} KB → "
            f"{len(json.dumps(self.history, ensure_ascii=False)) // 1024} KB", "stats")
        self.save_conv()
        self.refresh_conv_list()
        self.update_ctx_label()

    def _current_provider(self):
        ref = self.model_combo.currentData()
        if not ref:
            return None, None, None
        provider, _, model = ref.partition("::")
        cfg = self.providers.get(provider, {})
        return cfg.get("base", LMSTUDIO), model, cfg.get("key", "")

    def send(self):
        if self.worker is not None and self.worker.isRunning():
            return
        text = self.input.toPlainText().strip()
        if not text and not self.pending_images:
            return
        base, model, key = self._current_provider()
        if not model:
            self.append_chat("Selecciona un modelo válido (⚙ para configurar providers).", "error")
            return
        # Si hay imágenes y hay modelo de visión configurado, usarlo
        if self.pending_images:
            vm = self.prefs.get("vision_model", "")
            if vm and vm != model:
                # Buscar el provider del modelo de visión
                for pname, cfg in self.providers.items():
                    i = self.model_combo.findData(f"{pname}::{vm}")
                    if i >= 0:
                        base, model, key = cfg.get("base", LMSTUDIO), vm, cfg.get("key", "")
                        self.append_chat(f"🖼️ Usando modelo de visión: {vm}", "stats")
                        break
        # Armar el mensaje del usuario (multimodal si hay imágenes)
        self._prompt_counter += 1
        folder_name = os.path.basename(self.tools.root) or "proyecto"
        prompt_id = f"{folder_name}-prompt-{self._prompt_counter}"
        self._current_prompt_id = prompt_id
        if self.pending_images:
            content = [{"type": "text", "text": text or "(imagen adjunta)"}]
            for img_path in self.pending_images:
                try:
                    import base64
                    ext = os.path.splitext(img_path)[1].lower().lstrip(".")
                    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png",
                            "gif": "gif", "webp": "webp", "bmp": "bmp"}.get(ext, "png")
                    with open(img_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("ascii")
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/{mime};base64,{b64}"}
                    })
                except Exception as e:
                    self.append_chat(f"No se pudo cargar la imagen {img_path}: {e}", "error")
            user_msg = {"role": "user", "content": content}
            # Preview en el chat: texto + thumbnails
            display = text + ("\n" if text else "") + " ".join(
                f"🖼️ {os.path.basename(p)}" for p in self.pending_images)
            self.append_chat(display, "user", prompt_id=prompt_id)
        else:
            user_msg = {"role": "user", "content": text}
            self.append_chat(text, "user", prompt_id=prompt_id)
        self.history.append(user_msg)
        self.input.clear()
        images = list(self.pending_images)
        self._clear_images()
        # Filtrar turnos excluidos del historial que se envía al modelo
        filtered = self._filtered_history()
        self.worker = Worker(base, model, self.tools, filtered, key,
                             os.path.basename(self.conv_path), images=images,
                             no_context=self.chk_no_ctx.isChecked(),
                             prompt_id=prompt_id)
        self.worker.msg.connect(self.append_chat)
        self.worker.progress.connect(self.statusBar().showMessage)
        self.worker.files_changed.connect(self._on_files_changed)
        self.worker.turn_usage.connect(self._on_turn_usage)
        self.worker.stream_start.connect(self._on_stream_start)
        self.worker.chunk.connect(self._on_stream_chunk)
        self.worker.stream_end.connect(self._on_stream_end)
        self.worker.finished_run.connect(self.on_done)
        self.btn_send.setEnabled(False)
        self.btn_stop.setEnabled(True)
        play_sound("send")
        self.worker.start()

    def on_done(self):
        self.btn_send.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if self.worker is not None:
            self.last_prompt = self.worker.usage.get("prompt", 0)
        self.worker = None
        self._stream_active = False
        self.save_conv()
        self.refresh_conv_list()
        self.refresh_files()
        self._refresh_changes()
        self._fetch_ctx_limit()
        self.update_ctx_label()
        self._update_budget()
        play_sound("done")
        # Auto-resumir si el contexto supera el límite configurado
        if self.prefs.get("auto_summarize", True):
            max_ctx = int(self.prefs.get("max_context_tokens", 50000))
            total = sum(t["prompt"] + t["completion"] for t in self.token_log)
            if total > max_ctx:
                self.append_chat(
                    f"ℹ️ Contexto ({total:,} tok) supera el límite ({max_ctx:,} tok). "
                    "Resumiendo automáticamente…", "stats")
                self.summarize()

    def _on_turn_usage(self, usage):
        """Recibe el usage de un turno completo y lo acumula."""
        label = f"#{len(self.token_log) + 1}"
        self.token_log.append({
            "label": label,
            "prompt": usage.get("prompt", 0),
            "completion": usage.get("completion", 0),
            "total_time": usage.get("total_time", 0),
            "model": usage.get("model", ""),
        })
        self._update_tok_display()
        self._write_usage_md()
        self._update_budget()
        self._refresh_turn_list()

    def _update_tok_display(self):
        total = sum(t["prompt"] + t["completion"] for t in self.token_log)
        saved = sum(t["prompt"] + t["completion"] for i, t in enumerate(self.token_log)
                    if (i + 1) in self._excluded_turns)
        self.tok_total_lbl.setText(f"{total:,}")
        self.tok_bar.set_turns(list(self.token_log))
        self._refresh_turn_list()

    def _refresh_turn_list(self):
        """Llena la pestaña 📊 Turnos con cada turno, tokens y checkbox."""
        self.turn_list.blockSignals(True)
        self.turn_list.clear()
        total_tokens = 0
        saved_tokens = 0
        for i, t in enumerate(self.token_log):
            turn_num = i + 1
            tot = t["prompt"] + t["completion"]
            total_tokens += tot
            excluded = turn_num in self._excluded_turns
            if excluded:
                saved_tokens += tot
            check = "☐" if excluded else "☑"
            color = "#ef4444" if excluded else "#7cff6b"
            text = (f"{check} #{turn_num} · in:{t['prompt']:,} · "
                    f"out:{t['completion']:,} · total:{tot:,} · "
                    f"{t.get('model', '?')[:20]} · {t.get('total_time', 0):.1f}s")
            it = QListWidgetItem(text)
            it.setForeground(QColor(color))
            it.setData(Qt.UserRole, turn_num)
            it.setCheckState(Qt.Unchecked if excluded else Qt.Checked)
            it.setToolTip(f"Turno #{turn_num}\nPrompt: {t['prompt']:,} tok\n"
                          f"Completion: {t['completion']:,} tok\n"
                          f"Total: {tot:,} tok\n"
                          f"Modelo: {t.get('model', '?')}\n"
                          f"Tiempo: {t.get('total_time', 0):.1f}s\n"
                          f"{'⚠ EXCLUIDO del contexto' if excluded else '✔ Incluido en el contexto'}")
            self.turn_list.addItem(it)
        # Resumen
        active = len(self.token_log) - len(self._excluded_turns)
        self.turn_summary_lbl.setText(
            f"{len(self.token_log)} turnos · {total_tokens:,} tok totales · "
            f"🟢 {active} activos · 🔴 {len(self._excluded_turns)} excluidos · "
            f"💰 {saved_tokens:,} tok ahorrados")
        self.side_tabs.setTabText(2, f"📊 Turnos ({len(self.token_log)})")
        self.turn_list.blockSignals(False)
        self._update_budget()

    def _on_turn_check_changed(self, item):
        """Cuando se marca/desmarca un turno, lo excluye/incluye del contexto."""
        turn_num = item.data(Qt.UserRole)
        if item.checkState() == Qt.Unchecked:
            self._excluded_turns.add(turn_num)
        else:
            self._excluded_turns.discard(turn_num)
        self._refresh_turn_list()
        self._update_budget()

    def _filtered_history(self):
        """Devuelve el historial sin los turnos excluidos.
        Mapea turnos a mensajes: cada turno = un user msg + sus respuestas/tools
        hasta el siguiente user msg."""
        if not self._excluded_turns:
            return list(self.history)
        # Identificar qué mensajes pertenecen a qué turno
        turn = 0
        result = []
        for m in self.history:
            role = m.get("role", "")
            if role == "user" and not str(m.get("content", "")).startswith("[RESULTADO") \
               and not str(m.get("content", "")).startswith("[RESUMEN"):
                turn += 1
            if turn not in self._excluded_turns:
                result.append(m)
        return result

    def _write_usage_md(self):
        """Escribe usage-tokens.md junto a la conversación con tabla + barras."""
        if not self.token_log:
            return
        try:
            path = os.path.splitext(self.conv_path)[0] + "-usage.md"
            total_p = sum(t["prompt"] for t in self.token_log)
            total_c = sum(t["completion"] for t in self.token_log)
            total_t = total_p + total_c
            max_t = max((t["prompt"] + t["completion"] for t in self.token_log), default=1) or 1
            lines = [
                "# Uso de tokens — conversación",
                "",
                f"**Total:** {total_t:,} tokens ({total_p:,} prompt + {total_c:,} completion) en {len(self.token_log)} turnos",
                "",
                "## Detalle por turno",
                "",
                "| # | Prompt | Completion | Total | % | Barra | Modelo | Tiempo |",
                "|---|--------|------------|-------|---|-------|--------|--------|",
            ]
            for i, t in enumerate(self.token_log):
                tot = t["prompt"] + t["completion"]
                pct = (tot / max_t * 100) if max_t else 0
                bar_len = int(pct / 5)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                lines.append(
                    f"| {i + 1} | {t['prompt']:,} | {t['completion']:,} | "
                    f"**{tot:,}** | {pct:.0f}% | `{bar}` | "
                    f"{t['model']} | {t['total_time']:.1f}s |")
            lines += [
                "",
                "## Barra de progreso (turno más caro = barra llena)",
                "",
                "```",
            ]
            for i, t in enumerate(self.token_log):
                tot = t["prompt"] + t["completion"]
                bar_len = int((tot / max_t) * 30) if max_t else 0
                bar = "█" * bar_len + "░" * (30 - bar_len)
                lines.append(f"#{i + 1:3d} {bar} {tot:,} tok")
            lines += ["```", "",
                      "_Se actualiza automáticamente después de cada respuesta de la IA._"]
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except OSError:
            pass

    def stop(self):
        if self.worker is not None:
            self.worker.stop()
            self.statusBar().showMessage("Deteniendo tras el paso en curso…")

    def closeEvent(self, e):
        if self.worker is not None:
            self.worker.stop()
        for t in [self.worker] + self._threads:
            if t is not None and t.isRunning():
                t.wait(3000)
        self.stop_config()
        self.save_conv()
        super().closeEvent(e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_QSS)
    w = MainWindow()
    w.resize(1180, 700)
    w.showMaximized()
    sys.exit(app.exec())
