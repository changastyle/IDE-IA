# CORE â€” NG-Studio Logic

Arquitectura: core mÃ­nimo + servicios aislados en segundo plano.

> **Estado: implementado (v1).** Ver "Implementado" al final.

## Problema

Hoy todo corre en el hilo principal de Qt. Si un panel se cuelga
(file watcher en carpeta enorme, `git status` lento, request de red
del chat), se congela o crashea **toda la app**. No hay forma de
relanzar un panel sin reiniciar.

## RestricciÃ³n clave

**Qt exige que todos los widgets vivan en el hilo principal.** Un
`QWidget` no puede correr en otro thread ni en otro proceso. Lo que
se saca del core no es el panel â€” es **el trabajo** que el panel hace:

- **Core (hilo principal)**: ventana + widgets "tontos" que solo
  renderizan datos que les llegan por seÃ±ales.
- **Servicios (threads/procesos)**: todo lo pesado corre afuera y le
  empuja datos al panel.

## Estructura

### `UTILS/CORE-SERVICES/` â€” bootstrap mÃ­nimo

- `QApplication`, `UIMainWindow` (solo el shell: zonas, splitter,
  status bar), `_excepthook`, `_fit_to_largest_screen`, y el
  `ServiceManager`.
- **Nada de lÃ³gica de paneles acÃ¡.** Objetivo: el core compila y
  arranca aunque todo lo demÃ¡s estÃ© roto (~200 lÃ­neas).

### `ServiceManager` â€” el "init system" de la app

- Cada servicio se registra con nombre.
- Controla ciclo de vida: `start()`, `stop()`, `restart()`, heartbeat.
- Alimenta el **monitor de tareas interno**: panel que lista servicios
  con estado (running / hung / restarting) y botÃ³n de reinicio por
  servicio â€” estilo `chrome://task-manager`.

### Servicios en `QThread`

Cada cosa pesada â†’ worker `QObject` movido a su propio `QThread`,
comunicÃ¡ndose con el panel por seÃ±ales (queued connections =
thread-safe por diseÃ±o):

- **`GitService`** â€” todos los `is_repo`, `status`, `branch`, `pull`,
  `push` pasan por una cola de requests. Hoy `set_folder()` ejecuta
  subprocesses git en el hilo UI â†’ es lo que traba el arranque.
- **`FileWatchService`** â€” absorbe `GitListener` + los
  `QFileSystemWatcher` de los `FilesPanel`. El walk del Ã¡rbol y los
  `addPaths` van al thread; el panel solo recibe "cambiÃ³ X".
- **`ChatService`** â€” requests de red del chat (demoras de red/FS)
  aisladas con timeout y cancelaciÃ³n.
- **`SysInfoService`** â€” el `ps -axo` del `BottomBar` (en Windows
  falla silencioso â†’ 0 MB) â†’ `psutil` en un thread con poll propio.

### Arranque progresivo

- El core muestra la ventana **inmediatamente**.
- Los servicios levantan escalonados (boot queue con
  `QTimer.singleShot` encadenados o prioridades).
- Cada panel arranca en estado "cargandoâ€¦" hasta que su servicio
  publica datos.
- Si un servicio no levanta â†’ su panel muestra error + botÃ³n
  reintentar. El resto de la app ni se entera.

## Relanzar un panel sin crashear la app

- **Watchdog por heartbeat**: cada servicio emite `alive` cada N
  segundos. Si el manager no recibe heartbeat â†’ marca hung â†’ pide
  cancelaciÃ³n cooperativa (flag `_stop` que el worker chequea en su
  loop) â†’ si no responde, `QThread.quit()` + `wait(timeout)` â†’
  respawn limpio.
- **`QThread.terminate()` NO**: mata el thread a mitad de operaciÃ³n y
  puede dejar locks corruptos.
- **Aislamiento duro**: para un servicio que se pueda matar sin
  piedad â†’ `QProcess` (script Python separado hablando JSON por
  stdin/stdout). Reservado para lo que demuestre colgarse en serio
  (probablemente el file watcher en carpetas enormes).
- **Paneles desacoplados**: el panel nunca llama al servicio directo â€”
  publica un request y espera seÃ±al. Si el servicio estÃ¡ muerto, el
  request queda en cola y el panel muestra "reconectandoâ€¦" en vez de
  congelarse.

## Orden de ataque

1. **Paso 1** â€” extraer `UTILS/CORE-SERVICES/` y el `ServiceManager` con la interfaz
   de servicio. Sin mover nada todavÃ­a.
2. **Paso 2** â€” convertir `GitListener` + calls git de
   `set_folder`/`set_root` en `GitService` (mayor trabador actual).
3. **Paso 3** â€” `FileWatchService` para los watchers de `FilesPanel`.
4. **Paso 4** â€” monitor de tareas (panel de servicios con restart
   manual).
5. **Paso 5** â€” watchdog + auto-restart; promover a `QProcess` lo que
   siga colgÃ¡ndose.

## Lo que NO cambia

- Los widgets se quedan en el main thread â€” meterlos en procesos
  separados es pelearse con Qt y gana muy poco.
- `_update_diffs` ya es async â€” ese patrÃ³n es el que hay que
  generalizar, no reinventar.

## Implementado (v1)

### `UTILS/CORE-SERVICES/` â€” paquete nuevo

- **`UTILS/CORE-SERVICES/APP-LOG-UTILS.py`** â€” `AppLog`: log central (ring buffer de 5000
  lÃ­neas + seÃ±al `line(str)`). `log(msg, source)` es el atajo global;
  cualquier thread puede loguear (la seÃ±al llega encolada a la UI).
- **`UTILS/CORE-SERVICES/SERVICE-MANAGER-UTILS.py`** â€” `Service` + `ServiceManager`:
  - `Service` envuelve un worker `QObject` en su propio `QThread`.
    Estados: `stopped â†’ starting â†’ running â†’ hung â†’ stopping` / `error`.
  - **Heartbeat**: `QTimer.singleShot(0, worker, cb)` agenda un
    callback en el event loop del worker cada `PING_MS` (2s). Si el
    thread estÃ¡ sano â†’ `beat`. Si estÃ¡ colgado â†’ el callback no corre
    y el watchdog lo marca `hung` tras `HUNG_MS` (8s).
  - `start()` / `stop()` (cooperativo: `quit()` + `wait(3s)`, nunca
    `terminate()`) / `restart()`.
  - `ServiceManager.start_all()` = **boot queue**: arranca los
    servicios escalonados (200ms entre cada uno) emitiendo
    `boot_progress(name, done, total)` â†’ visible en el monitor.
- **`UTILS/CORE-SERVICES/SERVICES-UTILS.py`** â€” servicios concretos:
  - `GitWatchService` ("git-watch"): `GitListener` en su thread.
    `set_repo()` va por seÃ±al (el `QFileSystemWatcher` lo exige) y
    `subscribe(cb)` conecta a la seÃ±al `changed` â†’ los callbacks
    corren en la UI aunque el listener viva en otro thread.
  - `SysInfoService` ("sys-info"): poll de RAM cada 3s en su thread
    (psutil si estÃ¡, si no `ps -axo`). Emite `ram_mb` â†’ `BottomBar`.

### UI

- **`UI/panels/monitor_panel.py`** â€” `MonitorPanel`: tabla de
  servicios (nombre, estado con color, edad del Ãºltimo beat) +
  botones â–¶ start / â–  stop / â†» restart por fila. Arriba, barra de
  progreso de la boot queue. Panel "Servicios" en la zona izquierda,
  botÃ³n **â–¦** en la hotbar.
- **`UI/panels/log_overlay.py`** â€” `LogOverlay`: overlay flotante
  idÃ©ntico a `TerminalOverlay` pero mostrando el `AppLog` (eventos de
  servicios, boot, excepciones del excepthook). BotÃ³n **â‰£** en la
  hotbar, botÃ³n âŒ« para limpiar.

### Cableado en `main_window.py`

- `MainBody`: `git_listener` â†’ `git_service` (GitWatchService);
  `log_overlay` + `toggle_log()`; `sysinfo_service`.
- `BottomBar`: el timer de `ps -axo` se reemplazÃ³ por el slot
  `set_ram()` alimentado por `sys-info`.
- `UIMainWindow`: crea el `ServiceManager`, registra los servicios,
  agrega el `MonitorPanel`, conecta `aboutToQuit â†’ stop_all()` y
  dispara `start_all()` al final del init.
- `_excepthook` ahora tambiÃ©n loguea a `AppLog` (visible en el
  overlay â‰£).

### Shim de imports (`UTILS/__init__.py`)

Las subcarpetas de `UTILS` usan guiones (`GIT-UTILS/`, `MD-UTILS/`â€¦)
que no son paquetes Python vÃ¡lidos. El `__init__.py` carga cada
archivo con `importlib` y lo registra en `sys.modules` bajo el nombre
histÃ³rico (`UTILS.git`, `UTILS.git_utils`, `UTILS.listeners`,
`UTILS.markdown_utils.*`, `UTILS.ia`, `UTILS.shortcuts`,
`UTILS.stuff_dir`, `UTILS.screen_resolution`) â€” los call-sites no
cambiaron. `GIT-COMMANDS-UTILS.py` (funciones `is_repo`, `pull`â€¦) se
restaurÃ³ desde git HEAD.

### Pendiente (prÃ³ximos pasos)

- `FileWatchService`: watchers de `FilesPanel` a un thread.
- `ChatService`: requests de red del chat con timeout/cancelaciÃ³n.
- Auto-restart configurable por servicio (hoy el hung se reporta y se
  relanza a mano desde el monitor).
- Promover a `QProcess` lo que siga colgÃ¡ndose (aislamiento duro).

