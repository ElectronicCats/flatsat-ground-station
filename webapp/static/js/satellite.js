let countdownEnabled = localStorage.getItem("countdownEnabled") === "true";
let lastNotifiedThreshold = 9999;
let hwConnected = false;
let latestContext = null;

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

function setBanner(message, visible = true) {
    const banner = document.getElementById("sat-sync-banner");
    banner.textContent = message;
    banner.classList.toggle("hidden", !visible);
}

function setPanelState(name, state, message) {
    const panel = document.getElementById("panel-" + name);
    const status = document.getElementById("panel-" + name + "-status");
    if (!panel || !status) return;
    panel.classList.remove("panel-syncing", "panel-ready", "panel-error");
    if (state === "loading") panel.classList.add("panel-syncing");
    if (state === "ready") panel.classList.add("panel-ready");
    if (state === "error") panel.classList.add("panel-error");
    status.textContent = message;
}

function setControlsEnabled(enabled) {
    document.getElementById("panel-controls").classList.toggle("controls-disabled", !enabled);
}

function setText(id, value, fallback = "--") {
    const el = document.getElementById(id);
    el.textContent = value === null || value === undefined || value === "" ? fallback : value;
}

function formatHex(value) {
    if (value === null || value === undefined) return "--";
    return "0x" + Number(value).toString(16).padStart(2, "0");
}

function formatAge(ageSec, source) {
    if (source === "local" && (ageSec === null || ageSec === undefined)) return "Direct USB";
    if (ageSec === null || ageSec === undefined) return "Waiting for telemetry";
    const secs = Math.max(0, Math.round(ageSec));
    if (secs < 2) return "Just now";
    if (secs < 60) return secs + "s ago";
    const mins = Math.floor(secs / 60);
    const rem = secs % 60;
    return mins + "m " + String(rem).padStart(2, "0") + "s ago";
}

function formatUptime(seconds) {
    if (seconds === null || seconds === undefined) return "--";
    const total = Number(seconds);
    const days = Math.floor(total / 86400);
    const hours = Math.floor((total % 86400) / 3600);
    const mins = Math.floor((total % 3600) / 60);
    if (days > 0) return days + "d " + hours + "h";
    if (hours > 0) return hours + "h " + mins + "m";
    return mins + "m";
}

function applySatelliteSnapshot(satellite, role) {
    const sat = satellite || {};
    setText("sat-source", sat.source_label, role === "ground_station" ? "Waiting for telemetry" : "Direct USB");
    setText("sc-id", sat.sc_id !== null && sat.sc_id !== undefined ? formatHex(sat.sc_id) : null, role === "ground_station" ? "Waiting..." : "--");
    setText("cur-flight", sat.flight, role === "ground_station" ? "Waiting..." : "--");
    setText("cur-diff", sat.difficulty, role === "ground_station" ? "Waiting..." : "--");
    setText("sat-last-seen", formatAge(sat.age_sec, sat.source), role === "ground_station" ? "Waiting for telemetry" : "Direct USB");
    setText("sat-uptime", formatUptime(sat.uptime));
    setText("sat-tc-count", sat.tc_count, role === "ground_station" ? "Waiting..." : "--");
    setText("sat-error-count", sat.error_count, role === "ground_station" ? "Waiting..." : "--");
    setText("sat-rssi", sat.rssi !== null && sat.rssi !== undefined ? sat.rssi + " dBm" : null);
    setText("sat-snr", sat.snr !== null && sat.snr !== undefined ? sat.snr + " dB" : null);
    updateBattery(sat.battery_mv, sat.flight);

    const infoMessage = sat.available || role === "satellite" ? (sat.source_label || "Live") : "Waiting for Telemetry";
    const batteryMessage = sat.battery_mv !== null && sat.battery_mv !== undefined ? "Live" : "Waiting for Telemetry";
    setPanelState("info", "ready", infoMessage);
    setPanelState("battery", "ready", batteryMessage);
}

function applyLocalSnapshot(local) {
    const info = local || {};
    setText("local-role", info.role_label);
    setText("fw-version", info.fw_version);
    setText("fw-git", info.git_sha ? info.git_sha + (info.git_dirty ? " (dirty)" : "") : null);
    setText("fw-build", info.build_date);
    setText("local-mode", info.mode);
    setText("local-flight", info.flight);
    setText("local-diff", info.difficulty);
    setText("local-sc-id", info.sc_id !== null && info.sc_id !== undefined ? formatHex(info.sc_id) : null);

    if (info.difficulty !== null && info.difficulty !== undefined) {
        document.getElementById("diff-select").value = info.difficulty;
    }
    highlightBtn("mode-btns", info.mode || "");
    highlightBtn("flight-btns", info.flight ? info.flight.toLowerCase() : "");
    document.getElementById("btn-spoof").className = info.mode === "tinygs" ? "btn-active" : "";
    document.getElementById("controls-note").textContent = info.role === "ground_station"
        ? "Connected device is the ground station. Battery, counters, and sensors above come from relayed satellite telemetry."
        : "Connected device is the satellite. Controls below act directly on it.";

    setPanelState("local", "ready", info.role_label || "Live");
    setPanelState("controls", "ready", "Ready");
    setControlsEnabled(true);
}

function applyContext(data) {
    // Backend returns null for fields it didn't fetch (e.g. status skips fw_version).
    // Keep the previous value when the new one is null.
    const prev = (latestContext && latestContext.local) || {};
    const next = data.local || {};
    const merged = {};
    for (const key of new Set([...Object.keys(prev), ...Object.keys(next)])) {
        merged[key] = next[key] !== null && next[key] !== undefined ? next[key] : prev[key];
    }
    latestContext = {...data, local: merged};
    const role = latestContext.connection_role || "satellite";
    applySatelliteSnapshot(latestContext.satellite, role);
    applyLocalSnapshot(merged);
}

function applySensorSnapshot(data, role) {
    const source = (data && data.source) || (role === "ground_station" ? "remote" : "local");
    setText("sens-temp", data && data.temperature, role === "ground_station" ? "Waiting..." : "--");
    setText("sens-press", data && data.pressure, role === "ground_station" ? "Waiting..." : "--");
    setText("sens-humid", data && data.humidity, role === "ground_station" ? "Waiting..." : "--");
    setText("sens-ax", data && data.accel_x, role === "ground_station" ? "Waiting..." : "--");
    setText("sens-ay", data && data.accel_y, role === "ground_station" ? "Waiting..." : "--");
    setText("sens-az", data && data.accel_z, role === "ground_station" ? "Waiting..." : "--");
    const hasData = ["temperature", "pressure", "humidity", "accel_x", "accel_y", "accel_z"]
        .some((key) => data && data[key] !== null && data[key] !== undefined);
    const message = hasData ? (source === "remote" ? "Relayed Telemetry" : "Live") : "Waiting for Telemetry";
    setPanelState("sensors", "ready", message);
}

// --- Polling ---
async function pollInfo() {
    const data = await api("info");
    if (data.error) {
        hwConnected = false;
        document.getElementById("no-hw").style.display = "block";
        document.getElementById("sat-content").style.display = "none";
        setBanner("Satellite not connected.", false);
        setControlsEnabled(false);
        return;
    }
    hwConnected = true;
    document.getElementById("no-hw").style.display = "none";
    document.getElementById("sat-content").style.display = "block";
    applyContext(data);
    // Show hardware serial number
    fetch("/api/hardware/status").then(r => r.json()).then(d => {
        document.getElementById("hw-sn").textContent = d.serial_number || "-";
    }).catch(() => {});
}

function highlightBtn(groupId, active) {
    const btns = document.getElementById(groupId).querySelectorAll("button");
    btns.forEach(b => {
        // Normalize: "Ground Station" -> "ground_station" for comparison
        const btnKey = b.textContent.toLowerCase().replace(/\s+/g, "_");
        b.className = btnKey === active ? "btn-active" : "";
    });
}

function updateBattery(mv, flight) {
    if (mv === null || mv === undefined || mv === "") {
        document.getElementById("batt-mv").textContent = "Waiting...";
        document.getElementById("batt-fill").style.width = "0%";
        document.getElementById("batt-fill").className = "battery-fill batt-red";
        document.getElementById("countdown-timer").textContent = "--:--";
        return;
    }

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
    localStorage.setItem("countdownEnabled", countdownEnabled);
    document.getElementById("countdown-display").style.display = countdownEnabled ? "block" : "none";
    lastNotifiedThreshold = 9999;
}

async function pollSensors() {
    if (!hwConnected) return;
    if (latestContext && latestContext.connection_role === "ground_station") {
        applySensorSnapshot(latestContext.satellite, "ground_station");
        return;
    }
    const data = await api("sensors");
    if (data.error) {
        setPanelState("sensors", "error", "Unavailable");
        return;
    }
    applySensorSnapshot(data, "satellite");
}

async function pollLora() {
    if (!hwConnected) return;
    for (const radio of ["R0", "R1"]) {
        const data = await api("lora_config?radio=" + radio);
        if (data.error) {
            setPanelState(radio.toLowerCase(), "error", "Unavailable");
            continue;
        }
        const r = radio.toLowerCase();
        document.getElementById("lora-" + r + "-freq").textContent = data.frequency;
        document.getElementById("lora-" + r + "-sf").textContent = data.sf;
        document.getElementById("lora-" + r + "-bw").textContent = data.bw;
        document.getElementById("lora-" + r + "-power").textContent = data.power;
        setPanelState(r, "ready", "Live");
    }
}

// --- Lightweight polling (only flight/battery/mode) ---
async function pollStatus() {
    if (!hwConnected) return;
    const data = await api("status");
    if (data.error) {
        hwConnected = false;
        document.getElementById("no-hw").style.display = "block";
        document.getElementById("sat-content").style.display = "none";
        setPanelState("controls", "error", "Unavailable");
        setPanelState("battery", "error", "Unavailable");
        setPanelState("local", "error", "Unavailable");
        setControlsEnabled(false);
        return;
    }
    applyContext(data);
}

// --- Actions ---
async function setMode(m) {
    if (m === "ground_station") {
        await api("mode", "POST", {mode: "ground_station"});
    } else if (m === "tinygs") {
        // TinyGS immediately starts spoofing with selected profile
        const profile = document.getElementById("tinygs-profile").value;
        await api("tinygs", "POST", {action: "spoof", profile: profile});
    } else {
        await api("mode", "POST", {mode: m});
    }
    await pollStatus();
}
async function setFlight(f) { await api("flight", "POST", {flight: f}); await pollStatus(); }
async function setDifficulty(l) {
    const data = await api("difficulty", "POST", {level: parseInt(l)});
    if (data.error) { alert("Failed: " + data.error); return; }
    await pollStatus();
}
async function applyLora(radio) {
    const r = radio.toLowerCase();
    await api("lora_config", "POST", {
        radio: radio,
        frequency: parseInt(document.getElementById("set-" + r + "-freq").value),
        sf: parseInt(document.getElementById("set-" + r + "-sf").value),
        bw: parseInt(document.getElementById("set-" + r + "-bw").value),
        power: parseInt(document.getElementById("set-" + r + "-power").value),
    });
    await pollLora();
    showToast(radio + " LoRa config applied", 3000);
}
async function tinygsSpoof() {
    await api("tinygs", "POST", {action: "spoof", profile: document.getElementById("tinygs-profile").value});
    document.getElementById("btn-spoof").className = "btn-active";
    document.getElementById("btn-tinygs-stop").className = "";
    await pollStatus();
}
async function tinygsStop() {
    await api("tinygs", "POST", {action: "stop"});
    document.getElementById("btn-spoof").className = "";
    document.getElementById("btn-tinygs-stop").className = "";
    await pollStatus();
}
async function resetDefaults() {
    if (!confirm("Reset RF config and mode to factory defaults?")) return;
    await api("reset", "POST");
    await pollStatus();
    await pollLora();
    showToast("Defaults restored", 3000);
}

// --- Single sequential poll loop (avoids shell contention) ---
let pollCycle = 0;

async function pollLoop() {
    if (!hwConnected) {
        await pollInfo();  // try to connect
    } else {
        await pollStatus();            // every cycle: flight + battery
        if (pollCycle % 3 === 0) {
            await pollLora();          // every 3rd cycle: lora config
        }
        if (pollCycle % 2 === 0) {
            await pollSensors();       // every 2nd cycle: sensors
        }
        pollCycle++;
    }
    setTimeout(pollLoop, 3000);
}

// --- Init ---
// Restore countdown state
document.getElementById("countdown-toggle").checked = countdownEnabled;
document.getElementById("countdown-display").style.display = countdownEnabled ? "block" : "none";
setControlsEnabled(false);

async function init() {
    document.getElementById("sat-content").style.display = "block";
    document.getElementById("no-hw").style.display = "none";
    setBanner("Synchronizing with satellite...");
    await pollInfo();
    if (hwConnected) {
        setBanner("Refreshing live status...");
        await pollStatus();
        setBanner("Loading radio configuration and sensors...");
        Promise.allSettled([pollLora(), pollSensors()]).finally(() => {
            if (hwConnected) {
                setBanner("Satellite synchronized.", false);
            }
        });
    }
    setTimeout(pollLoop, 3000);
}
init();
