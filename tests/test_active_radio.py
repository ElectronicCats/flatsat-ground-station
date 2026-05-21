import os
import tempfile
from unittest.mock import MagicMock

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


def _setup_hardware(app):
    gs = app.config["GS_STATE"]
    mock_dev = MagicMock()
    mock_dev.serial_number = "TEST123"
    mock_dev.is_connected = True
    gs.set_hardware(mock_dev)
    return mock_dev


def test_active_radio_get(app, auth_client):
    gs = app.config["GS_STATE"]
    gs.active_radio = 1
    resp = auth_client.get("/api/hardware/active_radio")
    assert resp.status_code == 200
    assert resp.get_json()["active_radio"] == 1


def test_active_radio_switch(app, auth_client):
    mock_dev = _setup_hardware(app)
    gs = app.config["GS_STATE"]
    assert gs.active_radio == 0

    # Switch to Radio 1
    resp = auth_client.post("/api/hardware/active_radio", json={"active_radio": 1}, content_type="application/json")
    assert resp.status_code == 200
    assert gs.active_radio == 1
    mock_dev.send_shell_command_full.assert_any_call("radio1")
    mock_dev.reset_radio_input_buffers.assert_called_once()

    # Switch to Radio 0
    resp = auth_client.post("/api/hardware/active_radio", json={"active_radio": 0}, content_type="application/json")
    assert resp.status_code == 200
    assert gs.active_radio == 0
    mock_dev.send_shell_command_full.assert_any_call("radio0")


def test_active_radio_invalid(app, auth_client):
    resp = auth_client.post("/api/hardware/active_radio", json={"active_radio": 3}, content_type="application/json")
    assert resp.status_code == 400


def test_satellite_flight_post_ground_station(app, auth_client):
    mock_dev = _setup_hardware(app)
    # mock dev shell commands so it is treated as a ground station role
    mock_dev.send_shell_command_full.side_effect = lambda cmd, **kw: {
        "mode": "modemode: raw",
        "status": "statusmode=command",
    }.get(cmd)

    mock_dev.send_radio_tx.return_value = "Success"

    resp = auth_client.post("/api/satellite/flight", json={"flight": "nominal"}, content_type="application/json")
    assert resp.status_code == 200
    mock_dev.send_radio_tx.assert_called_once()
    call_args = mock_dev.send_radio_tx.call_args[0]
    assert call_args[0] == 1  # active_radio during tx
    assert len(call_args[1]) > 0  # CCSDS frame data


def test_satellite_difficulty_post_ground_station(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.side_effect = lambda cmd, **kw: {
        "mode": "modemode: raw",
        "status": "statusmode=command",
    }.get(cmd)

    mock_dev.send_radio_tx.return_value = "Success"

    resp = auth_client.post("/api/satellite/difficulty", json={"level": 2}, content_type="application/json")
    assert resp.status_code == 200
    mock_dev.send_radio_tx.assert_called_once()
    call_args = mock_dev.send_radio_tx.call_args[0]
    assert call_args[0] == 1  # active_radio during tx
    assert len(call_args[1]) > 0  # CCSDS difficulty frame data
    assert app.config["GS_STATE"].difficulty == 2


def test_satellite_reset_ground_station(app, auth_client):
    mock_dev = _setup_hardware(app)
    gs = app.config["GS_STATE"]
    gs.active_radio = 1
    gs.difficulty = 3
    mock_dev.send_shell_command_full.side_effect = lambda cmd, **kw: {
        "mode": "modemode: raw",
        "status": "statusmode=command",
        "reset_defaults": "Defaults restored",
    }.get(cmd)

    resp = auth_client.post("/api/satellite/reset")
    assert resp.status_code == 200
    assert gs.active_radio == 0
    assert gs.difficulty == 0
    mock_dev.send_shell_command_full.assert_any_call("reset_defaults")
    mock_dev.send_shell_command_full.assert_any_call("radio0")
