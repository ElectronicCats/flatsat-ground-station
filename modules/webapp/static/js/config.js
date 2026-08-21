function loadRadioConfig() {
    const radio = document.getElementById("radio").value;
    const cfg = configs[radio];
    if (cfg) {
        document.getElementById("frequency").value = cfg.frequency;
        document.getElementById("spreading_factor").value = cfg.spreading_factor;
        document.getElementById("bandwidth").value = cfg.bandwidth;
        document.getElementById("tx_power").value = cfg.tx_power;
    } else {
        document.getElementById("frequency").value = 915000000;
        document.getElementById("spreading_factor").value = 7;
        document.getElementById("bandwidth").value = 125000;
        document.getElementById("tx_power").value = 14;
    }
}

document.getElementById("config-form").addEventListener("submit", async function(e) {
    e.preventDefault();
    const pre = document.getElementById("config-response");
    try {
        const resp = await fetch("/api/config/radio", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                radio: document.getElementById("radio").value,
                frequency: document.getElementById("frequency").value,
                spreading_factor: document.getElementById("spreading_factor").value,
                bandwidth: document.getElementById("bandwidth").value,
                tx_power: document.getElementById("tx_power").value,
            }),
        });
        const result = await resp.json();
        if (!resp.ok || result.error) {
            pre.style.color = "#ff4444";
            pre.textContent = "Error: " + (result.error || "HTTP " + resp.status);
            return;
        }
        pre.style.color = "#00ff41";
        if (result.config) {
            configs[document.getElementById("radio").value] = result.config;
        }
        pre.textContent = JSON.stringify(result, null, 2);
    } catch (err) {
        pre.style.color = "#ff4444";
        pre.textContent = "Network error: " + err.message;
    }
});

// Load initial values for Radio 0
loadRadioConfig();
