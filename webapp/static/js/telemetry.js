const socket = io();
const MAX_ROWS = 500;
const ROWS_PER_PAGE = 50;
const COLUMN_PREFS_KEY = "dashboardTelemetryColumnsV1";
let currentPage = 1;
let filterText = "";
const DEFAULT_HIDDEN_COLUMNS = new Set(["seq", "sc_id", "flight", "difficulty", "frame_ts", "uptime", "tc_count", "error_count", "raw"]);
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

function addTelemetryRow(data, recvTimeOverride, skipPagination) {
    const d = data.decoded || {};

    const hasDecodedData = d.temperature != null
        || d.pressure != null
        || d.humidity != null
        || d.accel_x != null
        || d.sc_id != null;

    const tbody = document.getElementById("telemetry-body");
    const row = document.createElement("tr");
    const now = recvTimeOverride || new Date().toLocaleTimeString();

    if (hasDecodedData) {
        [
            ["recv_time", now],
            ["frame_ts", fmtFrameTime(data.timestamp)],
            ["apid", fmtHexApid(data.apid)],
            ["seq", fmt(data.seq_count)],
            ["sc_id", d.sc_id != null ? "0x" + Number(d.sc_id).toString(16).padStart(2, "0") : "-"],
            ["flight", fmtFlight(d)],
            ["difficulty", fmt(d.difficulty)],
            ["battery", d.battery_mv != null ? d.battery_mv + " mV" : "-"],
            ["uptime", d.uptime != null ? d.uptime + " s" : "-"],
            ["tc_count", fmt(d.tc_count)],
            ["error_count", fmt(d.error_count)],
            ["temp", d.temperature != null ? d.temperature.toFixed(2) + " C" : "-"],
            ["pressure", d.pressure != null ? d.pressure.toFixed(1) + " hPa" : "-"],
            ["humidity", d.humidity != null ? d.humidity + "%" : "-"],
            ["accel_x", fmt(d.accel_x)],
            ["accel_y", fmt(d.accel_y)],
            ["accel_z", fmt(d.accel_z)],
            ["rssi", data.rssi != null ? data.rssi + " dBm" : "-"],
            ["snr", data.snr != null ? data.snr + " dB" : "-"],
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
            ["rssi", data.rssi != null ? data.rssi + " dBm" : "-"],
            ["snr", data.snr != null ? data.snr + " dB" : "-"],
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

    if (!skipPagination) applyFilterAndPagination();
}

socket.on("telemetry_update", function(data) {
    addTelemetryRow(data);
});

async function loadHistory() {
    try {
        const resp = await fetch("/api/telemetry?limit=200");
        if (!resp.ok) return;
        const rows = await resp.json();
        if (!Array.isArray(rows)) return;
        rows.reverse().forEach(row => {
            addTelemetryRow({
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
            }, row.timestamp, true);
        });
        applyFilterAndPagination();
    } catch (e) {
        console.error("[TM] Failed to load history:", e);
    }
}

function clearTelemetry() {
    document.getElementById("telemetry-body").innerHTML = "";
    if (typeof pktCount !== "undefined") {
        pktCount = 0;
        const counter = document.getElementById("pkt-counter");
        if (counter) counter.textContent = "";
    }
    const lastSeen = document.getElementById("last-seen");
    if (lastSeen) lastSeen.textContent = "";
    currentPage = 1;
    updatePagination();
}

// --- Filter & Pagination ---

function getFilteredRows() {
    const tbody = document.getElementById("telemetry-body");
    const allRows = Array.from(tbody.children);
    if (!filterText) return allRows;
    const lower = filterText.toLowerCase();
    return allRows.filter(row => row.textContent.toLowerCase().includes(lower));
}

function applyFilterAndPagination() {
    const tbody = document.getElementById("telemetry-body");
    const allRows = Array.from(tbody.children);
    const lower = filterText.toLowerCase();

    // First pass: mark all rows hidden
    allRows.forEach(row => row.style.display = "none");

    // Get matching rows
    const matched = filterText
        ? allRows.filter(row => row.textContent.toLowerCase().includes(lower))
        : allRows;

    // Clamp page
    const totalPages = Math.max(1, Math.ceil(matched.length / ROWS_PER_PAGE));
    if (currentPage > totalPages) currentPage = totalPages;

    // Show only current page
    const start = (currentPage - 1) * ROWS_PER_PAGE;
    const end = start + ROWS_PER_PAGE;
    matched.slice(start, end).forEach(row => row.style.display = "");

    updatePagination(matched.length, totalPages);
}

function updatePagination(totalMatched, totalPages) {
    const info = document.getElementById("tm-page-info");
    const prevBtn = document.getElementById("tm-page-prev");
    const nextBtn = document.getElementById("tm-page-next");
    if (!info) return;

    const tbody = document.getElementById("telemetry-body");
    const totalRows = tbody.children.length;
    totalMatched = totalMatched !== undefined ? totalMatched : totalRows;
    totalPages = totalPages !== undefined ? totalPages : Math.max(1, Math.ceil(totalMatched / ROWS_PER_PAGE));

    const filterNote = filterText ? " (filtered from " + totalRows + ")" : "";
    info.textContent = "Page " + currentPage + "/" + totalPages + " | " + totalMatched + " rows" + filterNote;
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages;
}

function tmPagePrev() {
    if (currentPage > 1) {
        currentPage--;
        applyFilterAndPagination();
    }
}

function tmPageNext() {
    currentPage++;
    applyFilterAndPagination();
}

function tmFilter(value) {
    filterText = value;
    currentPage = 1;
    applyFilterAndPagination();
}

loadHistory();
initializeColumnControls();
applyFilterAndPagination();
