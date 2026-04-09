# FlatSat Ground Station — Design Spec

## 1. Overview

Web-based ground station for the FlatSat v2 CTF platform. Two components:

- **core/** — shared Python library used by both the Textual TUI and the Flask webapp
- **webapp/** — Flask frontend, deliberately vulnerable (12 CTF challenges GS-01 to GS-12)

The Flask app simulates a satellite ground station with telemetry monitoring, telecommand sending, radio configuration, and system diagnostics. Participants exploit web vulnerabilities to compromise the ground station and pivot to the satellite.

## 2. Architecture

```
                    +---------------------+
                    |       core/         |
                    |  serial_manager.py  |
                    |  device.py          |
                    |  ccsds.py           |
                    |  telemetry.py       |
                    |  telecommand.py     |
                    |  state.py           |
                    |  constants.py       |
                    +---------+-----------+
                              |
                 +------------+------------+
                 |                         |
            async API                 sync API
                 |                         |
          +------+------+          +-------+-------+
          |    TUI      |          |    Flask      |
          |  (Textual)  |          |   (webapp/)   |
          |  other repo |          |   this repo   |
          +-------------+          +---------------+
```

### Core library (`core/`)

Shared, non-vulnerable Python library. Starts as a local directory, migrates to installable package (`pyproject.toml`) later.

**Modules:**

| Module | Source | Description |
|--------|--------|-------------|
| `serial_manager.py` | Adapted from TUI `discovery.py` + `hotplug.py` | Device discovery (VID/PID 0x1209:0xBABC), endpoint grouping (radio0, radio1, shell), hotplug detection (udev/IOKit) |
| `device.py` | Adapted from TUI `device.py` | Serial I/O with dual API: async (`await device.send_tc()`) for TUI, sync (`device.send_tc_sync()`) for Flask. Command queue, response parsing, mode switching |
| `constants.py` | Adapted from TUI `constants.py` | USB IDs, baud rates (115200), endpoint names, shell commands, enums (DeviceHealth, CommandStatus) |
| `ccsds.py` | New | CCSDS SPP frame builder/parser. Big-endian headers per CCSDS 133.0-B-2. SPACECRAFT_ID=0x02, idle payload="pwnsat2" |
| `telemetry.py` | New | TM frame decoder, field extraction (temp, pressure, humidity, accel), event callbacks for real-time streaming |
| `telecommand.py` | New | TC frame builder, APID routing, AES-128 encryption for privileged commands (TC_OP_PRIVILEGED 0xD0) |
| `state.py` | New | FlatSat state tracking: connection status, mode, difficulty, flight state. Auto-detect hardware vs mock mode |

**Mock mode:** When no FlatSat is connected via USB, core falls back to simulated telemetry generation and accepts commands without sending them. Auto-detected at startup via `serial_manager.discover_devices()`.

**Dual API pattern for device.py:**

```python
class FlatSatDevice:
    async def send_tc(self, apid, payload):
        """Async API for TUI (Textual/asyncio)"""
        frame = ccsds.build_tc(apid, payload)
        await self._serial.write_async(frame)

    def send_tc_sync(self, apid, payload):
        """Sync API for Flask"""
        frame = ccsds.build_tc(apid, payload)
        self._serial.write(frame)

    async def read_tm(self, timeout=5.0):
        """Async TM read for TUI"""
        ...

    def read_tm_sync(self, timeout=5.0):
        """Sync TM read for Flask"""
        ...
```

### Flask webapp (`webapp/`)

Deliberately vulnerable web application. 12 CTF challenges.

## 3. Repository Structure

```
flatsat-ground-station/
├── core/
│   ├── __init__.py
│   ├── serial_manager.py      # Discovery + hotplug
│   ├── device.py              # Serial I/O (sync + async)
│   ├── constants.py           # USB IDs, enums, commands
│   ├── ccsds.py               # CCSDS SPP build/parse
│   ├── telemetry.py           # TM decoder + callbacks
│   ├── telecommand.py         # TC builder + AES
│   └── state.py               # FlatSat state + mock mode
│
├── webapp/
│   ├── app.py                 # Flask app factory, routes, WebSocket
│   ├── config.py              # Flask config (hardcoded secrets)
│   ├── radio_bridge.py        # Sync wrapper over core.device (vuln target for GS-07/GS-08)
│   ├── seed.py                # DB seed script
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── commands.html
│   │   ├── logs.html
│   │   └── config.html
│   ├── static/
│   │   └── js/
│   │       └── telemetry.js   # WebSocket client
│   └── flag.txt               # PWNSAT{RCE_ON_GROUND_STATION}
│
├── db/                        # Created by seed.py
│   └── telemetry.db
│
├── requirements.txt
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-04-09-ground-station-design.md
└── README.md
```

## 4. Database Schema

SQLite 3, raw `sqlite3` module (no ORM — deliberate for SQLi vulnerabilities).

### Table: `users`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| username | TEXT UNIQUE | |
| password_hash | TEXT | MD5 hash (deliberately weak) |
| role | TEXT | "admin" or "operator" |

**Seed data:**
- `admin` / `5f4dcc3b5aa765d61d8327deb882cf99` (MD5 of "password") / `admin`
- `operator` / `md5("operator123")` / `operator`

### Table: `telemetry`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| timestamp | TEXT | ISO 8601 |
| apid | INTEGER | CCSDS APID |
| spacecraft_id | INTEGER | 0x02 for PwnSat2 |
| temperature | REAL | Celsius |
| pressure | REAL | hPa |
| humidity | REAL | Percentage |
| accel_x | REAL | m/s^2 |
| accel_y | REAL | m/s^2 |
| accel_z | REAL | m/s^2 |
| raw_hex | TEXT | Full frame hex |

**Seed:** ~150 records with realistic sensor data and varied APIDs/timestamps.

### Table: `radio_config`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| owner | TEXT | Username |
| frequency | INTEGER | Hz (e.g., 915000000) |
| spreading_factor | INTEGER | 7-12 |
| bandwidth | INTEGER | Hz |
| tx_power | INTEGER | dBm |
| description | TEXT | |

**Seed:** Config ID 1 for admin (IDOR target GS-06), config ID 2 for operator.

### Table: `logs`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| timestamp | TEXT | ISO 8601 |
| level | TEXT | INFO, WARN, ERROR |
| source | TEXT | Module name |
| message | TEXT | Raw, no sanitization (XSS target GS-02) |

## 5. Flask Routes and Vulnerabilities

### Authentication

**`GET/POST /login`**
- Form-based login, MD5 password hashing
- Session token: `base64(username:role:timestamp)` — no signature (GS-05)
- Stored in cookie `session_token`

**`GET /logout`**
- Clears session cookie

### Dashboard

**`GET /dashboard`** (requires login)
- Renders `dashboard.html` with latest telemetry
- WebSocket connection via Flask-SocketIO for real-time updates
- Shows: connection status, last TM timestamp, sensor gauges, APID, spacecraft ID

**WebSocket `connect`/`telemetry_update`**
- Server pushes new TM frames as they arrive (from hardware or mock)
- Client: `static/js/telemetry.js`

### Telemetry API

**`GET /api/telemetry?search=&limit=`** (GS-01: SQL Injection)
```python
# VULNERABLE: string concatenation
query = f"SELECT * FROM telemetry WHERE raw_hex LIKE '%{search}%' LIMIT {limit}"
cursor.execute(query)
```
- Exploit: `search=' UNION SELECT id,username,password_hash,role,1,2,3,4,5,6,7 FROM users--`
- Flag: `PWNSAT{ADMIN_HASH_5F4DCC3B}`

### Logs

**`GET /logs`** (GS-02: Stored XSS)
- Renders log messages as raw HTML: `{{ log.message | safe }}`
- Exploit: inject `<script>` via satellite name in config

**`GET /api/logs?file=`** (GS-04: Local File Inclusion)
```python
# VULNERABLE: no path sanitization
filepath = f"/app/logs/{filename}"
with open(filepath) as f:
    return f.read()
```
- Exploit: `?file=../../../etc/passwd`
- Flag: `PWNSAT{LFI_TRAVERSAL_SUCCESS}`

**`POST /api/logs`** (GS-11: Log Injection)
- Accepts log message without sanitizing newlines/control chars
- Exploit: inject fake log entries with `\n` to cover tracks
- Flag: `PWNSAT{LOG_INJECTION_SUCCESS}`

### Diagnostics

**`POST /api/diagnostics`** (GS-03: Remote Code Execution)
```python
# VULNERABLE: shell=True with user input
result = subprocess.check_output(cmd, shell=True)
```
- No UI page — discovered via API enumeration (GS-12)
- Exploit: `{"cmd": "ping -c1 localhost; cat flag.txt"}`
- Flag: `PWNSAT{RCE_ON_GROUND_STATION}`

### Radio Configuration

**`GET /api/config/radio/<int:config_id>`** (GS-06: IDOR)
- Returns any config without checking ownership
- Exploit: access `/api/config/radio/1` as operator to read admin's config
- Flag: `PWNSAT{IDOR_ADMIN_CONFIG}`

**`POST /api/config/radio`** (GS-07: Command Injection)
```python
# VULNERABLE: f-string in shell command
subprocess.check_output(f"echo 'Setting frequency to {frequency}'", shell=True)
```
- Exploit: `{"frequency": "915000000; cat flag.txt"}`
- Flag: `PWNSAT{CMDI_IN_RADIO_CONFIG}`

### Radio Control

**`POST /api/radio/send`** (GS-08: Kill Chain Pivot)
- Sends raw bytes to FlatSat via `radio_bridge.py`
- After achieving RCE (GS-03/GS-07), attacker reads `radio_bridge.py` source and sends arbitrary TCs
- Flag: `PWNSAT{WEB_TO_SPACE_LINK}`

### API Enumeration

**`GET /api/endpoints`** (GS-12: No Rate Limiting)
- Lists all Flask routes with methods
- No authentication required, no rate limiting
- Flag: `PWNSAT{API_NO_RATE_LIMIT}`

### Auth Bypass

**GS-05: Broken Token Generation**
- Session token: `base64(username:role:timestamp)`
- No HMAC, no signature — attacker decodes, modifies role to "admin", re-encodes
- Flag: `PWNSAT{SESSION_TOKEN_FORGED}`

### Telemetry Tampering

**GS-09: Database Tampering** (via GS-01)
- Use SQLi to execute UPDATE/DELETE on telemetry table
- Modify/destroy historical records
- No separate endpoint — exploited through existing SQLi

### Supply Chain

**GS-10: Supply Chain Attack Simulation**
- `requirements.txt` has unpinned `requests` dependency
- Simulates package replacement attack
- Flag: `PWNSAT{SUPPLY_CHAIN_COMPROMISED}`

## 6. User Experience Flow

### What the participant sees

1. **Login** — form at `/login`, default credentials `operator/operator123`
2. **Dashboard** — real-time telemetry (WebSocket), sensor readings, connection status
3. **Commands** — send telecommands to satellite, view history + responses
4. **Logs** — system log viewer with search
5. **Config** — radio parameters (frequency, SF, BW, power), satellite identity

### Typical attack progression

1. Login as `operator`
2. Find `/api/endpoints` (GS-12) — discover all routes
3. SQLi in telemetry search (GS-01) — extract admin password hash
4. Crack MD5 — login as admin
5. Auth bypass via token forging (GS-05) — alternative path
6. RCE via diagnostics (GS-03) — read `flag.txt`
7. LFI (GS-04) — read system files
8. XSS in logs (GS-02) — inject scripts
9. IDOR (GS-06) — read admin's radio config
10. Command injection (GS-07) — RCE via radio config
11. Kill chain (GS-08) — from RCE, send TCs to satellite via `radio_bridge.py`
12. DB tampering (GS-09) — modify telemetry records to cover tracks

## 7. Technology Stack

| Component | Version | Reason |
|-----------|---------|--------|
| Python | 3.11+ | Runtime |
| Flask | 3.0.x | Web framework |
| Flask-SocketIO | 5.3.x | WebSocket for real-time telemetry |
| PySerial | 3.5 | USB serial to FlatSat |
| sqlite3 | stdlib | Database (no ORM, deliberate for SQLi) |
| pyudev | latest | Linux hotplug detection |
| Jinja2 | (via Flask) | Templates (with `| safe` for XSS) |

## 8. Mock Mode

When no FlatSat hardware is detected via USB:

- `serial_manager.discover_devices()` returns empty list
- `state.py` sets `connection_status = SIMULATED`
- `telemetry.py` generates synthetic TM frames every 2 seconds:
  - Temperature: 20-35C with noise
  - Pressure: 1010-1020 hPa
  - Humidity: 40-60%
  - Accelerometers: near-zero with vibration noise
  - Varied APIDs
- `telecommand.py` accepts commands, logs them, returns success (no serial write)
- WebSocket still pushes simulated data to dashboard
- All web vulnerabilities (GS-01 to GS-12) work identically in mock mode

This allows CTF participants to practice all web vulns without physical hardware. Only GS-08 (kill chain pivot to actual satellite) requires a connected FlatSat.

## 9. Hardcoded Secrets (Deliberate)

| Secret | Value | Purpose |
|--------|-------|---------|
| Flask SECRET_KEY | `pwnsat_ground_station_2026` | Session signing |
| Admin password | `password` (MD5: `5f4dcc3b...`) | GS-01 extraction target |
| CORS | `*` (open) | Realistic misconfiguration |
| AES key | Same as firmware `aes_key_hardcoded` | Privileged TC encryption |

## 10. Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Core packaging | Directory local (B), migrable a paquete (A) | Menos ceremonia inicial, `pyproject.toml` se agrega después |
| Core modules | Hybrid: adaptar TUI discovery/hotplug/device + nuevo CCSDS/TM/TC/state | Reutiliza la parte difícil (serial multi-device), escribe lo nuevo |
| Hardware mode | Auto-detect con fallback a mock | CTF funciona sin hardware; kill chain GS-08 requiere FlatSat |
| Database | SQLite precargada con seed | Participantes necesitan datos desde el inicio para SQLi |
| Docker | Local primero, Docker después | No afecta arquitectura del core |
| Real-time | WebSocket (Flask-SocketIO) | Spec lo requiere, experiencia de ground station real |
| ORM | Ninguno (sqlite3 raw) | Las vulns GS-01/GS-09 requieren SQL string concatenation |
