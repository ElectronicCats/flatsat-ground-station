import json
import os
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from modules.webapp.config import TestConfig
from modules.webapp.db import init_db
from modules.webapp.seed import seed_db
from modules.webapp.app import create_app


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app_instance = create_app(TestConfig, db_path=db_path)
    with app_instance.app_context():
        init_db()
        seed_db()
        yield app_instance
    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def operator_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client


@pytest.fixture
def admin_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "password"})
    return client


def test_api_endpoints_public_discovery(app):
    client = app.test_client()
    resp = client.get("/api/endpoints")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    routes = [item["rule"] for item in data]
    assert "/api/telemetry" in routes
    assert "/api/diagnostics" in routes
    assert "/api/admin/panel" in routes


def test_api_users_me(operator_client, admin_client):
    resp_op = operator_client.get("/api/users/me")
    assert resp_op.status_code == 200
    assert resp_op.get_json()["username"] == "operator"
    assert resp_op.get_json()["role"] == "operator"

    resp_adm = admin_client.get("/api/users/me")
    assert resp_adm.status_code == 200
    assert resp_adm.get_json()["username"] == "admin"
    assert "admin_notes" in resp_adm.get_json()


def test_api_radio_status(operator_client):
    resp = operator_client.get("/api/radio/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "connected" in data
    assert "mode" in data
    assert "bridge_key" in data


def test_api_hardware_status(operator_client):
    resp = operator_client.get("/api/hardware/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "mode" in data


@patch("modules.webapp.app.discover_devices")
def test_api_hardware_scan(mock_discover, operator_client):
    mock_discover.return_value = []
    resp = operator_client.post("/api/hardware/scan")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "devices" in data


def test_api_hardware_simulate_and_stop(operator_client):
    resp_sim = operator_client.post("/api/hardware/simulate")
    assert resp_sim.status_code == 200
    assert resp_sim.get_json()["mode"] == "simulated"

    resp_stop = operator_client.post("/api/hardware/stop")
    assert resp_stop.status_code == 200
    assert resp_stop.get_json()["mode"] == "idle"


def test_api_hardware_active_radio(operator_client, admin_client):
    # GET is accessible to operator
    resp_get = operator_client.get("/api/hardware/active_radio")
    assert resp_get.status_code == 200
    assert "active_radio" in resp_get.get_json()

    # POST is restricted to admin (operator gets 403)
    resp_op_post = operator_client.post("/api/hardware/active_radio", json={"active_radio": 1})
    assert resp_op_post.status_code == 403

    # Admin POST succeeds
    resp_adm_post = admin_client.post("/api/hardware/active_radio", json={"active_radio": 1})
    assert resp_adm_post.status_code == 200
    assert resp_adm_post.get_json()["active_radio"] == 1


def test_api_satellite_info_with_mock_hardware(app, operator_client):
    mock_dev = MagicMock()
    mock_dev.serial_number = "TEST_BOARD_1"
    mock_dev.has_radio1 = True
    mock_dev.send_shell_command_full.side_effect = lambda cmd, timeout=1.0: {
        "fw_version": "FW: v1.0.0",
        "mode": "mode: satellite",
        "flight": "flight: NOMINAL",
        "difficulty": "difficulty: 1",
        "sc_id": "sc_id: 0x01",
        "status": "State: OK",
    }.get(cmd, "OK")

    gs = app.config["GS_STATE"]
    gs.set_hardware(mock_dev)

    resp = operator_client.get("/api/satellite/info")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "connection_role" in data
    assert "flight" in data


def test_api_satellite_admin_controls(operator_client, admin_client):
    # Mode endpoint requires admin
    resp_op_mode = operator_client.post("/api/satellite/mode", json={"mode": "ground_station"})
    assert resp_op_mode.status_code == 403

    # Flight endpoint requires admin
    resp_op_flight = operator_client.post("/api/satellite/flight", json={"flight": "nominal"})
    assert resp_op_flight.status_code == 403

    # Difficulty endpoint requires admin
    resp_op_diff = operator_client.post("/api/satellite/difficulty", json={"difficulty": 2})
    assert resp_op_diff.status_code == 403


def test_api_logs_get_and_post(operator_client):
    # POST log
    resp_post = operator_client.post("/api/logs", json={"message": "System check initiated"})
    assert resp_post.status_code == 200

    # GET logs with query_string
    resp_get = operator_client.get("/api/logs", query_string={"file": "../modules/webapp/app.py"})
    assert resp_get.status_code in (200, 404)
