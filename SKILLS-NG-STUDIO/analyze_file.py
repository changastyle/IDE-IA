#!/usr/bin/env python3
"""Skill: analyze_file — analiza un archivo .py, .js o .java, genera un
resumen con su nombre, clases y funciones, lo escribe como comentario al
inicio del propio archivo y devuelve el resumen completo por stdout para
que la IA lo pueda usar.

Uso: python3 analyze_file.py <archivo> [--no-write]
  --no-write   solo devuelve el resumen, no modifica el archivo.
Salida: el resumen en texto. 0 = OK, 1 = error, 2 = uso incorrecto.
Si el archivo ya tenía un resumen generado por esta skill, se reemplaza.
"""
import ast
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.realpath(os.getcwd())
MARKER = "generado por analyze_file"

# Palabras que no son funciones aunque tengan paréntesis
KEYWORDS = {
    "if", "elif", "else", "for", "while", "do", "switch", "case", "catch",
    "try", "finally", "return", "throw", "throws", "new", "delete", "typeof",
    "instanceof", "in", "of", "function", "class", "import", "from", "super",
    "this", "assert", "synchronized", "with", "yield", "await",
}

# Si el "tipo de retorno" de un supuesto método Java es una de estas
# palabras, en realidad es una sentencia (return foo(...), throw new X(...))
REJECT_PREFIX = {
    "return", "throw", "new", "case", "assert", "yield", "if", "for",
    "while", "switch", "catch", "else", "do",
}

# ---------------------------------------------------------------- JS --
JS_PATTERNS = [
    # function nombre(...) / async function nombre(...) / export function
    re.compile(r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*\(([^)]*)\)"),
    # const nombre = (...) => / const nombre = async (...) =>
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>"),
    # const nombre = function(...) / = async function(...)
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?function\s*\*?\s*\(([^)]*)\)"),
    # nombre: function(...) / nombre: (...) =>   (métodos de objeto)
    re.compile(r"^\s*([A-Za-z_$][\w$]*)\s*:\s*(?:async\s+)?(?:function\s*\*?\s*)?\(([^)]*)\)\s*(?:=>|\{)"),
    # nombre = (...) =>   (campos de clase / asignaciones)
    re.compile(r"^\s*([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>"),
]
JS_CLASS_RE = re.compile(r"^\s*(?:export\s+(?:default\s+)?)?class\s+([A-Za-z_$][\w$]*)")
# nombre(...) {  /  static async nombre(...) {  /  get nombre() {
JS_METHOD_RE = re.compile(
    r"^\s*(?:static\s+)?(?:async\s+)?(?:get\s+|set\s+)?\*?\s*([A-Za-z_$][\w$]*)\s*\(([^)]*)\)\s*\{"
)

# -------------------------------------------------------------- Java --
JAVA_CLASS_RE = re.compile(r"\b(?:class|interface|enum|record|@interface)\s+([A-Za-z_]\w*)")
# [modificadores] tipoRetorno nombre(...) [throws X] { | ; | fin de línea
JAVA_METHOD_RE = re.compile(
    r"^\s*(?:@[\w.]+\s*)*(?:(?:public|private|protected|static|final|synchronized|abstract|native|default|strictfp|transient)\s+)*"
    r"([\w<>\[\],.?\s]+?)\s+([A-Za-z_]\w*)\s*\(([^;{}]*)\)\s*(?:throws\s+[\w\s,.]+)?\s*(?:\{|;|$)"
)
# Constructor: [modificador] Nombre(...) {
JAVA_CTOR_RE = re.compile(
    r"^\s*(?:public|private|protected)\s+([A-Za-z_]\w*)\s*\(([^;{}]*)\)\s*(?:throws\s+[\w\s,.]+)?\s*(?:\{|$)"
)


def _resolve(rel: str) -> str | None:
    """Resuelve una ruta relativa dentro del workspace."""
    rel = str(rel or "").strip().lstrip("/")
    if not rel or rel == ".":
        return None
    p = os.path.realpath(os.path.join(ROOT, rel))
    if p != ROOT and not p.startswith(ROOT + os.sep):
        return None
    return p


# --------------------------------------------------------- helpers --

def _doc(node: ast.AST) -> str:
    """Primera línea del docstring de un nodo Python."""
    d = ast.get_docstring(node)
    return d.split("\n")[0].strip() if d else ""


def _ret(node: ast.AST) -> str:
    """'-> tipo' si la función Python tiene anotación de retorno."""
    if getattr(node, "returns", None) is not None:
        try:
            return " -> " + ast.unparse(node.returns)
        except Exception:
            pass
    return ""


def _infer_py(dflt: ast.AST) -> str:
    """Tipo inferido del literal de un default Python."""
    if isinstance(dflt, ast.Constant):
        v = dflt.value
        return "any" if v is None else type(v).__name__
    if isinstance(dflt, (ast.List, ast.ListComp)):
        return "list"
    if isinstance(dflt, (ast.Dict, ast.DictComp)):
        return "dict"
    if isinstance(dflt, ast.Tuple):
        return "tuple"
    if isinstance(dflt, (ast.Set, ast.SetComp)):
        return "set"
    return "any"


def _fmt_one_py(name: str, ann: ast.AST | None,
                dflt: ast.AST | None) -> str:
    """'name: tipo = default' para un parámetro Python."""
    if ann is not None:
        t = ast.unparse(ann)
    elif dflt is not None:
        t = _infer_py(dflt)
    else:
        t = "any"
    s = f"{name}: {t}"
    if dflt is not None:
        try:
            s += " = " + ast.unparse(dflt)
        except Exception:
            pass
    return s


def _args_py(node: ast.AST) -> str:
    """Argumentos Python: 'a: int, b: str = x' — sin self/cls."""
    a = node.args
    pos = list(a.posonlyargs) + list(a.args)
    defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    out = []
    for i, (arg, dflt) in enumerate(zip(pos, defaults)):
        if i == 0 and arg.arg in ("self", "cls"):
            continue
        out.append(_fmt_one_py(arg.arg, arg.annotation, dflt))
    if a.vararg:
        out.append("*" + _fmt_one_py(a.vararg.arg, a.vararg.annotation, None))
    for arg, dflt in zip(a.kwonlyargs, a.kw_defaults):
        out.append(_fmt_one_py(arg.arg, arg.annotation, dflt))
    if a.kwarg:
        out.append("**" + _fmt_one_py(a.kwarg.arg, a.kwarg.annotation, None))
    return ", ".join(out)


def _split_params(s: str) -> list:
    """Divide 'a, b: List<X>, c' por comas fuera de <> [] () {}."""
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch in "<([{":
            depth += 1
        elif ch in ">)]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return parts


def _prev_comment(lines: list, i: int) -> str:
    """Comentario justo encima de la línea i (0-based): // o /* */.
    Salta líneas en blanco y anotaciones/decoradores (@...)."""
    j = i - 1
    while j >= 0 and (not lines[j].strip()
                      or lines[j].strip().startswith("@")):
        j -= 1
    if j < 0:
        return ""
    line = lines[j].strip()
    if line.startswith("//"):
        block = []
        while j >= 0 and lines[j].strip().startswith("//"):
            block.append(lines[j].strip()[2:].strip())
            j -= 1
        return " ".join(reversed(block))
    if line.endswith("*/"):
        k = j
        while k >= 0 and "/*" not in lines[k]:
            k -= 1
        if k < 0:
            return ""
        text = re.sub(r"/\*+|\*/", "", "\n".join(lines[k:j + 1]))
        desc = [l.strip().lstrip("*").strip() for l in text.splitlines()]
        return " ".join(l for l in desc if l and not l.startswith("@"))
    return ""


def _infer_js(d: str) -> str:
    """Tipo inferido del literal de un default JS."""
    if re.match(r"^['\"`]", d):
        return "str"
    if re.match(r"^\d+$", d):
        return "int"
    if re.match(r"^\d*\.\d+", d):
        return "float"
    if d in ("true", "false"):
        return "bool"
    if d.startswith("["):
        return "list"
    if d.startswith("{"):
        return "dict"
    return "any"


def _fmt_args_js(args: str) -> str:
    """'a, b = 5' -> 'a: any, b: int = 5'. Respeta anotaciones TS."""
    out = []
    for p in _split_params(args):
        p = p.strip()
        if not p:
            continue
        if ":" in p or p.startswith(("{", "[", "...")):
            out.append(p)  # ya tipado (TS) o destructuring/rest
        elif "=" in p:
            n, d = p.split("=", 1)
            n, d = n.strip(), d.strip()
            out.append(f"{n}: {_infer_js(d)} = {d}")
        else:
            out.append(f"{p}: any")
    return ", ".join(out)


def _ret_js(line: str) -> str:
    """'-> tipo' si hay anotación TS tras el cierre de paréntesis."""
    m = re.search(r"\)\s*:\s*([\w<>\[\]|&]+)", line)
    return " -> " + m.group(1) if m else ""


def _fmt_args_java(args: str) -> str:
    """'int width, final String s' -> 'width: int, s: String'."""
    out = []
    for p in _split_params(args):
        p = re.sub(r"^(?:@[\w.]+\s+)*", "", p.strip())
        p = re.sub(r"^final\s+", "", p)
        m = re.match(r"(.+?)\s+([A-Za-z_]\w*)$", p)
        out.append(f"{m.group(2)}: {m.group(1).strip()}" if m else p)
    return ", ".join(out)


JAVA_MODS = {
    "public", "private", "protected", "static", "final", "synchronized",
    "abstract", "native", "default", "strictfp", "transient",
}


def _scan_python(source: str) -> tuple:
    """Extrae funciones y clases de código Python usando ast.
    Items: (nombre, args, línea, desc, retorno); clases llevan su desc."""
    funcs, classes = [], []
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append((node.name, _args_py(node), node.lineno,
                          _doc(node), _ret(node)))
        elif isinstance(node, ast.ClassDef):
            methods = [
                (m.name, _args_py(m), m.lineno, _doc(m), _ret(m))
                for m in node.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            classes.append((node.name, node.lineno, methods, _doc(node)))
    return funcs, classes


def _scan_js(source: str) -> tuple:
    """Extrae funciones, clases y métodos de código JavaScript con regex.
    Los métodos se anidan dentro de su clase contando llaves.
    Items: (nombre, args, línea, desc, retorno); clases llevan su desc."""
    funcs, classes = [], []
    lines = source.splitlines()
    depth = 0
    stack = []  # (entrada_clase, profundidad de su cuerpo)
    for n, line in enumerate(lines, 1):
        while stack and depth < stack[-1][1]:
            stack.pop()
        m = JS_CLASS_RE.match(line)
        if m:
            entry = (m.group(1), n, [], _prev_comment(lines, n - 1))
            classes.append(entry)
            stack.append((entry, depth + 1))
        else:
            matched = False
            for pat in JS_PATTERNS:
                mm = pat.match(line)
                if mm and mm.group(1) not in KEYWORDS:
                    funcs.append((mm.group(1), _fmt_args_js(mm.group(2)), n,
                                  _prev_comment(lines, n - 1),
                                  _ret_js(line)))
                    matched = True
                    break
            if not matched:
                mm = JS_METHOD_RE.match(line)
                if mm and mm.group(1) not in KEYWORDS:
                    item = (mm.group(1), _fmt_args_js(mm.group(2)), n,
                            _prev_comment(lines, n - 1), _ret_js(line))
                    (stack[-1][0][2] if stack else funcs).append(item)
        depth += line.count("{") - line.count("}")
    return funcs, classes


def _scan_java(source: str) -> tuple:
    """Extrae clases y métodos de código Java con regex.
    Los métodos se anidan dentro de su clase contando llaves.
    Items: (nombre, args, línea, desc, retorno); clases llevan su desc."""
    funcs, classes = [], []
    lines = source.splitlines()
    depth = 0
    stack = []  # (entrada_clase, profundidad de su cuerpo)
    for n, line in enumerate(lines, 1):
        while stack and depth < stack[-1][1]:
            stack.pop()
        stripped = line.strip()
        if stripped.startswith(("//", "/*", "*")):
            depth += line.count("{") - line.count("}")
            continue
        m = JAVA_CLASS_RE.search(line)
        if m:
            entry = (m.group(1), n, [], _prev_comment(lines, n - 1))
            classes.append(entry)
            stack.append((entry, depth + 1))
        else:
            m = JAVA_METHOD_RE.match(line)
            ret = ""
            if m:
                parts = m.group(1).strip().split()
                # group(1) vacío = keyword tipo "if ("/"for ("; y si el
                # último token es una sentencia (return/throw/new) no es método
                if (not parts or parts[-1] in REJECT_PREFIX
                        or m.group(2) in KEYWORDS):
                    m = None
                elif parts[-1] not in JAVA_MODS:
                    ret = " -> " + parts[-1]  # último token = tipo retorno
            if m is None:
                m = JAVA_CTOR_RE.match(line)
                if m and m.group(1) in KEYWORDS:
                    m = None
            if m:
                desc = _prev_comment(lines, n - 1)
                if m.re is JAVA_METHOD_RE:
                    item = (m.group(2), _fmt_args_java(m.group(3)), n,
                            desc, ret)
                else:
                    item = (m.group(1), _fmt_args_java(m.group(2)), n,
                            desc, "")
                (stack[-1][0][2] if stack else funcs).append(item)
        depth += line.count("{") - line.count("}")
    return funcs, classes


def _build_summary(name: str, lang: str, funcs: list,
                   classes: list) -> str:
    """Construye el texto del resumen.
    Items: funcs/métodos = (nombre, args, línea, desc, retorno);
    clases = (nombre, línea, métodos, desc)."""
    lines = [f"{name} — Resumen del archivo.", "", f"Lenguaje: {lang}"]
    if classes:
        lines += ["", "Clases:"]
        for cname, lineno, cmethods, cdesc in classes:
            # El constructor va en la firma de la clase, no como método:
            # __init__ (Python), constructor (JS) o NombreClase (Java)
            ctor = next(
                (m for m in cmethods
                 if m[0] in ("__init__", "constructor") or m[0] == cname),
                None)
            sig = f"{cname}({ctor[1]})" if ctor else cname
            line = f"  - {sig}   [línea {lineno}]"
            if cdesc:
                line += f"  — {cdesc}"
            lines.append(line)
            for mname, margs, mlineno, mdesc, mret in cmethods:
                if ctor and mlineno == ctor[2]:
                    continue
                line = f"      - {mname}({margs}){mret}   [línea {mlineno}]"
                if mdesc:
                    line += f"  — {mdesc}"
                lines.append(line)
    if funcs:
        lines += ["", "Funciones:"]
        for fname, fargs, lineno, fdesc, fret in funcs:
            line = f"  - {fname}({fargs}){fret}   [línea {lineno}]"
            if fdesc:
                line += f"  — {fdesc}"
            lines.append(line)
    if not funcs and not classes:
        lines += ["", "(sin funciones ni clases detectadas)"]
    lines += ["", f"[{MARKER}]"]
    return "\n".join(lines)


def _wrap(summary: str, lang: str) -> str:
    """Envuelve el resumen en el comentario adecuado al lenguaje."""
    if lang == "Python":
        return '"""\n' + summary + '\n"""'
    body = "\n".join(" * " + l if l else " *" for l in summary.splitlines())
    return "/*\n" + body + "\n */"


def _strip_old(source: str, lang: str) -> str:
    """Quita resúmenes anteriores generados por esta skill (idempotente).
    Respeta shebang y línea de coding, y elimina bloques marcados
    consecutivos por si se duplicaron."""
    if lang == "Python":
        pat = (r'^((?:#![^\n]*\n|#[^\n]*coding[:=][^\n]*\n)*)\n*'
               r'(""".*?"""|\'\'\'.*?\'\'\')\n?')
    else:
        pat = r"^(#![^\n]*\n)?\n*(/\*.*?\*/)\n?"
    while True:
        m = re.match(pat, source, re.S)
        if not m or MARKER not in m.group(2):
            return source
        source = (m.group(1) or "") + source[m.end():]


def _insert(source: str, header: str, lang: str) -> str:
    """Inserta el comentario al inicio, respetando shebang y encoding."""
    lines = source.splitlines(keepends=True)
    i = 0
    if lines and lines[0].startswith("#!"):
        i = 1
    if lang == "Python" and i < len(lines) and re.match(r"#.*coding[:=]", lines[i]):
        i += 1
    return "".join(lines[:i]) + header + "\n\n" + "".join(lines[i:])


def analyze_file(path: str, write: bool = True) -> str:
    """Analiza el archivo, escribe el resumen al inicio y lo devuelve."""
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        source = f.read()
    ext = os.path.splitext(path)[1].lower()
    name = os.path.basename(path)
    if ext == ".py":
        lang = "Python"
        funcs, classes = _scan_python(source)
    elif ext in (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"):
        lang = "JavaScript" if ext in (".js", ".jsx", ".mjs", ".cjs") else "TypeScript"
        funcs, classes = _scan_js(source)
    elif ext == ".java":
        lang = "Java"
        funcs, classes = _scan_java(source)
    else:
        raise ValueError(f"extensión no soportada: {ext or '(sin extensión)'}")

    summary = _build_summary(name, lang, funcs, classes)
    if write:
        clean = _strip_old(source, lang)
        header = _wrap(summary, lang)
        with open(path, "w", encoding="utf-8") as f:
            f.write(_insert(clean, header, lang))
    return summary


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    no_write = "--no-write" in sys.argv
    if not args:
        print("Uso: analyze_file.py <archivo> [--no-write]")
        return 2
    path = _resolve(args[0])
    if path is None:
        print("ERROR: ruta fuera de la carpeta de trabajo")
        return 1
    if not os.path.isfile(path):
        print(f"ERROR: no existe '{args[0]}'")
        return 1
    try:
        summary = analyze_file(path, write=not no_write)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1
    except SyntaxError as e:
        print(f"ERROR: no se pudo parsear '{args[0]}': {e}")
        return 1
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
