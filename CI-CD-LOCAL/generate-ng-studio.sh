#!/bin/bash
# ============================================================================
#  GENERATE-NG-STUDIO.SH
#  Genera NG-STUDIO.AppImage con PyInstaller + appimagetool.
#  Entry point: ng-studio-app.py  (launcher de la nueva UI -> UI/main_window.py)
#
#  Flujo:
#    1. Genera version-linux.md (git log + stat).
#    2. Crea venv e instala dependencias.
#    3. pyinstaller --onefile --windowed -> binario autocontenido.
#    4. Construye un AppDir (estructura AppImage).
#    5. Descarga appimagetool si hace falta y empaqueta -> NG-STUDIO.AppImage.
# ============================================================================

set -e

# 1 - EL .sh ESTA EN CI-CD-LOCAL/ PERO LOS ARCHIVOS DEL PROYECTO ESTAN ARRIBA:
cd "$(dirname "$0")/.."

echo
echo "============================================================"
echo "  Build NG-STUDIO.AppImage  (Linux)"
echo "============================================================"
echo

# ---------------------------------------------------------------------------
# 2 - VERIFICAR QUE PYTHON3 ESTA EN EL PATH:
# ---------------------------------------------------------------------------
echo "[1/6] Verificando Python3..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 no encontrado en el PATH."
    read -p "Pulsa Enter para salir..." ; exit 1
fi
PYVER=$(python3 --version 2>&1)
echo "      $PYVER OK"

# ---------------------------------------------------------------------------
# 3 - VERIFICAR GIT (necesario para generar version-linux.md):
# ---------------------------------------------------------------------------
echo
echo "[2/6] Verificando git..."
if command -v git >/dev/null 2>&1; then
    echo "      git OK"
    HAVE_GIT=1
else
    echo "ADVERTENCIA: git no encontrado. Se generara version-linux.md sin git log."
    HAVE_GIT=0
fi

# ---------------------------------------------------------------------------
# 4 - GENERAR/ACTUALIZAR version-linux.md CON EL RESUMEN DE CAMBIOS:
# ---------------------------------------------------------------------------
echo
echo "[3/6] Generando CI-CD-LOCAL/version-linux.md ..."

BUILD_NUM=0
if [ "$HAVE_GIT" = "1" ]; then
    BUILD_NUM=$(git rev-list --count HEAD 2>/dev/null || echo 0)
fi

# Version semver: CI-CD-LOCAL/VERSION (MAJOR.MINOR.PATCH)
#   sin args        -> bump patch   (10.0.0 -> 10.0.1)
#   --minor         -> bump minor   (10.0.1 -> 10.1.0)
#   --major         -> bump major   (10.0.1 -> 11.0.0)
#   si no existe el archivo, arranca en <commits>.0.0
VERFILE_V="CI-CD-LOCAL/VERSION"
if [ ! -f "$VERFILE_V" ]; then
    echo "${BUILD_NUM}.0.0" > "$VERFILE_V"
fi
CURVER=$(tr -d '[:space:]' < "$VERFILE_V")
VMAJ=${CURVER%%.*}
VREST=${CURVER#*.}
VMIN=${VREST%%.*}
VPAT=${VREST#*.}
case "${1:-}" in
    --major) VMAJ=$((VMAJ+1)); VMIN=0; VPAT=0 ;;
    --minor) VMIN=$((VMIN+1)); VPAT=0 ;;
    *)       VPAT=$((VPAT+1)) ;;
esac
VERSION="${VMAJ}.${VMIN}.${VPAT}"
echo "$VERSION" > "$VERFILE_V"
echo "      VERSION: $VERSION"

FECHA=$(date "+%Y-%m-%d")
HORA=$(date "+%H:%M")

LAST_HASH="-"
LAST_MSG="-"
if [ "$HAVE_GIT" = "1" ]; then
    LAST_HASH=$(git log -1 --pretty="format:%h" 2>/dev/null || echo "-")
    LAST_MSG=$(git log -1 --pretty="format:%s" 2>/dev/null || echo "-")
fi

VERFILE="CI-CD-LOCAL/version-linux.md"
TMPFILE="CI-CD-LOCAL/_version_new.md"

{
    echo "# NG-STUDIO - Historial de versiones (Linux)"
    echo
    echo "Registro auto-generado por \`generate-ng-studio.sh\` en cada compilacion."
    echo "Cada build vuelca el \`git log\` y un resumen de los cambios del proyecto."
    echo
    echo "---"
    echo
    echo "## Build $BUILD_NUM  -  $FECHA $HORA  [linux]"
    echo
    echo "- **Versión:**   $VERSION"
    echo "- **Build:**     $BUILD_NUM"
    echo "- **Plataforma:** linux (.AppImage)"
    echo "- **Fecha:**     $FECHA $HORA"
    echo "- **Commit:**    $LAST_HASH"
    echo "- **Mensaje:**   $LAST_MSG"
    echo
    echo "### Resumen de cambios (git log --oneline -30)"
    echo
    echo '```'
    if [ "$HAVE_GIT" = "1" ]; then
        git log --oneline -30 2>&1 || echo "git no disponible"
    else
        echo "git no disponible"
    fi
    echo '```'
    echo
    echo "### Changelog detallado (git log -30 --stat)"
    echo
    echo '```'
    if [ "$HAVE_GIT" = "1" ]; then
        git log -30 --pretty=format:"%h|%ad|%an|%s" --date=short --stat 2>&1 || echo "git no disponible"
    else
        echo "git no disponible"
    fi
    echo '```'
    echo
    echo "---"
    echo
    if [ -f "$VERFILE" ]; then
        awk 'BEGIN{c=0} /^---$/{c++; next} c>=2{print}' "$VERFILE"
    fi
} > "$TMPFILE"

mv -f "$TMPFILE" "$VERFILE"
echo "      version-linux.md actualizado: $VERFILE"

# ---------------------------------------------------------------------------
# 5 - CREAR/ACTIVAR VIRTUAL ENV E INSTALAR DEPENDENCIAS:
# ---------------------------------------------------------------------------
echo
echo "[4/6] Verificando virtual environment y dependencias..."
if [ ! -f "venv/bin/activate" ]; then
    echo "      Creando venv..."
    python3 -m venv venv || { echo "ERROR: No se pudo crear el virtual environment."; read -p "Pulsa Enter..."; exit 1; }
fi
# shellcheck disable=SC1091
source venv/bin/activate

for P in PySide6-Essentials shiboken6 requests pyte pyinstaller; do
    if ! pip show "$P" >/dev/null 2>&1; then
        echo "      Instalando $P..."
        pip install "$P" || { echo "ERROR: No se pudo instalar $P."; read -p "Pulsa Enter..."; exit 1; }
    else
        echo "      $P OK"
    fi
done

# ---------------------------------------------------------------------------
# 6 - LIMPIAR BUILDS ANTERIORES DE NG-STUDIO:
# ---------------------------------------------------------------------------
echo
echo "[5/6] Limpiando build anterior..."
rm -rf "build/NG-STUDIO"
rm -rf "OUT/NG-STUDIO"
rm -rf "OUT/NG-STUDIO.AppImage"
rm -rf "AppDir"
rm -f  "NG-STUDIO.spec"
echo "      Limpieza OK"

# ---------------------------------------------------------------------------
# 7 - CONSTRUIR EL BINARIO CON PYINSTALLER (onefile):
# ---------------------------------------------------------------------------
echo
echo "[6/6] Construyendo NG-STUDIO (onefile)..."
pyinstaller --noconfirm --onefile --name "NG-STUDIO" \
    --distpath "OUT" \
    --paths "." \
    --add-data "UI:UI" \
    --add-data "Skills-py:Skills-py" \
    --add-data "Voice:Voice" \
    --add-data "utils:utils" \
    --add-data "iconos:iconos" \
    --add-data "conversaciones:conversaciones" \
    --add-data "README:README" \
    --add-data "CI-CD-LOCAL/version-linux.md:CI-CD-LOCAL" \
    --hidden-import "PySide6.QtWidgets" \
    --hidden-import "PySide6.QtCore" \
    --hidden-import "PySide6.QtGui" \
    --hidden-import "requests" \
    --hidden-import "pyte" \
    --hidden-import "pyte.streams" \
    ng-studio-app.py || { echo "ERROR: Fallo el build de NG-STUDIO."; read -p "Pulsa Enter..."; exit 1; }

# ---------------------------------------------------------------------------
# 8 - CONSTRUIR EL APPIMAGE:
# ---------------------------------------------------------------------------
echo
echo "Empaquetando NG-STUDIO.AppImage..."

APPDIR="AppDir"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# 8a - Copiar el binario al AppDir
cp -f "OUT/NG-STUDIO" "$APPDIR/usr/bin/NG-STUDIO"
chmod +x "$APPDIR/usr/bin/NG-STUDIO"

# 8b - Icono (usamos app_256.png si existe, si no un placeholder)
if [ -f "iconos/app_256.png" ]; then
    cp "iconos/app_256.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/ng-studio.png"
    cp "iconos/app_256.png" "$APPDIR/ng-studio.png"
else
    echo "ADVERTENCIA: iconos/app_256.png no encontrado. AppImage sin icono."
fi

# 8c - .desktop file
cat > "$APPDIR/ng-studio.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=NG-STUDIO
Comment=Asistente de IA local
Exec=NG-STUDIO
Icon=ng-studio
Categories=Development;
Terminal=false
DESKTOP

# 8d - AppRun: wrapper que ejecuta el binario
cat > "$APPDIR/AppRun" <<'RUN'
#!/bin/bash
SELF="$(readlink -f "$0")"
APPDIR="$(dirname "$SELF")"
exec "$APPDIR/usr/bin/NG-STUDIO" "$@"
RUN
chmod +x "$APPDIR/AppRun"

# 8e - Descargar appimagetool si no esta presente
APPIMAGETOOL="CI-CD-LOCAL/appimagetool-x86_64.AppImage"
if [ ! -f "$APPIMAGETOOL" ]; then
    echo "      Descargando appimagetool..."
    wget -q -O "$APPIMAGETOOL" \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" \
        || { echo "ERROR: No se pudo descargar appimagetool."; read -p "Pulsa Enter..."; exit 1; }
    chmod +x "$APPIMAGETOOL"
fi

# 8f - Empaquetar
"$APPIMAGETOOL" "$APPDIR" "OUT/NG-STUDIO.AppImage" \
    || { echo "ERROR: Fallo el empaquetado AppImage."; read -p "Pulsa Enter..."; exit 1; }

# Limpieza del AppDir temporal
rm -rf "$APPDIR"

# ---------------------------------------------------------------------------
# 9 - RESULTADO:
# ---------------------------------------------------------------------------
echo
echo "============================================================"
echo "  BUILD COMPLETADO: NG-STUDIO.AppImage  (Linux)"
echo "============================================================"
echo
echo "  Ubicacion: OUT/NG-STUDIO.AppImage"
echo "  Version:   $VERSION"
echo "  Historial: CI-CD-LOCAL/version-linux.md  (build $BUILD_NUM)"
echo
echo "  El AppImage es totalmente autocontenido y portable."
echo
echo "  Para usarlo en otra PC Linux:"
echo "    1. Copia solo OUT/NG-STUDIO.AppImage"
echo "    2. chmod +x NG-STUDIO.AppImage  (solo la 1ra vez)"
echo "    3. Doble clic o ./NG-STUDIO.AppImage"
echo "    4. No necesita Python ni nada instalado"
echo
read -p "Pulsa Enter para salir..."
