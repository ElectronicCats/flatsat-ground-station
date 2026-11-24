"""Tests for the web transport: the CLI driving a running webapp."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from modules.core.web_device import WebDevice, WebDeviceError

# ── A tiny fake of the ground station webapp ────────────────────────────────


class _Handler(BaseHTTPRequestHandler):
    """Answers the subset of the webapp API the CLI uses."""

    routes = {}

    def log_message(self, *args):  # silence the test output
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - required by BaseHTTPRequestHandler
        path = self.path.split("?")[0]
        handler = self.routes.get(path)
        if handler is None:
            self._send(404, {"error": "not found"})
            return
        code, payload = handler
        self._send(code, payload)

    def do_POST(self):  # noqa: N802 - required by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw or b"{}")
        except ValueError:
            payload = {}
        handler = self.routes.get(self.path)
        if handler is None:
            self._send(404, {"error": "not found"})
            return
        code, response = handler
        self._send(code, {"echo": payload, "response": response})


@pytest.fixture
def webapp():
    """Run a fake webapp and yield its base URL."""
    _Handler.routes = {
        "/api/hardware/status": (200, {"mode": "hardware", "serial_number": "ABC123", "active_radio": 2}),
        "/api/satellite/info": (
            200,
            {
                "fw_version": "1.2.3",
                "git_sha": "deadbee",
                "mode": "ground_station",
                "flight": "NOMINAL",
                "difficulty": 2,
                "sc_id": 2,
                "local": {"fw_version": "1.2.3", "git_sha": "deadbee"},
                "satellite": {"available": True, "battery_mv": 4100, "uptime": 99},
            },
        ),
        "/api/satellite/sensors": (
            200,
            {"available": True, "temperature": 22.5, "pressure": 1013.0, "humidity": 40.0},
        ),
        "/api/telemetry": (
            200,
            [
                {
                    "id": 7,
                    "apid": 31,
                    "raw_hex": "081FC00000140000009B4B",
                    "rssi": -27,
                    "snr": 12,
                    "timestamp": "2026-01-01T00:00:00",
                }
            ],
        ),
        "/api/satellite/lora_config": (200, {"frequency": 915000000, "sf": 7, "bw": 125000, "power": 14}),
    }
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


# ── Tests ───────────────────────────────────────────────────────────────────


def test_connect_reports_hardware(webapp):
    dev = WebDevice(webapp)
    result = dev.connect()
    assert result["shell"] is True
    assert dev.is_connected is True


def test_connect_fails_without_webapp():
    dev = WebDevice("http://127.0.0.1:1")
    with pytest.raises(WebDeviceError):
        dev.connect()


def test_status_command_uses_the_webapp(webapp):
    dev = WebDevice(webapp)
    dev.connect()
    out = dev.send_shell_command_full("status")
    assert "ground_station" in out
    assert "NOMINAL" in out
    assert "1.2.3" in out


def test_fw_version_command(webapp):
    dev = WebDevice(webapp)
    dev.connect()
    assert "1.2.3" in dev.send_shell_command_full("fw_version")


def test_sensors_command(webapp):
    dev = WebDevice(webapp)
    dev.connect()
    out = dev.send_shell_command_full("sensors")
    assert "Temperature" in out
    assert "22.5" in out


def test_read_line_reformats_the_frame(webapp):
    """The CLI expects the 'RX: <hex> | RSSI: x | SNR: y' radio format."""
    dev = WebDevice(webapp)
    dev.connect()
    line = dev.read_line_from_radio(0, timeout=1.0)
    assert line.startswith("RX: 081FC00000140000009B4B")
    assert "RSSI: -27" in line
    assert "SNR: 12" in line


def test_read_line_does_not_repeat_the_same_frame(webapp):
    dev = WebDevice(webapp)
    dev.connect()
    assert dev.read_line_from_radio(0, timeout=1.0) is not None
    # The same row must not be reported twice in a row
    assert dev.read_line_from_radio(0, timeout=1.0) is None


def test_unsupported_command_returns_none(webapp):
    dev = WebDevice(webapp)
    dev.connect()
    assert dev.send_shell_command_full("reboot") is None


def test_disconnect_is_harmless(webapp):
    dev = WebDevice(webapp)
    dev.connect()
    dev.disconnect()
    assert dev.is_connected is False


def test_cli_accepts_the_web_option():
    """The -w/--web flag is wired into the CLI root group."""
    from click.testing import CliRunner

    from modules.core.cli import cli

    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "--web" in result.output


def test_resolve_web_prefers_the_explicit_url():
    """-w is a flag: it must never swallow the sub-command name."""
    from modules.core.session import resolve_web

    assert resolve_web(True, None) == "http://127.0.0.1:5000"
    assert resolve_web(True, "http://10.0.0.5:5000") == "http://10.0.0.5:5000"
    assert resolve_web(None, None) is None
    assert resolve_web(False, None) is None


def test_web_flag_before_the_subcommand():
    """'flatsat -w status' must not eat 'status' as the value of -w."""
    from click.testing import CliRunner

    from modules.core.cli import cli

    result = CliRunner().invoke(cli, ["-w", "--help"])
    assert result.exit_code == 0
    assert "Missing command" not in result.output
