@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM ============================================================================
REM  GENERATE-NG-STUDIO-EXE.BAT
REM  Genera NG-STUDIO.exe con PyInstaller (--onefile, GUI windowed, sin consola)
REM  Todo (DLLs, runtime, dependencias) queda embebido en un unico .exe.
REM  Entry point: ng-studio-app.py  (launcher de la nueva UI -> UI/main_window.py)
REM
REM  Ademas, antes de compilar vuelca un resumen del git log a version.md
REM  para llevar registro de los cambios de cada build.
REM ============================================================================

REM 1 - EL .bat ESTA EN OUT/ PERO LOS ARCHIVOS DEL PROYECTO ESTAN ARRIBA:
cd /d "%~dp0\.."

echo.
echo ============================================================
echo   Build NG-STUDIO.exe
echo ============================================================
echo.

REM ---------------------------------------------------------------------------
REM 2 - VERIFICAR QUE PYTHON ESTA EN EL PATH:
REM ---------------------------------------------------------------------------
echo [1/5] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado en el PATH.
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo       Python !PYVER! OK

REM ---------------------------------------------------------------------------
REM 3 - VERIFICAR GIT (necesario para generar version.md):
REM ---------------------------------------------------------------------------
echo.
echo [2/5] Verificando git...
git --version >nul 2>&1
if errorlevel 1 (
    echo ADVERTENCIA: git no encontrado. Se generara version.md sin git log.
    set HAVE_GIT=0
) else (
    echo       git OK
    set HAVE_GIT=1
)

REM ---------------------------------------------------------------------------
REM 4 - GENERAR/ACTUALIZAR version.md CON EL RESUMEN DE CAMBIOS:
REM ---------------------------------------------------------------------------
echo.
echo [3/5] Generando OUT\version-windows.md ...

REM  Numero de build = cantidad de commits hasta ahora (si hay git)
set BUILD_NUM=0
if "!HAVE_GIT!"=="1" (
    for /f %%c in ('git rev-list --count HEAD 2^>^&1') do set BUILD_NUM=%%c
)

REM  Version semver: OUT\VERSION (MAJOR.MINOR.PATCH)
REM    sin args  -> bump patch   (10.0.0 -> 10.0.1)
REM    --minor   -> bump minor   (10.0.1 -> 10.1.0)
REM    --major   -> bump major   (10.0.1 -> 11.0.0)
REM    si no existe el archivo, arranca en <commits>.0.0
set VERFILE_V=OUT\VERSION
if not exist "!VERFILE_V!" echo !BUILD_NUM!.0.0> "!VERFILE_V!"
set /p CURVER=<"!VERFILE_V!"
for /f "tokens=1-3 delims=." %%a in ("!CURVER!") do (
    set VMAJ=%%a
    set VMIN=%%b
    set VPAT=%%c
)
if /i "%~1"=="--major" (
    set /a VMAJ+=1
    set VMIN=0
    set VPAT=0
) else if /i "%~1"=="--minor" (
    set /a VMIN+=1
    set VPAT=0
) else (
    set /a VPAT+=1
)
set VERSION=!VMAJ!.!VMIN!.!VPAT!
echo !VERSION!> "!VERFILE_V!"
echo       VERSION: !VERSION!

REM  Fecha y hora del build
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set FECHA=%%a/%%b/%%c
for /f "tokens=1-2 delims=: " %%x in ('time /t') do set HORA=%%x:%%y

REM  Ultimo commit (hash corto + mensaje)
set LAST_HASH=-
set LAST_MSG=-
if "!HAVE_GIT!"=="1" (
    for /f "tokens=*" %%l in ('git log -1 --pretty^="format:%%h" 2^>^&1') do set LAST_HASH=%%l
    for /f "tokens=*" %%l in ('git log -1 --pretty^="format:%%s" 2^>^&1') do set LAST_MSG=%%l
)

REM  Escribir encabezado del build en un archivo temporal
set VERFILE=OUT\version-windows.md
set TMPFILE=OUT\_version_new.md

echo # NG-STUDIO - Historial de versiones> "!TMPFILE!"
echo.>> "!TMPFILE!"
echo Registro auto-generado por `generate-ng-studio.exe.bat` en cada compilacion.>> "!TMPFILE!"
echo Cada build vuelca el `git log` y un resumen de los cambios del proyecto.>> "!TMPFILE!"
echo.>> "!TMPFILE!"
echo --->> "!TMPFILE!"
echo.>> "!TMPFILE!"
echo ## Build !BUILD_NUM!  -  !FECHA! !HORA!  [windows]>> "!TMPFILE!"
echo.>> "!TMPFILE!"
echo - **Versión:**   !VERSION!>> "!TMPFILE!"
echo - **Build:**     !BUILD_NUM!>> "!TMPFILE!"
echo - **Plataforma:** windows (.exe)>> "!TMPFILE!"
echo - **Fecha:**     !FECHA! !HORA!>> "!TMPFILE!"
echo - **Commit:**    !LAST_HASH!>> "!TMPFILE!"
echo - **Mensaje:**   !LAST_MSG!>> "!TMPFILE!"
echo.>> "!TMPFILE!"
echo ### Resumen de cambios (git log --oneline -30)>> "!TMPFILE!"
echo.>> "!TMPFILE!"
echo ```>> "!TMPFILE!"
if "!HAVE_GIT!"=="1" (
    git log --oneline -30 >> "!TMPFILE!" 2>&1
) else (
    echo git no disponible>> "!TMPFILE!"
)
echo ```>> "!TMPFILE!"
echo.>> "!TMPFILE!"
echo ### Changelog detallado (git log -30 --stat)>> "!TMPFILE!"
echo.>> "!TMPFILE!"
echo ```>> "!TMPFILE!"
if "!HAVE_GIT!"=="1" (
    git log -30 --pretty=format:"%%h|%%ad|%%an|%%s" --date=short --stat >> "!TMPFILE!" 2>&1
) else (
    echo git no disponible>> "!TMPFILE!"
)
echo ```>> "!TMPFILE!"
echo.>> "!TMPFILE!"
echo --->> "!TMPFILE!"
echo.>> "!TMPFILE!"

REM  Preservar el historial anterior (todo lo que ya habia debajo del segundo "---")
if exist "!VERFILE!" (
    findstr /n "^" "!VERFILE!" > OUT\_vlines.txt
    set SKIPPED=0
    for /f "usebackq tokens=1* delims=:" %%a in ("OUT\_vlines.txt") do (
        set LINE=%%b
        if "%%b"=="---" (
            set /a SKIPPED+=1
        )
        if !SKIPPED! GEQ 2 (
            echo(!LINE!>> "!TMPFILE!"
        )
    )
    del /q OUT\_vlines.txt
)

REM  Reemplazar version.md por el nuevo
move /y "!TMPFILE!" "!VERFILE!" >nul
echo       version-windows.md actualizado: !VERFILE!

REM ---------------------------------------------------------------------------
REM 5 - CREAR/ACTIVAR VIRTUAL ENV E INSTALAR DEPENDENCIAS:
REM ---------------------------------------------------------------------------
echo.
echo [4/5] Verificando virtual environment y dependencias...
if not exist "venv\Scripts\activate.bat" (
    echo       Creando venv...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: No se pudo crear el virtual environment.
        pause
        exit /b 1
    )
)
call venv\Scripts\activate.bat

REM 5a - INSTALAR TODO LO QUE FALTE (dependencias del proyecto + pyinstaller):
REM      requirements.txt tiene: PySide6-Essentials, shiboken6, requests, pyte
for %%P in (PySide6-Essentials shiboken6 requests pyte pyinstaller) do (
    pip show %%P >nul 2>&1
    if errorlevel 1 (
        echo       Instalando %%P...
        pip install %%P
        if errorlevel 1 (
            echo ERROR: No se pudo instalar %%P.
            pause
            exit /b 1
        )
    ) else (
        echo       %%P OK
    )
)

REM ---------------------------------------------------------------------------
REM 6 - LIMPIAR BUILDS ANTERIORES DE NG-STUDIO:
REM ---------------------------------------------------------------------------
echo.
echo [5/5] Limpiando build anterior...
if exist "OUT\build\NG-STUDIO" rmdir /s /q "OUT\build\NG-STUDIO"
if exist "OUT\NG-STUDIO" rmdir /s /q "OUT\NG-STUDIO"
if exist "OUT\NG-STUDIO.exe" del /q "OUT\NG-STUDIO.exe"
if exist "OUT\NG-STUDIO.spec" del /q "OUT\NG-STUDIO.spec"
echo       Limpieza OK

REM ---------------------------------------------------------------------------
REM 7 - CONSTRUIR EL .exe CON PYINSTALLER:
REM ---------------------------------------------------------------------------
echo.
echo Construyendo NG-STUDIO.exe (onefile)...
pyinstaller --noconfirm --windowed --onefile --name "NG-STUDIO" ^
    --distpath "OUT" ^
    --workpath "OUT\build" ^
    --specpath "OUT" ^
    --paths "." ^
    --add-data "UI;UI" ^
    --add-data "Skills-py;Skills-py" ^
    --add-data "Voice;Voice" ^
    --add-data "utils;utils" ^
    --add-data "iconos;iconos" ^
    --add-data "conversaciones;conversaciones" ^
    --add-data "README;README" ^
    --add-data "OUT\version-windows.md;OUT" ^
    --hidden-import "PySide6.QtWidgets" ^
    --hidden-import "PySide6.QtCore" ^
    --hidden-import "PySide6.QtGui" ^
    --hidden-import "requests" ^
    --hidden-import "pyte" ^
    --hidden-import "pyte.streams" ^
    ng-studio-app.py
if errorlevel 1 (
    echo ERROR: Fallo el build de NG-STUDIO.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------------------
REM 8 - RESULTADO:
REM ---------------------------------------------------------------------------
echo.
echo ============================================================
echo   BUILD COMPLETADO: NG-STUDIO.exe (onefile)
echo ============================================================
echo.
echo   Ubicacion: OUT\NG-STUDIO.exe
echo   Version:   !VERSION!
echo   Historial: OUT\version-windows.md  (build !BUILD_NUM!)
echo.
echo   El .exe es totalmente autocontenido (no necesita _internal/).
echo   Las conversaciones y la config se crean al lado del .exe
echo   en el primer arranque.
echo.
echo   Para llevar a otra PC:
echo     1. Copia solo OUT\NG-STUDIO.exe
echo     2. Ejecuta NG-STUDIO.exe (doble clic)
echo     3. No necesita Python ni nada instalado
echo.
pause
