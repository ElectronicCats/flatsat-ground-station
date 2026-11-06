# FlatSat Ground Station

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Platforms](https://img.shields.io/badge/windows%20%7C%20linux%20%7C%20macos-blue.svg)](docs/building.md)
[![Build Status](https://img.shields.io/badge/tests-462%20passed-success.svg)](tests/)

A modern, web-based and CLI ground station software for communicating with **PwnSat2 FlatSat** satellite hardware and **CatSniffer** LoRa transceivers. Designed for space systems engineering, satellite communications research, and cybersecurity CTF (Capture The Flag) educational labs.

---

## 🌟 Features

* **Real-time Web Dashboard**: Interactive telemetry telemetry monitoring, battery/sensor gauges, and live WebSocket graph streaming.
* **Interactive CLI Tool (`flatsat`)**: Rich-powered terminal interface for device discovery, RF sniffing, payload forging, and shell access.
* **CCSDS Space Packet Protocol**: Native support for CCSDS 133.0-B-2 primary/secondary packet headers and CRC-16-CCITT integrity checks.
* **Space Data Link Security (SDLS)**: AES-128-CTR payload encryption with MET-derived IVs and XOR key transformations.
* **Hardware & Simulation Modes**: Operates seamlessly in simulated mock mode without hardware, or connects to real USB hardware transceivers (RP2040 / SX1262).
* **Multi-Level CTF Cybersecurity Lab**: Built-in 3-level difficulty system (Web, CCSDS Protocol, Firmware/Crypto) for space cybersecurity training.
* **One application, no containers**: Installs itself in your user profile on Windows, Linux and macOS. No Docker, no virtual machine, no admin rights.

---

## 🚀 Quick Start

### La aplicación (sin Docker, sin máquina virtual, sin `pip install`)

**FlatSat Ground Station es una sola aplicación con dos caras: el dashboard
web y el CLI.** Se instala una vez en tu perfil de usuario, se usa sin
privilegios de administrador y se desinstala dejando el sistema limpio.

```bash
git clone https://github.com/ElectronicCats/flatsat-ground-station.git
cd flatsat-ground-station

python3 flatsat_app.py            # Linux / macOS  → dashboard web
python flatsat_app.py             # Windows        → dashboard web
run.cmd                           # Windows: detecta solo el Python correcto
```

> **En Windows**, si `python` abre la Microsoft Store es que el alias de la
> Store está tapando tu Python: usa `py flatsat_app.py` o `run.cmd`.

La primera ejecución comprueba qué falta, crea un entorno virtual local e
instala **7 dependencias** (todas con ruedas precompiladas: no hace falta
compilador). Las siguientes reutilizan ese entorno. Después:

| Comando | Descripción |
|---|---|
| `python flatsat_app.py` | Dashboard web → <http://127.0.0.1:5000> (abre el navegador) |
| `python flatsat_app.py cli` | CLI interactivo de la estación |
| `python flatsat_app.py doctor` | Diagnóstico del entorno y de los puertos serie |
| `python flatsat_app.py install` | Instala la app en el perfil del usuario (comandos `flatsat`, `flatsat-web`, `flatsat-gs`) |
| `python flatsat_app.py uninstall` | Desinstala la app y restaura el PATH |

Opciones del dashboard:

| Opción | Descripción |
|---|---|
| `--port 5001` | Puerto alternativo (macOS usa 5000 para AirPlay) |
| `--level 3` | Nivel CTF (1 fácil, 2 medio, 3 difícil) |
| `--no-mock` | No iniciar la telemetría simulada |
| `--no-browser` | No abrir el navegador automáticamente |

#### Instalación permanente (una vez, y a salvo)

```bash
python flatsat_app.py install
```

Esto deja **tres ejecutables reales** en el PATH del usuario (en Windows son
*hard links* al mismo fichero, así que no duplican los 20 MB):

* `flatsat.exe` → el CLI: `flatsat devices`, `flatsat status`, `flatsat web`…
* `flatsat-web.exe` → el dashboard directamente
* `flatsat-gs.exe` → la aplicación completa (dashboard + CLI + diagnóstico)

Y además, el CLI incluye los dos comandos que usarás cada día:

```bash
flatsat web            # abre el dashboard en el navegador
flatsat doctor         # diagnóstico: entorno, puertos serie y alias
```

Y los de la propia aplicación:

```bash
flatsat version        # versión instalada
flatsat help           # la ayuda completa
flatsat install        # instala (CLI en el PATH, accesos directos, datos)
flatsat uninstall      # desinstala y restaura el PATH
```

La instalación vive **dentro de la carpeta del proyecto**, en `flatsat-gs/`
(ejecutables, base de datos y entorno virtual), así que se puede mover,
copiar a otro equipo o borrar con un solo comando. También se crean
accesos directos con icono en el menú Inicio (Windows) o en
`~/.local/share/applications` (Linux).

La CLI queda como un comando normal en cualquier terminal (`flatsat`,
`flatsat-web`, `flatsat-gs`).

Al desinstalar se borra todo: los ejecutables, los accesos directos, la
entrada del PATH (restaurando el original) y **los alias de la shell** (las
funciones del perfil de PowerShell y los completados de bash/zsh/fish).

Para desinstalar:

```bash
flatsat-gs uninstall
```

Se borra todo lo que se creó (binarios, entorno virtual, accesos directos), se
restaura el PATH original y se limpian los alias del perfil de PowerShell
(solo si el repositorio ya no existe: si sigue ahí, los alias siguen
funcionando y no se tocan). Con `--keep-data` se conserva la base de datos
de telemetría en `~/.flatsat-ground-station/db/`.

> **Si tu empresa bloquea los ejecutables sin firmar** (Device Guard /
> AppLocker: *"was blocked by your organization's Device Guard policy"*),
> no hace falta hacer nada: el instalador lo detecta y usa automáticamente
> la vía con Python. Los comandos son idénticos en cualquier equipo.

> **¿Y si no tengo Python?** Usa el binario autónomo `flatsat-gs`, que lleva
> dentro Python, Flask, SocketIO, pyserial, click, rich y pycryptodome:
>
> ```bash
> # Está en dist/ (artefacto de compilación, no viaja en el git clone)
> .\run.cmd build            # Windows  → dist\flatsat-gs.exe
> ./compile_app.sh           # Linux/macOS → dist/flatsat-gs
>
> dist\flatsat-gs.exe              # se instala solo y abre el dashboard
> dist\flatsat-gs.exe cli          # CLI
> dist\flatsat-gs.exe install      # instalar sin arrancar
> ```
>
> En PowerShell, los ficheros de la carpeta actual necesitan el prefijo `.\`.
>
> También se publica en las
> [GitHub Releases](https://github.com/ElectronicCats/flatsat-ground-station/releases)
> cuando se adjuntan los assets de la release.

<details>
<summary>Instalación manual mínima (sin el launcher)</summary>

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-app.txt   # 7 paquetes: Flask, Flask-SocketIO,
                                      # simple-websocket, click, rich,
                                      # pyserial, pycryptodome
python3 -m webapp.app                 # dashboard
python3 flatsat.py                    # CLI
```

</details>

---

### Default Credentials:
* **Admin:** `admin` / `password`
* **Operator:** `operator` / `operator`

---

### Run Natively with Python

#### Linux (Ubuntu/Debian/Fedora)
```bash
git clone https://github.com/ElectronicCats/flatsat-ground-station.git
cd flatsat-ground-station

# Create & activate virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies (7 packages, all with pre-built wheels)
pip install -r requirements-app.txt

# Grant serial port permissions (logout & login required)
sudo usermod -aG dialout $USER

# Set CTF Level (1: Easy, 2: Medium, 3: Hard)
export FLATSAT_LEVEL=1

# Start Ground Station WebApp
python3 -m webapp.app
```

#### macOS
> **Note for macOS:** macOS Monterey and later uses port 5000 for AirPlay Receiver. Use `export FLATSAT_PORT=5001` to run on port 5001.

```bash
git clone https://github.com/ElectronicCats/flatsat-ground-station.git
cd flatsat-ground-station

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-app.txt

export FLATSAT_LEVEL=1
export FLATSAT_PORT=5001
python3 -m webapp.app
```

#### Windows (PowerShell / Command Prompt)
Run `run.cmd` (it finds a working Python for you) or use PowerShell:

```powershell
git clone https://github.com/ElectronicCats/flatsat-ground-station.git
cd flatsat-ground-station

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-app.txt

$env:FLATSAT_LEVEL="1"
python flatsat_app.py
```

---

## 🖥️ Interactive CLI (`flatsat`)

The repository includes a full-featured terminal CLI for satellite operators.
It is part of the same application as the dashboard: same install, same
commands, no extra dependencies.

```bash
# From the repository (no installation needed — it bootstraps itself)
python flatsat_app.py cli
python flatsat.py                    # same thing, classic entry point

# After 'flatsat_app.py install' the command is already on the PATH
flatsat

# Standalone CLI commands:
flatsat devices                # Scan and list connected USB devices
flatsat status                 # Query board status and firmware version
flatsat sniff -n 10 -o cap.json  # Capture 10 CCSDS frames to a file
flatsat tc 0x20 --text "PING"  # Send a PING telecommand frame
```

### Using the CLI while the webapp holds the hardware

The webapp owns the serial ports, so the CLI cannot open them at the same
time. Use `-w/--web` to drive the running webapp through its REST API:

```bash
flatsat-web                     # webapp connects the board

flatsat -w status               # state read through the webapp
flatsat -w devices              # which board the webapp has connected
flatsat -w sniff -n 10          # the frames the webapp is receiving
flatsat -w tc 0x20 --text PING
```

Any terminal works (cmd, PowerShell, macOS Terminal, bash) — `-w` is just an
HTTP client. For a webapp on another port or host:
`flatsat -w --web-url http://192.168.1.20:5001 status`.

Want both in the *same* terminal? Start the webapp in the background:

```bash
flatsat-web --background     # returns the prompt, server keeps running
flatsat -w status            # talk to it from the same terminal
```

The alternative is to press **Disconnect** in the dashboard and use the CLI
directly on the serial port.

> **Checklist de pruebas del CLI**: [docs/cli-testing.md](docs/cli-testing.md)

```bash
flatsat devices             # ¿está la placa y con qué puertos?
flatsat status              # firmware, modo, estado del radio
flatsat sensors             # sensores en vivo
flatsat sniff -n 3 -t 15    # capturar tramas CCSDS
```

---

## 🛰️ Hardware Setup & Modes

### Supported Hardware
1. **PwnSat2 / FlatSat Hardware** (Dual LoRa Radios: RX + TX, USB VID:PID `0x1209:0xBABC`).
2. **CatSniffer Hardware** (Single LoRa Radio: RX/TX overlay mode).

### Diagnosing the serial ports (native install)

If the board is not detected, run the diagnostic — it lists every serial port,
flags the FlatSat/CatSniffer ones, tries to open them and tells you exactly
what is blocking access:

```bash
flatsat-gs doctor                # installed app
python flatsat_app.py doctor     # from the repository
python scripts/serial_doctor.py  # standalone script
```

**Linux** — grant access to the USB serial devices:

```bash
sudo usermod -aG dialout $USER     # log out and back in afterwards
```

or install the udev rule, which also creates stable symlinks in
`/dev/flatsat/{radio0,radio1,shell}` and works without `dialout`:

```bash
sudo cp scripts/flatsat-udev.rules /etc/udev/rules.d/99-flatsat.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

**Windows** — no extra step is needed; the CDC-ACM ports show up as `COMx` and
`COM10+` are handled automatically by the port mapper.

**macOS** — grant access to the USB serial device in *System Settings →
Privacy & Security → Serial Port* (or use `/dev/cu.usbmodem*`).

---

## 🎯 CTF Cybersecurity Challenges

The laboratory supports 3 progressive security training levels controlled by `FLATSAT_LEVEL`:

* **Level 1 (Easy - Web & Cleartext)**: API enumeration, SQL injection, Base64 session forgery, cleartext radio telecommands.
* **Level 2 (Medium - Systems & CCSDS)**: Local File Inclusion (LFI), Remote Code Execution (RCE), IDOR, CCSDS Space Packet framing.
* **Level 3 (Hard - Firmware & Crypto)**: HMAC-SHA256 session signatures, SDLS AES-128-CTR payload encryption, RP2040 stack buffer overflows.

For detailed challenge solutions, hints, and curriculum plans:
* 📖 [CTF Challenge & Walkthrough Guide](docs/ctf_walkthrough_guide.md)
* 🎓 [Training Curriculum & Workshop Plan](docs/curriculum-plan.md)

For a step-by-step installation guide (all platforms, permissions, troubleshooting
and uninstall):
* 🧭 **[Installation Guide](docs/installation.md)**
* 🔨 **[Build & Install Guide](docs/building.md)** — compile the standalone binary and install it on Windows, Linux and macOS

---

## 📦 Maintainer Guide: Publishing GitHub Releases

When preparing an official GitHub release for **FlatSat Ground Station**:

### 1. Tag a New Release
```bash
git tag -a v1.0.0 -m "FlatSat Ground Station Release v1.0.0"
git push origin v1.0.0
```

### 2. Build the Standalone App (recommended for users)
There is **one spec and one binary**. This produces a single `flatsat-gs`
executable with Python, Flask, SocketIO, pyserial, click, rich and
pycryptodome bundled inside — the end user needs **no Python and no pip**:
```bash
# On Linux/macOS:
./compile_app.sh                 # just the binary
./compile_app.sh --bundle        # + .app/.dmg on macOS, + AppImage on Linux

# On Windows:
.\run.cmd build                 # -> dist\flatsat-gs.exe
```

---

## 📁 Repository Structure

```
flatsat-ground-station/
├── modules/                # All application code
│   ├── core/               # CLI, CCSDS/SDLS, device drivers, RF bridge
│   ├── utils/              # Rich output helpers, banner, version
│   ├── firmware/           # Firmware diagnostic checks
│   └── webapp/             # Flask & SocketIO presentation dashboard
├── cli/                    # Deprecated shims -> modules/ (kept for old imports)
├── core/                   # Deprecated shims -> modules/core/
├── webapp/                 # Deprecated shims -> modules/webapp/
├── db/                     # SQLite database models & seed files
├── docs/                   # Documentation & CTF walkthrough guides
├── scripts/                # Installation and system helper scripts
├── tests/                  # Pytest unit & integration test suite
├── toolkit/                # Standalone RF analysis & security tools
└── LICENSE                 # Open-source MIT License
```

---

## 📜 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

Developed with ❤️ by **[Electronic Cats](https://electroniccats.com)**.
