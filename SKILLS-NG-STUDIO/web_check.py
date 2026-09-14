#!/usr/bin/env python3
"""Skill: web_check — abre una web o archivo local en un navegador headless,
captura console logs, errores de JavaScript y recursos fallidos, y verifica
que todo cargue sin errores.

Uso: python3 web_check.py <url|archivo> [segundos_de_espera]
Salida: informe de texto. Código de salida 0 = sin errores, 1 = con errores.
"""
import os
import sys

# Forzar salida UTF-8 para que los acentos no se rompan al capturar el informe
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: web_check.py <url|archivo> [segundos]")
        return 2
    target = sys.argv[1]
    wait = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    if os.path.exists(target):
        target = "file://" + os.path.realpath(target)

    from playwright.sync_api import sync_playwright

    logs, errors, failed = [], [], []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("requestfailed", lambda r: failed.append(f"{r.url} → {r.failure}"))
        try:
            page.goto(target, wait_until="load", timeout=30000)
        except Exception as e:
            print(f"ERROR: no se pudo abrir {target}: {e}")
            return 1
        page.wait_for_timeout(int(wait * 1000))
        title = page.title()
        try:
            text = page.inner_text("body")[:800]
        except Exception:
            text = "(sin contenido de texto)"
        browser.close()

    lines = [f"=== web_check: {target} ===", f"Título: {title or '(sin título)'}"]
    if errors:
        lines.append(f"\nERRORES DE JAVASCRIPT ({len(errors)}):")
        lines += [f"  - {e}" for e in errors[:10]]
    if failed:
        lines.append(f"\nRECURSOS FALLIDOS ({len(failed)}):")
        lines += [f"  - {u}" for u in failed[:10]]
    if logs:
        lines.append(f"\nCONSOLA ({len(logs)} mensajes):")
        lines += [f"  {m}" for m in logs[:20]]
    if not errors and not failed:
        lines.append("\nSin errores de JavaScript ni recursos fallidos ✔")
    lines.append("\nCONTENIDO VISIBLE (primeros 800 caracteres):")
    lines.append(text)
    ok = not errors and not failed
    lines.append(f"\nRESULTADO: {'OK — todo cargó sin errores' if ok else 'CON ERRORES — hay que corregirlos'}")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
