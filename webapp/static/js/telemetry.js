const socket = io();
const MAX_ROWS = 200;

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
        row.innerHTML = [
            now,
            "0x" + data.apid.toString(16).padStart(3, "0"),
            d.temperature !== undefined ? d.temperature.toFixed(2) + " C" : "-",
            d.pressure !== undefined ? d.pressure.toFixed(1) + " hPa" : "-",
            d.humidity !== undefined ? d.humidity + "%" : "-",
            d.accel_x !== undefined ? d.accel_x : "-",
            d.accel_y !== undefined ? d.accel_y : "-",
            d.accel_z !== undefined ? d.accel_z : "-",
            data.rssi !== undefined ? data.rssi + " dBm" : "-",
            data.snr !== undefined ? data.snr + " dB" : "-",
        ].map(v => "<td>" + v + "</td>").join("");
    } else {
        // Raw frame (TinyGS beacons, unknown APIDs)
        const hex = data.raw_hex || "?";
        const shortHex = hex.length > 40 ? hex.substring(0, 40) + "..." : hex;
        row.innerHTML = [
            now,
            data.apid !== undefined ? "0x" + data.apid.toString(16).padStart(3, "0") : "RAW",
            '<span style="color:#888;font-size:0.85em;">' + shortHex + '</span>',
            "", "", "", "", "",
            data.rssi !== undefined ? data.rssi + " dBm" : "-",
            data.snr !== undefined ? data.snr + " dB" : "-",
        ].map(v => "<td>" + v + "</td>").join("");
        row.style.color = "#888";
    }

    tbody.insertBefore(row, tbody.firstChild);

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
