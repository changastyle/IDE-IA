#!/bin/bash
# ============================================================================
#  GENERATE-NG-STUDIO.COMMAND
#  Genera NG-STUDIO.app con PyInstaller (--onefile, GUI windowed, sin consola)
#  Entry point: ng-studio-app.py  (launcher de la nueva UI -> UI/main_window.py)
#
#  Ademas, antes de compilar vuelca un resumen del git log a version-macos.md
#  para llevar registro de los cambios de cada build.
# ============================================================================

set -e

# 1 - EL .command ESTA EN OUT/ PERO LOS ARCHIVOS DEL PROYECTO ESTAN ARRIBA:
cd "$(dirname "$0")/.."

echo
echo "============================================================"
echo "  Build NG-STUDIO.app  (macOS)"
echo "============================================================"
echo

# ---------------------------------------------------------------------------
# 2 - VERIFICAR QUE PYTHON3 ESTA EN EL PATH:
# ---------------------------------------------------------------------------
echo "[1/5] Verificando Python3..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 no encontrado en el PATH."
    read -p "Pulsa Enter para salir..."
    exit 1
fi
PYVER=$(python3 --version 2>&1)
echo "      $PYVER OK"

# ---------------------------------------------------------------------------
# 3 - VERIFICAR GIT (necesario para generar version-macos.md):
# ---------------------------------------------------------------------------
echo
echo "[2/5] Verificando git..."
if command -v git >/dev/null 2>&1; then
    echo "      git OK"
    HAVE_GIT=1
else
    echo "ADVERTENCIA: git no encontrado. Se generara version-macos.md sin git log."
    HAVE_GIT=0
fi

# ---------------------------------------------------------------------------
# 4 - GENERAR/ACTUALIZAR version-macos.md CON EL RESUMEN DE CAMBIOS:
# ---------------------------------------------------------------------------
echo
echo "[3/5] Generando OUT/version-macos.md ..."

BUILD_NUM=0
if [ "$HAVE_GIT" = "1" ]; then
    BUILD_NUM=$(git rev-list --count HEAD 2>/dev/null || echo 0)
fi

# Version semver: OUT/VERSION (MAJOR.MINOR.PATCH)
#   sin args        -> bump patch   (10.0.0 -> 10.0.1)
#   --minor         -> bump minor   (10.0.1 -> 10.1.0)
#   --major         -> bump major   (10.0.1 -> 11.0.0)
#   si no existe el archivo, arranca en <commits>.0.0
VERFILE_V="OUT/VERSION"
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

VERFILE="OUT/version-macos.md"
TMPFILE="OUT/_version_new.md"

{
    echo "# NG-STUDIO - Historial de versiones (macOS)"
    echo
    echo "Registro auto-generado por \`generate-ng-studio.command\` en cada compilacion."
    echo "Cada build vuelca el \`git log\` y un resumen de los cambios del proyecto."
    echo
    echo "---"
    echo
    echo "## Build $BUILD_NUM  -  $FECHA $HORA  [macos]"
    echo
    echo "- **Versión:**   $VERSION"
    echo "- **Build:**     $BUILD_NUM"
    echo "- **Plataforma:** macos (.app)"
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
    # Preservar el historial anterior (todo lo que ya habia debajo del segundo "---")
    if [ -f "$VERFILE" ]; then
        # awk: saltar hasta el segundo "---" (cabecera) y volcar el resto
        awk 'BEGIN{c=0} /^---$/{c++; next} c>=2{print}' "$VERFILE"
    fi
} > "$TMPFILE"

mv -f "$TMPFILE" "$VERFILE"
echo "      version-macos.md actualizado: $VERFILE"

# ---------------------------------------------------------------------------
# 5 - CREAR/ACTIVAR VIRTUAL ENV E INSTALAR DEPENDENCIAS:
# ---------------------------------------------------------------------------
echo
echo "[4/5] Verificando virtual environment y dependencias..."
if [ ! -f "venv/bin/activate" ]; then
    echo "      Creando venv..."
    python3 -m venv venv || { echo "ERROR: No se pudo crear el virtual environment."; read -p "Pulsa Enter..."; exit 1; }
fi
# shellcheck disable=SC1091
source venv/bin/activate

# 5a - INSTALAR TODO LO QUE FALTE (dependencias del proyecto + pyinstaller):
#      requirements.txt tiene: PySide6-Essentials, shiboken6, requests, pyte
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
echo "[5/5] Limpiando build anterior..."
rm -rf "OUT/build/NG-STUDIO"
rm -rf "OUT/NG-STUDIO.app"
rm -f  "OUT/NG-STUDIO"
rm -f  "OUT/NG-STUDIO.spec"
echo "      Limpieza OK"

# ---------------------------------------------------------------------------
# 7 - CONSTRUIR EL .app CON PYINSTALLER:
# ---------------------------------------------------------------------------
echo
echo "Construyendo NG-STUDIO.app (onefile, windowed)..."
pyinstaller --noconfirm --windowed --onefile --name "NG-STUDIO" \
    --distpath "OUT" \
    --workpath "OUT/build" \
    --specpath "OUT" \
    --paths "." \
    --add-data "UI:UI" \
    --add-data "Skills-py:Skills-py" \
    --add-data "Voice:Voice" \
    --add-data "utils:utils" \
    --add-data "iconos:iconos" \
    --add-data "conversaciones:conversaciones" \
    --add-data "README:README" \
    --add-data "OUT/version-macos.md:OUT" \
    --hidden-import "PySide6.QtWidgets" \
    --hidden-import "PySide6.QtCore" \
    --hidden-import "PySide6.QtGui" \
    --hidden-import "requests" \
    --hidden-import "pyte" \
    --hidden-import "pyte.streams" \
    ng-studio-app.py || { echo "ERROR: Fallo el build de NG-STUDIO."; read -p "Pulsa Enter..."; exit 1; }

# ---------------------------------------------------------------------------
# 8 - RESULTADO:
# ---------------------------------------------------------------------------
echo
echo "============================================================"
echo "  BUILD COMPLETADO: NG-STUDIO.app  (macOS)"
echo "============================================================"
echo
echo "  Ubicacion: OUT/NG-STUDIO.app"
echo "  Version:   $VERSION"
echo "  Historial: OUT/version-macos.md  (build $BUILD_NUM)"
echo
echo "  El .app es totalmente autocontenido (onefile)."
echo "  Las conversaciones y la config se crean al lado del .app"
echo "  en el primer arranque."
echo
echo "  Para llevar a otra Mac:"
echo "    1. Copia solo OUT/NG-STUDIO.app"
echo "    2. Doble clic (la 1ra vez: clic derecho > Abrir para autorizar)"
echo "    3. No necesita Python ni nada instalado"
echo
read -p "Pulsa Enter para salir..."
