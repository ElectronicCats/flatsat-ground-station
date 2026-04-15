# PwnSat2 Ground Station

A Flask-based ground station for communicating with PwnSat2 FlatSat hardware via LoRa radio. Designed for educational CTF (Capture The Flag) exercises where participants interact with real satellite hardware through a web dashboard.

## Requirements

- Python 3.11+
- pip

Optional for hardware mode:
- PwnSat2 FlatSat device (USB VID:PID `0x1209:0xBABC`)
- Linux recommended for USB device discovery (uses `pyudev`)

## Quick Start

```bash
git clone <repo-url>
cd flatsat-ground-station
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m webapp.app
```

Open `http://localhost:5000` in your browser.

The database is created automatically on first run. No manual setup needed.

> **Credentials:** Ask your instructor for login details.

### Simulated Mode

Click **Simulate** on the dashboard to generate mock telemetry without hardware. Useful for development and CTF setup.

### Hardware Mode

1. Connect a FlatSat device via USB
2. Click **Scan USB** on the dashboard
3. Select the device and click **Connect**

> **Linux USB permissions:** If the device is not detected, you may need to add a udev rule or run with appropriate permissions. See [Troubleshooting](#troubleshooting).

## Docker

```bash
docker compose up
```

Open `http://localhost:5000`. To use hardware mode, ensure the FlatSat is connected before starting the container.

See [docker-compose.yml](docker-compose.yml) for USB device mapping configuration.

## Architecture

```
browser  <->  webapp/ (Flask + SocketIO)  <->  core/ (protocol + serial)  <->  FlatSat USB
                 |
              db/ (SQLite)
```

### Core Library (`core/`)

| Module             | Purpose                                           |
|--------------------|---------------------------------------------------|
| `ccsds.py`         | CCSDS Space Packet encoder/decoder with SDLS       |
| `serial_manager.py`| USB device discovery by VID:PID                    |
| `device.py`        | Threadsafe serial wrapper for 3 CDC endpoints      |
| `telemetry.py`     | Telemetry payload decoder (Heartbeat, BME280, LIS2DH) |
| `telecommand.py`   | Telecommand frame builder with SDLS encryption     |
| `state.py`         | Ground station state machine (IDLE/HARDWARE/SIMULATED) |
| `shell_parser.py`  | Firmware shell response parsers                    |
| `constants.py`     | Opcode definitions and protocol constants          |

### Web Application (`webapp/`)

| Module          | Purpose                                    |
|-----------------|--------------------------------------------|
| `app.py`        | Flask routes, API endpoints, SocketIO      |
| `auth.py`       | Authentication (MD5 + base64 tokens)       |
| `db.py`         | SQLite schema and helpers                  |
| `radio_bridge.py`| Serial bridge for send operations         |
| `seed.py`       | Database seed data                         |
| `config.py`     | Flask configuration                        |

### Database (`db/`)

SQLite with tables: `users`, `telemetry`, `radio_config`, `secrets`, `logs`. Created automatically on first run.

## Webapp Pages

- **Dashboard** (`/dashboard`) — Live telemetry via WebSocket, hardware control (scan/connect/simulate), telecommand panel
- **Satellite** (`/satellite`) — Satellite status, battery monitor, LoRa radio config (R0/R1), sensor readout, device controls
- **Config** (`/config`) — Radio configuration with DB persistence
- **Logs** (`/logs`) — System log viewer

## Toolkit

Standalone scripts for interacting with FlatSat from the command line. Located in `toolkit/`.

| Script | Category | Purpose |
|--------|----------|---------|
| `ccsds_tools.py` | Protocol | CCSDS frame parser/builder, TM decoders, SDLS encrypt/decrypt |
| `forge_command.py` | Command | Telecommand forger — build and send TC frames |
| `crack_xor.py` | Crypto | Known-plaintext attack to recover XOR key |
| `crack_aes.py` | Crypto | AES key recovery via crypto oracle chosen-plaintext attack |
| `replay_capture.py` | RF | Capture and replay CCSDS frames over LoRa |
| `rf_scanner.py` | RF | LoRa frequency scanner — find the satellite's downlink |
| `frame_fuzzer.py` | Protocol | Mutate CCSDS fields to find parser bugs |
| `seq_predict.py` | Protocol | Predict sequence counters to bypass anti-replay |
| `fw_dumper.py` | Firmware | Dump memory via DIAG_MEMORY and analyze firmware binaries |
| `bus_sniffer.py` | Hardware | Decode SPI/I2C/UART captures from logic analyzers |
| `power_analysis.py` | Hardware | Simple/differential power analysis from oscilloscope traces |
| `neopixel_decode.py` | Mission | Decode covert channel data from Neopixel LED sequences |

```bash
cd toolkit

# Parse a captured frame
python ccsds_tools.py parse <hex>

# Build and send a PING command
python forge_command.py ping --send /dev/ttyACM1

# Scan for the satellite frequency
python rf_scanner.py quick /dev/ttyACM0 /dev/ttyACM1

# Fuzz the frame parser
python frame_fuzzer.py offline

# Capture and replay frames
python replay_capture.py capture /dev/ttyACM1 capture.json 30
python replay_capture.py replay /dev/ttyACM1 capture.json --modify-seq
```

## Tests

```bash
pytest
```

189 tests covering the core library, webapp routes, and vulnerability checks.

## Directory Structure

```
├── core/                  # Protocol and hardware library
│   ├── ccsds.py
│   ├── constants.py
│   ├── device.py
│   ├── serial_manager.py
│   ├── shell_parser.py
│   ├── state.py
│   ├── telecommand.py
│   └── telemetry.py
├── webapp/                # Flask web application
│   ├── app.py
│   ├── auth.py
│   ├── config.py
│   ├── db.py
│   ├── radio_bridge.py
│   ├── seed.py
│   ├── static/
│   │   ├── css/           # Stylesheets
│   │   └── js/            # Client-side JavaScript
│   └── templates/         # Jinja2 HTML templates
├── toolkit/               # Standalone attack/analysis scripts (12 tools)
│   ├── ccsds_tools.py     # CCSDS protocol library
│   ├── forge_command.py   # TC frame forger
│   ├── crack_xor.py       # XOR key cracker
│   ├── crack_aes.py       # AES oracle attack
│   ├── replay_capture.py  # Frame capture/replay
│   ├── rf_scanner.py      # Frequency scanner
│   ├── frame_fuzzer.py    # Protocol fuzzer
│   ├── seq_predict.py     # Sequence predictor
│   ├── fw_dumper.py       # Memory dumper
│   ├── bus_sniffer.py     # Bus traffic decoder
│   ├── power_analysis.py  # Power trace analysis
│   └── neopixel_decode.py # Covert channel decoder
├── tests/                 # pytest test suite
├── db/                    # SQLite database files (auto-created)
├── docs/                  # Design specs and plans
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Troubleshooting

### FlatSat not detected on Linux

Add a udev rule for the device:

```bash
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1209", ATTR{idProduct}=="babc", MODE="0666"' | sudo tee /etc/udev/rules.d/99-pwnsat.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Reconnect the FlatSat after applying the rule.

### Port 5000 already in use

```bash
python -m webapp.app  # defaults to port 5000
```

Kill the existing process or change the port in `webapp/app.py`.

### Database issues

Delete `db/telemetry.db` and restart — it will be recreated with seed data automatically.
