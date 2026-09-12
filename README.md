# IDE-IA

Un IDE local con IA construido en Python y Qt que se conecta a proveedores de IA locales (LM Studio, OpenCode Go) y permite a la IA operar directamente sobre los archivos del workspace.

![IDE-IA](README/README.png)

## Características

- **Proveedores de IA locales**: LM Studio, OpenCode Go y cualquier API compatible con OpenAI
- **Herramientas de archivos**: la IA puede listar, leer, crear y editar archivos del workspace
- **Workspace sandboxing**: cada carpeta tiene su propio contexto, conversación y presupuesto de tokens
- **Streaming de respuestas**: las respuestas de la IA aparecen en tiempo real
- **Multimodal**: soporte para imágenes (PNG, JPG, GIF, WEBP, BMP) con modelos de visión
- **Voz a texto**: grabación con micrófono y transcripción automática
- **Terminal integrada**: ejecuta archivos `.py`, `.js`, `.java` con un clic
- **Visor de imágenes**: doble clic en SVG/PNG/JPG abre un visor con zoom
- **Editor con diff**: visualiza los cambios que hace la IA en los archivos
- **Preferencias**: modelo primario, secundario, de visión, presupuesto de tokens por carpeta
- **Compresión de contexto**: resume conversaciones automáticamente para ahorrar tokens
- **Gestión de turnos**: excluye turnos del contexto para reducir el consumo de tokens
- **`contexto.txt`**: archivo de contexto persistente por proyecto
- **`indexado.txt`**: mapa del proyecto generado por la IA
- **Sonidos**: feedback de audio al grabar, enviar y recibir respuestas

## Instalación

```bash
pip install PySide6 requests SpeechRecognition
```

Requiere `ffmpeg` para grabación de voz:

```bash
# macOS
brew install ffmpeg
```

## Uso

```bash
python chat_ia.py
```

O doble clic en `run.command` (macOS).

## Estructura

```
cli-ia/
├── chat_ia.py          # Aplicación principal
├── run.command         # Launcher para macOS
├── requirements.txt    # Dependencias
├── iconos/             # Iconos SVG
├── Voice/              # Grabaciones de voz
├── Skills-py/          # Skills personalizadas
├── conversaciones/     # Conversaciones guardadas (auto)
└── README/
    └── README.png      # Captura de pantalla
```

## Configuración

1. Abrir Preferencias (⚙ arriba a la derecha)
2. Configurar providers (LM Studio, OpenCode Go, etc.)
3. Elegir modelo primario, secundario y de visión
4. Setear presupuesto de tokens por carpeta
5. Activar auto-resumir si se quiere compresión automática

## Licencia

Uso personal.
