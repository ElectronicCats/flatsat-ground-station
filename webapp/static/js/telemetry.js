const socket = io();
const MAX_ROWS = 200;
const COLUMN_PREFS_KEY = "dashboardTelemetryColumnsV1";
const DEFAULT_HIDDEN_COLUMNS = new Set(["difficulty", "frame_ts", "uptime", "tc_count", "error_count", "raw"]);
const FLIGHT_MODE_LABELS = {
    0: "IDLE",
    1: "NOMINAL",
    2: "SAFE",
    3: "DEBUG",
};

function fmt(value, fallback = "-") {
    return value === undefined || value === null || value === "" ? fallback : value;
}

function fmtFrameTime(ts) {
    if (ts === undefined || ts === null) return "-";
    return new Date(ts * 1000).toLocaleTimeString();
}

function fmtHexApid(apid) {
    if (apid === undefined || apid === null) return "RAW";
    return "0x" + apid.toString(16).padStart(3, "0");
}

function fmtFlight(decoded) {
    if (decoded.flight !== undefined) return decoded.flight;
    if (decoded.flight_mode !== undefined) return FLIGHT_MODE_LABELS[decoded.flight_mode] || decoded.flight_mode;
    return "-";
}

function fmtRaw(hex) {
    if (!hex) return "-";
    return '<span style="color:#888;font-size:0.85em;">' + hex + "</span>";
}

function buildCell(col, value, asHtml = false) {
    const td = document.createElement("td");
    td.dataset.col = col;
    if (asHtml) {
        td.innerHTML = value;
    } else {
        td.textContent = value;
    }
    return td;
}

function defaultColumnPrefs() {
    const prefs = {};
    document.querySelectorAll("#tm-column-controls input[data-col-toggle]").forEach((input) => {
        prefs[input.dataset.colToggle] = !DEFAULT_HIDDEN_COLUMNS.has(input.dataset.colToggle);
    });
    return prefs;
}

function loadColumnPrefs() {
    const defaults = defaultColumnPrefs();
    try {
        const raw = localStorage.getItem(COLUMN_PREFS_KEY);
        if (!raw) return defaults;
        return {...defaults, ...JSON.parse(raw)};
    } catch (_err) {
        return defaults;
    }
}

function saveColumnPrefs(prefs) {
    localStorage.setItem(COLUMN_PREFS_KEY, JSON.stringify(prefs));
}

function applyColumnVisibility() {
    const prefs = loadColumnPrefs();
    document.querySelectorAll("[data-col]").forEach((cell) => {
        const col = cell.dataset.col;
        cell.style.display = prefs[col] === false ? "none" : "";
    });
    document.querySelectorAll("#tm-column-controls input[data-col-toggle]").forEach((input) => {
        input.checked = prefs[input.dataset.colToggle] !== false;
    });
}

function initializeColumnControls() {
    const controls = document.getElementById("tm-column-controls");
    if (!controls) return;

    controls.querySelectorAll("input[data-col-toggle]").forEach((input) => {
        input.addEventListener("change", () => {
            const prefs = loadColumnPrefs();
            prefs[input.dataset.colToggle] = input.checked;
            saveColumnPrefs(prefs);
            applyColumnVisibility();
        });
    });

    const resetBtn = document.getElementById("tm-columns-reset");
    if (resetBtn) {
        resetBtn.addEventListener("click", () => {
            saveColumnPrefs(defaultColumnPrefs());
            applyColumnVisibility();
        });
    }

    applyColumnVisibility();
}

socket.on("connect", function() {
    document.getElementById("telemetry-status").textContent = "WebSocket connected";
});

socket.on("disconnect", function() {
    document.getElementById("telemetry-status").textContent = "WebSocket disconnected";
});

socket.on("telemetry_update", function(data) {
    const d = data.decoded || {};

    const hasDecodedData = d.temperature !== undefined
        || d.pressure !== undefined
        || d.humidity !== undefined
        || d.accel_x !== undefined
        || d.sc_id !== undefined;

    const tbody = document.getElementById("telemetry-body");
    const row = document.createElement("tr");
    const now = new Date().toLocaleTimeString();

    if (hasDecodedData) {
        [
            ["recv_time", now],
            ["frame_ts", fmtFrameTime(data.timestamp)],
            ["apid", fmtHexApid(data.apid)],
            ["seq", fmt(data.seq_count)],
            ["sc_id", d.sc_id !== undefined ? "0x" + Number(d.sc_id).toString(16).padStart(2, "0") : "-"],
            ["flight", fmtFlight(d)],
            ["difficulty", fmt(d.difficulty)],
            ["battery", d.battery_mv !== undefined ? d.battery_mv + " mV" : "-"],
            ["uptime", d.uptime !== undefined ? d.uptime + " s" : "-"],
            ["tc_count", fmt(d.tc_count)],
            ["error_count", fmt(d.error_count)],
            ["temp", d.temperature !== undefined ? d.temperature.toFixed(2) + " C" : "-"],
            ["pressure", d.pressure !== undefined ? d.pressure.toFixed(1) + " hPa" : "-"],
            ["humidity", d.humidity !== undefined ? d.humidity + "%" : "-"],
            ["accel_x", fmt(d.accel_x)],
            ["accel_y", fmt(d.accel_y)],
            ["accel_z", fmt(d.accel_z)],
            ["rssi", data.rssi !== undefined ? data.rssi + " dBm" : "-"],
            ["snr", data.snr !== undefined ? data.snr + " dB" : "-"],
            ["raw", fmtRaw(data.raw_hex), true],
        ].forEach(([col, value, asHtml]) => row.appendChild(buildCell(col, value, asHtml)));
    } else {
        // Raw frame (TinyGS beacons, unknown APIDs)
        [
            ["recv_time", now],
            ["frame_ts", fmtFrameTime(data.timestamp)],
            ["apid", fmtHexApid(data.apid)],
            ["seq", fmt(data.seq_count)],
            ["sc_id", "-"],
            ["flight", "-"],
            ["difficulty", "-"],
            ["battery", "-"],
            ["uptime", "-"],
            ["tc_count", "-"],
            ["error_count", "-"],
            ["temp", "-"],
            ["pressure", "-"],
            ["humidity", "-"],
            ["accel_x", "-"],
            ["accel_y", "-"],
            ["accel_z", "-"],
            ["rssi", data.rssi !== undefined ? data.rssi + " dBm" : "-"],
            ["snr", data.snr !== undefined ? data.snr + " dB" : "-"],
            ["raw", fmtRaw(data.raw_hex), true],
        ].forEach(([col, value, asHtml]) => row.appendChild(buildCell(col, value, asHtml)));
        row.style.color = "#888";
    }

    tbody.insertBefore(row, tbody.firstChild);
    applyColumnVisibility();

    // Update packet counter
    if (typeof pktCount !== "undefined") {
        pktCount++;
        const counter = document.getElementById("pkt-counter");
        if (counter) counter.textContent = "| Packets: " + pktCount;
    }

    // Update last-seen time
    const lastSeen = document.getElementById("last-seen");
    if (lastSeen) lastSeen.textContent = "| Last: " + now;

    // Update RSSI in status bar
    if (data.rssi !== undefined) {
        const el = document.getElementById("hw-rssi");
        if (el) el.textContent = " | RSSI: " + data.rssi + " dBm | SNR: " + data.snr + " dB";
    }

    while (tbody.children.length > MAX_ROWS) {
        tbody.removeChild(tbody.lastChild);
    }
});

initializeColumnControls();
