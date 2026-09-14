# Manual: nomenclatura para crear tools/skills

Reglas para que `analyze_file.py` (y la IA) entienda cualquier archivo
sin adivinar nada. Si el código sigue esto, el resumen sale 100%
tipado y documentado.

## 1. Cabecera del archivo

Todo archivo empieza con un docstring/comentario que diga **qué es**,
**cómo se usa** y **qué devuelve**:

```python
"""Skill: nombre — qué hace en una línea.

Uso: python3 nombre.py <args>
Salida: qué imprime/devuelve. 0 = OK, 1 = error.
"""
```

## 2. Type annotations OBLIGATORIAS en funciones públicas

```python
def save_file(path: str, content: str) -> bool:
def load_config(root: str, depth: int = 2) -> dict:
```

- Sin anotación la skill muestra `any` — eso es admitir "no sé qué recibo".
- El default también documenta: `key: str = ''`, `flag: bool = False`.
- Anotar el retorno: `-> bool`, `-> str`, `-> None`.

## 3. Docstring de UNA línea por función/clase

La **primera línea** del docstring es la descripción que sale en el
resumen. Que responda "qué hace" en criollo:

```python
def load_image(path: str) -> QPixmap:
    """Carga la imagen y la escala a máx. 1920x1080."""
```

```java
/** Visor de imágenes: SVG, PNG, JPG. */
public class ImageViewer { ... }
```

```javascript
// Carga la imagen y la escala a máx. 1920x1080
function loadImage(path) { ... }
```

En JS/Java la descripción es el comentario `//` o `/* */` justo encima
(la skill salta líneas en blanco y `@anotaciones`).

## 4. Nomenclatura

- **`snake_case`** para funciones y variables (Python). `camelCase` en JS/Java.
- **`_prefijo`** = privado/interno: no se llama desde fuera. La skill lo
  muestra igual pero el `_` ya avisa.
- **`PascalCase`** para clases.
- **`UPPER_CASE`** para constantes.
- **Nombres de parámetros que se entiendan**: `path`, `content`,
  `timeout` — no `x`, `a`, `rel` si se puede evitar.

## 5. Constructores

El constructor no aparece como método: se pliega en la firma de la
clase. `__init__` (Python), `constructor` (JS) y `NombreClase` (Java)
deben llevar sus parámetros tipados igual que cualquier función.

## 6. Qué sale en el resumen

```
  - ImageViewerDialog(parent: QWidget, path: str, rel: str)   [línea 1029]  — Visor de imágenes.
      - load_image(ext: str) -> QPixmap   [línea 1080]  — Carga y escala la imagen.
```

`Clase(params_ctor) [línea] — descripción` / `metodo(param: tipo) -> ret [línea] — descripción`

## Checklist antes de dar por terminada una tool

- [ ] Cabecera con qué es + uso + salida
- [ ] Todas las funciones públicas con `param: tipo` y `-> retorno`
- [ ] Docstring/comentario de una línea en cada función y clase
- [ ] `main()` devuelve exit code: 0 OK, 1 error, 2 uso incorrecto
- [ ] `sys.stdout.reconfigure(encoding="utf-8")` si imprime texto con acentos
