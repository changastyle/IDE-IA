# NG-STUDIO - Historial de versiones

Registro auto-generado por `generate-ng-studio.exe.bat` en cada compilacion.
Cada build vuelca el `git log` y un resumen de los cambios del proyecto.

---

## Build 10  -  2026-09-13  [windows]

- **Versión:**   10.0.0
- **Build:**     10
- **Plataforma:** windows (.exe)
- **Fecha:**     2026-09-13
- **Commit:**    19911d9
- **Mensaje:**   terminal working fine

### Resumen de cambios (git log --oneline -30)

```
19911d9 terminal working fine
18042bc por trabajar en la terminal
5b2f7c5 vamos a trabajar en la UI en el panel de la IA
f9ca232 ya esta funcionando la IA .. ahora a correguir cositas
a792a4c README-UPDATED
1942749 running-configs-working-voy-a-romper-panel-ia
f268220 por romper running configs
4b530d3 version-de-la-new-ui-bastante-bonita
be4b8ca Add README and workspace test files
a093ef9 First commit - checkpoint for restyle UI
```

### Changelog detallado (git log -30 --stat)

```
19911d9|2026-09-13|Nicolas Grossi|terminal working fine
 UI/__pycache__/main_window.cpython-314.pyc | Bin 117188 -> 126447 bytes
 UI/main_window.py                          | 191 +++++++++++++++++++++++++----
 prototype/image.png                        | Bin 0 -> 184865 bytes
 requirements.txt                           |   1 +
 4 files changed, 168 insertions(+), 24 deletions(-)

18042bc|2026-09-13|Nicolas Grossi|por trabajar en la terminal
 UI/__pycache__/main_window.cpython-314.pyc        |  Bin 95134 -> 117188 bytes
 UI/main_window.py                                 |  423 +++++++--
 UI/panels/__pycache__/chat_panel.cpython-314.pyc  |  Bin 137126 -> 175367 bytes
 UI/panels/__pycache__/files_panel.cpython-314.pyc |  Bin 30885 -> 29203 bytes
 UI/panels/chat_panel.py                           | 1044 ++++++++++++++++-----
 UI/panels/files_panel.py                          |  122 +--
 conversaciones/conv_20260912_100334.json          |    2 +-
 iconos/cerebro.svg                                |    8 +
 iconos/engranaje.svg                              |    4 +
 iconos/git_branch.svg                             |    8 +
 iconos/nube.svg                                   |    3 +
 iconos/terminal_w.svg                             |    5 +
 iconos/usuario.svg                                |    5 +
 last-conversation.txt                             |    2 +-
 sub-carpeta-for-test/ns-code/conversacion.json    |  100 +-
 sub-carpeta-for-test/ns-code/resumen.txt          |   65 ++
 16 files changed, 1380 insertions(+), 411 deletions(-)

5b2f7c5|2026-09-12|Nicolas Grossi|vamos a trabajar en la UI en el panel de la IA
 PENDIENTES.md                                      |   37 +
 Skills-py/move_file.py                             |   67 ++
 UI/__pycache__/main_window.cpython-314.pyc         |  Bin 83152 -> 95134 bytes
 UI/main_window.py                                  |  211 +++-
 UI/panels/__pycache__/chat_panel.cpython-314.pyc   |  Bin 70448 -> 137126 bytes
 UI/panels/__pycache__/editor_panel.cpython-314.pyc |  Bin 38090 -> 66312 bytes
 UI/panels/__pycache__/files_panel.cpython-314.pyc  |  Bin 30852 -> 30885 bytes
 .../__pycache__/run_configs_dialog.cpython-314.pyc |  Bin 0 -> 46005 bytes
 UI/panels/chat_panel.py                            | 1149 +++++++++++++++++++-
 UI/panels/editor_panel.py                          |  482 +++++++-
 UI/panels/files_panel.py                           |    7 +-
 UI/panels/run_configs_dialog.py                    |  736 +++++++++++++
 Voice/rec.mp3                                      |  Bin 46017 -> 25713 bytes
 __pycache__/chat_ia.cpython-314.pyc                |  Bin 263086 -> 263422 bytes
 iconos/compound.svg                                |    6 +
 iconos/java.svg                                    |    7 +
 iconos/node.svg                                    |    4 +
 iconos/npm.svg                                     |    4 +
 iconos/python.svg                                  |    5 +-
 iconos/quarkus.svg                                 |    5 +
 iconos/springboot.svg                              |    4 +
 iconos/terminal.svg                                |    5 +
 prototype/recent-projects-prototype.svg            |  150 +++
 sub-carpeta-for-test/.idea/workspace.xml           |    9 +-
 sub-carpeta-for-test/.run_configs.json             |   44 +-
 sub-carpeta-for-test/_trash/editor.html            |   33 +
 sub-carpeta-for-test/_trash/editor.js              |  149 +++
 sub-carpeta-for-test/changes.md                    |   86 ++
 sub-carpeta-for-test/contexto.txt                  |   13 -
 sub-carpeta-for-test/html/editor-de-mapas.html     |   33 +
 sub-carpeta-for-test/idea1.md                      |   74 ++
 sub-carpeta-for-test/ideas/idea2.txt               |   65 ++
 sub-carpeta-for-test/index.html                    |    2 +-
 sub-carpeta-for-test/js/editor.js                  |  149 +++
 sub-carpeta-for-test/ns-code/contexto.txt          |   29 +
 sub-carpeta-for-test/ns-code/conversacion.json     |  106 ++
 sub-carpeta-for-test/{ => ns-code}/indexado.txt    |    0
 sub-carpeta-for-test/ns-code/resumen.txt           |   38 +
 sub-carpeta-for-test/pulga.txt                     |   10 +
 sub-carpeta-for-test/server.js                     |    3 +
 sub-carpeta-for-test/snake.html                    |    2 +
 sub-carpeta-for-test/snake.js                      |   41 +-
 sub-carpeta-for-test/styles.css                    |  116 ++
 sub-carpeta-for-test/test-muy-largo.txt            |    0
 sub-carpeta-for-test/test-muy-muy-largo.txt        |    0
 sub-carpeta-for-test/test_new.txt                  |    3 -
 utils/__pycache__/run_configs.cpython-314.pyc      |  Bin 3177 -> 8591 bytes
 utils/run_configs.py                               |  124 ++-
 48 files changed, 3874 insertions(+), 134 deletions(-)

f9ca232|2026-09-12|Nicolas Grossi|ya esta funcionando la IA .. ahora a correguir cositas
 UI/__pycache__/main_window.cpython-314.pyc        |  Bin 79624 -> 83152 bytes
 UI/main_window.py                                 |   84 +-
 UI/panels/__pycache__/chat_panel.cpython-314.pyc  |  Bin 0 -> 70448 bytes
 UI/panels/__pycache__/files_panel.cpython-314.pyc |  Bin 21980 -> 30852 bytes
 UI/panels/chat_panel.py                           | 1070 +++++++++++++++++++++
 UI/panels/files_panel.py                          |  141 ++-
 Voice/rec.mp3                                     |  Bin 0 -> 46017 bytes
 Voice/rec.wav                                     |  Bin 247886 -> 73806 bytes
 iconos/ia.svg                                     |   22 +
 sub-carpeta-for-test/.idea/workspace.xml          |   17 +-
 sub-carpeta-for-test/.run_configs.json            |    4 +
 sub-carpeta-for-test/audio/sound.js               |   82 ++
 sub-carpeta-for-test/contexto.txt                 |   12 +
 sub-carpeta-for-test/index.html                   |    1 +
 sub-carpeta-for-test/server.js                    |   60 ++
 sub-carpeta-for-test/snake.html                   |    2 +
 sub-carpeta-for-test/snake.js                     |    4 +
 utils/__pycache__/ia.cpython-314.pyc              |  Bin 0 -> 67555 bytes
 utils/ia.py                                       | 1004 +++++++++++++++++++
 19 files changed, 2480 insertions(+), 23 deletions(-)

a792a4c|2026-09-12|Nicolas Grossi|README-UPDATED
 README.md         |   2 ++
 README/NEW-UI.png | Bin 0 -> 482583 bytes
 2 files changed, 2 insertions(+)

1942749|2026-09-12|Nicolas Grossi|running-configs-working-voy-a-romper-panel-ia
 UI/__pycache__/main_window.cpython-314.pyc         | Bin 76138 -> 79624 bytes
 UI/main_window.py                                  |  79 ++++++++++++++++++---
 UI/panels/__pycache__/editor_panel.cpython-314.pyc | Bin 38090 -> 38090 bytes
 UI/panels/__pycache__/files_panel.cpython-314.pyc  | Bin 20412 -> 21980 bytes
 UI/panels/editor_panel.py                          |   6 +-
 UI/panels/files_panel.py                           |  30 +++++++-
 iconos/play_bookmark.svg                           |   8 +++
 sub-carpeta-for-test/.idea/workspace.xml           |   6 +-
 sub-carpeta-for-test/.run_configs.json             |  12 ++++
 utils/__pycache__/run_configs.cpython-314.pyc      | Bin 0 -> 3177 bytes
 utils/run_configs.py                               |  65 +++++++++++++++++
 11 files changed, 191 insertions(+), 15 deletions(-)

f268220|2026-09-12|Nicolas Grossi|por romper running configs
 UI/__pycache__/main_window.cpython-314.pyc         | Bin 76210 -> 76138 bytes
 UI/main_window.py                                  |   1 -
 UI/panels/__pycache__/editor_panel.cpython-314.pyc | Bin 32358 -> 38090 bytes
 .../__pycache__/settings_panel.cpython-314.pyc     | Bin 7702 -> 8481 bytes
 UI/panels/editor_panel.py                          | 137 +++++++++++++++++++--
 UI/panels/settings_panel.py                        |  23 +++-
 sub-carpeta-for-test/.idea/workspace.xml           |  11 +-
 sub-carpeta-for-test/test.js                       |   4 +
 utils/__pycache__/shortcuts.cpython-314.pyc        | Bin 3269 -> 3409 bytes
 utils/shortcuts.py                                 |   2 +
 10 files changed, 156 insertions(+), 22 deletions(-)

4b530d3|2026-09-12|Nicolas Grossi|version-de-la-new-ui-bastante-bonita
 UI/__init__.py                                     |    2 +
 UI/__pycache__/__init__.cpython-314.pyc            |  Bin 0 -> 202 bytes
 UI/__pycache__/main_window.cpython-314.pyc         |  Bin 0 -> 76210 bytes
 UI/main_window.py                                  | 1147 ++++++++++++++++++++
 UI/panels/__init__.py                              |    2 +
 UI/panels/__pycache__/__init__.cpython-314.pyc     |  Bin 0 -> 233 bytes
 UI/panels/__pycache__/editor_panel.cpython-314.pyc |  Bin 0 -> 32358 bytes
 UI/panels/__pycache__/files_panel.cpython-314.pyc  |  Bin 0 -> 20412 bytes
 .../__pycache__/settings_panel.cpython-314.pyc     |  Bin 0 -> 7702 bytes
 UI/panels/editor_panel.py                          |  490 +++++++++
 UI/panels/files_panel.py                           |  276 +++++
 UI/panels/settings_panel.py                        |  113 ++
 Voice/rec.wav                                      |  Bin 693326 -> 247886 bytes
 __pycache__/UI.cpython-314.pyc                     |  Bin 0 -> 49772 bytes
 __pycache__/chat_ia.cpython-314.pyc                |  Bin 240690 -> 263086 bytes
 chat_ia.py                                         |  353 +++++-
 conversaciones/conv_20260912_091533.json           |    2 +-
 conversaciones/conv_20260912_100334-usage.md       |   23 +
 conversaciones/conv_20260912_100334.json           |   55 +
 conversaciones/conv_20260912_110027-usage.md       |   17 +
 conversaciones/conv_20260912_110027.json           |   28 +
 conversaciones/conv_20260912_112813.json           |    7 +
 conversaciones/conv_20260912_112820.json           |    7 +
 iconos/app.svg                                     |   44 +
 iconos/app_128.png                                 |  Bin 0 -> 5932 bytes
 iconos/app_16.png                                  |  Bin 0 -> 556 bytes
 iconos/app_256.png                                 |  Bin 0 -> 12610 bytes
 iconos/app_32.png                                  |  Bin 0 -> 1225 bytes
 iconos/app_512.png                                 |  Bin 0 -> 28465 bytes
 iconos/app_64.png                                  |  Bin 0 -> 2726 bytes
 iconos/close.svg                                   |    5 +
 last-conversation.txt                              |   36 +-
 open_recents.txt                                   |    2 +
 open_sessions.json                                 |    6 +
 sub-carpeta-for-test/.idea/vcs.xml                 |    7 +
 sub-carpeta-for-test/.idea/workspace.xml           |  107 ++
 sub-carpeta-for-test/test-muy-largo.txt            |    0
 sub-carpeta-for-test/test-muy-muy-largo.txt        |    0
 ui_app.py                                          |    8 +
 utils/__init__.py                                  |    1 +
 utils/__pycache__/__init__.cpython-314.pyc         |  Bin 0 -> 143 bytes
 utils/__pycache__/recents.cpython-314.pyc          |  Bin 0 -> 3580 bytes
 utils/__pycache__/sessions.cpython-314.pyc         |  Bin 0 -> 4228 bytes
 utils/__pycache__/shortcuts.cpython-314.pyc        |  Bin 0 -> 3269 bytes
 utils/git/__init__.py                              |   11 +
 utils/git/__pycache__/__init__.cpython-314.pyc     |  Bin 0 -> 454 bytes
 utils/git/__pycache__/git_utils.cpython-314.pyc    |  Bin 0 -> 4484 bytes
 utils/git/git_utils.py                             |   84 ++
 utils/markdown_utils/__init__.py                   |   11 +
 .../__pycache__/__init__.cpython-314.pyc           |  Bin 0 -> 459 bytes
 .../__pycache__/renderer.cpython-314.pyc           |  Bin 0 -> 10428 bytes
 .../__pycache__/viewer.cpython-314.pyc             |  Bin 0 -> 6567 bytes
 utils/markdown_utils/renderer.py                   |  182 ++++
 utils/markdown_utils/viewer.py                     |  102 ++
 utils/recents.py                                   |   59 +
 utils/sessions.py                                  |   78 ++
 utils/shortcuts.py                                 |   56 +
 57 files changed, 3302 insertions(+), 19 deletions(-)

be4b8ca|2026-09-12|Nicolas Grossi|Add README and workspace test files
 README.md                         |  71 +++++++++
 README/README.png                 | Bin 0 -> 1015325 bytes
 sub-carpeta-for-test/contexto.txt |   1 +
 sub-carpeta-for-test/index.html   |  29 ++++
 sub-carpeta-for-test/indexado.txt |  81 ++++++++++
 sub-carpeta-for-test/snake.html   |  29 ++++
 sub-carpeta-for-test/snake.js     | 300 ++++++++++++++++++++++++++++++++++++++
 sub-carpeta-for-test/styles.css   | 107 ++++++++++++++
 sub-carpeta-for-test/test_new.txt |   3 +
 9 files changed, 621 insertions(+)

a093ef9|2026-09-12|Nicolas Grossi|First commit - checkpoint for restyle UI
 AGENTS.md                                    |   29 +
 Skills-py/web_check.py                       |   72 +
 Voice/rec.wav                                |  Bin 0 -> 693326 bytes
 __pycache__/chat_ia.cpython-314.pyc          |  Bin 0 -> 240690 bytes
 chat_ia.py                                   | 3373 ++++++++++++++++++++++++++
 conversaciones/conv_20260912_000253-usage.md |   29 +
 conversaciones/conv_20260912_082537-usage.md |   21 +
 conversaciones/conv_20260912_084402-usage.md |   21 +
 conversaciones/conv_20260912_090212.json     |    7 +
 conversaciones/conv_20260912_091533-usage.md |   17 +
 conversaciones/conv_20260912_091533.json     |   20 +
 conversaciones/conv_20260912_091928.json     |    7 +
 iconos/archivo.svg                           |    1 +
 iconos/carpeta.svg                           |    1 +
 iconos/clip.svg                              |    3 +
 iconos/css.svg                               |    1 +
 iconos/detener.svg                           |    3 +
 iconos/enviar.svg                            |    4 +
 iconos/html.svg                              |    1 +
 iconos/js.svg                                |    1 +
 iconos/json.svg                              |    1 +
 iconos/markdown.svg                          |    1 +
 iconos/mic.svg                               |    6 +
 iconos/play.svg                              |    3 +
 iconos/pulir.svg                             |    5 +
 iconos/python.svg                            |    1 +
 iconos/tuerca.svg                            |    4 +
 iconos/txt.svg                               |    1 +
 last-conversation.txt                        |    2 +
 requirements.txt                             |    3 +
 run.command                                  |    3 +
 31 files changed, 3641 insertions(+)
```

---

## Historial anterior

> Esta seccion la rellena el .bat en cada compilacion nueva, conservando
> los builds anteriores por debajo de este separador.
