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
        // Keep connect enabled if we have scanned devices
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

function showDashboardStatus(msg) {
    const el = document.getElementById("telemetry-status");
    if (el) el.textContent = msg;
}

// --- Status (polls every 5s when hardware) ---
async function hwStatus() {
    try {
        const resp = await fetch("/api/hardware/status");
        if (!resp.ok) { showDashboardStatus("Status check failed"); return; }
        const data = await resp.json();
        const el = document.getElementById("hw-mode");
        const serial = document.getElementById("hw-serial");

        // Clear all active states first
        document.getElementById("btn-simulate").className = "";
        document.getElementById("btn-connect").className = "";

        if (data.mode === "hardware") {
            el.textContent = "HARDWARE";
            el.style.color = "#00ff41";
            const ports = data.ports || {};
            const portInfo = ports.radio0 || ports.shell || "";
            serial.textContent = " | SN: " + (data.serial_number || "") + (portInfo ? " | Port: " + portInfo : "");
            setButtons("hardware");
            setIndicator("hardware");
            document.getElementById("btn-connect").className = "btn-active";
            
            document.getElementById("hw-active-radio-container").style.display = "inline";
            if (data.active_radio !== undefined) {
                document.getElementById("hw-active-radio").value = data.active_radio;
            }
        } else if (data.mode === "simulated") {
            el.textContent = "SIMULATED";
            el.style.color = "#ffaa00";
            serial.textContent = "";
            document.getElementById("hw-rssi").textContent = "";
            setButtons("simulated");
            setIndicator("simulated");
            document.getElementById("btn-simulate").className = "btn-active";
            document.getElementById("hw-active-radio-container").style.display = "none";
        } else {
            el.textContent = "IDLE";
            el.style.color = "#888";
            serial.textContent = "";
            document.getElementById("hw-rssi").textContent = "";
            setButtons("idle");
            setIndicator("idle");
            document.getElementById("hw-active-radio-container").style.display = "none";
        }
    } catch (e) {
        console.error("[GS] Status error:", e);
    }
}

async function switchActiveRadio(radioIdx) {
    try {
        const resp = await fetch("/api/hardware/active_radio", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({active_radio: parseInt(radioIdx)})
        });
        if (!resp.ok) { alert("Switch active radio failed"); return; }
        const data = await resp.json();
        console.log("[GS] Active radio switched:", data);
        hwStatus();
    } catch (e) {
        alert("Switch active radio error: " + e.message);
    }
}

// Poll status every 5s to detect disconnects
setInterval(hwStatus, 5000);

// --- Actions ---
async function hwSimulate() {
    try {
        const resp = await fetch("/api/hardware/simulate", {method: "POST"});
        if (!resp.ok) { alert("Simulate failed"); return; }
        pktCount = 0;
        hwStatus();
    } catch (e) {
        alert("Simulate error: " + e.message);
    }
}

async function hwStop() {
    try {
        const resp = await fetch("/api/hardware/stop", {method: "POST"});
        if (!resp.ok) { alert("Stop failed"); return; }
        document.getElementById("telemetry-body").innerHTML = "";
        pktCount = 0;
        document.getElementById("pkt-counter").textContent = "";
        document.getElementById("last-seen").textContent = "";
        hwStatus();
    } catch (e) {
        alert("Stop error: " + e.message);
    }
}

async function hwScan() {
    console.log("[GS] Scanning for devices...");
    try {
        const resp = await fetch("/api/hardware/scan", {method: "POST"});
        if (!resp.ok) { alert("Scan failed"); return; }
        const data = await resp.json();
        console.log("[GS] Scan result:", data);
        const sel = document.getElementById("hw-devices");
        sel.innerHTML = "";

        if (data.devices && data.devices.length > 0) {
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
    } catch (e) {
        console.error("[GS] Scan error:", e);
        alert("Scan error: " + e.message);
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
    try {
        const resp = await fetch("/api/hardware/disconnect", {method: "POST"});
        if (!resp.ok) { alert("Disconnect failed"); return; }
        const data = await resp.json();
        console.log("[GS] Disconnect result:", data);
        document.getElementById("hw-devices").style.display = "none";
        hasScannedDevices = false;
        document.getElementById("telemetry-body").innerHTML = "";
        pktCount = 0;
        document.getElementById("pkt-counter").textContent = "";
        document.getElementById("last-seen").textContent = "";
        hwStatus();
    } catch (e) {
        console.error("[GS] Disconnect error:", e);
        alert("Disconnect error: " + e.message);
    }
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
    const ts = new Date().toLocaleTimeString();
    const pre = document.getElementById("tc-response");
    try {
        const resp = await fetch("/api/radio/send_tc", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({opcode: opcode, data: data})
        });
        const result = await resp.json();
        const status = resp.ok ? (result.status || "ok") : "HTTP " + resp.status;
        const entry = "[" + ts + "] " + cmdName + " → " + status
            + (result.frame_size ? " (" + result.frame_size + " bytes)" : "")
            + (result.frame_hex ? " [" + result.frame_hex + "]" : "")
            + (result.error ? " — " + result.error : "")
            + "\n";
        pre.textContent = entry + pre.textContent;
    } catch (e) {
        pre.textContent = "[" + ts + "] " + cmdName + " → NETWORK ERROR — " + e.message + "\n" + pre.textContent;
    }
});
