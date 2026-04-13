# Config Page, README, and Frontend Cleanup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the broken config page, add a project README, and extract all inline CSS/JS to separate static files.

**Architecture:** Three independent workstreams that touch different files. Config page changes span backend + frontend. README is standalone. Frontend cleanup is pure refactor — extract inline code to files, verify no regressions. Order: config page first (functional fix), then frontend cleanup (moves files that config page touched), then README last (no code dependencies).

**Tech Stack:** Python/Flask, vanilla JS, HTML/CSS, SQLite, pytest

---

## File Map

**Created:**
- `webapp/static/css/base.css` — extracted from `base.html`
- `webapp/static/css/dashboard.css` — extracted from `dashboard.html`
- `webapp/static/css/satellite.css` — extracted from `satellite.html`
- `webapp/static/js/dashboard.js` — extracted from `dashboard.html`
- `webapp/static/js/satellite.js` — extracted from `satellite.html`
- `webapp/static/js/config.js` — new form handler (replaces inline script)
- `README.md` — project documentation

**Modified:**
- `webapp/app.py` — `api_config_update` endpoint (lines 201-217)
- `webapp/templates/config.html` — full file rewrite (link to config.js)
- `webapp/templates/base.html` — replace `<style>` with CSS link
- `webapp/templates/dashboard.html` — replace `<style>` and `<script>` with links
- `webapp/templates/satellite.html` — replace `<style>` and `<script>` with links

**Test files:**
- `tests/test_config_api.py` — new: tests for the updated config endpoint

---

### Task 1: Config Page — Backend (upsert + shell commands for all 4 fields)

**Files:**
- Create: `tests/test_config_api.py`
- Modify: `webapp/app.py:201-217`

- [ ] **Step 1: Write failing tests for the updated config endpoint**

Create `tests/test_config_api.py`:

```python
import os
import tempfile

import pytest

from webapp.config import TestConfig
from webapp.db import get_db, init_db
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
def client(app):
    c = app.test_client()
    c.post("/login", data={"username": "operator", "password": "operator123"})
    return c


def test_config_update_all_fields(client, app):
    """POST /api/config/radio sends all 4 fields and persists them."""
    resp = client.post(
        "/api/config/radio",
        json={
            "frequency": "433000000",
            "spreading_factor": "10",
            "bandwidth": "250000",
            "tx_power": "20",
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["config"]["frequency"] == 433000000
    assert data["config"]["spreading_factor"] == 10
    assert data["config"]["bandwidth"] == 250000
    assert data["config"]["tx_power"] == 20


def test_config_update_persists_to_db(client, app):
    """Config is upserted for the logged-in user."""
    client.post(
        "/api/config/radio",
        json={
            "frequency": "868000000",
            "spreading_factor": "12",
            "bandwidth": "125000",
            "tx_power": "14",
        },
    )
    with app.app_context():
        db = get_db()
        row = db.execute(
            "SELECT * FROM radio_config WHERE owner = ? AND description = ?",
            ("operator", "Manual"),
        ).fetchone()
        assert row is not None
        assert row["frequency"] == 868000000
        assert row["spreading_factor"] == 12


def test_config_update_upserts(client, app):
    """Second POST updates existing row, not inserts a new one."""
    client.post("/api/config/radio", json={"frequency": "100"})
    client.post("/api/config/radio", json={"frequency": "200"})
    with app.app_context():
        db = get_db()
        rows = db.execute(
            "SELECT * FROM radio_config WHERE owner = ? AND description = ?",
            ("operator", "Manual"),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["frequency"] == 200


def test_config_update_shell_injection_surface(client):
    """GS-07: f-string shell injection works for all 4 fields."""
    resp = client.post(
        "/api/config/radio",
        json={"frequency": "915000000; echo pwned"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    # The shell command output should contain 'pwned'
    assert "pwned" in data.get("shell_output", "")


def test_config_update_defaults(client):
    """Missing fields use defaults."""
    resp = client.post("/api/config/radio", json={})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["config"]["frequency"] == 915000000
    assert data["config"]["spreading_factor"] == 7
    assert data["config"]["bandwidth"] == 125000
    assert data["config"]["tx_power"] == 14
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config_api.py -v`
Expected: FAIL — current endpoint returns `{"output": ...}` not `{"status": "ok", "config": {...}}`

- [ ] **Step 3: Implement the updated endpoint**

Replace `api_config_update` in `webapp/app.py` (lines 201-217) with:

```python
    @app.route("/api/config/radio", methods=["POST"])
    @login_required
    def api_config_update():
        import subprocess

        from webapp.db import get_db

        data = request.get_json(silent=True) or {}
        frequency = data.get("frequency", "915000000")
        spreading_factor = data.get("spreading_factor", "7")
        bandwidth = data.get("bandwidth", "125000")
        tx_power = data.get("tx_power", "14")

        # VULNERABLE: f-string in shell commands (GS-07 — all 4 fields)
        try:
            output = subprocess.check_output(
                f"echo 'Setting frequency to {frequency}, SF={spreading_factor}, BW={bandwidth}, power={tx_power}'",
                shell=True,
                stderr=subprocess.STDOUT,
            )
            shell_output = output.decode(errors="replace")
        except subprocess.CalledProcessError as e:
            shell_output = e.output.decode(errors="replace")

        # Upsert into radio_config for current user
        db = get_db()
        existing = db.execute(
            "SELECT id FROM radio_config WHERE owner = ? AND description = ?",
            (g.username, "Manual"),
        ).fetchone()
        freq_int = int(str(frequency).split(";")[0].split("&")[0].strip() or "0") if str(frequency).strip() else 915000000
        sf_int = int(str(spreading_factor).split(";")[0].strip() or "7") if str(spreading_factor).strip() else 7
        bw_int = int(str(bandwidth).split(";")[0].strip() or "125000") if str(bandwidth).strip() else 125000
        power_int = int(str(tx_power).split(";")[0].strip() or "14") if str(tx_power).strip() else 14

        if existing:
            db.execute(
                "UPDATE radio_config SET frequency=?, spreading_factor=?, bandwidth=?, tx_power=? WHERE id=?",
                (freq_int, sf_int, bw_int, power_int, existing["id"]),
            )
        else:
            db.execute(
                "INSERT INTO radio_config (owner, frequency, spreading_factor, bandwidth, tx_power, description) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (g.username, freq_int, sf_int, bw_int, power_int, "Manual"),
            )
        db.commit()

        config = db.execute(
            "SELECT * FROM radio_config WHERE owner = ? AND description = ?",
            (g.username, "Manual"),
        ).fetchone()

        return {
            "status": "ok",
            "shell_output": shell_output,
            "config": dict(config),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config_api.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `pytest --tb=short -q`
Expected: All 153+ tests PASS (148 existing + 5 new)

- [ ] **Step 6: Commit**

```bash
git add tests/test_config_api.py webapp/app.py
git commit -m "feat: complete config endpoint — all 4 radio fields with DB upsert

The POST /api/config/radio endpoint now accepts frequency, spreading_factor,
bandwidth, and tx_power. Values are persisted via upsert and all fields pass
through f-string shell interpolation (GS-07 CTF surface)."
```

---

### Task 2: Config Page — Frontend (send all 4 fields)

**Files:**
- Create: `webapp/static/js/config.js`
- Modify: `webapp/templates/config.html`

- [ ] **Step 1: Create `webapp/static/js/config.js`**

```javascript
document.getElementById("config-form").addEventListener("submit", async function(e) {
    e.preventDefault();
    const resp = await fetch("/api/config/radio", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            frequency: document.getElementById("frequency").value,
            spreading_factor: document.getElementById("spreading_factor").value,
            bandwidth: document.getElementById("bandwidth").value,
            tx_power: document.getElementById("tx_power").value,
        }),
    });
    const result = await resp.json();
    document.getElementById("config-response").textContent = JSON.stringify(result, null, 2);
});
```

- [ ] **Step 2: Update `webapp/templates/config.html`**

Replace the entire file with:

```html
{% extends "base.html" %}
{% block title %}Config{% endblock %}
{% block content %}
<h1>Radio Configuration</h1>
<form id="config-form">
    <label>Frequency (Hz): <input name="frequency" id="frequency" type="number" value="{{ config.frequency if config else 915000000 }}"></label><br><br>
    <label>Spreading Factor: <input name="spreading_factor" id="spreading_factor" type="number" min="7" max="12" value="{{ config.spreading_factor if config else 7 }}"></label><br><br>
    <label>Bandwidth (Hz): <input name="bandwidth" id="bandwidth" type="number" value="{{ config.bandwidth if config else 125000 }}"></label><br><br>
    <label>TX Power (dBm): <input name="tx_power" id="tx_power" type="number" value="{{ config.tx_power if config else 14 }}"></label><br><br>
    <button type="submit">Update Config</button>
</form>
<pre id="config-response"></pre>
<script src="/static/js/config.js"></script>
{% endblock %}
```

- [ ] **Step 3: Verify config page renders and link in nav**

The config page is not in `base.html` nav. Add it:

In `webapp/templates/base.html`, in the `<nav>` block, add a Config link after Satellite:

```html
<a href="/config">Config</a> |
```

So the nav becomes:
```html
<nav>
    <a href="/dashboard">Dashboard</a> |
    <a href="/logs">Logs</a> |
    <a href="/satellite">Satellite</a> |
    <a href="/config">Config</a> |
    <a href="/logout">Logout ({{ g.username }})</a>
</nav>
```

- [ ] **Step 4: Run existing tests to confirm no regressions**

Run: `pytest --tb=short -q`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add webapp/static/js/config.js webapp/templates/config.html webapp/templates/base.html
git commit -m "feat: config page sends all 4 radio fields, add nav link

Form now posts frequency, SF, bandwidth, and TX power to the backend.
JS extracted to static/js/config.js. Config page added to nav bar."
```

---

### Task 3: Frontend Cleanup — Extract CSS

**Files:**
- Create: `webapp/static/css/base.css`
- Create: `webapp/static/css/dashboard.css`
- Create: `webapp/static/css/satellite.css`
- Modify: `webapp/templates/base.html`
- Modify: `webapp/templates/dashboard.html`
- Modify: `webapp/templates/satellite.html`

- [ ] **Step 1: Create `webapp/static/css/base.css`**

Extract the contents of the `<style>` tag in `base.html`:

```css
body { font-family: monospace; background: #0a0a0a; color: #00ff41; margin: 20px; }
a { color: #00ccff; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #333; padding: 6px; text-align: left; }
th { background: #1a1a1a; }
input, select, button { background: #1a1a1a; color: #00ff41; border: 1px solid #333; padding: 5px; }
button { cursor: pointer; }
button:hover { background: #333; }
nav { margin-bottom: 20px; padding: 10px; background: #111; }
.error { color: #ff4444; }
pre { background: #111; padding: 10px; overflow-x: auto; }
```

- [ ] **Step 2: Create `webapp/static/css/dashboard.css`**

Extract the contents of the `<style>` tag in `dashboard.html` `{% block head %}` (everything between `<style>` and `</style>`):

```css
#hw-status { padding:10px; margin-bottom:15px; border:1px solid #333; background:#111; }
#hw-indicator { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:8px; }
.ind-idle { background:#888; }
.ind-sim { background:#ffaa00; animation: blink 2s infinite; }
.ind-hw { background:#00ff41; animation: blink 1s infinite; }
@keyframes blink { 50% { opacity:0.4; } }
#tm-column-controls { display:flex; gap:10px; margin:10px 0 12px; padding:10px; border:1px solid #333; background:#111; align-items:center; }
.tm-column-title { color:#888; font-size:0.9em; }
#tm-col-dropdown { position:relative; display:inline-block; }
#tm-col-btn { background:#1a1a1a; color:#00ff41; border:1px solid #333; padding:5px 10px; cursor:pointer; }
#tm-col-btn:hover { background:#333; }
#tm-col-menu { display:none; position:absolute; top:100%; left:0; background:#1a1a1a; border:1px solid #333; padding:8px; z-index:10; min-width:160px; max-height:50vh; overflow-y:auto; }
#tm-col-menu.open { display:block; }
#tm-col-menu label { display:block; color:#ddd; font-size:0.85em; padding:2px 0; white-space:nowrap; cursor:pointer; }
#tm-col-menu label:hover { color:#00ff41; }
#tm-col-menu label input { margin-right:6px; }
#tm-columns-reset { font-size:0.85em; }
#tm-container { max-height:60vh; overflow:auto; border:1px solid #333; }
#tm-container table { margin:0; }
#telemetry-table { table-layout:fixed; font-size:0.9em; }
#telemetry-table th, #telemetry-table td { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; padding:4px 6px; }
th[data-col="recv_time"],td[data-col="recv_time"] { width:80px; }
th[data-col="frame_ts"],td[data-col="frame_ts"] { width:70px; }
th[data-col="apid"],td[data-col="apid"] { width:55px; }
th[data-col="seq"],td[data-col="seq"] { width:50px; }
th[data-col="sc_id"],td[data-col="sc_id"] { width:45px; }
th[data-col="flight"],td[data-col="flight"] { width:70px; }
th[data-col="difficulty"],td[data-col="difficulty"] { width:35px; }
th[data-col="battery"],td[data-col="battery"] { width:72px; }
th[data-col="uptime"],td[data-col="uptime"] { width:65px; }
th[data-col="tc_count"],td[data-col="tc_count"] { width:40px; }
th[data-col="error_count"],td[data-col="error_count"] { width:40px; }
th[data-col="temp"],td[data-col="temp"] { width:72px; }
th[data-col="pressure"],td[data-col="pressure"] { width:85px; }
th[data-col="humidity"],td[data-col="humidity"] { width:40px; }
th[data-col="accel_x"],td[data-col="accel_x"] { width:45px; }
th[data-col="accel_y"],td[data-col="accel_y"] { width:45px; }
th[data-col="accel_z"],td[data-col="accel_z"] { width:45px; }
th[data-col="rssi"],td[data-col="rssi"] { width:68px; }
th[data-col="snr"],td[data-col="snr"] { width:55px; }
th[data-col="raw"],td[data-col="raw"] { width:280px; }
#pkt-counter { color:#00ccff; margin-left:15px; }
#last-seen { color:#888; margin-left:15px; font-size:0.9em; }
.btn-active { background:#00ff41 !important; color:#0a0a0a !important; font-weight:bold; }
#tm-filter:focus { outline:1px solid #00ff41; }
#tm-pagination button { background:#1a1a1a; color:#00ccff; border:1px solid #333; padding:4px 10px; cursor:pointer; }
#tm-pagination button:hover:not(:disabled) { background:#333; }
#tm-pagination button:disabled { color:#555; cursor:default; }
```

- [ ] **Step 3: Create `webapp/static/css/satellite.css`**

Extract the contents of the `<style>` tag in `satellite.html`:

```css
.panel { border:1px solid #333; padding:15px; margin-bottom:15px; background:#111; }
.panel h2 { margin-top:0; color:#00ccff; font-size:1.1em; display:flex; align-items:center; justify-content:space-between; gap:10px; }
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
.sync-banner { margin-bottom:15px; padding:12px 15px; border:1px solid #2c4b59; background:linear-gradient(90deg, #10222a 0%, #0f171a 100%); color:#9fd9eb; }
.sync-banner.hidden { display:none; }
.panel-status { color:#6f9ead; font-size:0.8em; text-transform:uppercase; letter-spacing:0.08em; }
.panel-syncing { opacity:0.78; }
.panel-syncing .field span { color:#78a0aa; }
.panel-ready .panel-status { color:#00ff41; }
.panel-error .panel-status { color:#ff7777; }
.loading-value { color:#78a0aa !important; }
.controls-disabled button,
.controls-disabled select,
.controls-disabled input { opacity:0.6; pointer-events:none; }
```

- [ ] **Step 4: Update `base.html` — replace `<style>` with CSS link**

Replace the `<style>...</style>` block in `base.html` with:

```html
<link rel="stylesheet" href="/static/css/base.css">
```

So the `<head>` becomes:

```html
<head>
    <title>PwnSat2 Ground Station — {% block title %}{% endblock %}</title>
    <link rel="stylesheet" href="/static/css/base.css">
    {% block head %}{% endblock %}
</head>
```

- [ ] **Step 5: Update `dashboard.html` — replace `<style>` with CSS link**

In the `{% block head %}` of `dashboard.html`, replace the `<style>...</style>` block with:

```html
<link rel="stylesheet" href="/static/css/dashboard.css">
```

Keep the `<script src="...socket.io...">` tag. The block becomes:

```html
{% block head %}
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.min.js"></script>
<link rel="stylesheet" href="/static/css/dashboard.css">
{% endblock %}
```

- [ ] **Step 6: Update `satellite.html` — replace `<style>` with CSS link**

In the `{% block head %}` of `satellite.html`, replace the `<style>...</style>` block with:

```html
{% block head %}
<link rel="stylesheet" href="/static/css/satellite.css">
{% endblock %}
```

- [ ] **Step 7: Run tests to verify no regressions**

Run: `pytest --tb=short -q`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add webapp/static/css/ webapp/templates/base.html webapp/templates/dashboard.html webapp/templates/satellite.html
git commit -m "refactor: extract inline CSS to separate static files

Move styles from base.html, dashboard.html, and satellite.html into
webapp/static/css/{base,dashboard,satellite}.css. No visual changes."
```

---

### Task 4: Frontend Cleanup — Extract JS

**Files:**
- Create: `webapp/static/js/dashboard.js`
- Create: `webapp/static/js/satellite.js`
- Modify: `webapp/templates/dashboard.html`
- Modify: `webapp/templates/satellite.html`

- [ ] **Step 1: Create `webapp/static/js/dashboard.js`**

Extract all inline JS from `dashboard.html` — everything inside the `<script>` tag that is NOT the socket.io CDN or the telemetry.js include. This is the block between `<script>` (line 154 in original) and `</script>` (line 342 in original):

```javascript
let pktCount = 0;
let hasScannedDevices = false;

// --- Button state management ---
function setButtons(state) {
    const els = {
        simulate: document.getElementById("btn-simulate"),
        stop: document.getElementById("btn-stop"),
        scan: document.getElementById("btn-scan"),
        connect: document.getElementById("btn-connect"),
        disconnect: document.getElementById("btn-disconnect"),
    };
    Object.values(els).forEach(b => b.disabled = true);

    if (state === "idle" || state === "simulated") {
        els.simulate.disabled = (state === "simulated");
        els.stop.disabled = (state !== "simulated");
        els.scan.disabled = false;
        if (hasScannedDevices) {
            els.connect.disabled = false;
        }
    } else if (state === "scanned") {
        els.simulate.disabled = false;
        els.connect.disabled = false;
        els.scan.disabled = false;
    } else if (state === "hardware") {
        els.disconnect.disabled = false;
    }
}

function setIndicator(mode) {
    const ind = document.getElementById("hw-indicator");
    ind.className = mode === "hardware" ? "ind-hw" : mode === "simulated" ? "ind-sim" : "ind-idle";
}

// --- Status (polls every 5s when hardware) ---
async function hwStatus() {
    const resp = await fetch("/api/hardware/status");
    const data = await resp.json();
    const el = document.getElementById("hw-mode");
    const serial = document.getElementById("hw-serial");

    document.getElementById("btn-simulate").className = "";
    document.getElementById("btn-connect").className = "";

    if (data.mode === "hardware") {
        el.textContent = "HARDWARE";
        el.style.color = "#00ff41";
        serial.textContent = " | SN: " + (data.serial_number || "");
        setButtons("hardware");
        setIndicator("hardware");
        document.getElementById("btn-connect").className = "btn-active";
    } else if (data.mode === "simulated") {
        el.textContent = "SIMULATED";
        el.style.color = "#ffaa00";
        serial.textContent = "";
        document.getElementById("hw-rssi").textContent = "";
        setButtons("simulated");
        setIndicator("simulated");
        document.getElementById("btn-simulate").className = "btn-active";
    } else {
        el.textContent = "IDLE";
        el.style.color = "#888";
        serial.textContent = "";
        document.getElementById("hw-rssi").textContent = "";
        setButtons("idle");
        setIndicator("idle");
    }
}

setInterval(hwStatus, 5000);

// --- Actions ---
async function hwSimulate() {
    await fetch("/api/hardware/simulate", {method: "POST"});
    pktCount = 0;
    hwStatus();
}

async function hwStop() {
    await fetch("/api/hardware/stop", {method: "POST"});
    document.getElementById("telemetry-body").innerHTML = "";
    pktCount = 0;
    document.getElementById("pkt-counter").textContent = "";
    document.getElementById("last-seen").textContent = "";
    hwStatus();
}

async function hwScan() {
    console.log("[GS] Scanning for devices...");
    const resp = await fetch("/api/hardware/scan", {method: "POST"});
    const data = await resp.json();
    console.log("[GS] Scan result:", data);
    const sel = document.getElementById("hw-devices");
    sel.innerHTML = "";

    if (data.devices.length > 0) {
        sel.style.display = "inline";
        hasScannedDevices = true;
        data.devices.forEach(d => {
            const opt = document.createElement("option");
            opt.value = d.serial_number;
            opt.textContent = d.serial_number + " (" + d.health + ")";
            sel.appendChild(opt);
        });
        setButtons("scanned");
    } else {
        sel.style.display = "none";
        hasScannedDevices = false;
        alert("No FlatSat devices found");
        setButtons("idle");
    }
}

async function hwConnect() {
    const sn = document.getElementById("hw-devices").value;
    console.log("[GS] Connecting to:", sn);
    if (!sn) { console.log("[GS] No device selected"); return; }
    try {
        const resp = await fetch("/api/hardware/connect", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({serial_number: sn})
        });
        const data = await resp.json();
        console.log("[GS] Connect result:", data);
        if (data.mode === "hardware") {
            pktCount = 0;
            hwStatus();
        } else {
            alert("Connection failed: " + (data.error || JSON.stringify(data)));
        }
    } catch (e) {
        console.error("[GS] Connect error:", e);
        alert("Connection error: " + e.message);
    }
}

async function hwDisconnect() {
    console.log("[GS] Disconnecting...");
    const resp = await fetch("/api/hardware/disconnect", {method: "POST"});
    const data = await resp.json();
    console.log("[GS] Disconnect result:", data);
    document.getElementById("hw-devices").style.display = "none";
    hasScannedDevices = false;
    document.getElementById("telemetry-body").innerHTML = "";
    pktCount = 0;
    document.getElementById("pkt-counter").textContent = "";
    document.getElementById("last-seen").textContent = "";
    hwStatus();
}

hwStatus();

// Close column dropdown on outside click
document.addEventListener("click", function(e) {
    const menu = document.getElementById("tm-col-menu");
    const btn = document.getElementById("tm-col-btn");
    if (!menu.contains(e.target) && e.target !== btn) {
        menu.classList.remove("open");
    }
});

// --- Telecommand form handler ---
document.getElementById("tc-form").addEventListener("submit", async function(e) {
    e.preventDefault();
    const opcode = document.getElementById("opcode").value;
    const cmdName = document.getElementById("opcode").selectedOptions[0].text;
    const data = document.getElementById("tc-data").value || "";
    const resp = await fetch("/api/radio/send_tc", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({opcode: opcode, data: data})
    });
    const result = await resp.json();
    const ts = new Date().toLocaleTimeString();
    const pre = document.getElementById("tc-response");
    const entry = "[" + ts + "] " + cmdName + " → " + (result.status || "error")
        + (result.frame_size ? " (" + result.frame_size + " bytes)" : "")
        + (result.frame_hex ? " [" + result.frame_hex + "]" : "")
        + (result.error ? " — " + result.error : "")
        + "\n";
    pre.textContent = entry + pre.textContent;
});
```

- [ ] **Step 2: Create `webapp/static/js/satellite.js`**

Extract all inline JS from `satellite.html` — everything inside the `<script>` tag (lines 190-583 in original). Copy it verbatim — the full ~400 lines starting with `let countdownEnabled = ...` through `init();`.

The file is too long to repeat here. Copy the exact content between `<script>` and `</script>` in `satellite.html` into `webapp/static/js/satellite.js`. No modifications needed.

- [ ] **Step 3: Update `dashboard.html` — replace inline `<script>` with file references**

Remove the inline `<script>` block (the one containing `let pktCount = 0; ...`). Keep the HTML content. At the end of `{% block content %}`, before `{% endblock %}`, have only:

```html
<script src="/static/js/dashboard.js"></script>
<script src="/static/js/telemetry.js"></script>
```

The socket.io CDN script stays in `{% block head %}`.

- [ ] **Step 4: Update `satellite.html` — replace inline `<script>` with file reference**

Remove the inline `<script>` block. At the end of `{% block content %}`, before `{% endblock %}`, have only:

```html
<script src="/static/js/satellite.js"></script>
```

- [ ] **Step 5: Run tests to verify no regressions**

Run: `pytest --tb=short -q`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add webapp/static/js/dashboard.js webapp/static/js/satellite.js webapp/templates/dashboard.html webapp/templates/satellite.html
git commit -m "refactor: extract inline JS to separate static files

Move JavaScript from dashboard.html and satellite.html into
webapp/static/js/{dashboard,satellite}.js. No behavior changes."
```

---

### Task 5: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README.md**

```markdown
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
browser  ←→  webapp/ (Flask + SocketIO)  ←→  core/ (protocol + serial)  ←→  FlatSat USB
                 ↕
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

148 tests covering the core library, webapp routes, and vulnerability checks.

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
```

- [ ] **Step 2: Run tests to confirm nothing broke**

Run: `pytest --tb=short -q`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add project README with architecture and setup guide"
```

---

### Task 6: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `pytest -v`
Expected: All tests PASS (153+ total)

- [ ] **Step 2: Verify no leftover inline styles or scripts**

Run these checks:

```bash
# Should find NO <style> tags in templates (except login.html which has none)
grep -l '<style>' webapp/templates/*.html
# Expected: no output

# Should find NO inline <script> blocks (only <script src=...> references)
grep -n '<script>' webapp/templates/*.html | grep -v 'src='
# Expected: no output
```

- [ ] **Step 3: Spot-check file sizes**

```bash
wc -l webapp/static/css/*.css webapp/static/js/*.js
```

Expected approximate line counts:
- `base.css`: ~11
- `dashboard.css`: ~50
- `satellite.css`: ~30
- `config.js`: ~15
- `dashboard.js`: ~160
- `satellite.js`: ~395
- `telemetry.js`: ~327
