# 💡 Idea 1 — Unificar `index.html` y `snake.html`

## 🎯 Objetivo

Eliminar la duplicación de páginas. Hoy `index.html` y `snake.html` son casi idénticas (mismo DOM, mismos scripts, mismos IDs); la única diferencia real es el `<title>` y un `<style>` inline en `snake.html` que fuerza el fondo plano. Mantener dos archivos obliga a aplicar cada cambio (nuevos IDs, scripts, enlaces) **dos veces**, con riesgo de que se desincronicen.

## 📊 Estado actual

| Aspecto | `index.html` | `snake.html` |
|---------|--------------|--------------|
| `<title>` | "Snake Game" | "Snake Game (versión simple)" |
| `<style>` inline | — | `body { background: #1a1a2e; }` |
| Footer | instrucciones + enlace al editor | solo enlace al editor |
| Scripts/CSS | `styles.css`, `audio/sound.js`, `snake.js` | idénticos |
| IDs del DOM | idénticos | idénticos |

`snake.js` depende del contrato de IDs (`#gameCanvas`, `#score`, `#level`, `#best`, `#overlay`, `#overlayTitle`, `#overlayMsg`, `#restartBtn`), que ambas páginas cumplen — por eso funcionan intercambiables.

## 🛠️ Plan de unificación

### Paso 1 — Decidir la página canónica

**`index.html`** queda como única página (es la que enlazan el editor y la documentación implícita).

### Paso 2 — Absorber lo único útil de `snake.html`

Nada que absorber: el fondo plano de `snake.html` es una preferencia menor. Si se quiere conservar, se puede lograr con una clase CSS en `styles.css`:


/* variante de fondo plano, por si se quiere alternar */
body.flat-bg { background: #1a1a2e; }


### Paso 3 — Redirigir `snake.html`

Reemplazar su contenido por una redirección inmediata (mejor UX que un 404 para quien tenga el enlace guardado):


<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="0; url=index.html">
  <title>Snake Game — redirigiendo…</title>
</head>
<body>
  <p>Esta página se movió. <a href="index.html">Ir al juego</a></p>
</body>
</html>


> Alternativa más agresiva: borrar `snake.html` directamente. La redirección es más amable si hay marcadores antiguos.

### Paso 4 — Actualizar referencias

- Buscar enlaces a `snake.html` en el proyecto (editor, `server.js`, README si existiera) y apuntarlos a `index.html`.
- `server.js`: si sirve `snake.html` explícitamente, quitar esa ruta o dejarla redirigiendo.

### Paso 5 — Verificación

1. Abrir `index.html` y confirmar que el juego arranca, el HUD muestra los 3 campos y el editor enlaza bien.
2. Abrir `snake.html` y confirmar la redirección.
3. Probar Game Over → Reiniciar, y un nivel personalizado del editor.

## ✅ Resultado esperado

- **1 sola página** que mantener → menos bugs de desincronización.
- Récords y niveles intactos (mismo origen `localStorage`).
- Diferencia de fondo disponible como clase CSS opcional, sin duplicar archivos.

## ⚠️ Riesgos

- Alguien con `snake.html` guardado en favoritos: mitigado con la redirección.
- Si en el futuro se quiere una variante real (p. ej. tema distinto), mejor hacerlo con **query params** (`index.html?theme=flat`) o clases CSS, no duplicando HTML.
