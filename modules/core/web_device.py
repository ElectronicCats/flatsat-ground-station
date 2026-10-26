"""Drive a running FlatSat Ground Station webapp through its REST API.

The webapp owns the serial ports.  While it is connected, the CLI cannot
open the same CDC-ACM devices: on Windows they are locked exclusively, and
on POSIX both processes would steal bytes from each other.

This adapter makes the CLI talk to the running webapp instead, so the two
tools can be used together:

    flatsat-web                 # webapp holds the hardware
    flatsat -w status           # CLI reads the state through the webapp
    flatsat -w sniff -n 10      # CLI shows the frames the webapp receives
    flatsat -w tc 0x20 --text PING

Only the standard library is used (urllib), so the CLI keeps working
without extra dependencies.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_URL = "http://127.0.0.1:5000"
DEFAULT_USER = os.environ.get("FLATSAT_USER", "admin")
DEFAULT_PASSWORD = os.environ.get("FLATSAT_PASS", "password")


class WebDeviceError(RuntimeError):
    """Raised when the webapp cannot be reached or refuses the request."""


class WebDevice:
    """A FlatSatDevice look-alike backed by the webapp's HTTP API."""

    def __init__(self, base_url: str = DEFAULT_URL, user: str = DEFAULT_USER, password: str = DEFAULT_PASSWORD):
        self.base_url = base_url.rstrip("/")
        self.user = user
        self.password = password
        self.has_radio1 = True
        self.active_radio = 0
        self._connected = False
        self._last_row_id = 0

        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))

    # ── HTTP plumbing ──────────────────────────────────────────────────────

    def _request(self, method: str, path: str, payload: dict | None = None, timeout: float = 10.0):
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self._opener.open(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code in (301, 302, 303, 307, 308):
                return None
            raise WebDeviceError(f"{method} {path} -> HTTP {exc.code}: {body[:200]}") from exc
        except urllib.error.URLError as exc:
            raise WebDeviceError(
                f"No se pudo contactar con la webapp en {self.base_url} ({exc.reason}). "
                "¿Está arrancada con 'flatsat-web'?"
            ) from exc

        if not body.strip():
            return None
        try:
            return json.loads(body)
        except ValueError:
            return body

    def _login(self) -> bool:
        """Authenticate so the protected endpoints can be used."""
        if not self._jar:
            pass
        payload = urllib.parse.urlencode({"username": self.user, "password": self.password}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/login",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with self._opener.open(req, timeout=10) as resp:
                resp.read()
                return True
        except urllib.error.HTTPError:
            return False
        except urllib.error.URLError:
            return False

    # ── FlatSatDevice-compatible surface ──────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self, forced_role=None) -> dict:
        """Check that the webapp is up and (optionally) log in."""
        status = self._request("GET", "/api/hardware/status")
        if status is None:
            raise WebDeviceError("La webapp no respondió en /api/hardware/status")

        if isinstance(status, dict) and status.get("mode") == "hardware":
            self._connected = True
            self.active_radio = status.get("active_radio", 0)
        else:
            self._connected = True  # the webapp is alive, even if idle

        # The protected endpoints need a session; the public ones do not.
        self._login()
        return {"shell": True, "web": self.base_url, "status": status}

    def disconnect(self) -> None:
        """Nothing to close: the webapp keeps the hardware."""
        self._connected = False

    def send_shell_command_full(self, cmd: str, timeout: float | None = None) -> str | None:
        """Map a shell command onto the webapp API.

        Only the commands the webapp exposes over HTTP are supported; the
        rest return None, exactly like a board that does not answer.
        """
        cmd = (cmd or "").strip()
        if not cmd:
            return None
        verb, _, rest = cmd.partition(" ")
        verb = verb.lower()
        rest = rest.strip()

        if verb in ("status", "fw_version", "mode", "flight", "difficulty", "sc_id"):
            return self._describe(verb, rest)
        if verb == "sensors":
            return self._sensors_text()
        if verb == "lora_config":
            return self._lora_config_text(rest or "R0")
        if verb == "lora_freq":
            return self._lora_update(rest, "frequency")
        if verb == "lora_sf":
            return self._lora_update(rest, "sf")
        if verb == "lora_bw":
            return self._lora_update(rest, "bw")
        if verb == "lora_power":
            return self._lora_update(rest, "power")
        if verb == "lora_apply":
            return self._lora_update(rest, None)
        if verb == "mode" and rest:
            return self._post_mode(rest)
        if verb == "flight" and rest:
            return self._post_flight(rest)
        if verb == "difficulty" and rest:
            return self._post_difficulty(rest)
        if verb == "reset_defaults":
            return self._post_simple("/api/satellite/reset")
        if verb == "tinygs":
            return self._post_simple("/api/satellite/tinygs", {"action": rest.split()[0] if rest else "status"})
        return None

    def read_line_from_radio(self, radio_idx: int = 0, timeout: float = 1.0) -> str | None:
        """Return the newest frame the webapp received, in the CLI's format.

        The webapp already decodes everything, so the CLI just re-serialises
        it as the ``RX: <hex> | RSSI: <rssi> | SNR: <snr>`` line the radio
        would have printed.
        """
        rows = self._request("GET", "/api/telemetry?limit=20")
        if not isinstance(rows, list) or not rows:
            return None

        newest = rows[0]
        row_id = newest.get("id", 0)
        if row_id == self._last_row_id:
            return None
        self._last_row_id = row_id

        raw_hex = newest.get("raw_hex") or ""
        if not raw_hex:
            return None
        rssi = newest.get("rssi")
        snr = newest.get("snr")
        rssi_txt = str(rssi) if rssi is not None else "0"
        snr_txt = str(snr) if snr is not None else "0"
        return f"RX: {raw_hex} | RSSI: {rssi_txt} | SNR: {snr_txt}"

    def send_radio_tx(self, radio_idx: int, data: bytes) -> str | None:
        """Transmit raw bytes through the webapp."""
        result = self._request("POST", "/api/radio/send", {"data": bytes(data).hex()})
        if isinstance(result, dict):
            return json.dumps(result)
        return str(result) if result else None

    # ── Helpers ────────────────────────────────────────────────────────────

    def _describe(self, what: str, rest: str) -> str | None:
        try:
            info = self._request("GET", "/api/satellite/info")
        except WebDeviceError:
            # The webapp is up but has no board connected: answer like a
            # silent board instead of blowing up the command.
            return None
        if not isinstance(info, dict):
            return None
        local = info.get("local") or {}
        satellite = info.get("satellite") or {}

        if what == "fw_version":
            version = local.get("fw_version") or info.get("fw_version") or "unknown"
            return f"FW: {version} (sha {local.get('git_sha', '?')})"
        if what == "status":
            lines = [
                f"Mode: {info.get('mode', 'unknown')}",
                f"Flight: {info.get('flight', 'unknown')}",
                f"Difficulty: {info.get('difficulty', 0)}",
                f"SC ID: {info.get('sc_id', '?')}",
                f"FW: {local.get('fw_version', 'unknown')}",
            ]
            if satellite.get("available"):
                lines.append(f"Battery: {satellite.get('battery_mv', '?')} mV")
                lines.append(f"Uptime: {satellite.get('uptime', '?')}")
            return "\n".join(lines)
        if what == "mode":
            return str(info.get("mode", "unknown"))
        if what == "flight":
            return str(info.get("flight", "unknown"))
        if what == "difficulty":
            return str(info.get("difficulty", 0))
        if what == "sc_id":
            return str(info.get("sc_id", "?"))
        return None

    def _sensors_text(self) -> str | None:
        try:
            data = self._request("GET", "/api/satellite/sensors")
        except WebDeviceError:
            return None
        if not isinstance(data, dict):
            return None
        if not data.get("available"):
            return None
        return (
            f"Temperature: {data.get('temperature')}\n"
            f"Pressure: {data.get('pressure')}\n"
            f"Humidity: {data.get('humidity')}\n"
            f"Accel X: {data.get('accel_x')}\n"
            f"Accel Y: {data.get('accel_y')}\n"
            f"Accel Z: {data.get('accel_z')}"
        )

    def _lora_config_text(self, radio: str) -> str | None:
        cfg = self._request("GET", f"/api/satellite/lora_config?radio={radio}")
        if not isinstance(cfg, dict):
            return None
        return (
            f"Radio {radio}: freq={cfg.get('frequency')} Hz  "
            f"sf={cfg.get('sf')}  bw={cfg.get('bw')}  power={cfg.get('power')}"
        )

    def _lora_update(self, rest: str, field: str | None) -> str | None:
        parts = rest.split()
        if not parts:
            return None
        radio = parts[0]
        value = parts[1] if len(parts) > 1 else None
        payload = {"radio": radio}
        if field and value is not None:
            payload[field] = value
        result = self._request("POST", "/api/satellite/lora_config", payload)
        return json.dumps(result) if isinstance(result, dict) else None

    def _post_mode(self, mode: str) -> str | None:
        result = self._request("POST", "/api/satellite/mode", {"mode": mode})
        return json.dumps(result) if isinstance(result, dict) else None

    def _post_flight(self, flight: str) -> str | None:
        result = self._request("POST", "/api/satellite/flight", {"flight": flight})
        return json.dumps(result) if isinstance(result, dict) else None

    def _post_difficulty(self, level: str) -> str | None:
        result = self._request("POST", "/api/satellite/difficulty", {"level": level})
        return json.dumps(result) if isinstance(result, dict) else None

    def _post_simple(self, path: str, payload: dict | None = None) -> str | None:
        result = self._request("POST", path, payload or {})
        return json.dumps(result) if isinstance(result, dict) else None
