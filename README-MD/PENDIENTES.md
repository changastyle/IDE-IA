# Pendientes — cli-ia

## Estado: resuelto el bug del "Pensando" eterno

`UI/panels/chat_panel.py` quedó completo y compilando. El bug era que `on_done` →
`set_final_stats` llamaba `self.stats_section` (que ya no existía tras el refactor a
`stats_frame`) → `AttributeError` dentro del slot Qt → `finish_status()` nunca corría
→ el timer "Pensando… Ns" seguía contando aunque la request hubiera terminado.

## ✅ Verificado offscreen (2026-09-12)

- Compila: `python -m py_compile UI/panels/chat_panel.py` → OK
- Aparición progresiva: `busy_bar`/`resp_section` visibles al crear; `files_section`,
  `summary_section`, `stats_frame` ocultos (isHidden=True)
- Timer de status: `_tick_status` actualiza "⏳ Pensando… Ns"
- `ToolChip`: chips con icono+verbo+path (`▶ 📝 Write server.js`), clic expande resultado
- `add_file_diff` + `add_file_changed` → `files_section` aparece con `FileDiffCard` expandida
- `_on_stream_end(ok=True)` → stream copiado a resumen + `resp_section` se colapsa sola
- `set_final_stats` → `stats_frame` visible con stats coloreados
- `finish_status` → timer parado, busy oculta, "✓ Completado en Ns"
- `file_diff` emitido ANTES de `file_changed` en el Worker (la card ya tiene el diff)
- OpenCode: `x-opencode-session` llega al server (verificado con mock HTTP local)
- Voz: MP3 32kbps genera con ffmpeg, faster-whisper `base` carga en 0.7s (cache) y transcribe

## ⬜ Pendiente — solo verificación en la app real

- [ ] Prompt real end-to-end en la app corriendo (todo lo de arriba fue offscreen)
- [ ] OpenCode Go real (mock confirmó el header; falta provider real con API key)
- [ ] Voz end-to-end con voz humana real (el test usó un tono; transcripción devolvió "")

## Notas de arquitectura

- `Worker._diff_lines(before, after)` usa `difflib.unified_diff` acotado a 300 líneas
- `FileDiffCard.MAX_LINES = 60` líneas mostradas, `MAX_LINE_LEN = 300` chars
- Orden de señales del Worker por archivo: `files_changed` → `file_diff` → `file_changed` → `msg`
- `add_tool` usa `files_touched[path].before == 0` para distinguir Create vs Write
- `add_stats` acumula líneas en `_stats_lines`; `set_final_stats` las anexa al row coloreado
