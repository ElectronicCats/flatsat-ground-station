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
