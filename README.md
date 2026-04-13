# PwnSat2 Ground Station

A Flask-based ground station for communicating with PwnSat2 FlatSat hardware via LoRa radio. Designed for educational CTF (Capture The Flag) exercises where participants interact with real satellite hardware through a web dashboard.

## Requirements

- Python 3.11+
- pip

Optional for hardware mode:
- PwnSat2 FlatSat device (USB VID:PID `0x1209:0xBABC`)

## Installation and Usage

```bash
pip install -r requirements.txt
python -m webapp.app
```

The server starts at `http://localhost:5000`. Default credentials:

| User     | Password    | Role     |
|----------|-------------|----------|
| admin    | password    | admin    |
| operator | operator123 | operator |

### Simulated Mode

Click **Simulate** on the dashboard to generate mock telemetry without hardware. Useful for development and CTF setup.

### Hardware Mode

1. Connect a FlatSat device via USB
2. Click **Scan USB** on the dashboard
3. Select the device and click **Connect**

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

SQLite with four tables: `users`, `telemetry`, `radio_config`, `logs`.

## Webapp Pages

- **Dashboard** (`/dashboard`) — Live telemetry via WebSocket, hardware control (scan/connect/simulate), telecommand panel
- **Satellite** (`/satellite`) — Satellite status, battery monitor, LoRa radio config (R0/R1), sensor readout, device controls
- **Config** (`/config`) — Radio configuration with DB persistence
- **Logs** (`/logs`) — System log viewer

## Tests

```bash
pytest
```

155+ tests covering the core library, webapp routes, and vulnerability checks.

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
├── tests/                 # pytest test suite
├── db/                    # SQLite database files
├── docs/                  # Design specs and plans
└── requirements.txt
```
