# -*- coding: utf-8 -*-
"""Editor de archivos para el panel central.

- Tabs arriba con el nombre del archivo (basename)
- Números de línea a la izquierda
- Resaltado básico de sintaxis (Python, JS, HTML, CSS, JSON, Markdown)
- Detección de cambios externos al ganar foco
"""
import os
import difflib

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QFont, QColor, QSyntaxHighlighter, QTextCharFormat, QTextCursor,
    QKeySequence, QShortcut, QTextBlockUserData, QTextFormat, QPixmap,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPlainTextEdit,
    QTextEdit, QLabel, QPushButton, QMessageBox, QScrollArea,
)


class _DiffData(QTextBlockUserData):
    """Marca de diff por bloque: 'add' (verde) o 'del' (rojo phantom)."""

    def __init__(self):
        super().__init__()
        self.flag = None

APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICONS_DIR = os.path.join(APP_DIR, "UI", "iconos")

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
        top = round(self.blockBoundingGeometry(block).translated(
            self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        real_ln = 0
        # Contar líneas reales (no phantom) hasta el primer bloque visible
        b0 = self.document().begin()
        while b0.isValid() and b0.blockNumber() < block.blockNumber():
            d = b0.userData()
            if not (d and getattr(d, "flag", None) == "del"):
                real_ln += 1
            b0 = b0.next()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible():
                d = block.userData()
                flag = getattr(d, "flag", None) if d else None
                h = self.fontMetrics().height()
                if flag == "del":
                    painter.fillRect(0, top, 3, h, QColor("#e05561"))
                    painter.setPen(QColor("#e05561"))
                    painter.drawText(8, top, self.line_numbers.width() - 16,
                                     h, Qt.AlignRight, "–")
                elif flag == "add":
                    real_ln += 1
                    painter.fillRect(0, top, 3, h, QColor("#4cc26b"))
                    painter.setPen(QColor("#4cc26b"))
                    painter.drawText(8, top, self.line_numbers.width() - 16,
                                     h, Qt.AlignRight, str(real_ln))
                else:
                    real_ln += 1
                    painter.setPen(QColor("#5c6370"))
                    painter.drawText(
                        8, top, self.line_numbers.width() - 16,
                        h, Qt.AlignRight, str(real_ln))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())


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

    review_accepted = Signal(str)   # path — usuario aceptó todos los cambios
    review_rejected = Signal(str)   # path — usuario rechazó (restaurar antes)
    prev_file = Signal(str)         # path — ir al archivo anterior en review
    next_file = Signal(str)         # path — ir al siguiente archivo en review

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self.original_content = ""
        self._merged = None          # [(flag|None, text)] durante review
        self._review_before = None
        self._hunk_idx = 0
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.editor = CodeEditor()
        v.addWidget(self.editor)
        # ---- Barra inferior de revisión (estilo Windsurf) ----
        self.review_bar = QWidget()
        self.review_bar.setObjectName("reviewBar")
        rb = QHBoxLayout(self.review_bar)
        rb.setContentsMargins(10, 4, 10, 4)
        rb.setSpacing(6)
        rb.addStretch(1)
        _nav_ss = (
            "QPushButton{background:#2a2d33;border:1px solid #3f4246;"
            "border-radius:4px;color:#dfe1e5;padding:3px 9px;font-size:12px;}"
            "QPushButton:hover{background:#353b45;}")
        b = QPushButton("↑")
        b.setToolTip("Cambio anterior")
        b.setStyleSheet(_nav_ss)
        b.setFixedHeight(26)
        b.clicked.connect(lambda: self._goto_hunk(-1))
        rb.addWidget(b)
        self.hunk_lbl = QLabel("")
        self.hunk_lbl.setStyleSheet("color:#e8eaed;font-size:12px;")
        rb.addWidget(self.hunk_lbl)
        b = QPushButton("↓")
        b.setToolTip("Siguiente cambio")
        b.setStyleSheet(_nav_ss)
        b.setFixedHeight(26)
        b.clicked.connect(lambda: self._goto_hunk(1))
        rb.addWidget(b)
        # Aceptar / rechazar solo el hunk actual
        b = QPushButton("✓")
        b.setToolTip("Aceptar este cambio")
        b.setStyleSheet(
            "QPushButton{background:#2a2d33;border:1px solid #3f4246;"
            "border-radius:4px;color:#4cc26b;padding:3px 9px;font-size:12px;"
            "font-weight:bold;} QPushButton:hover{background:#353b45;}")
        b.setFixedHeight(26)
        b.clicked.connect(self._accept_hunk)
        rb.addWidget(b)
        b = QPushButton("✗")
        b.setToolTip("Rechazar este cambio")
        b.setStyleSheet(
            "QPushButton{background:#2a2d33;border:1px solid #3f4246;"
            "border-radius:4px;color:#e05561;padding:3px 9px;font-size:12px;"
            "font-weight:bold;} QPushButton:hover{background:#353b45;}")
        b.setFixedHeight(26)
        b.clicked.connect(self._reject_hunk)
        rb.addWidget(b)
        rb.addSpacing(10)
        self.btn_acc_all = QPushButton("Accept File")
        self.btn_acc_all.setStyleSheet(
            "QPushButton{background:#3574f0;border:none;border-radius:6px;"
            "color:#fff;padding:4px 14px;font-size:12px;font-weight:600;}"
            "QPushButton:hover{background:#4a86f5;}")
        self.btn_acc_all.setFixedHeight(26)
        self.btn_acc_all.clicked.connect(self._accept_all)
        rb.addWidget(self.btn_acc_all)
        self.btn_rej_all = QPushButton("Reject File")
        self.btn_rej_all.setStyleSheet(
            "QPushButton{background:#2a2d33;border:1px solid #3f4246;"
            "border-radius:6px;color:#dfe1e5;padding:4px 14px;font-size:12px;}"
            "QPushButton:hover{background:#353b45;}")
        self.btn_rej_all.setFixedHeight(26)
        self.btn_rej_all.clicked.connect(self._reject_all)
        rb.addWidget(self.btn_rej_all)
        rb.addSpacing(10)
        # Navegación entre archivos en review: < 1 of 3 files >
        b = QPushButton("‹")
        b.setToolTip("Archivo anterior con cambios")
        b.setStyleSheet(_nav_ss)
        b.setFixedHeight(26)
        b.clicked.connect(lambda: self.prev_file.emit(self.path))
        rb.addWidget(b)
        self.files_lbl = QLabel("")
        self.files_lbl.setStyleSheet("color:#9da3ae;font-size:12px;")
        rb.addWidget(self.files_lbl)
        b = QPushButton("›")
        b.setToolTip("Siguiente archivo con cambios")
        b.setStyleSheet(_nav_ss)
        b.setFixedHeight(26)
        b.clicked.connect(lambda: self.next_file.emit(self.path))
        rb.addWidget(b)
        rb.addStretch(1)
        # Aceptar/rechazar el hunk actual: botones chicos discretos
        self.review_bar.setStyleSheet(
            "#reviewBar{background:#1d1f24;border-top:1px solid #32363d;}")
        self.review_bar.hide()
        v.addWidget(self.review_bar)
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            content = f"// Error al leer {self.path}: {e}"
        self.original_content = content
        self._merged = None
        self._review_before = None
        self.review_bar.hide()
        self.editor.setExtraSelections([])
        self.editor.setPlainText(content)
        ext = os.path.splitext(self.path)[1].lower()
        lang = EXT_LANG.get(ext, "text")
        self.editor.set_language(lang)

    def _sync_merged_from_doc(self):
        """Relee flags+texto del documento (por si el usuario editó en review)."""
        merged = []
        block = self.editor.document().begin()
        while block.isValid():
            d = block.userData()
            merged.append((getattr(d, "flag", None) if d else None,
                           block.text()))
            block = block.next()
        self._merged = merged

    def real_text(self):
        """Texto real del archivo = documento sin las phantom lines 'del'."""
        if self._merged is not None:
            self._sync_merged_from_doc()
            return "\n".join(t for f, t in self._merged if f != "del")
        return self.editor.toPlainText()

    def is_modified(self):
        return self.real_text() != self.original_content

    def save(self):
        try:
            text = self.real_text()
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(text)
            self.original_content = text
            if self._merged is not None:
                # Lo guardado pasa a ser la nueva base; seguir revisando el resto
                self._review_before = text
                self._render_review()
            return True
        except OSError:
            return False

    # ---- Review de cambios de la IA (diff inline) ----

    def in_review(self):
        return self._merged is not None

    def start_review(self, before):
        """Muestra el diff `before` vs contenido actual dentro del editor.

        Las líneas borradas aparecen como phantom lines rojas (no forman parte
        del texto real); las agregadas en verde. Navegación por hunks.
        """
        if not self.in_review():
            self._review_before = before
        # Si ya hay review activo, el "actual" es el texto real (sin phantom)
        after = self.real_text()
        self._merged = self._merge_lines(self._review_before, after)
        self._hunk_idx = 0
        self._render_review()
        self.review_bar.show()
        if self._hunks():
            self._scroll_to_hunk(0)

    @staticmethod
    def _merge_lines(before, after):
        """Combina before/after en [(flag, text)] con flag 'del'/'add'/None."""
        merged = []
        a, b = before.split("\n"), after.split("\n")
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                merged += [(None, t) for t in b[j1:j2]]
            elif tag == "delete":
                merged += [("del", t) for t in a[i1:i2]]
            elif tag == "insert":
                merged += [("add", t) for t in b[j1:j2]]
            else:  # replace → del primero, luego add (orden diff estándar)
                merged += [("del", t) for t in a[i1:i2]]
                merged += [("add", t) for t in b[j1:j2]]
        return merged

    def _render_review(self):
        """Vuelca _merged al documento, marcando bloques add/del."""
        ed = self.editor
        cur_pos = ed.textCursor().position()
        ed.blockSignals(True)
        ed.setPlainText("\n".join(t for _f, t in self._merged))
        block = ed.document().begin()
        for flag, _t in self._merged:
            if flag:
                d = _DiffData()
                d.flag = flag
                block.setUserData(d)
            block = block.next()
        ed.blockSignals(False)
        self._apply_diff_formats()
        # Restaurar cursor aproximado
        cur = ed.textCursor()
        cur.setPosition(min(cur_pos, len(ed.toPlainText())))
        ed.setTextCursor(cur)
        self._update_hunk_label()

    def _apply_diff_formats(self):
        """Colorea fondo verde/rojo en las líneas marcadas."""
        sels = []
        block = self.editor.document().begin()
        while block.isValid():
            d = block.userData()
            flag = getattr(d, "flag", None) if d else None
            if flag:
                sel = QTextEdit.ExtraSelection()
                fmt = QTextCharFormat()
                if flag == "add":
                    fmt.setBackground(QColor(46, 160, 67, 55))
                else:
                    fmt.setBackground(QColor(229, 72, 77, 45))
                    fmt.setFontStrikeOut(True)
                    fmt.setForeground(QColor("#f08080"))
                fmt.setProperty(QTextFormat.FullWidthSelection, True)
                sel.format = fmt
                sel.cursor = QTextCursor(block)
                sels.append(sel)
            block = block.next()
        self.editor.setExtraSelections(sels)

    def _hunks(self):
        """Rangos (start,end) en _merged de bloques contiguos marcados."""
        hunks, start = [], None
        for i, (flag, _t) in enumerate(self._merged or []):
            if flag and start is None:
                start = i
            elif not flag and start is not None:
                hunks.append((start, i - 1))
                start = None
        if start is not None:
            hunks.append((start, len(self._merged) - 1))
        return hunks

    def _update_hunk_label(self):
        hunks = self._hunks()
        n_edits = sum(1 for f, _t in (self._merged or []) if f)
        self.hunk_lbl.setText(
            f"{n_edits} edits" if hunks else "sin cambios")
        self.hunk_lbl.setToolTip(
            f"Cambio {min(self._hunk_idx + 1, len(hunks))} de {len(hunks)}"
            if hunks else "")

    def set_file_nav(self, idx, total):
        """Actualiza el contador '< i of N files >' de la barra."""
        self.files_lbl.setText(f"{idx} of {total} files" if total else "")

    def _scroll_to_hunk(self, idx):
        hunks = self._hunks()
        if not hunks:
            return
        self._hunk_idx = idx % len(hunks)
        line = hunks[self._hunk_idx][0] + 1  # 1-based en el doc merged
        EditorPanel.goto_line(self, line)
        self._update_hunk_label()

    def _goto_hunk(self, delta):
        if self._hunks():
            self._scroll_to_hunk(self._hunk_idx + delta)

    def _apply_hunk(self, accept):
        """Acepta (quita phantom del, desmarca add) o rechaza (quita add,
        desmarca del) el hunk actual."""
        if self._merged is not None:
            self._sync_merged_from_doc()
        hunks = self._hunks()
        if not hunks:
            return
        s, e = hunks[min(self._hunk_idx, len(hunks) - 1)]
        new_merged = []
        for i, (flag, t) in enumerate(self._merged):
            if s <= i <= e:
                if flag == "del" and accept:
                    continue          # borrar la phantom → queda borrada
                if flag == "add" and not accept:
                    continue          # borrar la agregada → se revierte
                new_merged.append((None, t))
            else:
                new_merged.append((flag, t))
        self._merged = new_merged
        if not self._hunks():
            # Resolvió todo hunk a hunk: guardar y marcar como aceptado
            self._finish_review()
            self.save()
            self.review_accepted.emit(self.path)
        else:
            self._hunk_idx = min(self._hunk_idx, len(self._hunks()) - 1)
            self._render_review()
            self._scroll_to_hunk(self._hunk_idx)

    def _accept_hunk(self):
        self._apply_hunk(accept=True)

    def _reject_hunk(self):
        self._apply_hunk(accept=False)

    def _accept_all(self):
        self._merged = [(None, t) for f, t in self._merged if f != "del"]
        self._finish_review()
        self.save()
        self.review_accepted.emit(self.path)

    def _reject_all(self):
        # No escribe acá: el chat restaura el backup (o borra el archivo nuevo)
        # de forma síncrona al emitir la señal; después recargamos desde disco.
        self.review_rejected.emit(self.path)
        if os.path.exists(self.path):
            self.end_review()

    def end_review(self):
        """Sale del modo review recargando desde disco."""
        self._merged = None
        self._review_before = None
        self.review_bar.hide()
        self.editor.setExtraSelections([])
        self.load()

    def _finish_review(self):
        """Render final: documento = texto real, sin marcas ni barra."""
        final = self.real_text()
        self._merged = None
        self._review_before = None
        self.editor.blockSignals(True)
        self.editor.setPlainText(final)
        self.editor.blockSignals(False)
        self.editor.setExtraSelections([])
        self.review_bar.hide()
        self.editor.viewport().update()
        self.editor.line_numbers.update()


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic",
              ".svg", ".tif", ".tiff"}


class ImageTab(QWidget):
    """Tab de imagen: viewer con scroll, ajuste a ventana y zoom.
    Misma API mínima que EditorTab para convivir en el EditorPanel."""

    review_accepted = Signal(str)   # compat: nunca se emiten en imágenes
    review_rejected = Signal(str)
    prev_file = Signal(str)
    next_file = Signal(str)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self._fit = True
        self._zoom = 1.0
        self._pm = QPixmap()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        # Barra superior: nombre + dimensiones + controles de zoom
        bar = QWidget()
        bar.setStyleSheet(
            "background:#1d1f24; border-bottom:1px solid #32363d;")
        bh = QHBoxLayout(bar)
        bh.setContentsMargins(10, 4, 10, 4)
        bh.setSpacing(6)
        self.info = QLabel("")
        self.info.setStyleSheet("color:#9da3ae; font-size:11px;")
        bh.addWidget(self.info)
        bh.addStretch(1)
        for txt, tip, cb in (
                ("Ajustar", "Ajustar a la ventana", self._set_fit),
                ("100%", "Tamaño real", self._set_100),
                ("＋", "Acercar", lambda: self._zoom_by(1.25)),
                ("－", "Alejar", lambda: self._zoom_by(0.8))):
            b = QPushButton(txt)
            b.setToolTip(tip)
            b.setFixedHeight(24)
            b.setStyleSheet(
                "QPushButton{background:#2a2d33;border:1px solid #3f4246;"
                "border-radius:4px;color:#dfe1e5;padding:2px 10px;"
                "font-size:11px;} QPushButton:hover{background:#353b45;}")
            b.clicked.connect(cb)
            bh.addWidget(b)
        v.addWidget(bar)
        # Scroll con la imagen centrada
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(
            "QScrollArea{background:#14161a; border:none;}")
        self.img = QLabel()
        self.img.setAlignment(Qt.AlignCenter)
        self.img.setStyleSheet("background:#14161a;")
        self.scroll.setWidget(self.img)
        v.addWidget(self.scroll, 1)
        self.load()

    # ---- API de tab (compatible con EditorTab) ----

    def load(self):
        self._pm = QPixmap(self.path)
        if self._pm.isNull():
            self.img.setText(f"No se pudo cargar la imagen:\n{self.path}")
            self.img.setStyleSheet("color:#ff6b63; background:#14161a;")
            return
        kb = max(1, os.path.getsize(self.path) // 1024)
        self.info.setText(
            f"{os.path.basename(self.path)}    "
            f"{self._pm.width()}×{self._pm.height()} · {kb} KB")
        self._refresh()

    def is_modified(self):
        return False

    def save(self):
        return False

    def in_review(self):
        return False

    def start_review(self, before):
        pass

    def end_review(self):
        pass

    def set_file_nav(self, idx, total):
        pass

    # ---- Zoom / ajuste ----

    def _set_fit(self):
        self._fit = True
        self._refresh()

    def _set_100(self):
        self._fit = False
        self._zoom = 1.0
        self._refresh()

    def _zoom_by(self, factor):
        self._fit = False
        self._zoom = max(0.05, min(20.0, self._zoom * factor))
        self._refresh()

    def _refresh(self):
        if self._pm.isNull():
            return
        if self._fit:
            avail = self.scroll.viewport().size()
            pm = self._pm.scaled(max(40, avail.width() - 8),
                                 max(40, avail.height() - 8),
                                 Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            pm = self._pm.scaled(int(self._pm.width() * self._zoom),
                                 int(self._pm.height() * self._zoom),
                                 Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.img.setPixmap(pm)
        self.img.adjustSize()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._fit:
            self._refresh()


class EditorPanel(QWidget):
    """Panel central: tabs de archivos abiertos con editor + números de línea."""

    file_opened = Signal(str)
    file_saved = Signal(str)
    review_accepted = Signal(str)   # path — todos los cambios aceptados
    review_rejected = Signal(str)   # path — cambios rechazados (restaurar)

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
        self._review_files = []  # paths con review activo (para ‹ 1 of N ›)

        # ---- Barra de estado del editor ----
        self.status = QLabel("Sin archivo")
        self.status.setObjectName("editorStatus")
        self.status.setContentsMargins(10, 4, 10, 4)
        v.addWidget(self.status)

        # ---- Shortcuts configurables ----
        from UTILS.shortcuts import load_shortcuts
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
        from UTILS.shortcuts import load_shortcuts
        self._shortcuts = load_shortcuts()
        self._apply_shortcuts()

    def open_file(self, path, goto_line=0):
        """Abre un archivo en una nueva pestaña (o activa la existente) y
        opcionalmente scrollea a una línea (1-based)."""
        if path in self._open_paths:
            self.tabs.setCurrentIndex(self._open_paths[path])
            tab = self.tabs.currentWidget()
            # Recargar desde disco si el usuario no tiene cambios sin guardar
            # (p. ej. la IA acaba de editar el archivo por fuera del editor)
            if tab and not tab.is_modified():
                tab.load()
            self._update_status(path)
        else:
            ext = os.path.splitext(path)[1].lower()
            if ext in IMAGE_EXTS and not QPixmap(path).isNull():
                tab = ImageTab(path)
            else:
                tab = EditorTab(path)
            tab.review_accepted.connect(self._on_tab_review_accepted)
            tab.review_rejected.connect(self._on_tab_review_rejected)
            tab.prev_file.connect(lambda p: self._review_nav(p, -1))
            tab.next_file.connect(lambda p: self._review_nav(p, 1))
            name = os.path.basename(path)
            idx = self.tabs.addTab(tab, name)
            self._open_paths[path] = idx
            self.tabs.setCurrentIndex(idx)
            self.file_opened.emit(path)
            self._update_status(path)
        if goto_line and tab and hasattr(tab, "editor"):
            self.goto_line(tab, goto_line)
        return tab

    def start_review(self, path, before):
        """Abre `path` y entra en modo review con diff vs `before`."""
        tab = self.open_file(path)
        if tab and hasattr(tab, "editor"):
            tab.start_review(before)
            if path not in self._review_files:
                self._review_files.append(path)
            self._update_review_nav()

    def end_review(self, path):
        """Sale del modo review en la tab de `path` (si está)."""
        if path in self._review_files:
            self._review_files.remove(path)
            self._update_review_nav()
        idx = self._open_paths.get(path)
        if idx is None:
            return
        tab = self.tabs.widget(idx)
        if tab and tab.in_review():
            tab.end_review()

    def _on_tab_review_accepted(self, path):
        self._drop_review_file(path)
        self.review_accepted.emit(path)

    def _on_tab_review_rejected(self, path):
        self._drop_review_file(path)
        self.review_rejected.emit(path)

    def _drop_review_file(self, path):
        if path in self._review_files:
            self._review_files.remove(path)
            self._update_review_nav()

    def _update_review_nav(self):
        """Actualiza el '< i of N files >' de cada tab en review."""
        total = len(self._review_files)
        for i, p in enumerate(self._review_files):
            idx = self._open_paths.get(p)
            tab = self.tabs.widget(idx) if idx is not None else None
            if tab:
                tab.set_file_nav(i + 1, total)

    def _review_nav(self, path, delta):
        """Cambia a la tab del siguiente/anterior archivo en review."""
        if path in self._review_files and len(self._review_files) > 1:
            i = self._review_files.index(path)
            nxt = self._review_files[(i + delta) % len(self._review_files)]
            idx = self._open_paths.get(nxt)
            if idx is not None:
                self.tabs.setCurrentIndex(idx)

    def close_path(self, path):
        """Cierra la tab de `path` sin preguntar (p. ej. archivo borrado)."""
        idx = self._open_paths.get(path)
        if idx is None:
            return
        tab = self.tabs.widget(idx)
        del self._open_paths[tab.path]
        self.tabs.removeTab(idx)
        self._reindex()
        if path in self._review_files:
            self._review_files.remove(path)
            self._update_review_nav()
        if self.tabs.count() == 0:
            self.status.setText("Sin archivo")

    @staticmethod
    def goto_line(tab, line):
        """Posiciona el cursor del editor en `line` (1-based) y centra."""
        doc = tab.editor.document()
        block = doc.findBlockByLineNumber(max(0, line - 1))
        if not block.isValid():
            return
        cur = tab.editor.textCursor()
        cur.setPosition(block.position())
        tab.editor.setTextCursor(cur)
        tab.editor.centerCursor()

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
