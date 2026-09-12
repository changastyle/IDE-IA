# 📋 Propuestas de mejora — Snake Game

Ideas de cambios y mejoras que se le podrían hacer al proyecto, ordenadas por prioridad.

---

## 🐛 Correcciones / limpieza

1. **Unificar `index.html` y `snake.html`**: son páginas casi idénticas. Mantener solo `index.html` (o redirigir `snake.html` a la principal) para evitar duplicar cambios en dos archivos.
2. **Limpiar `_trash/`**: los archivos `editor.html` y `editor.js` viejos ya no se usan; se pueden eliminar definitivamente.
3. **Rutas absolutas vs relativas**: el editor usa rutas absolutas (`/js/editor.js`, `/index.html`), lo que obliga a usar `server.js`. Unificar todo a rutas relativas permitiría abrir el juego con doble clic, sin servidor.
4. **`test.js` y `pulga.txt`**: revisar si siguen siendo necesarios o son restos de pruebas.

## ✨ Mejoras de gameplay

5. **Pausa**: tecla `P` o `Espacio` para pausar/reanudar, con overlay "Pausado".
6. **Comida dorada con temporizador**: que la comida dorada aparezca cada X comidas y desaparezca tras unos segundos (ahora solo hay probabilidad fija).
7. **Niveles de velocidad visibles**: mostrar un aviso breve "¡Nivel 2!" al subir de velocidad.
8. **Obstáculos aleatorios en modo clásico**: opción de activar algunos muros aleatorios para más dificultad.
9. **Selector de nivel en el juego**: en vez de ir al editor para elegir nivel, un menú inicial con "Clásico" y los niveles guardados.
10. **Exportar/importar niveles**: botón en el editor para descargar el nivel como JSON y compartirlo (evita depender solo de `localStorage`).

## 🎨 Mejoras visuales / UX

11. **D-pad en móvil**: botones de dirección en pantalla para móviles (el swipe actual es básico y a veces falla).
12. **Animaciones**: pequeño efecto al comer (partículas o flash), transición suave del overlay.
13. **Modo oscuro/claro** o temas de color seleccionables.
14. **Favicon e iconos**: el proyecto no tiene favicon; añadir uno simple (serpiente 🐍).

## 🔊 Audio

15. **Botón de mute**: toggle para silenciar, persistido en `localStorage`.
16. **Sonido de movimiento** opcional (tick sutil) y música de fondo generada.

## 🏗️ Código / arquitectura

17. **Separar la lógica en módulos**: `snake.js` crece; dividir en `game.js`, `render.js`, `input.js`, `levels.js` (o usar ES modules).
18. **Guardar partida**: opción de reanudar la partida si se recarga la página.
19. **Tests**: `test.js` existe pero conviene tener tests reales de la lógica (colisiones, crecimiento, colocación de comida) ejecutables con Node.
20. **README.md**: documentar cómo jugar, cómo usar el editor y cómo arrancar el servidor.

---

## 🚀 Segunda tanda de ideas

21. **Multijugador local**: dos serpientes en el mismo tablero (WASD vs flechas), gana la última en pie.
22. **Tabla de puntuaciones**: top 10 de récords con nombre del jugador (además del récord simple actual).
23. **Logros**: insignias por hitos (comer 10 doradas, llegar a nivel 5, 50 puntos sin morir…).
24. **Power-ups**: además de la comida dorada, ítems temporales (cámara lenta, atravesar muros, imán de comida).
25. **Editor: herramientas avanzadas** — relleno de rectángulos, deshacer/rehacer, limpiar todo, y vista previa jugable del nivel sin salir del editor.
26. **Editor: tamaño de tablero configurable** (no solo 20×20) y guardado de varios borradores.
27. **Modo espejo / laberintos predefinidos**: incluir 3–5 niveles de ejemplo creados por el editor, listos para jugar.
28. **PWA**: manifest + service worker para instalar el juego en el móvil y jugar offline.
29. **Compartir récord**: botón para copiar/compartir tu puntuación (Web Share API).
30. **Accesibilidad**: soporte de teclado alternativo, `aria-labels` en el HUD y opción de alto contraste.
31. **Replay**: guardar los movimientos de la partida y reproducirla al terminar.
32. **Estadísticas**: partidas jugadas, comida total, tiempo jugado — visibles en un panel.
33. **Efecto de serpiente más pulido**: ojos en la cabeza, cola que se afina, y degradado de color por segmento.
34. **Configuración de controles**: permitir remapear teclas y elegir sensibilidad del swipe.
35. **CI/CD simple**: GitHub Actions que valide sintaxis de los JS y despliegue a GitHub Pages.

## 🧪 Tercera tanda de ideas

36. **Modos de juego alternativos**: sin muros pero con velocidad creciente extrema, "serpiente infinita" (los bordes conectan los lados opuestos), o modo zen sin Game Over.
37. **Wrap-around configurable**: opción de activar/desactivar que la serpiente atraviese los bordes.
38. **Semilla aleatoria compartible**: partidas con comida en posiciones fijas por semilla, para competir en igualdad de condiciones.
39. **IA demo**: una serpiente que juega sola en pantalla de inicio (attract mode, como los arcades).
40. **Editor: importar imagen como plantilla** para trazar muros encima (pixel-art → nivel).
41. **Niveles con mecánicas nuevas**: puertas/teletransportes, comida que se mueve, muros que aparecen/desaparecen con timer.
42. **Guardado en archivo del progreso**: exportar todos los niveles y récords a un JSON de respaldo (los `localStorage` se pierden al limpiar el navegador).
43. **Internacionalización (i18n)**: textos en español e inglés con selector de idioma.
44. **Modo pantalla completa**: botón para usar `requestFullscreen` en el canvas.
45. **Linting y formateo**: ESLint + Prettier con config compartida para mantener el código consistente.
46. **Refactor del editor**: extraer la lógica de cuadrícula compartida entre juego y editor en un módulo común (evita duplicar constantes como `gridSize`).
47. **Manejo de errores global**: `window.onerror` que muestre un mensaje amigable en vez de fallar en silencio.
48. **Optimización de dibujo**: pre-renderizar la cuadrícula en un canvas offscreen en vez de redibujarla cada frame.
49. **Soporte de gamepad**: API Gamepad para jugar con mando.
50. **Página "acerca de"**: créditos, versión del juego y changelog visible desde el footer.

### 🎯 Prioridad sugerida

| Prioridad | Cambios |
|-----------|---------|
| Alta | 1, 3, 5, 11 |
| Media | 6, 9, 10, 15, 17, 20 |
| Baja | 2, 4, 7, 8, 12, 13, 14, 16, 18, 19 |
