#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# FlatSat Ground Station — build de la aplicación autónoma
# ──────────────────────────────────────────────────────────────────────────────
# Genera un único ejecutable `dist/flatsat-gs` con Python, Flask, SocketIO,
# pyserial, click, rich y pycryptodome dentro. El usuario final no necesita
# Python, pip ni Docker:
#
#     flatsat-gs            → dashboard web
#     flatsat-gs cli        → CLI interactivo
#     flatsat-gs install    → instalación en el perfil del usuario
#
#   ./compile_app.sh              → sólo el binario
#   ./compile_app.sh --bundle     → además, .app en macOS / AppImage en Linux
# ──────────────────────────────────────────────────────────────────────────────
set -e

BUNDLE=0
[ "$1" = "--bundle" ] && BUNDLE=1

echo "[*] Building FlatSat Ground Station app using PyInstaller..."

if [ -z "$PYTHON" ]; then
    if [ -f ".venv/bin/python" ]; then
        PYTHON=".venv/bin/python"
    else
        PYTHON="python3"
    fi
fi

if ! "$PYTHON" -m PyInstaller --version > /dev/null 2>&1; then
    echo "[!] PyInstaller not found. Installing pyinstaller..."
    "$PYTHON" -m pip install pyinstaller
fi

"$PYTHON" -m PyInstaller --clean --noconfirm flatsat_app.spec

echo "[+] Binary: dist/flatsat-gs"

# ── macOS: .app bundle ─────────────────────────────────────────────────────
if [ "$(uname -s)" = "Darwin" ] && [ "$BUNDLE" = "1" ]; then
    APP="dist/FlatSat GS.app"
    rm -rf "$APP"
    mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
    cp dist/flatsat-gs "$APP/Contents/MacOS/flatsat-gs"
    cp VERSION "$APP/Contents/Resources/VERSION"
    if [ -f assets/flatsat-gs.png ]; then
        cp assets/flatsat-gs.png "$APP/Contents/Resources/flatsat-gs.png"
    fi
    cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>            <string>FlatSat GS</string>
    <key>CFBundleDisplayName</key>     <string>FlatSat Ground Station</string>
    <key>CFBundleExecutable</key>      <string>flatsat-gs</string>
    <key>CFBundleIdentifier</key>      <string>com.electroniccats.flatsat-gs</string>
    <key>CFBundleIconFile</key>        <string>flatsat-gs</string>
    <key>CFBundleVersion</key>         <string>1.0.0</string>
    <key>CFBundleShortVersionString</key><string>1.0.0</string>
    <key>CFBundlePackageType</key>     <string>APPL</string>
    <key>LSMinimumSystemVersion</key>  <string>10.15</string>
    <key>NSHighResolutionCapable</key> <true/>
</dict>
</plist>
PLIST
    echo "[+] macOS bundle: $APP"

    if [ "$BUNDLE" = "1" ] && command -v hdiutil > /dev/null 2>&1; then
        DMG="dist/FlatSatGS-$(cat VERSION).dmg"
        rm -f "$DMG"
        hdiutil create -volname "FlatSat Ground Station" -srcfolder "dist" -ov -format UDZO "$DMG"
        echo "[+] DMG: $DMG"
    fi
fi

# ── Linux: AppImage (requiere appimagetool) o tarball ──────────────────────
if [ "$(uname -s)" = "Linux" ] && [ "$BUNDLE" = "1" ]; then
    if command -v appimagetool > /dev/null 2>&1; then
        APPDIR="dist/flatsat-gs.AppDir"
        rm -rf "$APPDIR"
        mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications"
        cp dist/flatsat-gs "$APPDIR/usr/bin/flatsat-gs"
        cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/flatsat-gs" "$@"
APPRUN
        chmod +x "$APPDIR/AppRun"
        cat > "$APPDIR/flatsat-gs.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=FlatSat Ground Station
Exec=flatsat-gs
Icon=flatsat-gs
Terminal=true
Categories=Science;Electronics;
DESKTOP
        cp "$APPDIR/flatsat-gs.desktop" "$APPDIR/usr/share/applications/"
        ( cd "$APPDIR" && appimagetool . )
        echo "[+] AppImage: dist/flatsat-gs-x86_64.AppImage"
    else
        tar -czf "dist/flatsat-gs-$(uname -m).tar.gz" -C dist flatsat-gs
        echo "[!] appimagetool not found — tarball instead: dist/flatsat-gs-$(uname -m).tar.gz"
    fi
fi

echo "[+] Done. Attach the artefact to the GitHub Release so users can download it directly."
