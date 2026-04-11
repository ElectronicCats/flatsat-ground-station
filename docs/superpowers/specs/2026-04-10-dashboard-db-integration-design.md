# Dashboard DB Integration & Commands Panel

**Date:** 2026-04-10
**Status:** Approved

## Overview

Maximize use of the SQLite database for telemetry persistence, integrate the
commands panel into the dashboard, show full serial numbers, and sync
radio_config with real hardware state.

## 1. Telemetry History from DB

**Problem:** Telemetry data is stored in the `telemetry` table on every
received frame, but the dashboard only shows real-time WebSocket data. Navigating
away loses all visible data.

**Solution:**
- On dashboard load, `GET /api/telemetry?limit=200` fetches the last 200 rows
  from the DB and populates the table before connecting WebSocket.
- WebSocket continues appending new rows in real time (existing behavior).
- Add a **Clear** button that empties the DOM table only (DB retains everything).
- Add `rssi` and `snr` INTEGER columns to the `telemetry` table schema.
- Update the telemetry thread INSERT to include RSSI/SNR values.

**Endpoint:** `/api/telemetry` already exists (GS-01 SQLi target). The
dashboard JS consumes it legitimately; the vulnerability remains intact.

## 2. Commands Panel in Dashboard

**Problem:** Commands page (`/commands`) is separate from telemetry. Users
cannot see TC responses alongside incoming TM.

**Solution:**
- Add a collapsible panel above the telemetry table in `dashboard.html`,
  collapsed by default.
- Panel contains: opcode selector, hex data field, Send button, response
  history list.
- Responses (frame_hex, frame_size, timestamp) are kept in DOM memory only —
  no new DB table.
- POST goes to `/api/radio/send_tc` (existing endpoint with SDLS support).
- Remove `/commands` route, `commands.html` template, and nav link from
  `base.html`.

## 3. Serial Number Display

**Problem:** SN shown as `...XXXX` (last 4 chars) — not enough to
differentiate devices clearly.

**Solution:**
- Dashboard hardware bar: show full SN.
- Scan dropdown options: full SN + health.
- Satellite page info panel: full SN.

**Files:** `dashboard.html`, `satellite.html`.

## 4. radio_config Sync with Hardware

**Problem:** `radio_config` DB table only has seed data for the IDOR vuln.
Does not reflect actual hardware configuration.

**Solution:**
- On hardware connect (`/api/hardware/connect`): read `lora_config R0` and
  `lora_config R1` via shell, upsert into `radio_config` for the current user.
- On LoRa config change (`/api/satellite/lora_config POST`): update the
  corresponding `radio_config` row in DB after applying to hardware.
- `/config` page now shows real hardware state.
- IDOR vulnerability (GS-06) remains intact — no ownership check added.

## 5. Schema Changes

```sql
-- Add RSSI/SNR to telemetry table
ALTER TABLE telemetry ADD COLUMN rssi INTEGER;
ALTER TABLE telemetry ADD COLUMN snr INTEGER;
```

For fresh installs, the CREATE TABLE in `db.py` includes the new columns
directly. For existing DBs, the ALTER is handled on init (or DB is recreated).

## Files Affected

| File | Changes |
|------|---------|
| `webapp/db.py` | Add rssi/snr columns to telemetry schema |
| `webapp/app.py` | Update INSERT with rssi/snr; remove /commands route; add radio_config sync on connect and lora_config POST |
| `webapp/templates/dashboard.html` | Add Clear button, commands panel, full SN display |
| `webapp/templates/base.html` | Remove Commands nav link |
| `webapp/templates/commands.html` | Delete file |
| `webapp/templates/satellite.html` | Full SN display |
| `webapp/static/js/telemetry.js` | Load history from DB on init, Clear button handler |
| `tests/test_satellite_api.py` | Update if commands tests reference /commands route |
| `tests/test_vuln_auth_bypass.py` | Update if it tests /commands page |

## What Does NOT Change

- All 12 CTF vulnerabilities remain intact
- WebSocket real-time telemetry continues working
- SDLS encrypt/decrypt, threading locks, satellite page adaptive layout
- `logs` table and `/logs` page unchanged
- Mock/simulated mode unchanged
