# Compilar e instalar — FlatSat Ground Station

Guía completa para **Windows, Linux y macOS**: requisitos, compilación del
binario autónomo, instalación, verificación, desinstalación y resolución de
problemas.

---

## 1. Qué se puede instalar

| Vía | Qué obtienes | Requiere |
|---|---|---|
| **Binario autónomo** | Un único fichero con Python, Flask, pyserial, click… dentro. Sin dependencias en el equipo destino. | Ninguno |
| **Desde el código** | El código + un entorno virtual propio en la carpeta del proyecto. | Python 3.9+ |

Las dos Instalaciones se hacen **en la carpeta del proyecto** (`flatsat-gs/`) y
crean los mismos comandos:

| Comando | Qué hace |
|---|---|
| `flatsat web` | Abre el dashboard en el navegador |
| `flatsat doctor` | Diagnóstico: entorno, puertos serie, alias |
| `flatsat devices` | La placa conectada y sus puertos |
| `flatsat status` | Firmware, modo y estado del radio |
| `flatsat sensors` | Sensores en vivo |
| `flatsat sniff -n 3` | Capturar tramas CCSDS |
| `flatsat install` / `flatsat uninstall` | Instalar / desinstalar la app |
| `flatsat-web`, `flatsat-gs` | Alias del dashboard y de la app completa |

---

## 2. Requisitos

| | Versión | Nota |
|---|---|---|
| Python | 3.9 o superior | Windows: marca *"Add Python to PATH"* al instalarlo |
| pip | incluido con Python | Todas las dependencias tienen ruedas precompiladas: **no hace falta compilador** |
| Disco | ~80 MB | Binario (20 MB) o entorno virtual (~60 MB) |
| Puertos serie | Acceso al grupo `dialout` (Linux) | Ver §7 |

---

## 3. Windows

### 3.1 Compilar el binario autónomo

```bat
cd C:\ruta\al\proyecto\flatsat-ground-station
.\run.cmd build
```

O, equivalente, con el script directo:

```bat
.\build_app_windows.bat
```

> **En PowerShell los ficheros de la carpeta actual necesitan el prefijo
> `.\`**. Sin él aparece *"no se reconoce como un cmdlet"*. `run.cmd build`
> funciona igual porque el propio script resuelve su ruta.

Resultado: `dist\flatsat-gs.exe` (20 MB).

El script:
1. usa el `.venv` del proyecto si existe (binario más ligero: 20 MB en vez de
   51 MB); si no, busca `py -3` y luego `python`;
2. instala PyInstaller si falta;
3. genera el ejecutable con icono propio.

### 3.2 Instalar

```bat
dist\flatsat-gs.exe install
```

O desde el código:

```bat
.\run.cmd install
```

### 3.3 Si tu empresa bloquea los ejecutables sin firmar

Algunas políticas de Windows Defender Application Control (Device Guard /
AppLocker) rechazan los `.exe` sin firmar:

```
'...\dist\flatsat-gs.exe' was blocked by your organization's Device Guard policy.
```

Es normal: el binario no está firmado. Y puede ser **intermitente** (el
antivirus lo marca y lo levanta en unas compilaciones, o al revés).

**No hace nada falta**: el instalador lo comprueba antes de instalar y cae
solo a la vía que funciona en tu equipo:

```
[!] El ejecutable flatsat-gs.exe está bloqueado por la política de seguridad del sistema.
[!]   Se instala la versión con Python: los mismos comandos, el mismo comportamiento.
```

La versión con Python usa el intérprete (que ya está autorizado) y unos
lanzadores `.cmd`. **Los comandos son idénticos** en cualquier equipo:

```bash
flatsat web            # dashboard
flatsat doctor         # diagnóstico
flatsat devices        # la placa
flatsat status
flatsat sniff -n 3
```

| Equipo | Qué instala el instalador |
|---|---|
| Sin política restrictiva | El binario autónomo (20 MB, sin Python) |
| Con Device Guard / AppLocker | Código + entorno virtual + lanzadores `.cmd` |

En los dos casos la instalación vive en `<proyecto>\flatsat-gs`, y
`flatsat-gs uninstall` la deja igual de limpia.

> **El antivirus puede bloquear el binario recién compilado durante unos
> segundos** mientras lo escanea. Espera y reintenta; si sigue bloqueado, el
> instalador usará la versión con Python automáticamente.

### 3.4 Verificar

```bat
flatsat version
flatsat devices
flatsat doctor
```

Abre una **terminal nueva** después de instalar: el PATH se lee al arrancar la
shell. Si aun así no lo encuentra, el instalador dejó además unos lanzadores en
`%LOCALAPPDATA%\Microsoft\WindowsApps`, que ya está en el PATH de Windows.

---

## 4. Linux

### 4.1 Dependencias del sistema

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

Sin compilador: todas las dependencias tienen ruedas precompiladas.

### 4.2 Compilar el binario autónomo

```bash
cd ~/ruta/al/proyecto/flatsat-ground-station
./compile_app.sh
```

Para un **AppImage** (un solo fichero ejecutable):

```bash
./compile_app.sh --bundle
```

Necesita `appimagetool` en el PATH; si no está, el script genera un `.tar.gz`
en su lugar.

Resultado: `dist/flatsat-gs` (o `dist/flatsat-gs-x86_64.AppImage`).

### 4.3 Instalar

```bash
./dist/flatsat-gs install
```

O desde el código:

```bash
python3 flatsat_app.py install
```

La instalación crea:

```
flatsat-gs/
├── bin/          # flatsat-gs, flatsat-web, flatsat
├── db/           # base de datos de telemetría
├── venv/         # entorno virtual de la app
└── install-manifest.json
```

Y además symlinks en `~/.local/bin` (que debe estar en tu PATH):

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc   # o ~/.zshrc
source ~/.bashrc
```

Si `~/.local/bin` no está en el PATH, el instalador te lo avisa.

### 4.4 Verificar

```bash
flatsat version
flatsat devices
flatsat doctor
```

---

## 5. macOS

### 5.1 Requisitos

```bash
# Homebrew (si no lo tienes: https://brew.sh)
brew install python@3.11
```

### 5.2 Compilar el binario autónomo

```bash
cd ~/ruta/al/proyecto/flatsat-ground-station
./compile_app.sh
```

Para el **bundle .app y el .dmg**:

```bash
./compile_app.sh --bundle
```

Resultado:
- `dist/flatsat-gs` — el ejecutable
- `dist/FlatSat GS.app` — la aplicación para doble clic (con icono)
- `dist/FlatSatGS-<versión>.dmg` — el disco instalable

### 5.3 Instalar

```bash
./dist/flatsat-gs install
```

O copia el `.app` a `~/Applications`:

```bash
cp -R "dist/FlatSat GS.app" ~/Applications/
```

> La base de datos va a la carpeta del proyecto (`flatsat-gs/db/`). Si
> instalas el `.app` en `/Applications` (que es de sólo lectura para el
> usuario), la app la guarda en `~/.flatsat-ground-station/` automáticamente.

### 5.4 El puerto 5000

macOS Monterey+ usa el 5000 para **AirPlay Receiver**, así que el dashboard
puede no arrancar:

```bash
flatsat web --port 5001
# o de forma permanente:
export FLATSAT_PORT=5001
```

### 5.5 Permisos del puerto serie

macOS pide permiso explícito para los puertos serie:

*Ajustes del Sistema → Privacidad y seguridad → Puertos de serie* → añade
Terminal (o iTerm) y tu editor.

Verifica con:

```bash
flatsat doctor
```

Los puertos del FlatSat aparecen como `/dev/cu.usbmodem*` (o `/dev/tty.*`).

### 5.6 Verificar

```bash
flatsat version
flatsat devices
flatsat doctor
```

---

## 6. Comprobaciones por plataforma

| | Windows | Linux | macOS |
|---|---|---|---|
| Compilar | `.\run.cmd build` | `./compile_app.sh` | `./compile_app.sh` |
| Bundle extra | — | AppImage (`--bundle`) | `.app` + `.dmg` (`--bundle`) |
| Instalar | `dist\flatsat-gs.exe install` | `./dist/flatsat-gs install` | `./dist/flatsat-gs install` |
| Comandos | `flatsat`, `flatsat-web`, `flatsat-gs` | iguales | iguales |
| Permisos serie | Ninguno | grupo `dialout` | permiso de macOS |
| Puerto por defecto | 5000 | 5000 | **5001** (AirPlay) |

---

## 7. Permisos de los puertos serie (Linux)

La placa expone tres endpoints CDC-ACM: **Radio 0**, **Radio 1** y **Shell**.

Opción A — grupo `dialout`:

```bash
sudo usermod -aG dialout $USER
# cierra la sesión y vuelve a entrar
```

Opción B — regla udev (crea symlinks estables en `/dev/flatsat/` y no
necesita `dialout`):

```bash
sudo cp scripts/flatsat-udev.rules /etc/udev/rules.d/99-flatsat.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Comprueba con `flatsat doctor`.

---

## 8. Desinstalar

```bash
flatsat-gs uninstall
```

Elimina la carpeta `flatsat-gs/` de dentro del proyecto, los accesos directos,
la entrada del PATH (**restaurando el PATH original**) y los alias de la shell
(perfil de PowerShell, completados de bash/zsh/fish).

Si queda algo:

```
[!] Si la carpeta sigue ahí, es que la webapp o el CLI están corriendo. Ciérralos y ejecuta 'flatsat-gs uninstall' de nuevo.
```

En Windows no se puede borrar un ejecutable en uso: cierra la webapp y el CLI
antes de desinstalar.

Variantes:

```bash
flatsat-gs uninstall --keep-data   # conserva la base de datos de telemetría
```

---

## 9. Publicar una release

```bash
# Linux / macOS
./compile_app.sh --bundle
# Windows
.\run.cmd build
```

Adjunta a la release de GitHub:

| Artefacto | Sistema |
|---|---|
| `dist/flatsat-gs` | Linux / macOS |
| `dist/flatsat-gs-x86_64.AppImage` | Linux (AppImage) |
| `dist/FlatSat GS.app` | macOS |
| `dist/FlatSatGS-<ver>.dmg` | macOS |
| `dist/flatsat-gs.exe` | Windows |

Si prefieres un instalador `.exe` para Windows (que aparece en *Agregar o
quitar programas*), edita `installer/flatsat_installer.iss`… o simplemente
comparte el binario: **se instala a sí mismo** con `flatsat-gs install`.

---

## 10. Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `no se reconoce como un cmdlet` | PowerShell no ejecuta ficheros del directorio actual sin `.\` | `.\run.cmd build` |
| `was blocked by your organization's Device Guard policy` | Política de Application Control | El instalador cae a la versión con Python solo |
| `no se encuentra un Python 3.9+ utilizable` | Python no está en el PATH, o es el alias de la Store | Instala Python marcando *"Add Python to PATH"*; usa `py -3` |
| `python3-venv` / `ensurepip` | Falta el módulo venv | `sudo apt install python3-venv` |
| El binario pesa 51 MB | Se compiló con el Python del sistema | Borra `build/` y recompila con el `.venv` del proyecto |
| `flatsat` no se encuentra | PATH old o `~/.local/bin` fuera del PATH | Abre terminal nueva; `export PATH="$HOME/.local/bin:$PATH"` |
| El puerto 5000 está ocupado (macOS) | AirPlay Receiver | `flatsat web --port 5001` |
| `flatsat devices` no ve la placa | Permisos del puerto serie | §7, y luego `flatsat doctor` |
| La webapp no muestra telemetría | Falta el cliente WebSocket (no hay internet) | Va incluido: `webapp/static/js/socket-client.js` |
| La carpeta no se borra al desinstalar | La webapp está corriendo | Ciérrala y repite |

---

## 11. Referencias

- [Guía de instalación](installation.md) — detalle por método
- [Probar el CLI](cli-testing.md) — checklist y problemas
- [Walkthrough del CTF](ctf_walkthrough_guide.md)
- [Plan de taller](curriculum-plan.md)
