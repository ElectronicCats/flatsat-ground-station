# Dashboard DB Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Maximize DB usage — telemetry history on dashboard load, commands panel in dashboard, full SN display, radio_config sync with hardware.

**Architecture:** Extend existing SQLite schema (add rssi/snr), load history from `/api/telemetry` on page init, merge commands.html into dashboard as collapsible panel, sync radio_config on connect/config change.

**Tech Stack:** Flask, SQLite3, Socket.IO, vanilla JS

---

### Task 1: Add RSSI/SNR columns to telemetry schema and INSERT

**Files:**
- Modify: `webapp/db.py:15-27` — add columns to CREATE TABLE
- Modify: `webapp/app.py:817-834` — add rssi/snr to INSERT

- [ ] **Step 1: Update telemetry schema in db.py**

In `webapp/db.py`, change the telemetry table definition:

```python
CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    apid INTEGER NOT NULL,
    spacecraft_id INTEGER NOT NULL DEFAULT 2,
    temperature REAL,
    pressure REAL,
    humidity REAL,
    accel_x REAL,
    accel_y REAL,
    accel_z REAL,
    raw_hex TEXT NOT NULL,
    rssi INTEGER,
    snr INTEGER
);
```

- [ ] **Step 2: Update telemetry INSERT in app.py**

In `webapp/app.py`, find the INSERT INTO telemetry block (~line 818) and change to:

```python
db.execute(
    "INSERT INTO telemetry "
    "(timestamp, apid, spacecraft_id, temperature, "
    "pressure, humidity, accel_x, accel_y, accel_z, "
    "raw_hex, rssi, snr) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    (
        datetime.now().isoformat(),
        pkt.apid,
        2,
        decoded.get("temperature"),
        decoded.get("pressure"),
        decoded.get("humidity"),
        decoded.get("accel_x"),
        decoded.get("accel_y"),
        decoded.get("accel_z"),
        parsed["data"],
        parsed.get("rssi"),
        parsed.get("snr"),
    ),
)
```

- [ ] **Step 3: Delete existing DB so schema recreates**

Run: `rm -f db/ground_station.db`

The DB will be recreated with the new schema on next app start via `init_db()`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/ --tb=short -q`
Expected: all pass (tests use in-memory DB that gets fresh schema)

- [ ] **Step 5: Commit**

```bash
git add webapp/db.py webapp/app.py
git commit -m "feat: add rssi/snr columns to telemetry table and INSERT"
```

---

### Task 2: Load telemetry history from DB on dashboard init

**Files:**
- Modify: `webapp/static/js/telemetry.js` — add loadHistory() on init
- Modify: `webapp/templates/dashboard.html` — add Clear button

- [ ] **Step 1: Add loadHistory function to telemetry.js**

At the end of `telemetry.js`, before the Socket.IO connect block, add:

```javascript
async function loadHistory() {
    try {
        const resp = await fetch("/api/telemetry?limit=200");
        if (!resp.ok) return;
        const rows = await resp.json();
        if (!Array.isArray(rows)) return;
        // Rows come oldest-first from DB; render in order so newest is at top
        rows.reverse().forEach(row => {
            const data = {
                apid: row.apid,
                seq_count: null,
                raw_hex: row.raw_hex,
                timestamp: null,
                rssi: row.rssi,
                snr: row.snr,
                decoded: {
                    temperature: row.temperature,
                    pressure: row.pressure,
                    humidity: row.humidity,
                    accel_x: row.accel_x,
                    accel_y: row.accel_y,
                    accel_z: row.accel_z,
                    sc_id: row.spacecraft_id,
                },
                _recv_time: row.timestamp,
            };
            addTelemetryRow(data);
        });
    } catch (e) {
        console.error("[TM] Failed to load history:", e);
    }
}
```

- [ ] **Step 2: Update addTelemetryRow to accept optional recv_time override**

In the `addTelemetryRow` function, change the line that sets `recv_time`:

```javascript
const now = data._recv_time || new Date().toLocaleTimeString();
```

This allows history rows to show their original timestamp instead of "now".

- [ ] **Step 3: Call loadHistory before WebSocket connect**

In the Socket.IO init block at the bottom of `telemetry.js`, add `loadHistory()` before connecting:

```javascript
loadHistory();
const socket = io();
// ... existing socket.on handlers
```

- [ ] **Step 4: Add Clear button to dashboard.html**

In `dashboard.html`, after the `<h2>Live Telemetry</h2>` line, add:

```html
<button id="tm-clear" onclick="clearTelemetry()">Clear</button>
```

And add the handler in the existing `<script>` block:

```javascript
function clearTelemetry() {
    document.getElementById("telemetry-body").innerHTML = "";
    pktCount = 0;
    document.getElementById("pkt-counter").textContent = "";
    document.getElementById("last-seen").textContent = "";
}
```

- [ ] **Step 5: Test manually**

Start server, open dashboard. Should see historical rows from DB.
New WebSocket rows should prepend on top. Clear button should empty table.

- [ ] **Step 6: Run tests**

Run: `pytest tests/ --tb=short -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add webapp/static/js/telemetry.js webapp/templates/dashboard.html
git commit -m "feat(webapp): load telemetry history from DB and add Clear button"
```

---

### Task 3: Commands panel in dashboard

**Files:**
- Modify: `webapp/templates/dashboard.html` — add collapsible commands panel
- Delete: `webapp/templates/commands.html`
- Modify: `webapp/app.py:284-287` — remove /commands route
- Modify: `webapp/templates/base.html:24` — remove Commands nav link
- Modify: `tests/test_vuln_auth_bypass.py:47-49` — remove commands page test

- [ ] **Step 1: Add commands panel HTML to dashboard.html**

In `dashboard.html`, after the hardware status `</div>` and before `<h2>Live Telemetry</h2>`, add:

```html
<details id="cmd-panel" style="margin-bottom:15px; border:1px solid #333; background:#111;">
    <summary style="padding:10px; cursor:pointer; color:#00ccff; font-weight:bold;">Telecommand Panel</summary>
    <div style="padding:10px;">
        <form id="tc-form" style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
            <label>Command:
                <select name="opcode" id="opcode">
                    <option value="10">PING (0x10)</option>
                    <option value="20">READ_SENSOR (0x20)</option>
                    <option value="01">SET_SAFE_MODE (0x01)</option>
                    <option value="02">SET_NOMINAL (0x02)</option>
                    <option value="42">READ_FLAG (0x42)</option>
                </select>
            </label>
            <label>Data (hex): <input name="data" id="tc-data" placeholder="optional" style="width:120px;"></label>
            <button type="submit">Send TC</button>
        </form>
        <pre id="tc-response" style="margin-top:8px; max-height:150px; overflow-y:auto; font-size:0.85em;"></pre>
    </div>
</details>
```

- [ ] **Step 2: Add TC form handler in dashboard script block**

In the existing `<script>` block in `dashboard.html`, add:

```javascript
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

- [ ] **Step 3: Remove /commands route from app.py**

Delete the route block at ~line 284-287:

```python
    @app.route("/commands")
    @login_required
    def commands_page():
        return render_template("commands.html")
```

- [ ] **Step 4: Remove Commands nav link from base.html**

In `webapp/templates/base.html`, remove the line:

```html
    <a href="/commands">Commands</a> |
```

- [ ] **Step 5: Delete commands.html**

Run: `rm webapp/templates/commands.html`

- [ ] **Step 6: Update test_vuln_auth_bypass.py**

Remove `test_commands_page` test (~line 47-49) since the route no longer exists.

- [ ] **Step 7: Run tests**

Run: `pytest tests/ --tb=short -q`
Expected: all pass (one less test)

- [ ] **Step 8: Commit**

```bash
git add webapp/app.py webapp/templates/dashboard.html webapp/templates/base.html tests/test_vuln_auth_bypass.py
git rm webapp/templates/commands.html
git commit -m "feat(webapp): move commands panel into dashboard, remove /commands route"
```

---

### Task 4: Full serial number display

**Files:**
- Modify: `webapp/templates/dashboard.html` — full SN in hardware bar and scan dropdown
- Modify: `webapp/templates/satellite.html` — full SN in info panel

- [ ] **Step 1: Update dashboard.html hardware bar SN**

Find the line in `hwStatus()` that shows truncated SN:

```javascript
serial.textContent = " | SN: ..." + (data.serial_number || "").slice(-4);
```

Change to:

```javascript
serial.textContent = " | SN: " + (data.serial_number || "");
```

- [ ] **Step 2: Update dashboard.html scan dropdown**

Find in `hwScan()` the line:

```javascript
opt.textContent = "..." + d.serial_number.slice(-4) + " (" + d.health + ")";
```

Change to:

```javascript
opt.textContent = d.serial_number + " (" + d.health + ")";
```

- [ ] **Step 3: Update satellite.html SN display**

In the `pollInfo()` function in `satellite.html`, find the SC ID line and add SN display. Find the field that shows `sc-id`:

```javascript
document.getElementById("sc-id").textContent = "0x" + (data.sc_id || 0).toString(16).padStart(2, "0");
```

This already exists. Add a new field for SN. In the Satellite Info panel HTML, after the Spacecraft ID field add:

```html
<div class="field"><label>Serial Number:</label> <span id="hw-sn">-</span></div>
```

And in `pollInfo()`, after setting sc-id:

```javascript
// Show hardware SN
fetch("/api/hardware/status").then(r => r.json()).then(d => {
    document.getElementById("hw-sn").textContent = d.serial_number || "-";
});
```

- [ ] **Step 4: Test manually**

Verify full SN shows in dashboard hardware bar, scan dropdown, and satellite info panel.

- [ ] **Step 5: Commit**

```bash
git add webapp/templates/dashboard.html webapp/templates/satellite.html
git commit -m "feat(webapp): show full serial number in dashboard and satellite page"
```

---

### Task 5: Sync radio_config with hardware

**Files:**
- Modify: `webapp/app.py` — sync on connect and lora_config POST

- [ ] **Step 1: Add radio_config sync helper in app.py**

Inside `create_app()`, add a helper function (near the `_require_hardware` helper):

```python
def _sync_radio_config_to_db(dev):
    """Read LoRa config from hardware and upsert into radio_config for current user."""
    try:
        from webapp.db import get_db

        db = get_db()
        for radio, radio_label in [("R0", "Radio 0"), ("R1", "Radio 1")]:
            raw = dev.send_shell_command_full(f"lora_config {radio}")
            cfg = parse_lora_config(raw)
            if cfg["frequency"] == 0:
                continue
            existing = db.execute(
                "SELECT id FROM radio_config WHERE owner = ? AND description = ?",
                (g.username, radio_label),
            ).fetchone()
            if existing:
                db.execute(
                    "UPDATE radio_config SET frequency=?, spreading_factor=?, bandwidth=?, tx_power=? WHERE id=?",
                    (cfg["frequency"], cfg["sf"], cfg["bw"] * 1000, cfg["power"], existing["id"]),
                )
            else:
                db.execute(
                    "INSERT INTO radio_config (owner, frequency, spreading_factor, bandwidth, tx_power, description) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (g.username, cfg["frequency"], cfg["sf"], cfg["bw"] * 1000, cfg["power"], radio_label),
                )
        db.commit()
    except Exception:
        pass
```

- [ ] **Step 2: Call sync on hardware connect**

In the `/api/hardware/connect` route, after the bootstrap commands and before the return, add:

```python
_sync_radio_config_to_db(device)
```

Note: this runs inside a request context so `g.username` is available.

- [ ] **Step 3: Call sync after lora_config POST**

In the `/api/satellite/lora_config` POST handler, after `lora_apply` and before the return, add:

```python
_sync_radio_config_to_db(dev)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/ --tb=short -q`
Expected: all pass

- [ ] **Step 5: Test manually**

Connect to hardware, then check `/config` — should show real LoRa params.
Change config from satellite page, check `/config` again — should update.

- [ ] **Step 6: Commit**

```bash
git add webapp/app.py
git commit -m "feat(webapp): sync radio_config DB with real hardware LoRa state"
```
