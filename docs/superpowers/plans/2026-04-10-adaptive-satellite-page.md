# Adaptive Satellite Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/satellite` page adapt its UI based on mode — showing remote satellite data (from heartbeat telemetry) in Ground Station mode, and local satellite controls in Mission/Raw/TinyGS modes.

**Architecture:** The telemetry thread stores the last decoded heartbeat in `app.config["LAST_HEARTBEAT"]`. A new API endpoint `/api/satellite/remote` exposes it. The frontend JS detects the current mode and shows/hides sections, changes the title, and switches between local shell data and remote heartbeat data for battery/flight/difficulty.

**Tech Stack:** Existing Flask + JS, no new dependencies.

---

## File Structure

```
webapp/
├── app.py                    # MODIFY: store last heartbeat, add /api/satellite/remote
├── templates/
│   └── satellite.html        # REWRITE: adaptive layout with remote/local sections

tests/
├── test_satellite_api.py     # MODIFY: add test for /api/satellite/remote
```

---

### Task 1: Store last heartbeat and expose via API

**Files:**
- Modify: `webapp/app.py`
- Modify: `tests/test_satellite_api.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_satellite_api.py`:

```python
def test_satellite_remote_no_data(app, auth_client):
    _setup_hardware(app)
    resp = auth_client.get("/api/satellite/remote")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["available"] is False


def test_satellite_remote_with_heartbeat(app, auth_client):
    _setup_hardware(app)
    # Simulate a stored heartbeat
    app.config["LAST_HEARTBEAT"] = {
        "sc_id": 2,
        "uptime": 500,
        "battery_mv": 3500,
        "flight_mode": 1,
        "difficulty": 0,
        "tc_count": 10,
        "error_count": 0,
        "timestamp": "2026-04-10T12:00:00",
    }
    resp = auth_client.get("/api/satellite/remote")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["available"] is True
    assert data["battery_mv"] == 3500
    assert data["flight_mode"] == 1
    assert data["tc_count"] == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_satellite_api.py::test_satellite_remote_no_data -v`
Expected: FAIL (route not found)

- [ ] **Step 3: Add LAST_HEARTBEAT config and /api/satellite/remote route**

In `webapp/app.py`, after the line `app.config["SCANNED_DEVICES"] = {}`, add:

```python
    app.config["LAST_HEARTBEAT"] = None
```

Add the new route inside `create_app()`, after the existing `/api/satellite/reset` route:

```python
    @app.route("/api/satellite/remote")
    @login_required
    def api_satellite_remote():
        """Last received heartbeat from remote satellite (Ground Station mode)."""
        hb = app.config.get("LAST_HEARTBEAT")
        if not hb:
            return {"available": False}
        return {"available": True, **hb}
```

- [ ] **Step 4: Store heartbeat in telemetry thread**

In the telemetry thread's hardware mode section, after `decoded = decode_tm_payload(pkt.apid, pkt.payload)`, add heartbeat storage. Find the line that does `decoded = decode_tm_payload(pkt.apid, pkt.payload)` and add after it:

```python
                                # Store heartbeat for /api/satellite/remote
                                if pkt.apid == 0x001 and "sc_id" in decoded:
                                    from datetime import datetime

                                    app.config["LAST_HEARTBEAT"] = {
                                        **decoded,
                                        "timestamp": datetime.now().isoformat(),
                                        "rssi": parsed.get("rssi"),
                                        "snr": parsed.get("snr"),
                                    }
```

Note: the `from datetime import datetime` is already imported in that block, so just add the heartbeat storage.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_satellite_api.py -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add webapp/app.py tests/test_satellite_api.py
git commit -m "feat(webapp): store last heartbeat and expose via /api/satellite/remote"
```

---

### Task 2: Rewrite satellite.html with adaptive layout

**Files:**
- Rewrite: `webapp/templates/satellite.html`

- [ ] **Step 1: Replace satellite.html with adaptive layout**

Replace the entire file with the new template. The key changes:

1. **Title** changes based on mode: "Satellite Control" vs "Ground Station Control"
2. **Mode buttons** always visible at top
3. **In Ground Station mode:**
   - Shows "Remote Satellite" panel (from heartbeat data via `/api/satellite/remote`)
   - Battery/countdown uses remote satellite battery
   - Flight, difficulty, SC ID from heartbeat (read-only)
   - "Last beacon" indicator with age color
   - Hides: Flight buttons, Difficulty selector, TinyGS controls
   - Shows: "Local Station" panel (firmware, sensors, reset)
   - Radio labels: "Downlink" / "Uplink"
4. **In Satellite mode (Mission/Raw/TinyGS):**
   - Shows all controls (flight, difficulty, TinyGS, battery from shell)
   - Hides: Remote Satellite panel, Local Station panel
   - Radio labels: "TM TX" / "TC RX"

`webapp/templates/satellite.html`:
```html
{% extends "base.html" %}
{% block title %}Satellite{% endblock %}
{% block head %}
<style>
    .panel { border:1px solid #333; padding:15px; margin-bottom:15px; background:#111; }
    .panel h2 { margin-top:0; color:#00ccff; font-size:1.1em; }
    .panel-remote h2 { color:#00ff41; }
    .panel-local h2 { color:#ffaa00; }
    .grid { display:grid; grid-template-columns:1fr 1fr; gap:15px; }
    .full-width { grid-column: 1 / -1; }
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
    .beacon-age { display:inline-block; padding:2px 8px; border-radius:3px; font-size:0.85em; }
    .beacon-fresh { background:#00ff41; color:#0a0a0a; }
    .beacon-stale { background:#ffaa00; color:#0a0a0a; }
    .beacon-lost { background:#ff4444; color:white; }
    .note { color:#666; font-size:0.85em; font-style:italic; margin-top:8px; }
</style>
{% endblock %}
{% block content %}
<h1 id="page-title">Satellite Control</h1>

<div id="no-hw" style="display:none; color:#ff4444; font-size:1.2em; padding:20px;">
    No device connected — <a href="/dashboard">connect from Dashboard</a>.
</div>

<div id="sat-content" style="display:none;">

<!-- Mode buttons — always visible -->
<div class="panel">
    <label style="color:#888;">Mode:</label>
    <div class="btn-group" id="mode-btns">
        <button onclick="setMode('raw')">Raw</button>
        <button onclick="setMode('mission')">Mission</button>
        <button onclick="setMode('ground_station')">Ground Station</button>
        <button onclick="setMode('tinygs')">TinyGS</button>
    </div>
    <select id="tinygs-profile" style="margin-left:10px;">
        <option value="norbi">Norbi (436.703 MHz)</option>
        <option value="fossasat2">FossaSat-2 (436.7 MHz)</option>
        <option value="vr3x">VR3X (915.6 MHz)</option>
    </select>
</div>

<!-- ============ GROUND STATION MODE ============ -->
<div id="gs-mode" style="display:none;">

<!-- Remote Satellite Panel (full width, prominent) -->
<div class="panel panel-remote full-width">
    <h2>Remote Satellite <span id="beacon-age" class="beacon-age beacon-lost">No beacon</span></h2>
    <div class="grid">
        <div>
            <div class="field"><label>SC ID:</label> <span id="remote-scid">-</span></div>
            <div class="field"><label>Flight:</label> <span id="remote-flight">-</span></div>
            <div class="field"><label>Difficulty:</label> <span id="remote-diff">-</span></div>
            <div class="field"><label>Uptime:</label> <span id="remote-uptime">-</span></div>
            <div class="field"><label>TC Count:</label> <span id="remote-tc">-</span></div>
            <div class="field"><label>Errors:</label> <span id="remote-err">-</span></div>
            <div class="field"><label>RSSI:</label> <span id="remote-rssi">-</span> dBm</div>
        </div>
        <div>
            <div class="field">
                <label>Battery:</label> <span id="remote-batt">-</span> mV
            </div>
            <div class="battery-bar"><div id="remote-batt-fill" class="battery-fill batt-green" style="width:100%"></div></div>
            <div style="margin-top:10px;">
                <label><input type="checkbox" id="countdown-toggle" onchange="toggleCountdown()"> Enable Countdown</label>
            </div>
            <div id="countdown-display" style="display:none;">
                <div class="countdown" id="countdown-timer">--:--</div>
                <div style="color:#888;">before forced SAFE mode</div>
            </div>
        </div>
    </div>
    <div class="note">Live data from remote satellite via telemetry heartbeat (read-only)</div>
</div>

<!-- Radio configs -->
<div class="grid">
    <div class="panel">
        <h2>Radio 0 — Downlink</h2>
        <div class="field"><label>Frequency:</label> <span id="lora-r0-freq">-</span> Hz</div>
        <div class="field"><label>SF:</label> <span id="lora-r0-sf">-</span></div>
        <div class="field"><label>BW:</label> <span id="lora-r0-bw">-</span> kHz</div>
        <div class="field"><label>Power:</label> <span id="lora-r0-power">-</span> dBm</div>
        <hr style="border-color:#333;">
        <div class="field"><label>Set Freq (Hz):</label> <input id="set-r0-freq" type="number" value="915000000" style="width:130px;"></div>
        <div class="field"><label>Set SF:</label> <input id="set-r0-sf" type="number" min="7" max="12" value="7" style="width:60px;"></div>
        <div class="field"><label>Set BW (kHz):</label> <select id="set-r0-bw"><option>125</option><option>250</option><option>500</option></select></div>
        <div class="field"><label>Set Power (dBm):</label> <input id="set-r0-power" type="number" min="-9" max="22" value="20" style="width:60px;"></div>
        <button onclick="applyLora('R0')">Apply R0</button>
    </div>
    <div class="panel">
        <h2>Radio 1 — Uplink</h2>
        <div class="field"><label>Frequency:</label> <span id="lora-r1-freq">-</span> Hz</div>
        <div class="field"><label>SF:</label> <span id="lora-r1-sf">-</span></div>
        <div class="field"><label>BW:</label> <span id="lora-r1-bw">-</span> kHz</div>
        <div class="field"><label>Power:</label> <span id="lora-r1-power">-</span> dBm</div>
        <hr style="border-color:#333;">
        <div class="field"><label>Set Freq (Hz):</label> <input id="set-r1-freq" type="number" value="916000000" style="width:130px;"></div>
        <div class="field"><label>Set SF:</label> <input id="set-r1-sf" type="number" min="7" max="12" value="7" style="width:60px;"></div>
        <div class="field"><label>Set BW (kHz):</label> <select id="set-r1-bw"><option>125</option><option>250</option><option>500</option></select></div>
        <div class="field"><label>Set Power (dBm):</label> <input id="set-r1-power" type="number" min="-9" max="22" value="20" style="width:60px;"></div>
        <button onclick="applyLora('R1')">Apply R1</button>
    </div>
</div>

<!-- Local Station -->
<div class="panel panel-local">
    <h2>Local Station</h2>
    <div class="grid">
        <div>
            <div class="field"><label>Firmware:</label> <span id="gs-fw-version">-</span></div>
            <div class="field"><label>Git:</label> <span id="gs-fw-git">-</span></div>
            <div class="field"><label>Build:</label> <span id="gs-fw-build">-</span></div>
        </div>
        <div>
            <div class="field"><label>Temperature:</label> <span id="gs-sens-temp">-</span> C</div>
            <div class="field"><label>Pressure:</label> <span id="gs-sens-press">-</span> Pa</div>
            <div class="field"><label>Humidity:</label> <span id="gs-sens-humid">-</span>%</div>
            <div class="field"><label>Accel:</label> <span id="gs-sens-ax">-</span>, <span id="gs-sens-ay">-</span>, <span id="gs-sens-az">-</span> mg</div>
        </div>
    </div>
    <button onclick="resetDefaults()" style="background:#442; border-color:#664; margin-top:10px;">Reset Defaults</button>
</div>

</div><!-- gs-mode -->

<!-- ============ SATELLITE MODE ============ -->
<div id="sat-mode" style="display:none;">
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
        <label><input type="checkbox" id="sat-countdown-toggle" onchange="toggleCountdown()"> Enable Countdown</label>
    </div>
    <div id="sat-countdown-display" style="display:none;">
        <div class="countdown" id="sat-countdown-timer">--:--</div>
        <div style="color:#888;">before forced SAFE mode</div>
    </div>
</div>

<!-- Radio 0 -->
<div class="panel">
    <h2>Radio 0 — TM TX</h2>
    <div class="field"><label>Frequency:</label> <span id="sat-lora-r0-freq">-</span> Hz</div>
    <div class="field"><label>SF:</label> <span id="sat-lora-r0-sf">-</span></div>
    <div class="field"><label>BW:</label> <span id="sat-lora-r0-bw">-</span> kHz</div>
    <div class="field"><label>Power:</label> <span id="sat-lora-r0-power">-</span> dBm</div>
    <hr style="border-color:#333;">
    <div class="field"><label>Set Freq (Hz):</label> <input id="sat-set-r0-freq" type="number" value="915000000" style="width:130px;"></div>
    <div class="field"><label>Set SF:</label> <input id="sat-set-r0-sf" type="number" min="7" max="12" value="7" style="width:60px;"></div>
    <div class="field"><label>Set BW (kHz):</label> <select id="sat-set-r0-bw"><option>125</option><option>250</option><option>500</option></select></div>
    <div class="field"><label>Set Power (dBm):</label> <input id="sat-set-r0-power" type="number" min="-9" max="22" value="20" style="width:60px;"></div>
    <button onclick="applyLora('R0')">Apply R0</button>
</div>

<!-- Radio 1 -->
<div class="panel">
    <h2>Radio 1 — TC RX</h2>
    <div class="field"><label>Frequency:</label> <span id="sat-lora-r1-freq">-</span> Hz</div>
    <div class="field"><label>SF:</label> <span id="sat-lora-r1-sf">-</span></div>
    <div class="field"><label>BW:</label> <span id="sat-lora-r1-bw">-</span> kHz</div>
    <div class="field"><label>Power:</label> <span id="sat-lora-r1-power">-</span> dBm</div>
    <hr style="border-color:#333;">
    <div class="field"><label>Set Freq (Hz):</label> <input id="sat-set-r1-freq" type="number" value="916000000" style="width:130px;"></div>
    <div class="field"><label>Set SF:</label> <input id="sat-set-r1-sf" type="number" min="7" max="12" value="7" style="width:60px;"></div>
    <div class="field"><label>Set BW (kHz):</label> <select id="sat-set-r1-bw"><option>125</option><option>250</option><option>500</option></select></div>
    <div class="field"><label>Set Power (dBm):</label> <input id="sat-set-r1-power" type="number" min="-9" max="22" value="20" style="width:60px;"></div>
    <button onclick="applyLora('R1')">Apply R1</button>
</div>

<!-- Sensors -->
<div class="panel">
    <h2>Sensors</h2>
    <div class="field"><label>Temperature:</label> <span id="sens-temp">-</span> C</div>
    <div class="field"><label>Pressure:</label> <span id="sens-press">-</span> Pa</div>
    <div class="field"><label>Humidity:</label> <span id="sens-humid">-</span>%</div>
    <div class="field"><label>Accel X:</label> <span id="sens-ax">-</span> mg</div>
    <div class="field"><label>Accel Y:</label> <span id="sens-ay">-</span> mg</div>
    <div class="field"><label>Accel Z:</label> <span id="sens-az">-</span> mg</div>
</div>

<!-- Controls -->
<div class="panel">
    <h2>Controls</h2>
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
        <label style="color:#888;">Difficulty:</label>
        <select id="diff-select" onchange="setDifficulty(this.value)">
            <option value="0">0 — Training</option>
            <option value="1">1 — Normal</option>
            <option value="2">2 — Hardened</option>
            <option value="3">3 — Blue Team</option>
        </select>
    </div>
    <div style="margin-bottom:10px;">
        <label style="color:#888;">TinyGS:</label>
        <button id="btn-spoof" onclick="tinygsSpoof()">Spoof</button>
        <button id="btn-tinygs-stop" onclick="tinygsStop()">Stop</button>
    </div>
    <button onclick="resetDefaults()" style="background:#442; border-color:#664;">Reset Defaults</button>
</div>

</div><!-- grid -->
</div><!-- sat-mode -->

</div><!-- sat-content -->

<div id="toast" class="toast"></div>

<script>
let countdownEnabled = localStorage.getItem("countdownEnabled") === "true";
let lastNotifiedThreshold = 9999;
let hwConnected = false;
let currentMode = "raw";
let lastBeaconTime = null;

// --- Mode-aware element IDs ---
function loraId(radio, field) {
    const prefix = currentMode === "ground_station" ? "" : "sat-";
    return prefix + "lora-" + radio.toLowerCase() + "-" + field;
}
function loraSetId(radio, field) {
    const prefix = currentMode === "ground_station" ? "" : "sat-";
    return prefix + "set-" + radio.toLowerCase() + "-" + field;
}

// --- API helpers ---
async function api(path, method, body) {
    const opts = {method: method || "GET", headers: {}};
    if (body) {
        opts.headers["Content-Type"] = "application/json";
        opts.body = JSON.stringify(body);
    }
    try {
        const resp = await fetch("/api/satellite/" + path, opts);
        const data = await resp.json();
        if (!resp.ok) data.error = data.error || "request failed";
        return data;
    } catch (e) {
        return {error: e.message};
    }
}

function showToast(msg, duration) {
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.style.display = "block";
    setTimeout(() => t.style.display = "none", duration || 5000);
}

// --- Layout switching ---
function switchLayout(mode) {
    currentMode = mode;
    const isGS = mode === "ground_station";
    document.getElementById("page-title").textContent = isGS ? "Ground Station Control" : "Satellite Control";
    document.getElementById("gs-mode").style.display = isGS ? "block" : "none";
    document.getElementById("sat-mode").style.display = isGS ? "none" : "block";
}

// --- Polling ---
async function pollInfo() {
    const data = await api("info");
    if (data.error) {
        hwConnected = false;
        document.getElementById("no-hw").style.display = "block";
        document.getElementById("sat-content").style.display = "none";
        return;
    }
    hwConnected = true;
    document.getElementById("no-hw").style.display = "none";
    document.getElementById("sat-content").style.display = "block";

    switchLayout(data.mode);
    highlightBtn("mode-btns", data.mode);

    if (data.mode !== "ground_station") {
        // Satellite mode — show local data
        document.getElementById("fw-version").textContent = data.fw_version;
        document.getElementById("fw-git").textContent = data.git_sha + (data.git_dirty ? " (dirty)" : "");
        document.getElementById("fw-build").textContent = data.build_date;
        document.getElementById("sc-id").textContent = "0x" + (data.sc_id || 0).toString(16).padStart(2, "0");
        document.getElementById("cur-mode").textContent = data.mode;
        document.getElementById("cur-flight").textContent = data.flight;
        document.getElementById("cur-diff").textContent = data.difficulty;
        document.getElementById("diff-select").value = data.difficulty;
        highlightBtn("flight-btns", data.flight.toLowerCase());
        updateBattery("batt-mv", "batt-fill", data.battery_mv, data.flight);
    } else {
        // Ground Station mode — show local firmware info
        document.getElementById("gs-fw-version").textContent = data.fw_version;
        document.getElementById("gs-fw-git").textContent = data.git_sha + (data.git_dirty ? " (dirty)" : "");
        document.getElementById("gs-fw-build").textContent = data.build_date;
    }
}

async function pollRemote() {
    if (currentMode !== "ground_station") return;
    const data = await api("remote");
    if (!data.available) {
        document.getElementById("beacon-age").textContent = "No beacon";
        document.getElementById("beacon-age").className = "beacon-age beacon-lost";
        return;
    }

    // Update beacon age
    lastBeaconTime = new Date(data.timestamp);
    updateBeaconAge();

    // Flight mode names
    const flightNames = {0: "SAFE", 1: "NOMINAL", 2: "DEBUG", 3: "IDLE"};
    const flightName = flightNames[data.flight_mode] || "MODE_" + data.flight_mode;
    const diffNames = {0: "Training", 1: "Normal", 2: "Hardened", 3: "Blue Team"};

    document.getElementById("remote-scid").textContent = "0x" + (data.sc_id || 0).toString(16).padStart(2, "0");
    document.getElementById("remote-flight").textContent = flightName;
    document.getElementById("remote-diff").textContent = data.difficulty + " (" + (diffNames[data.difficulty] || "?") + ")";

    // Uptime
    const mins = Math.floor(data.uptime / 60);
    const secs = data.uptime % 60;
    const hrs = Math.floor(mins / 60);
    document.getElementById("remote-uptime").textContent =
        String(hrs).padStart(2, "0") + ":" + String(mins % 60).padStart(2, "0") + ":" + String(secs).padStart(2, "0");

    document.getElementById("remote-tc").textContent = data.tc_count;
    document.getElementById("remote-err").textContent = data.error_count;
    document.getElementById("remote-rssi").textContent = data.rssi || "-";

    // Battery from remote satellite
    updateBattery("remote-batt", "remote-batt-fill", data.battery_mv, flightName);
}

function updateBeaconAge() {
    if (!lastBeaconTime) return;
    const ageSec = Math.floor((Date.now() - lastBeaconTime.getTime()) / 1000);
    const el = document.getElementById("beacon-age");
    el.textContent = ageSec + "s ago";
    if (ageSec < 15) {
        el.className = "beacon-age beacon-fresh";
    } else if (ageSec < 30) {
        el.className = "beacon-age beacon-stale";
    } else {
        el.className = "beacon-age beacon-lost";
    }
}

function highlightBtn(groupId, active) {
    const el = document.getElementById(groupId);
    if (!el) return;
    const btns = el.querySelectorAll("button");
    btns.forEach(b => {
        const btnKey = b.textContent.toLowerCase().replace(/\s+/g, "_");
        b.className = btnKey === active ? "btn-active" : "";
    });
}

function updateBattery(mvId, fillId, mv, flight) {
    const mvEl = document.getElementById(mvId);
    if (mvEl) mvEl.textContent = mv;
    const pct = Math.max(0, Math.min(100, ((mv - 3000) / 700) * 100));
    const fill = document.getElementById(fillId);
    if (fill) {
        fill.style.width = pct + "%";
        fill.className = "battery-fill " + (mv > 3500 ? "batt-green" : mv > 3200 ? "batt-yellow" : "batt-red");
    }

    if (countdownEnabled) {
        const drainRate = flight === "DEBUG" ? 0.3 : 0.1;
        const secsLeft = Math.max(0, (mv - 3000) / drainRate);
        const mins = Math.floor(secsLeft / 60);
        const secs = Math.floor(secsLeft % 60);
        const timerId = currentMode === "ground_station" ? "countdown-timer" : "sat-countdown-timer";
        const timer = document.getElementById(timerId);
        if (timer) {
            timer.textContent = String(mins).padStart(2, "0") + ":" + String(secs).padStart(2, "0");
            timer.className = "countdown" + (mv < 3200 ? " countdown-danger" : "");
        }

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
    const toggle = document.getElementById("countdown-toggle") || document.getElementById("sat-countdown-toggle");
    countdownEnabled = toggle ? toggle.checked : false;
    localStorage.setItem("countdownEnabled", countdownEnabled);
    const displays = ["countdown-display", "sat-countdown-display"];
    displays.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = countdownEnabled ? "block" : "none";
    });
    lastNotifiedThreshold = 9999;
}

async function pollSensors() {
    if (!hwConnected) return;
    const data = await api("sensors");
    if (data.error) return;
    if (currentMode === "ground_station") {
        document.getElementById("gs-sens-temp").textContent = data.temperature;
        document.getElementById("gs-sens-press").textContent = data.pressure;
        document.getElementById("gs-sens-humid").textContent = data.humidity;
        document.getElementById("gs-sens-ax").textContent = data.accel_x;
        document.getElementById("gs-sens-ay").textContent = data.accel_y;
        document.getElementById("gs-sens-az").textContent = data.accel_z;
    } else {
        document.getElementById("sens-temp").textContent = data.temperature;
        document.getElementById("sens-press").textContent = data.pressure;
        document.getElementById("sens-humid").textContent = data.humidity;
        document.getElementById("sens-ax").textContent = data.accel_x;
        document.getElementById("sens-ay").textContent = data.accel_y;
        document.getElementById("sens-az").textContent = data.accel_z;
    }
}

async function pollLora() {
    if (!hwConnected) return;
    for (const radio of ["R0", "R1"]) {
        const data = await api("lora_config?radio=" + radio);
        if (data.error) continue;
        const freqEl = document.getElementById(loraId(radio, "freq"));
        const sfEl = document.getElementById(loraId(radio, "sf"));
        const bwEl = document.getElementById(loraId(radio, "bw"));
        const powerEl = document.getElementById(loraId(radio, "power"));
        if (freqEl) freqEl.textContent = data.frequency;
        if (sfEl) sfEl.textContent = data.sf;
        if (bwEl) bwEl.textContent = data.bw;
        if (powerEl) powerEl.textContent = data.power;
    }
}

async function pollStatus() {
    if (!hwConnected) return;
    const data = await api("status");
    if (data.error) { hwConnected = false; return; }

    if (data.mode !== currentMode) {
        switchLayout(data.mode);
    }
    highlightBtn("mode-btns", data.mode);

    if (data.mode !== "ground_station") {
        document.getElementById("cur-mode").textContent = data.mode;
        document.getElementById("cur-flight").textContent = data.flight;
        highlightBtn("flight-btns", data.flight.toLowerCase());
        updateBattery("batt-mv", "batt-fill", data.battery_mv, data.flight);
        document.getElementById("btn-spoof").className = data.mode === "tinygs" ? "btn-active" : "";
    }
}

// --- Actions ---
async function setMode(m) {
    if (m === "ground_station") {
        await api("mode", "POST", {mode: "ground_station"});
    } else if (m === "tinygs") {
        const profile = document.getElementById("tinygs-profile").value;
        await api("tinygs", "POST", {action: "spoof", profile: profile});
    } else {
        await api("mode", "POST", {mode: m});
    }
    await pollInfo();
    await pollLora();
}

async function setFlight(f) { await api("flight", "POST", {flight: f}); await pollStatus(); }

async function setDifficulty(l) {
    const data = await api("difficulty", "POST", {level: parseInt(l)});
    if (data.error) { alert("Failed: " + data.error); return; }
    document.getElementById("cur-diff").textContent = l;
}

async function applyLora(radio) {
    const r = radio.toLowerCase();
    await api("lora_config", "POST", {
        radio: radio,
        frequency: parseInt(document.getElementById(loraSetId(radio, "freq")).value),
        sf: parseInt(document.getElementById(loraSetId(radio, "sf")).value),
        bw: parseInt(document.getElementById(loraSetId(radio, "bw")).value),
        power: parseInt(document.getElementById(loraSetId(radio, "power")).value),
    });
    await pollLora();
    showToast(radio + " LoRa config applied", 3000);
}

async function tinygsSpoof() {
    await api("tinygs", "POST", {action: "spoof", profile: document.getElementById("tinygs-profile").value});
    await pollStatus();
}

async function tinygsStop() {
    await api("tinygs", "POST", {action: "stop"});
    await pollStatus();
}

async function resetDefaults() {
    if (!confirm("Reset RF config and mode to factory defaults?")) return;
    await api("reset", "POST");
    await pollInfo();
    await pollLora();
    showToast("Defaults restored", 3000);
}

// --- Sequential poll loop ---
let pollCycle = 0;

async function pollLoop() {
    if (!hwConnected) {
        await pollInfo();
    } else {
        await pollStatus();
        if (currentMode === "ground_station") {
            await pollRemote();
            updateBeaconAge();
        }
        if (pollCycle % 3 === 0) {
            await pollLora();
        }
        if (pollCycle % 2 === 0) {
            await pollSensors();
        }
        pollCycle++;
    }
    setTimeout(pollLoop, 3000);
}

// Update beacon age every second
setInterval(updateBeaconAge, 1000);

// --- Init ---
// Restore countdown state
async function init() {
    await pollInfo();
    if (hwConnected) {
        // Restore countdown checkbox
        const toggle = currentMode === "ground_station"
            ? document.getElementById("countdown-toggle")
            : document.getElementById("sat-countdown-toggle");
        if (toggle) toggle.checked = countdownEnabled;
        const display = currentMode === "ground_station" ? "countdown-display" : "sat-countdown-display";
        const el = document.getElementById(display);
        if (el) el.style.display = countdownEnabled ? "block" : "none";

        await pollLora();
        await pollSensors();
        if (currentMode === "ground_station") {
            await pollRemote();
        }
    }
    setTimeout(pollLoop, 3000);
}
init();
</script>
{% endblock %}
```

- [ ] **Step 2: Run all tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add webapp/templates/satellite.html
git commit -m "feat(webapp): adaptive satellite page — Ground Station vs Satellite layout"
```

---

## Summary

| Task | Component | Files |
|------|-----------|-------|
| 1 | Store heartbeat + API endpoint | webapp/app.py, tests/test_satellite_api.py |
| 2 | Adaptive satellite.html | webapp/templates/satellite.html |
