# Satellite Control Panel — Design Spec

## Overview

New page `/satellite` for monitoring and controlling the connected FlatSat. Displays firmware info, LoRa configuration, battery gauge with countdown mode, sensor readings, and provides controls for mode, flight, TinyGS, difficulty, and reset. Only functional in HARDWARE mode.

## Page: `/satellite`

Requires login (any role). If no FlatSat connected (IDLE/SIMULATED mode), shows "No satellite connected — connect from Dashboard."

### Section 1: Satellite Info (read-only)

Queried once on page load via `GET /api/satellite/info`.

| Field | Shell Command | Example Output |
|-------|---------------|----------------|
| Firmware version | `fw_version` | `dev-c6512ae-dirty` |
| Git SHA | `fw_version` | `c6512ae (dirty)` |
| Build date | `fw_version` | `2026-04-10T00:31:46Z` |
| Spacecraft ID | `sc_id` | `spacecraft_id: 0x02` |
| Operating mode | `mode` | `mission` |
| Flight state | `flight` | `NOMINAL` |
| Difficulty | `difficulty` | `1 (normal)` |

### Section 2: LoRa Config (read + write)

Queried every 3 seconds via `GET /api/satellite/lora_config`. Writable via `POST /api/satellite/lora_config`.

**Display:**
- Frequency (MHz)
- Spreading Factor (7-12)
- Bandwidth (125/250/500 kHz)
- TX Power (dBm)

**Controls:** Input fields for each parameter + "Apply" button. The POST handler sends:
```
lora_freq R0 <hz>
lora_sf R0 <sf>
lora_bw R0 <bw>
lora_power R0 <power>
lora_apply R0
```

### Section 3: Battery + Countdown

Queried every 3 seconds via `GET /api/satellite/info` (battery is in `flight` output).

**Battery gauge:**
- Visual bar: 3700mV (full) to 3000mV (empty)
- Green: >3500mV
- Yellow: 3200-3500mV
- Red: <3200mV

**Countdown mode** (toggle on/off, default off):
- Timer display: "MM:SS before SAFE mode"
- Calculation: `(battery_mv - 3000) / drain_rate_per_second`
  - Normal drain: 1mV per 10s = 0.1 mV/s
  - Debug drain: 3mV per 10s = 0.3 mV/s
- Toast notifications at:
  - 3500mV: "Warning: battery at 3500mV"
  - 3200mV: "Critical: battery at 3200mV"
  - 3100mV: "DANGER: 100mV until forced SAFE"
  - 3000mV: "SATELLITE FORCED TO SAFE MODE"
- Toggle button: "Enable Countdown" / "Disable Countdown"

### Section 4: Controls

**Mode:** Four buttons — `raw` / `mission` / `ground_station` / `tinygs`. Active mode highlighted.
POST `/api/satellite/mode` with `{mode: "mission"}`.

Button actions:
- **Raw:** sends `mode raw` + `lora_mode stream`
- **Mission:** sends `mode mission` + `lora_mode stream`
- **Ground Station:** sends `lora_mode command` (puts radio in command-receive mode for ground station reception)
- **TinyGS:** sends `mode tinygs`

**Flight:** Four buttons — `idle` / `nominal` / `safe` / `debug`. Active state highlighted.
POST `/api/satellite/flight` with `{flight: "nominal"}`.

**TinyGS:** Dropdown (Norbi / FossaSat-2 / VR3X) + "Spoof" button + "Stop" button.
POST `/api/satellite/tinygs` with `{action: "spoof", profile: "norbi"}` or `{action: "stop"}`.

**Difficulty:** Select dropdown 0-3 with labels (Training / Normal / Hardened / Blue Team).
POST `/api/satellite/difficulty` with `{level: 1}`.

**Reset Defaults:** Single button with confirm dialog. Sends `POST /api/satellite/reset`.
Executes: `lora_freq ALL 915000000`, `lora_sf ALL 12`, `lora_bw ALL 250`, `lora_power ALL 20`, `lora_apply ALL`, `mode raw`, `flight idle`.

### Section 5: Sensors (read-only)

Queried every 5 seconds via `GET /api/satellite/sensors`.

| Sensor | Fields |
|--------|--------|
| BME280 | Temperature (C), Pressure (Pa), Humidity (%) |
| LIS2DH | Accel X (mg), Accel Y (mg), Accel Z (mg) |

## API Routes

All routes require login. All routes that send shell commands require HARDWARE mode (return 400 if not connected).

| Route | Method | Action | Shell Command(s) |
|-------|--------|--------|-----------------|
| `/api/satellite/info` | GET | FW version, mode, flight, battery, difficulty, sc_id | `fw_version`, `mode`, `flight`, `difficulty`, `sc_id` |
| `/api/satellite/sensors` | GET | Sensor readings | `sensors` |
| `/api/satellite/lora_config` | GET | Current LoRa params | `lora_config R0` |
| `/api/satellite/lora_config` | POST | Set LoRa params + apply | `lora_freq`, `lora_sf`, `lora_bw`, `lora_power`, `lora_apply R0` |
| `/api/satellite/mode` | POST | Set operating mode | `mode <raw\|mission\|tinygs>` |
| `/api/satellite/flight` | POST | Set flight state | `flight <idle\|nominal\|safe\|debug>` |
| `/api/satellite/difficulty` | POST | Set difficulty level | `difficulty <0-3>` |
| `/api/satellite/tinygs` | POST | Spoof or stop TinyGS | `tinygs spoof <profile>` or `tinygs stop` |
| `/api/satellite/reset` | POST | Reset RF + mode to defaults | Sequence of lora_freq/sf/bw/power + lora_apply + mode raw + flight idle |

## Shell Command Parsing

Each shell command returns text that must be parsed. Parsing rules:

**`fw_version`** response:
```
FW: dev-c6512ae-dirty
Git: c6512ae (dirty)
Built: 2026-04-10T00:31:46Z
Compiler: GNU 12.2.0
```
Parse: extract lines by prefix.

**`mode`** response: `mode: raw` — extract after `mode: `.

**`flight`** response: `flight: NOMINAL  battery: 3694 mV  tm_rate: 10 sec` — regex extract flight state, battery mV, tm_rate.

**`difficulty`** response: `difficulty: 1 (normal)` — extract number.

**`sc_id`** response: `spacecraft_id: 0x02` — extract hex value (format is `spacecraft_id: 0xNN`, not `sc_id: N`).

**`sensors`** response:
```
Accel: x=15 mg  y=-8 mg  z=1012 mg
Temp:  25.340 C
Press: 101325 Pa
Humid: 48%
```
Parse: regex for each field.

**`lora_config R0`** response:
```
Radio 0 LoRa Config:
  Frequency: 915000000 Hz
  Spreading Factor: SF12
  Bandwidth: 250 kHz
  Coding Rate: 4/5
  Preamble Length: 12
  Sync Word: Private (0x12)
  IQ: normal
  Power: 20 dBm
```
Parse: regex per line. Note field name differences from original design:
- `SF: 7` is now `Spreading Factor: SF12` (includes "SF" prefix in value)
- `BW: 125 kHz` is now `Bandwidth: 250 kHz`
- `CR: 4/5` is now `Coding Rate: 4/5`
- `Preamble: 12` is now `Preamble Length: 12`
- `SyncWord: 0x12 (private)` is now `Sync Word: Private (0x12)` (order reversed)

## Polling Strategy

| Data | Interval | Trigger |
|------|----------|---------|
| `info` (fw_version, mode, flight, battery, difficulty, sc_id) | Once on load + 3s polling for flight/battery | Page load |
| `lora_config` | 3s polling | Page load |
| `sensors` | 5s polling | Page load |

Static fields (fw_version, sc_id) queried once. Dynamic fields (flight, battery, mode) polled every 3s.

## Navigation

Add `/satellite` link to the nav bar in `base.html`:
```
Dashboard | Commands | Logs | Config | Satellite | Logout
```

## Firmware Changes Required

**Add `reset_defaults` shell command** — executes the following sequence:
```
lora_freq ALL 915000000
lora_sf ALL 12
lora_bw ALL 250
lora_power ALL 20
lora_apply ALL
mode raw
flight idle
```

This is the only firmware change needed. All other commands already exist.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Page location | Separate `/satellite` page | Dashboard already crowded with telemetry + hardware controls |
| Read/Write | Full read + write | Webapp is the mission console; also enables GS-08 kill chain to control satellite |
| Battery alert | Visual + countdown (toggleable) | "Contra reloj" CTF scenario; default off so it doesn't distract |
| Reset scope | RF + mode (not battery/difficulty/flags) | Battery and difficulty are CTF scenario settings, reset separately |
| Polling interval | 3s for dynamic, 5s for sensors | Balance between responsiveness and serial port load |
