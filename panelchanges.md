# Panel Changes — diseño validado con dibujos

Este documento explica, con dibujos, cómo va a ser el nuevo **panel de Changes**
(el botón "2" de la hotbar izquierda, que pasa a tener el ícono de commit:
círculo con palito) y el nuevo **panel de Diff** que se abre al clickear un archivo.

---

## 1. Panel de Changes (botón "2" de la hotbar)

Es un solo panel con **tres zonas**, de arriba a abajo:

1. **Input de mensaje** (estilo VS Code): campo de texto con 3 botones a la derecha.
2. **Lista de cambios** (estilo IntelliJ): grupos *Changes* y *Unversioned Files*,
   con checkboxes por archivo. Un archivo puede entrarse **entero** (☑),
   **parcial** (⊟ rayita, solo algunas líneas) o **no entrar** (☐).
3. **Historial**: los commits de la rama actual, con la pill de la rama pintada
   con su color único (el mismo color de `colores-branches.txt`, el grafo y el
   cartelito de arriba).

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="720" height="660" viewBox="0 0 720 660" font-family="-apple-system, Helvetica, sans-serif">
  <!-- fondo del panel -->
  <rect x="0" y="0" width="720" height="660" rx="10" fill="#1e1f22" stroke="#3a3d45"/>

  <!-- ===== header del panel ===== -->
  <path d="M 0 10 A 10 10 0 0 1 10 0 L 710 0 A 10 10 0 0 1 720 10 L 720 36 L 0 36 Z" fill="#2b2d31"/>
  <text x="16" y="24" fill="#d7dae0" font-size="14" font-weight="bold">▾ Changes</text>
  <text x="664" y="24" fill="#8e8e93" font-size="14">↻</text>
  <text x="694" y="24" fill="#8e8e93" font-size="14">—</text>

  <!-- ===== zona 1: input de mensaje + 3 botones ===== -->
  <rect x="16" y="48" width="512" height="34" rx="8" fill="#26282e" stroke="#3a3d45"/>
  <text x="30" y="70" fill="#6b7078" font-size="13">Message (⌘Ent…)</text>

  <rect x="540" y="48" width="34" height="34" rx="8" fill="#26282e" stroke="#3a3d45"/>
  <text x="552" y="71" fill="#a78bfa" font-size="15">✨</text>

  <rect x="580" y="48" width="34" height="34" rx="8" fill="#3574f0"/>
  <text x="593" y="70" fill="#ffffff" font-size="14" font-weight="bold">✓</text>

  <rect x="620" y="48" width="34" height="34" rx="8" fill="#26282e" stroke="#3a3d45"/>
  <text x="634" y="70" fill="#22c55e" font-size="14" font-weight="bold">↑</text>

  <text x="540" y="98" fill="#6b7078" font-size="10">generate</text>
  <text x="584" y="98" fill="#6b7078" font-size="10">commit</text>
  <text x="624" y="98" fill="#6b7078" font-size="10">push</text>

  <!-- ===== zona 2: lista de cambios ===== -->
  <!-- grupo Changes -->
  <text x="16" y="132" fill="#8e8e93" font-size="12">▾</text>
  <rect x="36" y="120" width="15" height="15" rx="3" fill="#3574f0"/>
  <text x="39" y="132" fill="#fff" font-size="12" font-weight="bold">✓</text>
  <text x="60" y="132" fill="#d7dae0" font-size="13" font-weight="bold">Changes</text>
  <text x="672" y="132" fill="#8e8e93" font-size="12">1 file</text>

  <!-- archivo con RAYITA = parcial -->
  <rect x="52" y="144" width="15" height="15" rx="3" fill="#1e1f22" stroke="#3574f0"/>
  <line x1="55" y1="151.5" x2="64" y2="151.5" stroke="#3574f0" stroke-width="2"/>
  <text x="76" y="156" fill="#8e8e93" font-size="12">≡</text>
  <text x="94" y="156" fill="#d7dae0" font-size="13">archivo.txt</text>
  <text x="180" y="156" fill="#6b7078" font-size="11" font-style="italic">1 of 2 changes ← parcial</text>

  <!-- grupo Unversioned Files -->
  <text x="16" y="192" fill="#8e8e93" font-size="12">▾</text>
  <rect x="36" y="180" width="15" height="15" rx="3" fill="#1e1f22" stroke="#555a63"/>
  <text x="60" y="192" fill="#d7dae0" font-size="13" font-weight="bold">Unversioned Files</text>
  <text x="660" y="192" fill="#8e8e93" font-size="12">5 files</text>

  <rect x="52" y="204" width="15" height="15" rx="3" fill="#1e1f22" stroke="#555a63"/>
  <text x="76" y="216" fill="#e05561" font-size="13">⊘  .gitignore</text>
  <text x="660" y="216" fill="#8e8e93" font-size="11">.idea</text>

  <rect x="52" y="228" width="15" height="15" rx="3" fill="#1e1f22" stroke="#555a63"/>
  <text x="76" y="240" fill="#e05561" font-size="13">📄  cpu-ps2-rust.iml</text>
  <text x="648" y="240" fill="#8e8e93" font-size="11">.idea</text>

  <rect x="52" y="252" width="15" height="15" rx="3" fill="#1e1f22" stroke="#555a63"/>
  <text x="76" y="264" fill="#e05561" font-size="13">&lt;&gt;  index.html</text>

  <!-- amend -->
  <rect x="16" y="288" width="15" height="15" rx="3" fill="#1e1f22" stroke="#555a63"/>
  <text x="40" y="300" fill="#d7dae0" font-size="13">Amend</text>
  <text x="648" y="300" fill="#22c55e" font-size="12">+12 −3</text>

  <!-- ===== zona 3: historial de la rama ===== -->
  <line x1="0" y1="322" x2="720" y2="322" stroke="#3a3d45"/>
  <text x="16" y="350" fill="#8e8e93" font-size="12">▾</text>
  <text x="36" y="350" fill="#d7dae0" font-size="13" font-weight="bold">Historial</text>
  <!-- pill de la rama con su color único -->
  <rect x="110" y="334" width="58" height="22" rx="11" fill="#3574f0"/>
  <text x="126" y="349" fill="#fff" font-size="12" font-weight="bold">main</text>
  <text x="180" y="350" fill="#6b7078" font-size="11">solo los commits de esta rama</text>

  <!-- commits -->
  <circle cx="24" cy="376" r="5" fill="#3574f0"/>
  <text x="40" y="380" fill="#8e8e93" font-size="11" font-family="Menlo, monospace">2ad97763</text>
  <text x="116" y="380" fill="#d7dae0" font-size="12">gitignore + limpieza</text>
  <text x="480" y="380" fill="#8e8e93" font-size="11">Nicolas G.</text>
  <text x="668" y="380" fill="#8e8e93" font-size="11">13/09</text>

  <circle cx="24" cy="402" r="5" fill="#3574f0"/>
  <text x="40" y="406" fill="#8e8e93" font-size="11" font-family="Menlo, monospace">a1b2c3d</text>
  <text x="116" y="406" fill="#d7dae0" font-size="12">terminal working fine</text>
  <text x="480" y="406" fill="#8e8e93" font-size="11">Nicolas G.</text>
  <text x="668" y="406" fill="#8e8e93" font-size="11">12/09</text>

  <circle cx="24" cy="428" r="5" fill="#3574f0"/>
  <text x="40" y="432" fill="#8e8e93" font-size="11" font-family="Menlo, monospace">e4f5a6b</text>
  <text x="116" y="432" fill="#d7dae0" font-size="12">por trabajar en la terminal</text>
  <text x="480" y="432" fill="#8e8e93" font-size="11">Nicolas G.</text>
  <text x="668" y="432" fill="#8e8e93" font-size="11">12/09</text>

  <!-- leyenda de estados -->
  <line x1="16" y1="456" x2="704" y2="456" stroke="#3a3d45"/>
  <text x="16" y="482" fill="#8e8e93" font-size="12">Estados del checkbox de un archivo:</text>

  <rect x="16" y="496" width="15" height="15" rx="3" fill="#3574f0"/>
  <text x="19" y="508" fill="#fff" font-size="12" font-weight="bold">✓</text>
  <text x="40" y="508" fill="#d7dae0" font-size="12">el archivo entra entero al commit</text>

  <rect x="16" y="522" width="15" height="15" rx="3" fill="#1e1f22" stroke="#3574f0"/>
  <line x1="19" y1="529.5" x2="28" y2="529.5" stroke="#3574f0" stroke-width="2"/>
  <text x="40" y="534" fill="#d7dae0" font-size="12">entra PARCIAL: solo las líneas tildadas en el diff</text>

  <rect x="16" y="548" width="15" height="15" rx="3" fill="#1e1f22" stroke="#555a63"/>
  <text x="40" y="560" fill="#d7dae0" font-size="12">no entra nada</text>

  <!-- leyenda de botones -->
  <line x1="16" y1="584" x2="704" y2="584" stroke="#3a3d45"/>
  <text x="16" y="610" fill="#a78bfa" font-size="13">✨</text>
  <text x="40" y="610" fill="#d7dae0" font-size="12">Generate → la IA escribe el mensaje mirando el diff de lo tildado</text>
  <text x="16" y="634" fill="#8e8e93" font-size="12">✓ Commit → commitea lo tildado      ↑ Push → commitea (si falta) y hace git push</text>
</svg>
```

---

## 2. Panel de Diff (se abre al clickear un archivo de la lista)

- **Se parte a la mitad**: izquierda = el archivo en el último commit (HEAD),
  derecha = tu versión actual (working tree).
- Cada mitad muestra el **nombre del archivo** en su encabezado.
- **Gutter de blame en la izquierda** (como el annotate de IntelliJ): cada línea
  muestra la **fecha** en que fue escrita y el **autor** (quién la escribió).
  Las líneas más nuevas se destacan con fondo azul, como en la foto de referencia.
- En el subtítulo de la izquierda también se ve la **última fecha de modificación
  del archivo en la rama**.
- Los **checkboxes de línea** están solo en las líneas cambiadas, del lado derecho.
  Tildás las líneas que querés subir.
- No es el editor de código: es otro panel que ocupa el mismo lugar del centro.

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="920" height="520" viewBox="0 0 920 520" font-family="-apple-system, Helvetica, sans-serif">
  <!-- fondo -->
  <rect x="0" y="0" width="920" height="520" rx="10" fill="#1e1f22" stroke="#3a3d45"/>

  <!-- header -->
  <path d="M 0 10 A 10 10 0 0 1 10 0 L 910 0 A 10 10 0 0 1 920 10 L 920 40 L 0 40 Z" fill="#2b2d31"/>
  <text x="16" y="26" fill="#d7dae0" font-size="13" font-weight="bold">≡  archivo.txt</text>
  <text x="380" y="26" fill="#7aa2f7" font-size="13" font-weight="bold">⇄  Commit: archivo.txt</text>
  <text x="890" y="26" fill="#8e8e93" font-size="14">✕</text>

  <!-- subtítulos de cada mitad -->
  <text x="16" y="64" fill="#8e8e93" font-size="11" font-family="Menlo, monospace">🔒 2ad97763 · último commit · modificado 04/03/2026</text>
  <text x="476" y="64" fill="#8e8e93" font-size="11">✏  tu versión (sin commitear)</text>

  <!-- divisor central -->
  <line x1="460" y1="76" x2="460" y2="460" stroke="#3a3d45" stroke-width="2"/>

  <!-- ===== MITAD IZQUIERDA: HEAD (último commit) + BLAME ===== -->
  <!-- gutter de blame: fecha + autor de cada línea -->
  <rect x="0" y="76" width="150" height="384" fill="#23252b"/>
  <g font-family="Menlo, monospace" font-size="11">
    <text x="10" y="96"  fill="#6b7078">15/01/2026</text>
    <text x="92" y="96"  fill="#6b7078">Grossi</text>
    <text x="10" y="120" fill="#6b7078">15/01/2026</text>
    <text x="92" y="120" fill="#6b7078">Grossi</text>
    <!-- línea más nueva: destacada en azul -->
    <rect x="0" y="128" width="150" height="22" fill="#2c4a77"/>
    <text x="10" y="144" fill="#cfe0f5">04/03/2026</text>
    <text x="92" y="144" fill="#cfe0f5">Grossi</text>
  </g>
  <g font-family="Menlo, monospace" font-size="13">
    <text x="160" y="96" fill="#6b7078">1</text>
    <text x="192" y="96" fill="#c8ccd4">linea 1</text>

    <text x="160" y="120" fill="#6b7078">2</text>
    <text x="192" y="120" fill="#c8ccd4">linea 2</text>

    <text x="160" y="144" fill="#6b7078">3</text>
    <text x="192" y="144" fill="#c8ccd4">linea 3</text>
  </g>

  <!-- ===== MITAD DERECHA: tu versión, con checkboxes ===== -->
  <g font-family="Menlo, monospace" font-size="13">
    <text x="476" y="96" fill="#6b7078">1</text>
    <text x="508" y="96" fill="#c8ccd4">linea 1</text>

    <!-- línea modificada y TILDADA ☑ -->
    <rect x="462" y="104" width="456" height="22" fill="#1d3327"/>
    <rect x="472" y="108" width="14" height="14" rx="3" fill="#3574f0"/>
    <text x="475" y="119" fill="#fff" font-size="10" font-weight="bold">✓</text>
    <text x="494" y="120" fill="#6b7078">2</text>
    <text x="526" y="120" fill="#7ce495">linea-1.5</text>

    <!-- línea NUEVA y DESTILDADA ☐ -->
    <rect x="462" y="128" width="456" height="22" fill="#1d3327"/>
    <rect x="472" y="132" width="14" height="14" rx="3" fill="#1e1f22" stroke="#555a63"/>
    <text x="494" y="144" fill="#6b7078">3</text>
    <text x="526" y="144" fill="#7ce495">linea 2-bis</text>

    <text x="476" y="168" fill="#6b7078">4</text>
    <text x="508" y="168" fill="#c8ccd4">linea 3</text>
  </g>

  <!-- flecha: lo tildado pasa a la izquierda al commitear -->
  <text x="380" y="120" fill="#3574f0" font-size="16">⇐</text>
  <text x="300" y="140" fill="#6b7078" font-size="10">lo tildado se commitea</text>

  <!-- barra inferior del diff -->
  <line x1="0" y1="470" x2="920" y2="470" stroke="#3a3d45"/>
  <text x="16" y="496" fill="#8e8e93" font-size="12">2 differences, 1 included</text>
  <rect x="700" y="478" width="200" height="26" rx="6" fill="#3574f0"/>
  <text x="726" y="496" fill="#fff" font-size="12" font-weight="bold">✓ Commit selección</text>
</svg>
```

---

## 3. Cómo se conectan entre sí

```
 hotbar "2"                PANEL CHANGES                     PANEL DIFF
┌───────┐          ┌──────────────────────────┐      ┌─────────────────────────┐
│  ⊙─   │  abre →  │ [Message]    ✨  ✓  ↑    │      │ archivo.txt │ Commit:…  │
└───────┘          │ ☑ Changes      1 file    │      │  HEAD      │ tu versión│
   ícono           │ ⊟ archivo.txt  (parcial) │ ───→ │  linea 1    │ ☑ linea-1.5│
   commit          │ ☐ Unversioned  5 files   │click │  linea 2    │ ☐ linea 2-bis│
                   │ ───────── Historial ──── │      │  (rojo)     │  (verde)   │
                   │ ● main · 2ad97763 …      │      │ [✓ Commit selección]    │
                   └──────────────────────────┘      └─────────────────────────┘
```

- Clickeás el **nombre** de un archivo → se abre el panel de Diff (el centro
  deja de mostrar el editor y muestra el diff; con ✕ vuelve el editor).
- Tildás líneas en la mitad derecha → el archivo pasa a ⊟ (parcial) en la lista.
- `✓` del input → commitea todo lo tildado (archivos enteros + líneas tildadas).
- `↑` del input → commitea y hace push.
- `✨` del input → genera el mensaje con IA.
- El historial de abajo muestra **solo los commits de la rama actual**, con la
  pill del nombre en el color único de la rama, con autor y fecha.
- En el diff, la mitad izquierda tiene **gutter de blame**: fecha + autor línea
  a línea (quién escribió cada línea y cuándo), con las líneas más nuevas
  destacadas en azul. El subtítulo muestra la última fecha de modificación
  del archivo en la rama.
- La barra de abajo del diff ("2 differences, 1 included") permite commitear
  directo desde el diff, sin volver a la lista.

---

## 4. Popup al cambiar de rama con cambios sin commitear

Hoy: si estás en `feature/perro-gato` con cambios y te pasás a `dev`, git
rechaza el checkout y abajo aparece el cartel de error feo.

Nuevo: aparece un **popup** que te ofrece guardar todo en el stash antes
de cambiar de rama.

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="460" height="270" viewBox="0 0 460 270" font-family="-apple-system, Helvetica, sans-serif">
  <rect x="0" y="0" width="460" height="270" rx="12" fill="#26282e" stroke="#3a3d45"/>

  <text x="20" y="34" fill="#eab308" font-size="15" font-weight="bold">⚠  Cambios sin commitear</text>

  <text x="20" y="62" fill="#c8ccd4" font-size="12">Estos archivos se pueden pisar al pasarte a</text>
  <text x="20" y="80" fill="#7aa2f7" font-size="12" font-weight="bold">dev</text>

  <rect x="20" y="92" width="420" height="58" rx="8" fill="#1e1f22" stroke="#3a3d45"/>
  <text x="34" y="112" fill="#d7dae0" font-size="12">•  UI/main_window.py</text>
  <text x="34" y="132" fill="#d7dae0" font-size="12">•  UI/panels/git_panel.py</text>

  <text x="20" y="172" fill="#c8ccd4" font-size="12">¿Querés guardarlos en el stash (tu bolsillo)?</text>

  <rect x="20" y="192" width="210" height="30" rx="7" fill="#22c55e"/>
  <text x="36" y="212" fill="#fff" font-size="12" font-weight="bold">📥 Stash y cambiar de rama</text>

  <rect x="240" y="192" width="90" height="30" rx="7" fill="#3574f0"/>
  <text x="258" y="212" fill="#fff" font-size="12" font-weight="bold">Commit…</text>

  <rect x="340" y="192" width="100" height="30" rx="7" fill="#2b2e34"/>
  <text x="368" y="212" fill="#d7dae0" font-size="12">Cancelar</text>
</svg>
```

- **📥 Stash y cambiar de rama** → `git stash` (todo) + checkout a la rama
  elegida. Los cambios quedan a salvo en el panel de Stash.
- **Commit…** → cierra el popup y abre el panel de Changes para commitear.
- **Cancelar** → no cambia de rama.

---

## 5. Panel 3 — Stash (el bolsillo)

El botón "3" de la hotbar abre el panel de Stash: todo lo que tenés guardado
sin commitear, esperando ser recuperado.

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="720" height="520" viewBox="0 0 720 520" font-family="-apple-system, Helvetica, sans-serif">
  <rect x="0" y="0" width="720" height="520" rx="10" fill="#1e1f22" stroke="#3a3d45"/>

  <!-- header -->
  <path d="M 0 10 A 10 10 0 0 1 10 0 L 710 0 A 10 10 0 0 1 720 10 L 720 36 L 0 36 Z" fill="#2b2d31"/>
  <text x="16" y="24" fill="#d7dae0" font-size="14" font-weight="bold">▾ Stash — el bolsillo</text>
  <text x="664" y="24" fill="#8e8e93" font-size="14">↻</text>
  <text x="694" y="24" fill="#8e8e93" font-size="14">—</text>

  <!-- botón guardar todo -->
  <rect x="16" y="48" width="220" height="30" rx="7" fill="#22c55e"/>
  <text x="32" y="68" fill="#fff" font-size="12" font-weight="bold">📥 Guardar todo en el stash</text>
  <text x="248" y="68" fill="#6b7078" font-size="11">guarda TODOS tus cambios sin commitear</text>

  <!-- stash@{0} expandido -->
  <text x="16" y="112" fill="#8e8e93" font-size="12">▾</text>
  <text x="36" y="112" fill="#d7dae0" font-size="13" font-weight="bold">stash@{0}</text>
  <text x="110" y="112" fill="#8e8e93" font-size="11" font-style="italic">WIP on main: 2ad97763 gitignore + limpieza</text>
  <text x="668" y="112" fill="#8e8e93" font-size="11">13/09 10:42</text>

  <rect x="52" y="124" width="15" height="15" rx="3" fill="#3574f0"/>
  <text x="39" y="136" fill="#fff" font-size="12" font-weight="bold">✓</text>
  <text x="76" y="136" fill="#d7dae0" font-size="12">UI/main_window.py</text>
  <text x="640" y="136" fill="#e8c97a" font-size="10" fill-opacity="0.9">UI/panels</text>

  <rect x="52" y="148" width="15" height="15" rx="3" fill="#3574f0"/>
  <text x="39" y="160" fill="#fff" font-size="12" font-weight="bold">✓</text>
  <text x="76" y="160" fill="#d7dae0" font-size="12">UI/panels/git_panel.py</text>

  <!-- stash@{1} colapsado -->
  <text x="16" y="196" fill="#8e8e93" font-size="12">▸</text>
  <text x="36" y="196" fill="#d7dae0" font-size="13" font-weight="bold">stash@{1}</text>
  <text x="110" y="196" fill="#8e8e93" font-size="11" font-style="italic">WIP on dev: a1b2c3d terminal working fine</text>
  <text x="668" y="196" fill="#8e8e93" font-size="11">12/09 18:03</text>

  <!-- botones de abajo -->
  <line x1="0" y1="452" x2="720" y2="452" stroke="#3a3d45"/>
  <rect x="16" y="466" width="230" height="30" rx="7" fill="#3574f0"/>
  <text x="32" y="486" fill="#fff" font-size="12" font-weight="bold">⤴ Recuperar lo tildado (pop)</text>

  <rect x="256" y="466" width="120" height="30" rx="7" fill="#2b2e34"/>
  <text x="276" y="486" fill="#e05561" font-size="12" font-weight="bold">🗑 Descartar</text>

  <text x="400" y="486" fill="#6b7078" font-size="11">lo tildado vuelve a tus archivos; el stash vacío se borra solo</text>
</svg>
```

Cómo funciona:

- **📥 Guardar todo en el stash** → `git stash push -u` (incluye archivos sin
  trackear). Tus archivos vuelven al estado limpio del último commit.
- Cada entrada `stash@{N}` muestra el mensaje (rama + commit de origen) y la
  fecha. Se expande y muestra **los archivos que tiene adentro**, cada uno con
  su checkbox.
- **⤴ Recuperar lo tildado (pop)** → vuelve a tus archivos **solo los archivos
  tildados** de ese stash (`git checkout stash@{N} -- <archivos>`). Si
  recuperaste todo el stash, se borra solo (como `git stash pop`); si
  recuperaste parte, el resto queda en el bolsillo.
- **🗑 Descartar** → borra la entrada del stash (`git stash drop`), con
  confirmación.
- El stash es **global del repo**: ves entradas creadas en cualquier rama.
