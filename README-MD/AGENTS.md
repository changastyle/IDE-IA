# Reglas del proyecto — cli-ia

## Testing (CRÍTICO)

- **NUNCA** ejecutar tests que escriban/editen/borren archivos del workspace real del usuario.
  El workspace por defecto es `sub-carpeta-for-test/` (o el que cargue la app al iniciar).
  Un test anterior sobreescribió `snake.js` real con datos de prueba y se perdió el archivo.
- Para cualquier test que use `Tools._save`, `_edit`, `_run_skill`, o `MainWindow` con operaciones
  de archivos, **siempre** redirigir `w.tools.root` a un `tempfile.mkdtemp()` antes:
  ```python
  import tempfile
  w.tools = chat_ia.Tools(tempfile.mkdtemp())
  ```
- Los tests offscreen de Qt deben esperar que terminen los threads de discovery antes de
  destruir el widget, sino crashean con `QThread: Destroyed while thread is still running`.

## Encoding

- Los servers OpenAI-compatibles (LM Studio, OpenCode) responden en UTF-8 sin declarar charset.
  `requests` asume ISO-8859-1 por default → mojibake. Siempre forzar `r.encoding = "utf-8"`
  antes de `iter_lines(decode_unicode=True)` o `r.json()`.
- `web_check.py` y `_run_skill` deben forzar `PYTHONIOENCODING=utf-8` y `encoding="utf-8"`.

## Arquitectura

- App monolítica en `chat_ia.py` (~2200 líneas). No separar en módulos salvo razón fuerte.
- Skills van en `Skills-py/*.py` con docstring descriptivo (aparecen solas en el diálogo).
- Iconos SVG en `iconos/`, mapeados por extensión en `EXT_ICONS`.
- Conversaciones en `conversaciones/*.json`, con `token_log` embebido y `-usage.md` adjunto.
