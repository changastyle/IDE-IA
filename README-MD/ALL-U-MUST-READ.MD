# ALL-U-MUST-READ — índice troncal de NG-Studio

**Acá va todo lo troncal e importante que hay que leer de verdad.**
Este es el índice: si sos una tool, una IA o alguien nuevo en el
proyecto, empezá por acá. Cada entrada dice qué es, dónde está y por
qué importa — sintetizado, sin vueltas.

---

## 1. El proyecto

- **`README.md`** (raíz) — Qué es NG-Studio: IDE local con IA en
  Python + Qt. Proveedores locales (LM Studio, OpenCode Go), tools de
  archivos, streaming, voz, terminal, diff editor. Instalación y uso.
  **Leer primero** para entender qué se está construyendo.

## 2. Reglas del juego (leer SIEMPRE antes de tocar código)

- **`README-MD/AGENTS.md`** — Reglas críticas del proyecto:
  - NUNCA testear sobre archivos reales del workspace (usar
    `tempfile.mkdtemp()`).
  - Forzar UTF-8 en requests/responses (mojibake si no).
  - Arquitectura monolítica en `chat_ia.py`, skills en
    `SKILLS-NG-STUDIO/`, conversaciones en `conversaciones/`.

- **`README-MD/MANUAL-CREAR-TOOLS-NOMECLATURA.MD`** — Cómo escribir
  código para que `analyze_file.py` lo entienda perfecto: type
  annotations obligatorias, docstring de una línea por función/clase,
  `_` = privado, exit codes (0/1/2). **Obligatorio antes de crear
  cualquier tool o skill.**

## 3. Arquitectura

- **`README-MD/CORE-NG-STUDIO-LOGIC.MD`** — Diseño del CORE: widgets
  "tontos" en el hilo principal + servicios pesados en `QThread`
  (GitService, FileWatchService, ChatService, SysInfoService) con
  `ServiceManager` como init system, heartbeat y watchdog. Explica por
  qué la app se congela hoy y cómo se arregla.

- **`CORE/`** — Implementación del bootstrap: `service_manager.py`
  (ciclo de vida de servicios), `services.py`, `app_log.py`.

## 4. La IA y sus tools

- **`chat_ia.py`** — App principal (~3700 líneas): `Tools` (la IA
  lista/lee/crea/edita archivos), `Worker` (streaming + requests),
  `MainWindow`, diálogos, voz, tokens, conversaciones.
- **`SKILLS-NG-STUDIO/`** — Skills ejecutables por la IA:
  `analyze_file.py` (resumen tipado de archivos .py/.js/.java),
  `move_file.py`, `web_check.py`. Siguen el manual de nomenclatura.
- **`UI/panels/`** — Paneles de la UI: `chat_panel.py`,
  `changes_panel.py`, `planner_panel.py`, `monitor_panel.py`, etc.

## 5. Diseño de UI

- **`README-MD/panelchanges.md`** — Diseño del panel Changes (botón
  "2" de la hotbar): input de mensaje, lista de cambios con checkboxes
  parciales, historial con pills de rama coloreadas. Con dibujos SVG.
- **`NG-STUDIO-STUFF/prototype/`** — Mockups SVG de la UI.

## 6. Estado y pendientes

- **`README-MD/PENDIENTES.md`** — Qué está verificado y qué falta
  probar en la app real (prompt end-to-end, OpenCode real, voz real).
  Notas de arquitectura del Worker y FileDiffCard.

## 7. Testing

- **`TESTS/TEST-SKILL-ANALYSE/`** — `TEST-ANALYSE-SKILL.py` corre
  `analyze_file` sobre `ALL-FILES-TO-TEST-ANALYSE/` y deja resultados
  en `ALL-RESULTS-TEST-ANALYSE/`. Patrón replicable para testear
  cualquier skill: `TESTS/TEST-<NOMBRE>/` con su runner.

---

## Regla de oro

> Antes de crear o modificar código: **AGENTS.md** (reglas) +
> **MANUAL-CREAR-TOOLS-NOMECLATURA.MD** (cómo escribirlo). Antes de
> tocar arquitectura: **CORE-NG-STUDIO-LOGIC.MD**.
