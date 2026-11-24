@echo off
setlocal enabledelayedexpansion
REM ──────────────────────────────────────────────────────────────────────────────
REM FlatSat Ground Station — lanzador para Windows
REM
REM Es el UNICO comando que necesitas recordar en Windows:
REM
REM     run.cmd                 -> dashboard web (abre el navegador)
REM     run.cmd cli             -> CLI interactivo
REM     run.cmd doctor          -> diagnostico
REM     run.cmd build           -> compila el binario autonomo (dist\flatsat-gs.exe)
REM     run.cmd install         -> instala la app (flatsat-gs install)
REM     run.cmd uninstall       -> desinstala la app
REM     run.cmd web --port 5001 -> opciones del dashboard
REM
REM Nota: en PowerShell los ficheros .bat del directorio actual necesitan el
REM prefijo ".\" (".\run.cmd"), pero este atajo se puede llamar desde cmd
REM directamente.
REM ──────────────────────────────────────────────────────────────────────────────

set "GS_DIR=%~dp0"

REM Si ya está instalada, se usa el ejecutable de la propia instalacion.
if exist "%GS_DIR%flatsat-gs\bin\flatsat-gs.exe" (
    "%GS_DIR%flatsat-gs\bin\flatsat-gs.exe" %*
    exit /b %errorlevel%
)

REM "build" necesita compilar, y eso no lo hace la app instalada.
if /i "%~1"=="build" (
    echo [*] Compilando el binario autonomo...
    call "%GS_DIR%build_app_windows.bat"
    exit /b %errorlevel%
)

set "PY="

py -3 -c "import sys" >nul 2>&1
if %errorlevel% equ 0 set "PY=py -3"

if not defined PY (
    python -c "import sys" >nul 2>&1
    if %errorlevel% equ 0 set "PY=python"
)

if not defined PY (
    echo.
    echo [!] No se encuentra un Python 3.9+ utilizable.
    echo.
    echo     Opcion 1: instala Python desde https://www.python.org/
    echo               y marca "Add Python to PATH" durante la instalacion.
    echo     Opcion 2: compila el binario autonomo con build_app_windows.bat
    echo               y ejecuta dist\flatsat-gs.exe install
    echo.
    pause
    exit /b 1
)

%PY% "%GS_DIR%flatsat_app.py" %*
exit /b %errorlevel%
