# Satellite Control Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/satellite` page that displays FlatSat status (firmware, battery, LoRa config, sensors) and provides controls for mode, flight, TinyGS, difficulty, and reset defaults.

**Architecture:** A `core/shell_parser.py` module parses multi-line shell responses into structured dicts. `webapp/app.py` gets new `/api/satellite/*` routes that send shell commands via the connected `FlatSatDevice` and return parsed JSON. A new `satellite.html` template displays the data with JS polling and controls.

**Tech Stack:** Existing Flask + core/device.py (extended with multi-line read)

**Spec:** `docs/superpowers/specs/2026-04-09-satellite-control-design.md`

---

## File Structure

```
core/
├── device.py              # MODIFY: add send_shell_command_full (multi-line)
├── shell_parser.py        # NEW: parse fw_version, flight, sensors, lora_config responses

webapp/
├── app.py                 # MODIFY: add /satellite route + /api/satellite/* routes
├── templates/
│   ├── base.html          # MODIFY: add Satellite link to nav
│   └── satellite.html     # NEW: satellite control page

tests/
├── test_shell_parser.py   # NEW
├── test_satellite_api.py  # NEW
```

---

### Task 1: Multi-line shell command in device.py

**Files:**
- Modify: `core/device.py`

- [ ] **Step 1: Add `send_shell_command_full` method to `FlatSatDevice`**

Add after the existing `send_shell_command` method in `core/device.py`:

```python
    def send_shell_command_full(self, cmd: str, timeout: float = 2.0, read_time: float = 0.8) -> str | None:
        """Send command to Shell (CDC2), return full multi-line response."""
        if not self._shell or not self._shell.is_open:
            return None
        try:
            import time

            self._shell.timeout = timeout
            self._shell.reset_input_buffer()
            self._shell.write(f"{cmd}\r\n".encode("ascii"))
            self._shell.flush()
            time.sleep(read_time)
            data = self._shell.read(self._shell.in_waiting or 1)
            if data:
                return data.decode("ascii", errors="ignore").strip()
            return None
        except Exception:
            return None
```

- [ ] **Step 2: Run existing tests to verify nothing broke**

Run: `python -m pytest tests/test_device.py -v`
Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add core/device.py
git commit -m "feat(core): add send_shell_command_full for multi-line responses"
```

---

### Task 2: Shell response parser

**Files:**
- Create: `core/shell_parser.py`
- Create: `tests/test_shell_parser.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_shell_parser.py`:
```python
from core.shell_parser import (
    parse_fw_version,
    parse_flight,
    parse_mode,
    parse_difficulty,
    parse_sc_id,
    parse_sensors,
    parse_lora_config,
)


def test_parse_fw_version():
    raw = """fw_versionFW: dev-c6512ae-dirty
Git: c6512ae (dirty)
Built: 2026-04-10T00:31:46Z
Compiler: GNU 12.2.0"""
    result = parse_fw_version(raw)
    assert result["fw_version"] == "dev-c6512ae-dirty"
    assert result["git_sha"] == "c6512ae"
    assert result["git_dirty"] is True
    assert result["build_date"] == "2026-04-10T00:31:46Z"


def test_parse_fw_version_clean():
    raw = """fw_versionFW: v1.0.0
Git: abc1234 (clean)
Built: 2026-04-10T00:00:00Z
Compiler: GNU 12.2.0"""
    result = parse_fw_version(raw)
    assert result["fw_version"] == "v1.0.0"
    assert result["git_dirty"] is False


def test_parse_flight():
    raw = "flightflight: NOMINAL  battery: 3694 mV  tm_rate: 10 sec"
    result = parse_flight(raw)
    assert result["flight"] == "NOMINAL"
    assert result["battery_mv"] == 3694
    assert result["tm_rate"] == 10


def test_parse_flight_safe():
    raw = "flightflight: SAFE  battery: 2999 mV  tm_rate: 10 sec"
    result = parse_flight(raw)
    assert result["flight"] == "SAFE"
    assert result["battery_mv"] == 2999


def test_parse_mode():
    assert parse_mode("modemode: mission") == "mission"
    assert parse_mode("modemode: raw") == "raw"
    assert parse_mode("modemode: tinygs") == "tinygs"


def test_parse_difficulty():
    assert parse_difficulty("difficultydifficulty: 1 (normal)") == 1
    assert parse_difficulty("difficultydifficulty: 0 (training)") == 0
    assert parse_difficulty("difficultydifficulty: 3 (blue_team)") == 3


def test_parse_sc_id():
    assert parse_sc_id("sc_idsc_id: 2") == 2
    assert parse_sc_id("sc_idsc_id: 255") == 255


def test_parse_sensors():
    raw = """sensorsAccel: x=15 mg  y=-8 mg  z=1012 mg
Temp:  25.340 C
Press: 101325 Pa
Humid: 48%"""
    result = parse_sensors(raw)
    assert result["accel_x"] == 15
    assert result["accel_y"] == -8
    assert result["accel_z"] == 1012
    assert result["temperature"] == 25.340
    assert result["pressure"] == 101325
    assert result["humidity"] == 48


def test_parse_lora_config():
    raw = """lora_config R0Radio 0 LoRa Config:
  Frequency: 915000000 Hz
  SF: 7
  BW: 125 kHz
  CR: 4/5
  Power: 20 dBm
  Preamble: 12
  SyncWord: 0x12 (private)
  IQ: normal"""
    result = parse_lora_config(raw)
    assert result["frequency"] == 915000000
    assert result["sf"] == 7
    assert result["bw"] == 125
    assert result["cr"] == "4/5"
    assert result["power"] == 20
    assert result["preamble"] == 12
    assert result["syncword"] == "0x12"
    assert result["iq"] == "normal"


def test_parse_flight_none():
    assert parse_flight(None) == {"flight": "unknown", "battery_mv": 0, "tm_rate": 0}


def test_parse_sensors_none():
    result = parse_sensors(None)
    assert result["temperature"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_shell_parser.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`core/shell_parser.py`:
```python
"""Parse FlatSat shell command responses into structured data.

Each shell response is prefixed with the echo of the command itself
(e.g., "flightflight: NOMINAL..."), so parsers handle that.
"""

import re


def parse_fw_version(raw: str | None) -> dict:
    """Parse fw_version response."""
    if not raw:
        return {"fw_version": "unknown", "git_sha": "", "git_dirty": False, "build_date": ""}
    result = {"fw_version": "unknown", "git_sha": "", "git_dirty": False, "build_date": ""}

    fw_match = re.search(r"FW:\s*(.+)", raw)
    if fw_match:
        result["fw_version"] = fw_match.group(1).strip()

    git_match = re.search(r"Git:\s*(\w+)\s*\((\w+)\)", raw)
    if git_match:
        result["git_sha"] = git_match.group(1)
        result["git_dirty"] = git_match.group(2) == "dirty"

    built_match = re.search(r"Built:\s*(.+)", raw)
    if built_match:
        result["build_date"] = built_match.group(1).strip()

    return result


def parse_flight(raw: str | None) -> dict:
    """Parse flight response: 'flight: NOMINAL  battery: 3694 mV  tm_rate: 10 sec'"""
    if not raw:
        return {"flight": "unknown", "battery_mv": 0, "tm_rate": 0}

    result = {"flight": "unknown", "battery_mv": 0, "tm_rate": 0}

    flight_match = re.search(r"flight:\s*(\w+)", raw)
    if flight_match:
        result["flight"] = flight_match.group(1)

    batt_match = re.search(r"battery:\s*(\d+)\s*mV", raw)
    if batt_match:
        result["battery_mv"] = int(batt_match.group(1))

    rate_match = re.search(r"tm_rate:\s*(\d+)\s*sec", raw)
    if rate_match:
        result["tm_rate"] = int(rate_match.group(1))

    return result


def parse_mode(raw: str | None) -> str:
    """Parse mode response: 'mode: raw'"""
    if not raw:
        return "unknown"
    match = re.search(r"mode:\s*(\w+)", raw)
    return match.group(1) if match else "unknown"


def parse_difficulty(raw: str | None) -> int:
    """Parse difficulty response: 'difficulty: 1 (normal)'"""
    if not raw:
        return 0
    match = re.search(r"difficulty:\s*(\d+)", raw)
    return int(match.group(1)) if match else 0


def parse_sc_id(raw: str | None) -> int:
    """Parse sc_id response: 'sc_id: 2'"""
    if not raw:
        return 0
    match = re.search(r"sc_id:\s*(\d+)", raw)
    return int(match.group(1)) if match else 0


def parse_sensors(raw: str | None) -> dict:
    """Parse sensors response."""
    defaults = {
        "accel_x": 0, "accel_y": 0, "accel_z": 0,
        "temperature": 0, "pressure": 0, "humidity": 0,
    }
    if not raw:
        return defaults

    result = dict(defaults)

    accel_match = re.search(r"x=(-?\d+)\s*mg\s+y=(-?\d+)\s*mg\s+z=(-?\d+)\s*mg", raw)
    if accel_match:
        result["accel_x"] = int(accel_match.group(1))
        result["accel_y"] = int(accel_match.group(2))
        result["accel_z"] = int(accel_match.group(3))

    temp_match = re.search(r"Temp:\s*([\d.]+)\s*C", raw)
    if temp_match:
        result["temperature"] = float(temp_match.group(1))

    press_match = re.search(r"Press:\s*(\d+)\s*Pa", raw)
    if press_match:
        result["pressure"] = int(press_match.group(1))

    humid_match = re.search(r"Humid:\s*(\d+)%", raw)
    if humid_match:
        result["humidity"] = int(humid_match.group(1))

    return result


def parse_lora_config(raw: str | None) -> dict:
    """Parse lora_config R0 response."""
    defaults = {
        "frequency": 0, "sf": 0, "bw": 0, "cr": "",
        "power": 0, "preamble": 0, "syncword": "", "iq": "",
    }
    if not raw:
        return defaults

    result = dict(defaults)

    freq_match = re.search(r"Frequency:\s*(\d+)\s*Hz", raw)
    if freq_match:
        result["frequency"] = int(freq_match.group(1))

    sf_match = re.search(r"SF:\s*(\d+)", raw)
    if sf_match:
        result["sf"] = int(sf_match.group(1))

    bw_match = re.search(r"BW:\s*(\d+)\s*kHz", raw)
    if bw_match:
        result["bw"] = int(bw_match.group(1))

    cr_match = re.search(r"CR:\s*([\d/]+)", raw)
    if cr_match:
        result["cr"] = cr_match.group(1)

    power_match = re.search(r"Power:\s*(-?\d+)\s*dBm", raw)
    if power_match:
        result["power"] = int(power_match.group(1))

    preamble_match = re.search(r"Preamble:\s*(\d+)", raw)
    if preamble_match:
        result["preamble"] = int(preamble_match.group(1))

    sw_match = re.search(r"SyncWord:\s*(0x\w+)", raw)
    if sw_match:
        result["syncword"] = sw_match.group(1)

    iq_match = re.search(r"IQ:\s*(\w+)", raw)
    if iq_match:
        result["iq"] = iq_match.group(1)

    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_shell_parser.py -v`
Expected: all 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/shell_parser.py tests/test_shell_parser.py
git commit -m "feat(core): add shell response parsers for satellite control"
```

---

### Task 3: Satellite API routes

**Files:**
- Modify: `webapp/app.py`
- Create: `tests/test_satellite_api.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_satellite_api.py`:
```python
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from webapp.config import TestConfig
from webapp.db import init_db
from webapp.seed import seed_db


@pytest.fixture
def app():
    from webapp.app import create_app

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app = create_app(TestConfig, db_path=db_path)
    with app.app_context():
        init_db()
        seed_db()
        yield app
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def auth_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client


def test_satellite_info_not_connected(auth_client):
    resp = auth_client.get("/api/satellite/info")
    assert resp.status_code == 400
    assert "not connected" in resp.get_json()["error"].lower()


def test_satellite_page_renders(auth_client):
    resp = auth_client.get("/satellite")
    assert resp.status_code == 200
    assert b"Satellite" in resp.data


def _setup_hardware(app):
    """Put app in HARDWARE mode with a mock device."""
    gs = app.config["GS_STATE"]
    mock_dev = MagicMock()
    mock_dev.serial_number = "TEST123"
    mock_dev.is_connected = True
    gs.set_hardware(mock_dev)
    return mock_dev


def test_satellite_info_connected(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.side_effect = lambda cmd, **kw: {
        "fw_version": "fw_versionFW: dev-test\nGit: abc1234 (dirty)\nBuilt: 2026-01-01\nCompiler: GNU",
        "mode": "modemode: mission",
        "flight": "flightflight: NOMINAL  battery: 3650 mV  tm_rate: 10 sec",
        "difficulty": "difficultydifficulty: 1 (normal)",
        "sc_id": "sc_idsc_id: 2",
    }.get(cmd)

    resp = auth_client.get("/api/satellite/info")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["fw_version"] == "dev-test"
    assert data["mode"] == "mission"
    assert data["flight"] == "NOMINAL"
    assert data["battery_mv"] == 3650
    assert data["difficulty"] == 1
    assert data["sc_id"] == 2


def test_satellite_sensors(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = (
        "sensorsAccel: x=10 mg  y=-5 mg  z=1000 mg\n"
        "Temp:  23.500 C\nPress: 101300 Pa\nHumid: 50%"
    )
    resp = auth_client.get("/api/satellite/sensors")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["temperature"] == 23.5
    assert data["humidity"] == 50


def test_satellite_lora_config_get(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = (
        "lora_config R0Radio 0 LoRa Config:\n"
        "  Frequency: 915000000 Hz\n  SF: 7\n  BW: 125 kHz\n"
        "  CR: 4/5\n  Power: 20 dBm\n  Preamble: 12\n"
        "  SyncWord: 0x12 (private)\n  IQ: normal"
    )
    resp = auth_client.get("/api/satellite/lora_config")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["frequency"] == 915000000
    assert data["sf"] == 7


def test_satellite_lora_config_post(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = "OK"
    resp = auth_client.post(
        "/api/satellite/lora_config",
        json={"frequency": 436703000, "sf": 10, "bw": 250, "power": 22},
        content_type="application/json",
    )
    assert resp.status_code == 200
    calls = [c[0][0] for c in mock_dev.send_shell_command_full.call_args_list]
    assert "lora_freq R0 436703000" in calls
    assert "lora_apply R0" in calls


def test_satellite_mode_post(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = "mode set to mission"
    resp = auth_client.post(
        "/api/satellite/mode",
        json={"mode": "mission"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    mock_dev.send_shell_command_full.assert_called_with("mode mission")


def test_satellite_flight_post(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = "flight mode set to: nominal"
    resp = auth_client.post(
        "/api/satellite/flight",
        json={"flight": "nominal"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    mock_dev.send_shell_command_full.assert_called_with("flight nominal")


def test_satellite_difficulty_post(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = "difficulty set to 2"
    resp = auth_client.post(
        "/api/satellite/difficulty",
        json={"level": 2},
        content_type="application/json",
    )
    assert resp.status_code == 200
    mock_dev.send_shell_command_full.assert_called_with("difficulty 2")


def test_satellite_tinygs_spoof(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = "Spoofing Norbi"
    resp = auth_client.post(
        "/api/satellite/tinygs",
        json={"action": "spoof", "profile": "norbi"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    mock_dev.send_shell_command_full.assert_called_with("tinygs spoof norbi")


def test_satellite_tinygs_stop(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = "TinyGS stopped"
    resp = auth_client.post(
        "/api/satellite/tinygs",
        json={"action": "stop"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    mock_dev.send_shell_command_full.assert_called_with("tinygs stop")


def test_satellite_reset(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = "OK"
    resp = auth_client.post("/api/satellite/reset")
    assert resp.status_code == 200
    calls = [c[0][0] for c in mock_dev.send_shell_command_full.call_args_list]
    assert "reset_defaults" in calls
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_satellite_api.py -v`
Expected: FAIL (routes not found)

- [ ] **Step 3: Add satellite routes to app.py**

Add these imports at the top of `webapp/app.py`:
```python
from core.shell_parser import (
    parse_fw_version,
    parse_flight,
    parse_mode,
    parse_difficulty,
    parse_sc_id,
    parse_sensors,
    parse_lora_config,
)
```

Add inside `create_app()`, before the `@socketio.on("connect")` handler:

```python
    @app.route("/satellite")
    @login_required
    def satellite_page():
        return render_template("satellite.html")

    def _require_hardware():
        """Return (device, None) if connected, or (None, error_response) if not."""
        gs = app.config["GS_STATE"]
        if not gs.is_hardware or not gs.device:
            return None, ({"error": "Satellite not connected"}, 400)
        return gs.device, None

    @app.route("/api/satellite/info")
    @login_required
    def api_satellite_info():
        dev, err = _require_hardware()
        if err:
            return err

        fw_raw = dev.send_shell_command_full("fw_version")
        mode_raw = dev.send_shell_command_full("mode")
        flight_raw = dev.send_shell_command_full("flight")
        diff_raw = dev.send_shell_command_full("difficulty")
        scid_raw = dev.send_shell_command_full("sc_id")

        fw = parse_fw_version(fw_raw)
        flight = parse_flight(flight_raw)

        return {
            **fw,
            "mode": parse_mode(mode_raw),
            "flight": flight["flight"],
            "battery_mv": flight["battery_mv"],
            "tm_rate": flight["tm_rate"],
            "difficulty": parse_difficulty(diff_raw),
            "sc_id": parse_sc_id(scid_raw),
        }

    @app.route("/api/satellite/sensors")
    @login_required
    def api_satellite_sensors():
        dev, err = _require_hardware()
        if err:
            return err
        raw = dev.send_shell_command_full("sensors")
        return parse_sensors(raw)

    @app.route("/api/satellite/lora_config", methods=["GET", "POST"])
    @login_required
    def api_satellite_lora_config():
        dev, err = _require_hardware()
        if err:
            return err

        if request.method == "GET":
            raw = dev.send_shell_command_full("lora_config R0")
            return parse_lora_config(raw)

        data = request.get_json(silent=True) or {}
        freq = data.get("frequency")
        sf = data.get("sf")
        bw = data.get("bw")
        power = data.get("power")

        results = []
        if freq:
            results.append(dev.send_shell_command_full(f"lora_freq R0 {freq}"))
        if sf:
            results.append(dev.send_shell_command_full(f"lora_sf R0 {sf}"))
        if bw:
            results.append(dev.send_shell_command_full(f"lora_bw R0 {bw}"))
        if power:
            results.append(dev.send_shell_command_full(f"lora_power R0 {power}"))
        results.append(dev.send_shell_command_full("lora_apply R0"))

        return {"status": "ok", "responses": results}

    @app.route("/api/satellite/mode", methods=["POST"])
    @login_required
    def api_satellite_mode():
        dev, err = _require_hardware()
        if err:
            return err
        data = request.get_json(silent=True) or {}
        mode = data.get("mode", "raw")
        resp = dev.send_shell_command_full(f"mode {mode}")
        return {"status": "ok", "response": resp}

    @app.route("/api/satellite/flight", methods=["POST"])
    @login_required
    def api_satellite_flight():
        dev, err = _require_hardware()
        if err:
            return err
        data = request.get_json(silent=True) or {}
        flight = data.get("flight", "idle")
        resp = dev.send_shell_command_full(f"flight {flight}")
        return {"status": "ok", "response": resp}

    @app.route("/api/satellite/difficulty", methods=["POST"])
    @login_required
    def api_satellite_difficulty():
        dev, err = _require_hardware()
        if err:
            return err
        data = request.get_json(silent=True) or {}
        level = data.get("level", 0)
        resp = dev.send_shell_command_full(f"difficulty {level}")
        return {"status": "ok", "response": resp}

    @app.route("/api/satellite/tinygs", methods=["POST"])
    @login_required
    def api_satellite_tinygs():
        dev, err = _require_hardware()
        if err:
            return err
        data = request.get_json(silent=True) or {}
        action = data.get("action", "status")
        if action == "spoof":
            profile = data.get("profile", "norbi")
            resp = dev.send_shell_command_full(f"tinygs spoof {profile}")
        elif action == "stop":
            resp = dev.send_shell_command_full("tinygs stop")
        else:
            resp = dev.send_shell_command_full("tinygs status")
        return {"status": "ok", "response": resp}

    @app.route("/api/satellite/reset", methods=["POST"])
    @login_required
    def api_satellite_reset():
        dev, err = _require_hardware()
        if err:
            return err
        resp = dev.send_shell_command_full("reset_defaults")
        return {"status": "ok", "response": resp}
```

- [ ] **Step 4: Create minimal satellite.html for tests**

`webapp/templates/satellite.html`:
```html
{% extends "base.html" %}
{% block title %}Satellite{% endblock %}
{% block content %}
<h1>Satellite Control</h1>
<p>Placeholder — full UI in next task.</p>
{% endblock %}
```

- [ ] **Step 5: Add Satellite link to nav in base.html**

In `webapp/templates/base.html`, change the nav line:
```html
    <a href="/dashboard">Dashboard</a> |
    <a href="/commands">Commands</a> |
    <a href="/logs">Logs</a> |
    <a href="/config">Config</a> |
    <a href="/satellite">Satellite</a> |
    <a href="/logout">Logout ({{ g.username }})</a>
```

- [ ] **Step 6: Run all tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add webapp/app.py webapp/templates/satellite.html webapp/templates/base.html tests/test_satellite_api.py
git commit -m "feat(webapp): add satellite API routes and page scaffold"
```

---

### Task 4: Satellite control page UI

**Files:**
- Modify: `webapp/templates/satellite.html`

- [ ] **Step 1: Replace satellite.html with full UI**

`webapp/templates/satellite.html`:
```html
{% extends "base.html" %}
{% block title %}Satellite{% endblock %}
{% block head %}
<style>
    .panel { border:1px solid #333; padding:15px; margin-bottom:15px; background:#111; }
    .panel h2 { margin-top:0; color:#00ccff; font-size:1.1em; }
    .grid { display:grid; grid-template-columns:1fr 1fr; gap:15px; }
    .field { margin:5px 0; }
    .field label { display:inline-block; width:140px; color:#888; }
    .field span { color:#00ff41; }
    .btn-group button { margin-right:5px; margin-bottom:5px; }
    .btn-active { background:#00ff41; color:#0a0a0a; font-weight:bold; }
    .battery-bar { width:200px; height:20px; background:#333; border:1px solid #555; display:inline-block; vertical-align:middle; }
    .battery-fill { height:100%; transition: width 0.5s; }
    .batt-green { background:#00ff41; }
    .batt-yellow { background:#ffaa00; }
    .batt-red { background:#ff4444; }
    .countdown { font-size:1.5em; font-weight:bold; margin:10px 0; }
    .countdown-danger { color:#ff4444; animation: blink 1s infinite; }
    @keyframes blink { 50% { opacity:0.4; } }
    .toast { position:fixed; top:20px; right:20px; background:#ff4444; color:white; padding:15px; border-radius:5px; display:none; z-index:999; }
</style>
{% endblock %}
{% block content %}
<h1>Satellite Control</h1>

<div id="no-hw" style="display:none; color:#ff4444; font-size:1.2em; padding:20px;">
    No satellite connected — <a href="/dashboard">connect from Dashboard</a>.
</div>

<div id="sat-content" style="display:none;">
<div class="grid">

<!-- Info Panel -->
<div class="panel">
    <h2>Satellite Info</h2>
    <div class="field"><label>Firmware:</label> <span id="fw-version">-</span></div>
    <div class="field"><label>Git:</label> <span id="fw-git">-</span></div>
    <div class="field"><label>Build:</label> <span id="fw-build">-</span></div>
    <div class="field"><label>Spacecraft ID:</label> <span id="sc-id">-</span></div>
    <div class="field"><label>Mode:</label> <span id="cur-mode">-</span></div>
    <div class="field"><label>Flight:</label> <span id="cur-flight">-</span></div>
    <div class="field"><label>Difficulty:</label> <span id="cur-diff">-</span></div>
</div>

<!-- Battery Panel -->
<div class="panel">
    <h2>Battery</h2>
    <div class="field">
        <label>Voltage:</label> <span id="batt-mv">-</span> mV
    </div>
    <div class="battery-bar"><div id="batt-fill" class="battery-fill batt-green" style="width:100%"></div></div>
    <div style="margin-top:10px;">
        <label><input type="checkbox" id="countdown-toggle" onchange="toggleCountdown()"> Enable Countdown</label>
    </div>
    <div id="countdown-display" style="display:none;">
        <div class="countdown" id="countdown-timer">--:--</div>
        <div style="color:#888;">before forced SAFE mode</div>
    </div>
</div>

<!-- LoRa Config Panel -->
<div class="panel">
    <h2>LoRa Configuration</h2>
    <div class="field"><label>Frequency:</label> <span id="lora-freq">-</span> Hz</div>
    <div class="field"><label>SF:</label> <span id="lora-sf">-</span></div>
    <div class="field"><label>BW:</label> <span id="lora-bw">-</span> kHz</div>
    <div class="field"><label>Power:</label> <span id="lora-power">-</span> dBm</div>
    <hr style="border-color:#333;">
    <div class="field"><label>Set Freq (Hz):</label> <input id="set-freq" type="number" value="915000000" style="width:130px;"></div>
    <div class="field"><label>Set SF:</label> <input id="set-sf" type="number" min="7" max="12" value="7" style="width:60px;"></div>
    <div class="field"><label>Set BW (kHz):</label> <select id="set-bw"><option>125</option><option>250</option><option>500</option></select></div>
    <div class="field"><label>Set Power (dBm):</label> <input id="set-power" type="number" min="-9" max="22" value="20" style="width:60px;"></div>
    <button onclick="applyLora()">Apply LoRa Config</button>
</div>

<!-- Sensors Panel -->
<div class="panel">
    <h2>Sensors</h2>
    <div class="field"><label>Temperature:</label> <span id="sens-temp">-</span> C</div>
    <div class="field"><label>Pressure:</label> <span id="sens-press">-</span> Pa</div>
    <div class="field"><label>Humidity:</label> <span id="sens-humid">-</span>%</div>
    <div class="field"><label>Accel X:</label> <span id="sens-ax">-</span> mg</div>
    <div class="field"><label>Accel Y:</label> <span id="sens-ay">-</span> mg</div>
    <div class="field"><label>Accel Z:</label> <span id="sens-az">-</span> mg</div>
</div>

</div><!-- grid -->

<!-- Controls Panel (full width) -->
<div class="panel">
    <h2>Controls</h2>

    <div style="margin-bottom:10px;">
        <label style="color:#888;">Mode:</label>
        <div class="btn-group" id="mode-btns">
            <button onclick="setMode('raw')">Raw</button>
            <button onclick="setMode('mission')">Mission</button>
            <button onclick="setMode('tinygs')">TinyGS</button>
        </div>
    </div>

    <div style="margin-bottom:10px;">
        <label style="color:#888;">Flight:</label>
        <div class="btn-group" id="flight-btns">
            <button onclick="setFlight('idle')">Idle</button>
            <button onclick="setFlight('nominal')">Nominal</button>
            <button onclick="setFlight('safe')">Safe</button>
            <button onclick="setFlight('debug')">Debug</button>
        </div>
    </div>

    <div style="margin-bottom:10px;">
        <label style="color:#888;">TinyGS:</label>
        <select id="tinygs-profile">
            <option value="norbi">Norbi (436.703 MHz)</option>
            <option value="fossasat2">FossaSat-2 (436.7 MHz)</option>
            <option value="vr3x">VR3X (915.6 MHz)</option>
        </select>
        <button onclick="tinygsSpoof()">Spoof</button>
        <button onclick="tinygsStop()">Stop</button>
    </div>

    <div style="margin-bottom:10px;">
        <label style="color:#888;">Difficulty:</label>
        <select id="diff-select" onchange="setDifficulty(this.value)">
            <option value="0">0 — Training</option>
            <option value="1">1 — Normal</option>
            <option value="2">2 — Hardened</option>
            <option value="3">3 — Blue Team</option>
        </select>
    </div>

    <div>
        <button onclick="resetDefaults()" style="background:#442; border-color:#664;">Reset Defaults</button>
    </div>
</div>

</div><!-- sat-content -->

<div id="toast" class="toast"></div>

<script>
let countdownEnabled = false;
let lastNotifiedThreshold = 9999;

// --- API helpers ---
async function api(path, method, body) {
    const opts = {method: method || "GET", headers: {}};
    if (body) {
        opts.headers["Content-Type"] = "application/json";
        opts.body = JSON.stringify(body);
    }
    const resp = await fetch("/api/satellite/" + path, opts);
    return await resp.json();
}

function showToast(msg, duration) {
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.style.display = "block";
    setTimeout(() => t.style.display = "none", duration || 5000);
}

// --- Polling ---
async function pollInfo() {
    const data = await api("info");
    if (data.error) {
        document.getElementById("no-hw").style.display = "block";
        document.getElementById("sat-content").style.display = "none";
        return;
    }
    document.getElementById("no-hw").style.display = "none";
    document.getElementById("sat-content").style.display = "block";

    document.getElementById("fw-version").textContent = data.fw_version;
    document.getElementById("fw-git").textContent = data.git_sha + (data.git_dirty ? " (dirty)" : "");
    document.getElementById("fw-build").textContent = data.build_date;
    document.getElementById("sc-id").textContent = "0x" + (data.sc_id || 0).toString(16).padStart(2, "0");
    document.getElementById("cur-mode").textContent = data.mode;
    document.getElementById("cur-flight").textContent = data.flight;
    document.getElementById("cur-diff").textContent = data.difficulty;
    document.getElementById("diff-select").value = data.difficulty;

    // Highlight active mode/flight buttons
    highlightBtn("mode-btns", data.mode);
    highlightBtn("flight-btns", data.flight.toLowerCase());

    // Battery
    updateBattery(data.battery_mv, data.flight);
}

function highlightBtn(groupId, active) {
    const btns = document.getElementById(groupId).querySelectorAll("button");
    btns.forEach(b => {
        b.className = b.textContent.toLowerCase() === active ? "btn-active" : "";
    });
}

function updateBattery(mv, flight) {
    document.getElementById("batt-mv").textContent = mv;
    const pct = Math.max(0, Math.min(100, ((mv - 3000) / 700) * 100));
    const fill = document.getElementById("batt-fill");
    fill.style.width = pct + "%";
    fill.className = "battery-fill " + (mv > 3500 ? "batt-green" : mv > 3200 ? "batt-yellow" : "batt-red");

    // Countdown
    if (countdownEnabled) {
        const drainRate = flight === "DEBUG" ? 0.3 : 0.1; // mV per second
        const secsLeft = Math.max(0, (mv - 3000) / drainRate);
        const mins = Math.floor(secsLeft / 60);
        const secs = Math.floor(secsLeft % 60);
        const timer = document.getElementById("countdown-timer");
        timer.textContent = String(mins).padStart(2, "0") + ":" + String(secs).padStart(2, "0");
        timer.className = "countdown" + (mv < 3200 ? " countdown-danger" : "");

        // Toast notifications
        if (mv <= 3000 && lastNotifiedThreshold > 3000) {
            showToast("SATELLITE FORCED TO SAFE MODE", 10000);
            lastNotifiedThreshold = 3000;
        } else if (mv <= 3100 && lastNotifiedThreshold > 3100) {
            showToast("DANGER: 100mV until forced SAFE", 5000);
            lastNotifiedThreshold = 3100;
        } else if (mv <= 3200 && lastNotifiedThreshold > 3200) {
            showToast("Critical: battery at " + mv + "mV", 5000);
            lastNotifiedThreshold = 3200;
        } else if (mv <= 3500 && lastNotifiedThreshold > 3500) {
            showToast("Warning: battery at " + mv + "mV", 4000);
            lastNotifiedThreshold = 3500;
        }
    }
}

function toggleCountdown() {
    countdownEnabled = document.getElementById("countdown-toggle").checked;
    document.getElementById("countdown-display").style.display = countdownEnabled ? "block" : "none";
    lastNotifiedThreshold = 9999;
}

async function pollSensors() {
    const data = await api("sensors");
    if (data.error) return;
    document.getElementById("sens-temp").textContent = data.temperature;
    document.getElementById("sens-press").textContent = data.pressure;
    document.getElementById("sens-humid").textContent = data.humidity;
    document.getElementById("sens-ax").textContent = data.accel_x;
    document.getElementById("sens-ay").textContent = data.accel_y;
    document.getElementById("sens-az").textContent = data.accel_z;
}

async function pollLora() {
    const data = await api("lora_config");
    if (data.error) return;
    document.getElementById("lora-freq").textContent = data.frequency;
    document.getElementById("lora-sf").textContent = data.sf;
    document.getElementById("lora-bw").textContent = data.bw;
    document.getElementById("lora-power").textContent = data.power;
}

// --- Actions ---
async function setMode(m) { await api("mode", "POST", {mode: m}); pollInfo(); }
async function setFlight(f) { await api("flight", "POST", {flight: f}); pollInfo(); }
async function setDifficulty(l) { await api("difficulty", "POST", {level: parseInt(l)}); pollInfo(); }
async function applyLora() {
    await api("lora_config", "POST", {
        frequency: parseInt(document.getElementById("set-freq").value),
        sf: parseInt(document.getElementById("set-sf").value),
        bw: parseInt(document.getElementById("set-bw").value),
        power: parseInt(document.getElementById("set-power").value),
    });
    pollLora();
    showToast("LoRa config applied", 3000);
}
async function tinygsSpoof() {
    await api("tinygs", "POST", {action: "spoof", profile: document.getElementById("tinygs-profile").value});
    pollInfo();
}
async function tinygsStop() {
    await api("tinygs", "POST", {action: "stop"});
    pollInfo();
}
async function resetDefaults() {
    if (!confirm("Reset RF config and mode to factory defaults?")) return;
    await api("reset", "POST");
    pollInfo();
    pollLora();
    showToast("Defaults restored", 3000);
}

// --- Init ---
pollInfo();
pollLora();
pollSensors();
setInterval(pollInfo, 3000);
setInterval(pollLora, 3000);
setInterval(pollSensors, 5000);
</script>
{% endblock %}
```

- [ ] **Step 2: Run all tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add webapp/templates/satellite.html
git commit -m "feat(webapp): add satellite control page with full UI"
```

---

## Summary

| Task | Component | Files |
|------|-----------|-------|
| 1 | Multi-line shell command | core/device.py |
| 2 | Shell response parsers | core/shell_parser.py, tests/test_shell_parser.py |
| 3 | Satellite API routes + page scaffold | webapp/app.py, satellite.html, base.html, tests/test_satellite_api.py |
| 4 | Satellite control page full UI | webapp/templates/satellite.html |
