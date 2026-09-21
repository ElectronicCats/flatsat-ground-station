# FlatSat Ground Station

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Docker Supported](https://img.shields.io/badge/docker-ready-brightgreen.svg)](Dockerfile)
[![Build Status](https://img.shields.io/badge/tests-215%20passed-success.svg)](tests/)

A modern, web-based and CLI ground station software for communicating with **PwnSat2 FlatSat** satellite hardware and **CatSniffer** LoRa transceivers. Designed for space systems engineering, satellite communications research, and cybersecurity CTF (Capture The Flag) educational labs.

---

## 🌟 Features

* **Real-time Web Dashboard**: Interactive telemetry telemetry monitoring, battery/sensor gauges, and live WebSocket graph streaming.
* **Interactive CLI Tool (`flatsat`)**: Rich-powered terminal interface for device discovery, RF sniffing, payload forging, and shell access.
* **CCSDS Space Packet Protocol**: Native support for CCSDS 133.0-B-2 primary/secondary packet headers and CRC-16-CCITT integrity checks.
* **Space Data Link Security (SDLS)**: AES-128-CTR payload encryption with MET-derived IVs and XOR key transformations.
* **Hardware & Simulation Modes**: Operates seamlessly in simulated mock mode without hardware, or connects to real USB hardware transceivers (RP2040 / SX1262).
* **Multi-Level CTF Cybersecurity Lab**: Built-in 3-level difficulty system (Web, CCSDS Protocol, Firmware/Crypto) for space cybersecurity training.

---

## 🚀 Quick Start

### Option 1: Run with Docker Compose (Recommended)

Docker provides an isolated, cross-platform environment ready out-of-the-box.

```bash
# 1. Clone repository
git clone https://github.com/ElectronicCats/flatsat-ground-station.git
cd flatsat-ground-station

# 2. Create local database directory
mkdir -p db

# 3. Launch container
docker compose up -d
```

Open your browser at **[http://localhost:5000](http://localhost:5000)**.

#### Default Credentials:
* **Admin:** `admin` / `password`
* **Operator:** `operator` / `operator`

---

### Option 2: Run Natively with Python

#### Linux (Ubuntu/Debian/Fedora)
```bash
git clone https://github.com/ElectronicCats/flatsat-ground-station.git
cd flatsat-ground-station

# Create & activate virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

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
pip install -r requirements.txt

export FLATSAT_LEVEL=1
export FLATSAT_PORT=5001
python3 -m webapp.app
```

#### Windows (PowerShell / Command Prompt)
Double-click `install_windows.bat` or run in PowerShell:

```powershell
git clone https://github.com/ElectronicCats/flatsat-ground-station.git
cd flatsat-ground-station

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .

$env:FLATSAT_LEVEL="1"
python -m webapp.app
```

---

## 🖥️ Interactive CLI (`flatsat`)

The repository includes a full-featured terminal CLI for satellite operators.

```bash
# Install CLI in editable mode
pip install -e .

# Launch interactive terminal shell
flatsat

# Standalone CLI commands:
flatsat devices               # Scan and list connected USB devices
flatsat status                # Query ground station status
flatsat transmit --opcode 0x10 # Send PING telecommand frame
```

---

## Getting Started (Guía rápida con la CLI)

Guía paso a paso para dejar el sistema en **modo fácil** (dificultad 1), configurar una placa como **Ground Station** (`gs`) y otra como **Satélite** (`sat`) desde la CLI, validar cada configuración y ejecutar todos los comandos.

> **Ejecución:** si no tienes el alias global `flatsat` instalado, ejecuta el CLI directamente con el intérprete del entorno virtual:
> ```bash
> # Linux/macOS
> source .venv/bin/activate && python flatsat_cli.py ...
> # Windows (PowerShell / CMD)
> .venv\Scripts\activate && python flatsat_cli.py ...
> ```

### Paso 0 — Poner todo en modo fácil (dificultad 1)

**Modo fácil = nivel 1 (CTF Level 1):** la radio transmite en texto plano (sin cifrado SDLS), no requiere claves ni manejo de CCSDS/SDLS, y las vulnerabilidades web están totalmente explotables. Se configura en dos sitios:

1. **En la webapp:** define `FLATSAT_LEVEL=1` antes de arrancar (por defecto ya es `1`; niveles: `1` Fácil, `2` Medio, `3` Difícil):
   - Linux/macOS: `export FLATSAT_LEVEL=1`
   - Windows (PowerShell): `$env:FLATSAT_LEVEL="1"`
   - Windows (CMD): `set FLATSAT_LEVEL=1`
2. **En la(s) placa(s) FlatSat:** fija el nivel de seguridad del satélite desde la CLI:
   ```bash
   flatsat difficulty 1
   ```

**Validar el modo fácil:**
```bash
flatsat difficulty    # debe responder: Security Level: 1
flatsat status        # muestra la dificultad y el estado de las radios
```

### Paso 1 — Configurar la placa como Ground Station (`mode gs`)

Conecta la placa que hará de **estación terrena** y ejecuta:

```bash
flatsat mode gs
```

Esto envía a la placa la secuencia `mode gs` + `lora_apply ALL` + `lora_mode ALL command`: el firmware pasa a rol de estación terrena y las radios quedan en modo *command* (reciben telemetría y envían telecomandos). Al terminar, la placa parpadea sus LEDs para identificarse.

**Validación:**
```bash
flatsat mode               # consulta el modo actual (debe decir rol ground_station)
flatsat status             # el rol y las radios deben aparecer en command
flatsat config --radio 0   # muestra la configuración LoRa de la radio local (RX)
flatsat sniff -t 15        # escucha en vivo qué capta la GS por el aire
```

### Paso 2 — Configurar la placa como Satélite (`mode sat`)

Conecta la placa que hará de **satélite** (la que transmite la telemetría) y ejecuta:

```bash
flatsat mode sat
```

Esto envía a la placa la secuencia `mode sat` + `lora_mode ALL stream`: el firmware pasa a rol de satélite y mantiene **ambas** radios en modo *stream* para emitir telemetría.

> **Importante:** un satélite debe mantener **las dos radios en `stream`**. El firmware asocia el rol a `lora_mode`: si pones cualquier radio en `command`, la placa deja de comportarse como satélite. No uses `flatsat config --radio 0 --mode command` en una placa configurada como satélite.

**Validación:**
```bash
flatsat mode               # consulta el modo actual (debe decir rol satellite)
flatsat status             # el rol y las radios deben aparecer en stream
flatsat sensors            # lectura de BME280/LIS2DH: confirma que el satélite responde
flatsat flight nominal     # entra en estado nominal y transmite telemetría por RF
```

### Paso 3 — Comandos y ejemplos (modo fácil)

| Comando | Descripción | Ejemplo |
|---|---|---|
| `flatsat devices` | Lista las placas FlatSat conectadas (puertos y salud) | `flatsat devices` |
| `flatsat status` | Firmware, versión de Git, fecha de build, radio activa y estado de los transceptores | `flatsat status` |
| `flatsat sensors` | Lecturas de telemetría (BME280: temperatura, presión, humedad; LIS2DH: acelerómetro) | `flatsat sensors` |
| `flatsat mode [gs\|sat]` | Cambia o consulta el modo operativo | `flatsat mode` · `flatsat mode sat` · `flatsat mode gs` |
| `flatsat config --radio 0\|1` | Consulta la configuración LoRa de la radio indicada | `flatsat config --radio 0` |
| `flatsat config ... --apply` | Prepara (stages) y aplica los cambios LoRa al chip de la radio | `flatsat config --radio 0 --freq 915000000 --sf 7 --bw 125 --power 18 --apply` |
| `flatsat flight [idle\|nominal\|safe\|debug]` | Consulta o cambia el estado de vuelo del satélite | `flatsat flight nominal` · `flatsat flight idle` |
| `flatsat difficulty [1\|2\|3]` | Nivel de seguridad del CTF (1 = fácil) | `flatsat difficulty 1` |
| `flatsat color R G B` | Color RGB del LED NeoPixel (canales de 0 a 255) | `flatsat color 0 255 0` |
| `flatsat identify` | Hace parpadear los LEDs para ubicar la placa físicamente | `flatsat identify` |
| `flatsat reboot` | Reinicia a BOOTSEL (monta el volumen `RPI-RP2`) | `flatsat reboot` |
| `flatsat cmd "[comando]"` | Envía un comando crudo al shell de la placa | `flatsat cmd "sensors"` |
| `flatsat console` | Consola interactiva persistente con la placa | `flatsat console` |
| `flatsat sniff [-t seg] [-o archivo]` | Captura y muestra tramas CCSDS del aire (Radio 0 por defecto) | `flatsat sniff -t 30` · `flatsat sniff -o captura.json` |
| `flatsat replay archivo` | Reenvía por RF tramas guardadas con `sniff` | `flatsat replay captura.json` |
| `flatsat transmit "hex"` / `--text` | Transmite un payload (hex o texto) por RF | `flatsat transmit --text "HOLA SAT"` |
| `flatsat completion install` | Instala el autocompletado de tab (bash/zsh/fish) | `flatsat completion install` |

### Paso 4 — Validación de extremo a extremo

Con una placa en `gs` y otra en `sat`, ambas en dificultad 1:

```bash
flatsat sniff -t 30     # en la GS deben aparecer tramas TM (telemetría) del satélite
flatsat flight idle     # desde la GS envía el telecomando "idle" al satélite por RF
flatsat mode            # verifica que el rol de cada placa sigue siendo el correcto
```

---

## 🛰️ Hardware Setup & Modes

### Supported Hardware
1. **PwnSat2 / FlatSat Hardware** (Dual LoRa Radios: RX + TX, USB VID:PID `0x1209:0xBABC`).
2. **CatSniffer Hardware** (Single LoRa Radio: RX/TX overlay mode).

### Hardware Pass-Through in Docker
To enable physical USB hardware scanning inside Docker:

Uncomment the privileged hardware section in `docker-compose.yml`:
```yaml
    privileged: true
    volumes:
      - ./db:/app/db
      - /dev:/dev
      - /sys:/sys:ro
      - /run/udev:/run/udev:ro
```
Then restart Docker Compose: `docker compose up -d`.

---

## 🎯 CTF Cybersecurity Challenges

The laboratory supports 3 progressive security training levels controlled by `FLATSAT_LEVEL`:

* **Level 1 (Easy - Web & Cleartext)**: API enumeration, SQL injection, Base64 session forgery, cleartext radio telecommands.
* **Level 2 (Medium - Systems & CCSDS)**: Local File Inclusion (LFI), Remote Code Execution (RCE), IDOR, CCSDS Space Packet framing.
* **Level 3 (Hard - Firmware & Crypto)**: HMAC-SHA256 session signatures, SDLS AES-128-CTR payload encryption, RP2040 stack buffer overflows.

For detailed challenge solutions, hints, and curriculum plans:
* 📖 [CTF Challenge & Walkthrough Guide](docs/ctf_walkthrough_guide.md)
* 🎓 [Training Curriculum & Workshop Plan](docs/curriculum-plan.md)

---

## 📦 Maintainer Guide: Publishing GitHub Releases

When preparing an official GitHub release for **FlatSat Ground Station**:

### 1. Tag a New Release
```bash
git tag -a v1.0.0 -m "FlatSat Ground Station Release v1.0.0"
git push origin v1.0.0
```

### 2. Export Offline Docker Asset (Optional Release Attachment)
To attach an offline Docker image archive to the GitHub Release:
```bash
docker build -t flatsat-gs:latest .
docker save flatsat-gs:latest | gzip > flatsat-gs.tar.gz
```
*Upload `flatsat-gs.tar.gz` and `docker-compose.yml` to the Release Assets section.*

### 3. Build Standalone CLI Executables
To generate standalone binaries for Linux and Windows:
```bash
# On Linux/macOS:
./compile.sh

# On Windows:
build_windows.bat
```
*Executables will be generated in `dist/` and can be attached to the release.*

---

## 📁 Repository Structure

```
flatsat-ground-station/
├── cli/                    # Click-based CLI application (`flatsat` command)
├── core/                   # Core protocol engine (CCSDS, SDLS, device drivers, bridge)
├── db/                     # SQLite database models & seed files
├── docs/                   # Documentation & CTF walkthrough guides
├── scripts/                # Installation and system helper scripts
├── tests/                  # Pytest unit & integration test suite (215 tests)
├── toolkit/                # Standalone RF analysis & security tools
├── webapp/                 # Flask & SocketIO presentation dashboard
├── Dockerfile              # Container definition with gosu entrypoint
├── docker-compose.yml      # Container orchestration
├── docker-entrypoint.sh    # Permission-safe entrypoint script
└── LICENSE                 # Open-source MIT License
```

---

## 📜 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

Developed with ❤️ by **[Electronic Cats](https://electroniccats.com)**.
