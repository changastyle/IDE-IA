#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runner de tests para CHECK-MONITOR-RESOLUTION-UTILS.

Detecta los monitores conectados con el módulo
UTILS/SCREEN-RESOLUTION-UTILS/CHECK-MONITOR-RESOLUTION-UTILS.py,
valida la info que devuelve y guarda el reporte en
ALL-RESULTS-TEST-RESOLUTION/RESULTADO-monitores.txt

Uso: python TEST-RESOLUTION-SCREEN-MONITOR.py
Salida: un .txt con el reporte + resumen por consola. 0 = todo OK, 1 = fallos.
"""
import importlib.util
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # raíz NG-Studio
MODULE_PATH = os.path.join(
    ROOT, "UTILS", "SCREEN-RESOLUTION-UTILS",
    "CHECK-MONITOR-RESOLUTION-UTILS.py")

DST = os.path.join(HERE, "ALL-RESULTS-TEST-RESOLUTION")
OUT_TXT = os.path.join(DST, "RESULTADO-monitores.txt")

REQUIRED_KEYS = {"name", "primary", "width", "height",
                 "avail_width", "avail_height", "x", "y"}


def _load_module():
    """Carga el módulo por ruta (el nombre lleva guiones)."""
    spec = importlib.util.spec_from_file_location(
        "check_monitor_resolution", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    if not os.path.isfile(MODULE_PATH):
        print(f"ERROR: no existe {MODULE_PATH}")
        return 1
    os.makedirs(DST, exist_ok=True)

    mon = _load_module()
    report = []
    failures = []

    def check(cond, label, detail=""):
        tag = "PASS" if cond else "FAIL"
        line = f"[{tag}] {label}" + (f"  ({detail})" if detail else "")
        report.append(line)
        print(line)
        if not cond:
            failures.append(label)

    # ---- list_monitors() ----
    try:
        monitors = mon.list_monitors()
    except Exception as e:
        print(f"ERROR list_monitors(): {e}")
        return 1

    check(bool(monitors), "list_monitors() devuelve monitores",
          f"{len(monitors)} detectados")

    for i, m in enumerate(monitors):
        check(REQUIRED_KEYS <= set(m), f"monitor {i}: tiene todas las claves",
              f"faltan {REQUIRED_KEYS - set(m)}" if REQUIRED_KEYS - set(m) else "")
        check(m["width"] > 0 and m["height"] > 0,
              f"monitor {i}: resolución válida",
              f"{m['width']}x{m['height']}")
        check(0 < m["avail_width"] <= m["width"]
              and 0 < m["avail_height"] <= m["height"],
              f"monitor {i}: área disponible coherente",
              f"{m['avail_width']}x{m['avail_height']}")

    primaries = [m for m in monitors if m["primary"]]
    check(len(primaries) == 1, "exactamente un monitor primary",
          f"{len(primaries)} primaries")

    # ---- largest_screen() / check_monitor_resolution() ----
    biggest = mon.largest_screen()
    check(biggest is not None, "largest_screen() devuelve un QScreen")

    # (x, y) que la función devuelve al que la llame
    res = mon.check_monitor_resolution()

    if biggest is not None and monitors:
        expected = max(monitors,
                       key=lambda m: m["avail_width"] * m["avail_height"])
        geo = biggest.availableGeometry()
        check((geo.width(), geo.height())
              == (expected["avail_width"], expected["avail_height"]),
              "largest_screen() coincide con el de mayor área disponible",
              f"{geo.width()}x{geo.height()}")

        check(res == (expected["avail_width"], expected["avail_height"]),
              "check_monitor_resolution() devuelve (w, h) del más grande",
              f"{res}")

    # ---- fit_window_to_largest() ----
    try:
        from PySide6.QtWidgets import QWidget
        w = QWidget()
        mon.fit_window_to_largest(w)
        check(biggest is None or w.screen() is biggest,
              "fit_window_to_largest() mueve la ventana al monitor más grande",
              w.screen().name() if w.screen() else "sin screen")
        w.close()
    except Exception as e:
        check(False, "fit_window_to_largest() no lanza excepciones", str(e))

    # ---- reporte de monitores (igual que el modo standalone) ----
    report.append("")
    report.append("Monitores detectados:")
    for m in monitors:
        tag = " [primary]" if m["primary"] else ""
        report.append(
            f"  {m['name']}{tag}: {m['width']}x{m['height']} "
            f"(disponible {m['avail_width']}x{m['avail_height']} "
            f"en {m['x']},{m['y']})")

    resumen = (f"\n{len(report) - len(failures) - len(monitors) - 2} checks, "
               f"{len(failures)} fallos")
    report.append(resumen)
    print(resumen)

    # Return de la función al caller: dos coordenadas (x, y)
    final = (f"RESOLUCION FINAL SUGERIDA : {res[0]} X {res[1]}"
             if res else "RESOLUCION FINAL SUGERIDA : (sin pantallas)")
    report.append(final)
    print(final)

    with open(OUT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    print(f"Reporte -> {os.path.basename(OUT_TXT)}")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
