# Hardware Mode (USB Direct) — Design Spec

## Overview

Add USB serial connectivity to the ground station webapp. Users manually connect/disconnect to a FlatSat via a button in the dashboard. When connected, telemetry comes from real hardware; when disconnected, falls back to simulated mode.

## Modules

### `core/serial_manager.py` (new)

Adapted from TUI `discovery.py`. Sync-only, no hotplug.

- `DiscoveredDevice` dataclass: serial_number, radio0_port, radio1_port, shell_port, health, is_complete
- `discover_devices() -> list[DiscoveredDevice]`: filters serial ports by VID `0x1209` / PID `0xBABC`, groups 3 endpoints per device by serial number, maps endpoints by description string ("Cat-Radio0", "Cat-Radio1", "Cat-Shell")
- `check_port_available(port) -> bool`: checks if a port can be opened

### `core/device.py` (new)

Adapted from TUI `device.py`. Sync-only API for Flask.

```python
class FlatSatDevice:
    def __init__(self, discovered: DiscoveredDevice):
        """Wraps 3 serial ports for one FlatSat."""

    def connect(self) -> dict[str, bool]:
        """Open all serial ports. Returns {endpoint: success}."""

    def disconnect(self):
        """Close all serial ports."""

    @property
    def is_connected(self) -> bool

    def send_shell_command(self, cmd: str, timeout: float = 2.0) -> str:
        """Send command to Shell (CDC2), return response."""

    def send_raw(self, data: bytes) -> bool:
        """Send raw bytes to Radio 0 (CDC0)."""

    def read_line(self, timeout: float = 1.0) -> str | None:
        """Read one line from Radio 0. Returns None on timeout."""

    def send_radio1_raw(self, data: bytes) -> bool:
        """Send raw bytes to Radio 1 (CDC1)."""
```

Serial config: 115200 baud, 8N1, dsrdtr=False, rtscts=False (required for CDC-ACM).

### `webapp/radio_bridge.py` (modify)

- Remove module-level `_state` singleton
- Accept `GroundStationState` from app context
- When state is HARDWARE, use `state.device` (a `FlatSatDevice`) to send/receive
- When state is SIMULATED, behave as currently (log and return success)

### `webapp/app.py` (modify)

New API routes:

- `GET /api/hardware/status` — returns `{mode, serial_number, ports}` or `{mode: "simulated"}`
- `POST /api/hardware/scan` — runs `discover_devices()`, returns list of available FlatSats
- `POST /api/hardware/connect` — accepts `{serial_number}`, connects to that FlatSat, switches to HARDWARE mode
- `POST /api/hardware/disconnect` — disconnects current FlatSat, switches to SIMULATED mode

All routes require login (any role).

Store `GroundStationState` instance on `app.config["GS_STATE"]` so it's shared across requests and the background thread.

### Background telemetry thread (modify)

When in HARDWARE mode:
- Read lines from Radio 0 using `device.read_line(timeout=1.0)`
- Parse LoRa RX format: `"RX: <hex> | RSSI: <int> | SNR: <int>"`
- Extract hex payload, run through `parse_frame()` + `decode_tm_payload()`
- Emit via WebSocket and insert into telemetry DB
- If read fails or device disconnects, fall back to SIMULATED mode

When in SIMULATED mode:
- Generate mock telemetry every 2 seconds (as currently)

### Dashboard UI changes

Add a hardware status section at the top of `dashboard.html`:

```
[Status: SIMULATED] [Scan] [Connect] [Disconnect]
```

- "Scan" button: POST `/api/hardware/scan`, shows list of available FlatSats
- "Connect" button: POST `/api/hardware/connect` with selected serial number
- "Disconnect" button: POST `/api/hardware/disconnect`
- Status shows: mode, serial number, RSSI/SNR of last received frame

## Setup Requirements

The following conditions must be met for hardware communication to work correctly. These were verified during implementation and testing.

### Receptor (Ground Station) Setup

- The receptor must be in `lora_mode command` to receive LoRa packets formatted as `RX:` lines. Without this, incoming packets are not printed in the parseable format.
- After changing any LoRa parameter (freq, SF, BW), `lora_apply R0` **must** be called. Parameters remain in a "pending" state until applied — the radio does not use the new values until `lora_apply` is executed.

### Satellite Setup for Beacon Reception

For the ground station to receive satellite beacons:
1. Satellite must be in `mode mission` — enables periodic beacon transmission
2. Satellite must be in `lora_mode stream` — sends beacon frames over LoRa
3. Satellite flight state must be `flight nominal` — SAFE/IDLE states suppress beacons

### LoRa Parameter Matching

Both devices (satellite and ground station) must have identical LoRa parameters:
- Frequency (Hz)
- Spreading Factor (SF)
- Bandwidth (BW)

Mismatched parameters result in no frames received (no error shown — frames are simply not demodulated).

### State Transitions

- **Disconnect:** transitions to IDLE state. User must manually choose next action (reconnect, scan, or stay idle).
- **Hardware error / read failure:** automatically falls back to SIMULATED mode. The webapp continues to function with synthetic telemetry.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Multi-device | Single FlatSat at a time | Webapp is CTF target, not ops tool |
| Connect trigger | Manual button | User controls when to engage hardware |
| Who can connect | Any logged-in user | CTF — no access barriers |
| Hotplug | Not implemented | Manual scan/reconnect via button |
| Async | No — sync serial only | Flask doesn't need asyncio |
| Fallback | Auto-fallback to SIMULATED on disconnect/error | Webapp always works |
