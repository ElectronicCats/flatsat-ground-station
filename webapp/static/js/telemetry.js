const socket = io();
const MAX_ROWS = 50;

socket.on("connect", function() {
    document.getElementById("telemetry-status").textContent = "Connected";
});

socket.on("disconnect", function() {
    document.getElementById("telemetry-status").textContent = "Disconnected";
});

socket.on("telemetry_update", function(data) {
    const tbody = document.getElementById("telemetry-body");
    const row = document.createElement("tr");
    const d = data.decoded || {};

    row.innerHTML = [
        new Date(data.timestamp * 1000).toISOString(),
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

    tbody.insertBefore(row, tbody.firstChild);

    // Update RSSI display in status bar
    if (data.rssi !== undefined) {
        const el = document.getElementById("hw-rssi");
        if (el) el.textContent = " | RSSI: " + data.rssi + " dBm | SNR: " + data.snr + " dB";
    }

    while (tbody.children.length > MAX_ROWS) {
        tbody.removeChild(tbody.lastChild);
    }
});
