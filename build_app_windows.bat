@echo off
REM ──────────────────────────────────────────────────────────────────────────────
REM FlatSat Ground Station — compila el binario autónomo
REM
REM     dist\flatsat-gs.exe      (Linux/macOS: ./compile_app.sh)
REM
REM Detecta un Python utilizable: el alias "python" de Microsoft Store falla
REM con exit code 49, así que se comprueba de verdad que ejecute código.
REM ──────────────────────────────────────────────────────────────────────────────

set "GS_DIR=%~dp0"

REM El entorno virtual del proyecto produce un binario mucho mas ligero
REM (solo se empaqueta lo que la app necesita).
set "PY="
if exist "%GS_DIR%.venv\Scripts\python.exe" set "PY=%GS_DIR%.venv\Scripts\python.exe"

if not defined PY (
    py -3 -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PY=py -3"
)

if not defined PY (
    python -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PY=python"
)

if not defined PY (
    echo.
    echo [!] No se encuentra un Python 3.9+ utilizable.
    echo     Instala Python desde https://www.python.org/ y marca
    echo     "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

echo [*] Building FlatSat Ground Station app for Windows...

%PY% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo [*] PyInstaller not found. Installing pyinstaller...
    %PY% -m pip install --no-warn-script-location pyinstaller
    if errorlevel 1 (
        echo [!] Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

%PY% -m PyInstaller --clean --noconfirm flatsat_app.spec
if errorlevel 1 (
    echo [!] PyInstaller compilation failed!
    pause
    exit /b 1
)

echo [+] Windows build completed successfully!
echo [+] Binary location: dist\flatsat-gs.exe
echo [+] Run it once to install the app (CLI + shortcuts) automatically.
pause
