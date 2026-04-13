# Config Page, README, and Frontend Cleanup — Design Spec

**Date:** 2026-04-12
**Scope:** Three improvements to the ground station webapp and project docs.

---

## 1. Config Page — Complete Radio Configuration

### Problem
The config page (`/config`) has 4 form fields (frequency, SF, BW, TX power) but the POST handler only sends `frequency`. The backend `api_config_update` also only processes frequency.

### Changes

**Frontend (`webapp/templates/config.html`):**
- Update the form submit handler to send all 4 fields in the JSON body: `frequency`, `spreading_factor`, `bandwidth`, `tx_power`.

**Backend (`webapp/app.py` > `api_config_update`):**
- Receive all 4 fields from the request body.
- Persist to `radio_config` table via upsert (INSERT or UPDATE keyed on `owner`).
- Execute shell commands to the hardware for each parameter when hardware is connected.
- The 3 new fields (SF, BW, power) also use f-string interpolation in shell commands, extending the GS-07 CTF attack surface.

**Validation:**
- No server-side validation (deliberate for CTF).
- HTML `min`/`max` attributes on inputs serve as guidance only.

### Data Flow
```
Form submit → POST /api/config/radio
  → DB: upsert radio_config (owner, frequency, sf, bw, power)
  → Hardware: shell commands for each param (if hardware connected)
  → Response: {status, config} or {error}
```

---

## 2. README

### Location
`README.md` at the project root.

### Structure

```
# PwnSat2 Ground Station

One-paragraph description: what it is, what it's for (educational CTF + FlatSat control).

## Requirements
- Python 3.11+
- Dependencies via requirements.txt
- Optional hardware: FlatSat device (VID:PID 0x1209:0xBABC)

## Installation and Usage
- pip install -r requirements.txt
- python -m webapp.seed (initialize DB)
- python -m webapp.app (run Flask)
- Simulated mode vs hardware mode

## Architecture
- Text diagram: core/ → webapp/ → browser
- core/: CCSDS protocol, serial manager, telemetry decoder, telecommand builder, state machine
- webapp/: Flask + SocketIO, auth, DB, radio bridge
- db/: SQLite with tables: users, telemetry, radio_config, logs

## Webapp Pages
- Dashboard: live telemetry, hardware control, telecommand panel
- Satellite: control panel, LoRa config, battery monitor, sensors
- Config: radio configuration with DB persistence
- Logs: system log viewer

## Tests
- Run with: pytest
- 148 tests covering core library, webapp routes, and vulnerability checks

## Directory Structure
- Simplified tree of the project
```

### Exclusions
- No hardware setup guide (separate doc).
- No CTF vulnerability list (spoiler).
- No screenshots.

---

## 3. Frontend Cleanup — CSS and JS Extraction

### Strategy
Extract inline CSS and JS to separate files. No rewrite, no frameworks, no functional changes.

### New Files

```
webapp/static/css/
  base.css          ← styles from base.html <style>
  dashboard.css     ← styles from dashboard.html <style>
  satellite.css     ← styles from satellite.html <style>

webapp/static/js/
  telemetry.js      ← already exists, unchanged
  dashboard.js      ← inline JS from dashboard.html (~190 lines)
  satellite.js      ← inline JS from satellite.html (~400 lines)
  config.js         ← form handler from config.html (rewritten as part of item 1)
```

### Template Changes

- `base.html`: Replace `<style>` block with `<link rel="stylesheet" href="/static/css/base.css">`.
- `dashboard.html`: Add `<link>` to `dashboard.css` in `{% block head %}`. Replace inline `<script>` with `<script src="/static/js/dashboard.js">` at end of `{% block content %}`.
- `satellite.html`: Same pattern with `satellite.css` and `satellite.js`.
- `config.html`: Same pattern with `config.js`.

### JS Module Strategy

- `dashboard.js`, `satellite.js`, `config.js` loaded as classic scripts (not ES6 modules) because they define global functions referenced by `onclick` attributes in the HTML.
- `telemetry.js` stays as-is (classic script, loaded by dashboard.html).
- No shared utility modules needed — each file is self-contained.

### What Does NOT Change

- The hacker aesthetic (colors, monospace, dark theme).
- Functionality of any page.
- No CSS frameworks added.
- `logs.html` has no inline CSS/JS — stays as-is.
- `login.html` — stays as-is (minimal page).

---

## Testing

- All existing 148 tests must continue to pass.
- Manual browser verification of each page after extraction to confirm styles and behavior are preserved.
- Config page: verify all 4 fields are sent and persisted.
