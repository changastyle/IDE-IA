# -*- coding: utf-8 -*-
"""Editor de archivos para el panel central.

- Tabs arriba con el nombre del archivo (basename)
- Números de línea a la izquierda
- Resaltado básico de sintaxis (Python, JS, HTML, CSS, JSON, Markdown)
- Detección de cambios externos al ganar foco
"""
import os

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import (
    QFont, QColor, QSyntaxHighlighter, QTextCharFormat, QTextCursor,
    QKeySequence, QShortcut,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPlainTextEdit,
    QLabel, QPushButton, QFileDialog, QMessageBox, QScrollArea,
    QTabBar, QStyle, QStyleOptionTab,
)

APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICONS_DIR = os.path.join(APP_DIR, "iconos")

EXT_LANG = {
    ".py": "python", ".js": "javascript", ".html": "html",
    ".css": "css", ".json": "json", ".md": "markdown",
    ".txt": "text", ".java": "java",
}

# ---- Resaltado de sintaxis ----

KEYWORDS = {
    "python": {"def", "class", "import", "from", "return", "if", "else",
               "elif", "for", "while", "try", "except", "finally", "with",
               "as", "lambda", "yield", "global", "nonlocal", "pass",
               "break", "continue", "raise", "assert", "del", "in", "not",
               "and", "or", "is", "None", "True", "False", "self"},
    "javascript": {"function", "return", "if", "else", "for", "while",
                    "do", "switch", "case", "break", "continue", "var",
                    "let", "const", "class", "extends", "new", "this",
                    "super", "import", "export", "from", "default", "try",
                    "catch", "finally", "throw", "typeof", "instanceof",
                    "null", "undefined", "true", "false", "async", "await",
                    "yield", "delete", "void"},
    "java": {"public", "private", "protected", "class", "interface", "extends",
             "implements", "return", "if", "else", "for", "while", "do",
             "switch", "case", "break", "continue", "new", "this", "super",
             "try", "catch", "finally", "throw", "throws", "import", "package",
             "static", "final", "void", "int", "double", "float", "long",
             "boolean", "char", "String", "true", "false", "null", "instanceof"},
}

HTML_TAGS = {"html", "head", "body", "div", "span", "p", "a", "img", "ul", "li",
             "ol", "table", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6",
             "script", "style", "link", "meta", "title", "br", "hr", "input",
             "form", "button", "label", "select", "option", "nav", "header",
             "footer", "section", "article", "main", "aside"}

CSS_PROPS = {"color", "background", "background-color", "border", "margin",
             "padding", "width", "height", "display", "position", "top",
             "left", "right", "bottom", "flex", "grid", "font-size", "font",
             "text-align", "z-index", "opacity", "border-radius", "transition",
             "transform", "cursor", "overflow", "box-shadow", "gap"}


class SyntaxHighlighter(QSyntaxHighlighter):
    """Resaltado básico por lenguaje."""

    def __init__(self, document, lang="text"):
        super().__init__(document)
        self.lang = lang
        self._build_formats()

    def _build_formats(self):
        self.fmt_keyword = QTextCharFormat()
        self.fmt_keyword.setForeground(QColor("#c678dd"))
        self.fmt_keyword.setFontWeight(QFont.Bold)

        self.fmt_string = QTextCharFormat()
        self.fmt_string.setForeground(QColor("#98c379"))

        self.fmt_comment = QTextCharFormat()
        self.fmt_comment.setForeground(QColor("#5c6370"))
        self.fmt_comment.setFontItalic(True)

        self.fmt_number = QTextCharFormat()
        self.fmt_number.setForeground(QColor("#d19a66"))

        self.fmt_tag = QTextCharFormat()
        self.fmt_tag.setForeground(QColor("#e06c75"))

        self.fmt_prop = QTextCharFormat()
        self.fmt_prop.setForeground(QColor("#61afef"))

    def highlightBlock(self, text):
        if self.lang in ("python", "javascript", "java"):
            self._highlight_code(text)
        elif self.lang == "html":
            self._highlight_html(text)
        elif self.lang == "css":
            self._highlight_css(text)
        elif self.lang == "json":
            self._highlight_json(text)
        elif self.lang == "markdown":
            self._highlight_markdown(text)

    def _highlight_code(self, text):
        kw = KEYWORDS.get(self.lang, set())
        # Strings (simple y doble comilla)
        self._highlight_strings(text)
        # Comentarios
        if self.lang == "python":
            idx = text.find("#")
            if idx >= 0:
                fmt = self.fmt_comment
                self.setFormat(idx, len(text) - idx, fmt)
        else:
            if "//" in text:
                idx = text.find("//")
                if idx >= 0:
                    self.setFormat(idx, len(text) - idx, self.fmt_comment)
        # Keywords
        words = text.replace("(", " ").replace(")", " ").replace(
            ".", " ").replace(",", " ").replace(":", " ").split()
        for w in words:
            clean = w.strip(";{}[]=+-*/<>!&|")
            if clean in kw:
                pos = text.find(w)
                while pos >= 0:
                    self.setFormat(pos, len(w), self.fmt_keyword)
                    pos = text.find(w, pos + 1)
        # Números
        self._highlight_numbers(text)

    def _highlight_strings(self, text):
        i = 0
        while i < len(text):
            if text[i] in ('"', "'"):
                quote = text[i]
                start = i
                i += 1
                while i < len(text) and text[i] != quote:
                    if text[i] == "\\" and i + 1 < len(text):
                        i += 2
                    else:
                        i += 1
                self.setFormat(start, i - start + 1, self.fmt_string)
            i += 1

    def _highlight_numbers(self, text):
        i = 0
        while i < len(text):
            if text[i].isdigit():
                start = i
                while i < len(text) and (text[i].isdigit() or text[i] == "."):
                    i += 1
                self.setFormat(start, i - start, self.fmt_number)
            else:
                i += 1

    def _highlight_html(self, text):
        # Tags <...>
        i = 0
        while i < len(text):
            if text[i] == "<":
                end = text.find(">", i)
                if end < 0:
                    break
                self.setFormat(i, end - i + 1, self.fmt_tag)
                i = end + 1
            else:
                i += 1
        # Strings dentro de tags
        self._highlight_strings(text)

    def _highlight_css(self, text):
        # Propiedad: valor;
        if ":" in text and text.strip().endswith(";"):
            idx = text.find(":")
            prop = text[:idx].strip()
            pos = text.find(prop)
            if pos >= 0:
                self.setFormat(pos, len(prop), self.fmt_prop)
        self._highlight_strings(text)
        self._highlight_numbers(text)

    def _highlight_json(self, text):
        self._highlight_strings(text)
        self._highlight_numbers(text)
        if "true" in text or "false" in text or "null" in text:
            for kw in ("true", "false", "null"):
                pos = text.find(kw)
                while pos >= 0:
                    self.setFormat(pos, len(kw), self.fmt_keyword)
                    pos = text.find(kw, pos + 1)

    def _highlight_markdown(self, text):
        # Headers
        if text.startswith("#"):
            self.setFormat(0, len(text), self.fmt_keyword)
        # Bold **text**
        i = 0
        while i < len(text) - 3:
            if text[i:i + 2] == "**":
                end = text.find("**", i + 2)
                if end > 0:
                    self.setFormat(i, end - i + 2, self.fmt_keyword)
                    i = end + 2
                    continue
            i += 1
        # Code `text`
        i = 0
        while i < len(text):
            if text[i] == "`":
                end = text.find("`", i + 1)
                if end > 0:
                    self.setFormat(i, end - i + 1, self.fmt_string)
                    i = end + 1
                    continue
            i += 1


class CodeEditor(QPlainTextEdit):
    """Editor con números de línea."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Menlo", 12))
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setStyleSheet("""
            QPlainTextEdit {
                background: #1a1c21;
                color: #e8eaed;
                border: none;
                selection-background-color: #2f6fdb;
            }""")
        # Widget de números de línea
        self.line_numbers = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_width)
        self.updateRequest.connect(self._update_line_area)
        self._update_line_width()
        self.highlighter = None
        self._lang = "text"

    def set_language(self, lang):
        if self.highlighter:
            self.highlighter.deleteLater()
        self.highlighter = SyntaxHighlighter(self.document(), lang)
        self._lang = lang

    def duplicate_line(self):
        """Duplica la línea actual o la selección hacia abajo."""
        cursor = self.textCursor()
        if cursor.hasSelection():
            # Duplicar la selección
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            # selectedText() usa \u2029 para saltos de línea
            text = cursor.selectedText().replace("\u2029", "\n")
            # Insertar el texto duplicado después de la selección
            cursor.setPosition(end)
            # Si la selección no termina en salto de línea, agregar uno
            if not text.endswith("\n"):
                text = "\n" + text
            cursor.insertText(text)
            # Seleccionar el texto duplicado
            new_end = end + len(text)
            cursor.setPosition(end)
            cursor.setPosition(new_end, QTextCursor.KeepAnchor)
            self.setTextCursor(cursor)
        else:
            # Duplicar la línea actual
            cursor.beginEditBlock()
            block = cursor.block()
            line_text = block.text()
            # Insertar la línea duplicada abajo
            cursor.movePosition(QTextCursor.EndOfLine)
            cursor.insertText("\n" + line_text)
            cursor.endEditBlock()
            self.setTextCursor(cursor)

    def toggle_comment(self):
        """Comenta/descomenta las líneas seleccionadas (o la línea actual)."""
        cursor = self.textCursor()
        # Determinar el rango de líneas a procesar
        if cursor.hasSelection():
            start_pos = cursor.selectionStart()
            end_pos = cursor.selectionEnd()
        else:
            start_pos = cursor.position()
            end_pos = cursor.position()
        # Obtener el bloque inicial y final
        doc = self.document()
        start_block = doc.findBlock(start_pos)
        end_block = doc.findBlock(end_pos)
        # Detectar el prefijo de comentario según el lenguaje
        comment = self._comment_prefix()
        if not comment:
            return
        # Verificar si todas las líneas ya están comentadas
        all_commented = True
        block = start_block
        while block.isValid() and block != end_block.next():
            text = block.text()
            stripped = text.lstrip()
            if stripped and not stripped.startswith(comment):
                all_commented = False
                break
            block = block.next()
        # Comentar o descomentar
        cursor.beginEditBlock()
        block = start_block
        while block.isValid() and block != end_block.next():
            text = block.text()
            if all_commented:
                # Descomentar: quitar el prefijo y el espacio siguiente
                if text.lstrip().startswith(comment):
                    idx = text.find(comment)
                    after = idx + len(comment)
                    # Quitar un espacio después del comment si existe
                    if after < len(text) and text[after] == " ":
                        after += 1
                    new_text = text[:idx] + text[after:]
                    cursor.setPosition(block.position())
                    cursor.movePosition(QTextCursor.EndOfBlock,
                                        QTextCursor.KeepAnchor)
                    cursor.removeSelectedText()
                    cursor.insertText(new_text)
            else:
                # Comentar: agregar el prefijo
                # Preservar indentación
                stripped = text.lstrip()
                indent = text[:len(text) - len(stripped)]
                new_text = indent + comment + " " + stripped if stripped else indent + comment
                cursor.setPosition(block.position())
                cursor.movePosition(QTextCursor.EndOfBlock,
                                    QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                cursor.insertText(new_text)
            block = block.next()
        cursor.endEditBlock()

    def _comment_prefix(self):
        """Devuelve el prefijo de comentario según el lenguaje."""
        lang = getattr(self, "_lang", "text")
        if lang in ("python"):
            return "#"
        elif lang in ("javascript", "java", "css"):
            return "//"
        elif lang == "html":
            return "<!--"
        elif lang == "markdown":
            return "<!--"
        return None

    def _update_line_width(self):
        digits = len(str(max(1, self.blockCount())))
        # 8px padding izquierda + dígitos + 8px padding derecha
        w = 16 + digits * self.fontMetrics().horizontalAdvance("9")
        self.line_numbers.setFixedWidth(w)
        self.setViewportMargins(w, 0, 0, 0)

    def _update_line_area(self, rect, dy):
        if dy:
            self.line_numbers.scroll(0, dy)
        else:
            self.line_numbers.update(0, rect.y(), self.line_numbers.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_width()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cr = self.contentsRect()
        self.line_numbers.setGeometry(
            cr.left(), cr.top(),
            self.line_numbers.width(), cr.height())

    def line_number_paint(self, event):
        painter = __import__("PySide6.QtGui", fromlist=["QPainter"]).QPainter(
            self.line_numbers)
        painter.fillRect(event.rect(), QColor("#22242a"))
        block = self.firstVisibleBlock()
        block_num = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(
            self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible():
                num = str(block_num + 1)
                painter.setPen(QColor("#5c6370"))
                painter.drawText(
                    8, top, self.line_numbers.width() - 16,
                    self.fontMetrics().height(),
                    Qt.AlignRight, num)
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_num += 1


class LineNumberArea(QWidget):
    """Widget que muestra los números de línea."""

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setFixedWidth(24)  # se actualiza en _update_line_width

    def paintEvent(self, event):
        self.editor.line_number_paint(event)


class EditorTab(QWidget):
    """Una pestaña del editor: contiene el CodeEditor + datos del archivo."""

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self.original_content = ""
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.editor = CodeEditor()
        v.addWidget(self.editor)
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            content = f"// Error al leer {self.path}: {e}"
        self.original_content = content
        self.editor.setPlainText(content)
        ext = os.path.splitext(self.path)[1].lower()
        lang = EXT_LANG.get(ext, "text")
        self.editor.set_language(lang)

    def is_modified(self):
        return self.editor.toPlainText() != self.original_content

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            self.original_content = self.editor.toPlainText()
            return True
        except OSError:
            return False


class EditorPanel(QWidget):
    """Panel central: tabs de archivos abiertos con editor + números de línea."""

    file_opened = Signal(str)
    file_saved = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._open_paths = {}  # path → index
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # ---- Tabs con scroll oculto ----
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.ElideRight)
        # Alinear tabs a la izquierda (no centradas ni expandiendo)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.setTabBarAutoHide(False)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        v.addWidget(self.tabs, 1)

        # ---- Barra de estado del editor ----
        self.status = QLabel("Sin archivo")
        self.status.setObjectName("editorStatus")
        self.status.setContentsMargins(10, 4, 10, 4)
        v.addWidget(self.status)

        # ---- Shortcuts configurables ----
        from utils.shortcuts import load_shortcuts
        self._shortcuts = load_shortcuts()
        self._shortcut_objs = []
        self._apply_shortcuts()

    def _apply_shortcuts(self):
        """Crea/recrea los QShortcut con las secuencias actuales."""
        for sc in self._shortcut_objs:
            sc.deleteLater()
        self._shortcut_objs = []
        sc_defs = {
            "save":           self._save_current,
            "close_tab":      self._close_current,
            "next_tab":       self._next_tab,
            "prev_tab":       self._prev_tab,
            "duplicate_line": self._duplicate_line,
            "toggle_comment": self._toggle_comment,
        }
        for key, cb in sc_defs.items():
            seq = self._shortcuts.get(key)
            if seq:
                sc = QShortcut(QKeySequence(seq), self)
                sc.setContext(Qt.ApplicationShortcut)
                sc.activated.connect(cb)
                self._shortcut_objs.append(sc)

    def _next_tab(self):
        n = self.tabs.count()
        if n > 1:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + 1) % n)
            self._focus_editor()

    def _prev_tab(self):
        n = self.tabs.count()
        if n > 1:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() - 1) % n)
            self._focus_editor()

    def _close_current(self):
        if self.tabs.count() > 0:
            self._close_tab(self.tabs.currentIndex())

    def _duplicate_line(self):
        tab = self.tabs.currentWidget()
        if tab and hasattr(tab, "editor"):
            tab.editor.duplicate_line()

    def _toggle_comment(self):
        tab = self.tabs.currentWidget()
        if tab and hasattr(tab, "editor"):
            tab.editor.toggle_comment()

    def reload_shortcuts(self):
        """Recarga los shortcuts desde el archivo (tras cambiar en settings)."""
        from utils.shortcuts import load_shortcuts
        self._shortcuts = load_shortcuts()
        self._apply_shortcuts()

    def open_file(self, path):
        """Abre un archivo en una nueva pestaña, o activa la existente."""
        if path in self._open_paths:
            self.tabs.setCurrentIndex(self._open_paths[path])
            return
        tab = EditorTab(path)
        name = os.path.basename(path)
        idx = self.tabs.addTab(tab, name)
        self._open_paths[path] = idx
        self.tabs.setCurrentIndex(idx)
        self.file_opened.emit(path)
        self._update_status(path)

    def _close_tab(self, idx):
        tab = self.tabs.widget(idx)
        if tab is None:
            return
        if tab.is_modified():
            btn = QMessageBox.question(
                self, "Cerrar archivo",
                f"¿Guardar cambios en {os.path.basename(tab.path)}?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if btn == QMessageBox.Cancel:
                return
            if btn == QMessageBox.Yes:
                tab.save()
        # Reconstruir _open_paths
        del self._open_paths[tab.path]
        self.tabs.removeTab(idx)
        # Reindexar
        self._reindex()
        if self.tabs.count() == 0:
            self.status.setText("Sin archivo")
        else:
            self._update_status(self.tabs.currentWidget().path)
        # Devolver el foco al editor
        self._focus_editor()

    def _focus_editor(self):
        """Pone el foco en el editor de la tab actual."""
        tab = self.tabs.currentWidget()
        if tab and hasattr(tab, "editor"):
            tab.editor.setFocus()

    def _reindex(self):
        self._open_paths = {}
        for i in range(self.tabs.count()):
            self._open_paths[self.tabs.widget(i).path] = i

    def _save_current(self):
        tab = self.tabs.currentWidget()
        if tab is None:
            return
        if tab.save():
            self.file_saved.emit(tab.path)
            self._update_status(tab.path)

    def _on_tab_changed(self, idx):
        tab = self.tabs.widget(idx)
        if tab:
            self._update_status(tab.path)

    def _update_status(self, path):
        name = os.path.basename(path)
        ext = os.path.splitext(path)[1].lower()
        lang = EXT_LANG.get(ext, "text")
        self.status.setText(f"  {name}   —   {lang}")
