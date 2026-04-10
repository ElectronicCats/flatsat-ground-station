import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from webapp.config import TestConfig
from webapp.db import init_db
from webapp.seed import seed_db


@pytest.fixture
def app():
    from webapp.app import create_app

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app = create_app(TestConfig, db_path=db_path)
    with app.app_context():
        init_db()
        seed_db()
        yield app
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def auth_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client


def test_hardware_status_idle(auth_client):
    resp = auth_client.get("/api/hardware/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mode"] == "idle"


@patch("webapp.app.discover_devices")
def test_hardware_scan(mock_discover, auth_client):
    mock_dev = MagicMock()
    mock_dev.identity.serial_number = "TESTSERIAL"
    mock_dev.is_complete = True
    mock_dev.radio0_port = "/dev/ttyACM0"
    mock_dev.radio1_port = "/dev/ttyACM1"
    mock_dev.shell_port = "/dev/ttyACM2"
    mock_dev.health.name = "HEALTHY"
    mock_discover.return_value = [mock_dev]

    resp = auth_client.post("/api/hardware/scan")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["devices"]) == 1
    assert data["devices"][0]["serial_number"] == "TESTSERIAL"


def test_hardware_connect_no_device(auth_client):
    resp = auth_client.post(
        "/api/hardware/connect",
        json={"serial_number": "NONEXISTENT"},
        content_type="application/json",
    )
    assert resp.status_code == 404


def test_hardware_disconnect_goes_idle(auth_client):
    resp = auth_client.post("/api/hardware/disconnect")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mode"] == "idle"


def test_simulate_mode(auth_client):
    resp = auth_client.post("/api/hardware/simulate")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mode"] == "simulated"
    assert data["mock_running"] is True

    # Stop goes back to idle
    resp = auth_client.post("/api/hardware/stop")
    assert resp.get_json()["mode"] == "idle"


@patch("webapp.app.discover_devices")
@patch("webapp.app.FlatSatDevice")
def test_hardware_connect_success(mock_device_cls, mock_discover, auth_client):
    mock_discovered = MagicMock()
    mock_discovered.identity.serial_number = "ABC123"
    mock_discovered.is_complete = True
    mock_discovered.radio0_port = "/dev/ttyACM0"
    mock_discovered.radio1_port = "/dev/ttyACM1"
    mock_discovered.shell_port = "/dev/ttyACM2"
    mock_discovered.health.name = "HEALTHY"
    mock_discover.return_value = [mock_discovered]

    mock_dev = MagicMock()
    mock_dev.connect.return_value = {"radio0": True, "radio1": True, "shell": True}
    mock_dev.is_connected = True
    mock_dev.serial_number = "ABC123"
    mock_device_cls.return_value = mock_dev

    # First scan
    auth_client.post("/api/hardware/scan")

    # Then connect
    resp = auth_client.post(
        "/api/hardware/connect",
        json={"serial_number": "ABC123"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mode"] == "hardware"

    # Status should now be hardware
    resp = auth_client.get("/api/hardware/status")
    assert resp.get_json()["mode"] == "hardware"
