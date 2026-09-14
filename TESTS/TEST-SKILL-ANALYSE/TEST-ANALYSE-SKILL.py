#!/usr/bin/env python3
"""Runner de tests para la skill analyze_file.

Analiza todos los archivos soportados (.py, .js, .java, .ts...) que haya
en ALL-FILES-TO-TEST-ANALYSE/ (recursivo) y guarda cada resumen en
ALL-RESULTS-TEST-ANALYSE/RESULTADO-<nombre>.txt

Uso: python run_tests.py
Salida: un .txt por archivo + resumen por consola. 0 = todo OK, 1 = fallos.
"""
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # raíz NG-Studio
sys.path.insert(0, os.path.join(ROOT, "SKILLS-NG-STUDIO"))

from analyze_file import analyze_file  # noqa: E402

SRC = os.path.join(HERE, "ALL-FILES-TO-TEST-ANALYSE")
DST = os.path.join(HERE, "ALL-RESULTS-TEST-ANALYSE")
SUPPORTED = {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".java"}


def main():
    if not os.path.isdir(SRC):
        print(f"ERROR: no existe {SRC}")
        return 1
    os.makedirs(DST, exist_ok=True)

    files = []
    for dirpath, _, filenames in os.walk(SRC):
        for f in sorted(filenames):
            if os.path.splitext(f)[1].lower() in SUPPORTED:
                files.append(os.path.join(dirpath, f))
    if not files:
        print(f"No hay archivos soportados en {SRC}")
        return 1

    ok = 0
    for path in files:
        rel = os.path.relpath(path, SRC)
        out_name = "RESULTADO-" + rel.replace(os.sep, "__")
        out_name = os.path.splitext(out_name)[0] + ".txt"
        out = os.path.join(DST, out_name)
        try:
            summary = analyze_file(path, write=True)
        except Exception as e:
            print(f"ERROR {rel}: {e}")
            continue
        with open(out, "w", encoding="utf-8") as f:
            f.write(summary + "\n")
        print(f"OK {rel} -> {out_name}")
        print(summary)
        print("-" * 60)
        ok += 1

    print(f"\n{ok}/{len(files)} archivos analizados")
    return 0 if ok == len(files) else 1


if __name__ == "__main__":
    sys.exit(main())
