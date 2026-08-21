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
