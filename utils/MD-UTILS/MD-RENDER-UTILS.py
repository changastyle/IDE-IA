# -*- coding: utf-8 -*-
"""Conversor liviano de Markdown a HTML, sin dependencias externas.

Soporta: encabezados, negrita/cursiva/tachado, código inline y bloques
cercados, listas (ordenadas y no), citas, reglas horizontales, tablas,
enlaces e imágenes (resolviendo rutas relativas contra base_dir).
"""
import html
import os
import re


def is_markdown_file(path):
    """¿El path es un archivo markdown?"""
    return os.path.splitext(path)[1].lower() in (".md", ".markdown")


def _inline(text):
    """Formatea markdown inline (después de escapar HTML)."""
    # Código inline primero (proteger su contenido)
    codes = []

    def _stash(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", _stash, text)
    # Imágenes ![alt](src)
    text = re.sub(
        r"!\[([^\]]*)\]\(([^)\s]+)\)",
        lambda m: f'<img src="{m.group(2)}" alt="{m.group(1)}">',
        text)
    # Enlaces [texto](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>',
        text)
    # Negrita, cursiva, tachado
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__([^_]+)__", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"<i>\1</i>", text)
    text = re.sub(r"~~([^~]+)~~", r"<s>\1</s>", text)
    # Restaurar código inline
    def _unstash(m):
        return f"<code>{codes[int(m.group(1))]}</code>"

    return re.sub(r"\x00(\d+)\x00", _unstash, text)


def _table_html(rows):
    out = ["<table>"]
    for i, row in enumerate(rows):
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue  # fila separadora
        tag = "th" if i == 0 else "td"
        out.append("<tr>" + "".join(
            f"<{tag}>{_inline(c)}</{tag}>" for c in cells) + "</tr>")
    out.append("</table>")
    return "".join(out)


def md_to_html(md_text, base_dir=None):
    """Convierte markdown a HTML. Las imágenes relativas se resuelven
    contra base_dir para que el visor las encuentre."""
    lines = md_text.replace("\r\n", "\n").split("\n")
    out = []
    i = 0
    in_list = None  # "ul" | "ol" | None

    def close_list():
        nonlocal in_list
        if in_list:
            out.append(f"</{in_list}>")
            in_list = None

    while i < len(lines):
        line = lines[i]
        s = line.strip()

        # Bloque de código cercado
        m = re.match(r"^```(\w*)\s*$", s)
        if m:
            close_list()
            lang = m.group(1)
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1  # saltar ```
            cls = f' class="language-{lang}"' if lang else ""
            out.append(f"<pre><code{cls}>{html.escape(chr(10).join(code))}</code></pre>")
            continue

        # Tabla: línea actual y siguiente con separador |---|---|
        if s.startswith("|") and i + 1 < len(lines) and \
                re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            close_list()
            rows = [s]
            i += 1
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            out.append(_table_html(rows))
            continue

        # Encabezado
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            close_list()
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_inline(html.escape(m.group(2)))}</h{lvl}>")
            i += 1
            continue

        # Regla horizontal
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s):
            close_list()
            out.append("<hr>")
            i += 1
            continue

        # Cita
        if s.startswith(">"):
            close_list()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append(f"<blockquote>{md_to_html(chr(10).join(quote), base_dir)}</blockquote>")
            continue

        # Listas
        m_ul = re.match(r"^[-*+]\s+(.*)$", s)
        m_ol = re.match(r"^\d+[.)]\s+(.*)$", s)
        if m_ul or m_ol:
            want = "ul" if m_ul else "ol"
            if in_list != want:
                close_list()
                out.append(f"<{want}>")
                in_list = want
            out.append(f"<li>{_inline(html.escape((m_ul or m_ol).group(1)))}</li>")
            i += 1
            continue

        # Línea vacía
        if not s:
            close_list()
            i += 1
            continue

        # Párrafo (agrupa líneas contiguas)
        close_list()
        para = [s]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith(("#", ">", "```", "|", "- ", "* ", "+ "))
                    or re.match(r"^\d+[.)]\s", nxt)
                    or re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", nxt)):
                break
            para.append(nxt)
            i += 1
        out.append(f"<p>{_inline(html.escape(' '.join(para)))}</p>")

    close_list()
    html_out = "\n".join(out)
    # Resolver imágenes relativas contra base_dir
    if base_dir:
        def _abs_img(m):
            src = m.group(1)
            if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", src) and \
               not src.startswith("/") and not src.startswith("file:"):
                p = os.path.join(base_dir, src)
                if os.path.exists(p):
                    return f'<img src="{p}" alt="{m.group(2)}">'
            return m.group(0)

        html_out = re.sub(r'<img src="([^"]+)" alt="([^"]*)">', _abs_img, html_out)
    return html_out
