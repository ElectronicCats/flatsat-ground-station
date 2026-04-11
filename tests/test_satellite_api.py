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


def test_satellite_info_not_connected(auth_client):
    resp = auth_client.get("/api/satellite/info")
    assert resp.status_code == 400
    assert "not connected" in resp.get_json()["error"].lower()


def test_satellite_page_renders(auth_client):
    resp = auth_client.get("/satellite")
    assert resp.status_code == 200
    assert b"Satellite" in resp.data


def _setup_hardware(app):
    gs = app.config["GS_STATE"]
    mock_dev = MagicMock()
    mock_dev.serial_number = "TEST123"
    mock_dev.is_connected = True
    gs.set_hardware(mock_dev)
    return mock_dev


def test_satellite_info_connected(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.side_effect = lambda cmd, **kw: {
        "fw_version": "fw_versionFW: dev-test\nGit: abc1234 (dirty)\nBuilt: 2026-01-01\nCompiler: GNU",
        "mode": "modemode: mission",
        "flight": "flightflight: NOMINAL  battery: 3650 mV  tm_rate: 10 sec",
        "difficulty": "difficultydifficulty: 1 (normal)",
        "sc_id": "sc_idspacecraft_id: 0x02",
        "status": "statusmode=stream",
    }.get(cmd)

    resp = auth_client.get("/api/satellite/info")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["fw_version"] == "dev-test"
    assert data["mode"] == "mission"
    assert data["flight"] == "NOMINAL"
    assert data["battery_mv"] == 3650
    assert data["difficulty"] == 1
    assert data["sc_id"] == 2
    assert data["local"]["role"] == "satellite"
    assert data["satellite"]["source"] == "local"


def test_satellite_status_ground_station_prefers_remote_tm(app, auth_client):
    mock_dev = _setup_hardware(app)
    gs = app.config["GS_STATE"]
    gs.update_remote_satellite(
        0x001,
        {
            "sc_id": 2,
            "flight_mode": 2,
            "difficulty": 3,
            "battery_mv": 3410,
            "uptime": 90,
            "tc_count": 14,
            "error_count": 2,
        },
        rssi=-71,
        snr=8.0,
    )
    mock_dev.send_shell_command_full.side_effect = lambda cmd, **kw: {
        "mode": "modemode: raw",
        "flight": "flightflight: IDLE  battery: 0 mV  tm_rate: 10 sec",
        "difficulty": "difficultydifficulty: 1 (normal)",
        "status": "statusmode=command",
    }.get(cmd)

    resp = auth_client.get("/api/satellite/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["connection_role"] == "ground_station"
    assert data["local"]["mode"] == "ground_station"
    assert data["satellite"]["source"] == "remote"
    assert data["satellite"]["battery_mv"] == 3410
    assert data["satellite"]["flight"] == "SAFE"
    assert data["satellite"]["tc_count"] == 14


def test_satellite_sensors_ground_station_use_remote_snapshot(app, auth_client):
    mock_dev = _setup_hardware(app)
    gs = app.config["GS_STATE"]
    gs.update_remote_satellite(0x010, {"temperature": 22.75, "pressure": 101250.0, "humidity": 48}, rssi=-69, snr=7.5)
    gs.update_remote_satellite(0x011, {"accel_x": 12, "accel_y": -4, "accel_z": 1003}, rssi=-69, snr=7.5)
    mock_dev.send_shell_command_full.side_effect = lambda cmd, **kw: {
        "mode": "modemode: raw",
        "status": "statusmode=command",
    }.get(cmd)

    resp = auth_client.get("/api/satellite/sensors")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["source"] == "remote"
    assert data["temperature"] == 22.75
    assert data["accel_z"] == 1003


def test_satellite_sensors(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = (
        "sensorsAccel: x=10 mg  y=-5 mg  z=1000 mg\nTemp:  23.500 C\nPress: 101300 Pa\nHumid: 50%"
    )
    resp = auth_client.get("/api/satellite/sensors")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["temperature"] == 23.5
    assert data["humidity"] == 50


def test_satellite_lora_config_get(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = (
        "lora_config R0Radio 0 LoRa Config:\n"
        "  Frequency: 915000000 Hz\n  SF: 7\n  BW: 125 kHz\n"
        "  CR: 4/5\n  Power: 20 dBm\n  Preamble: 12\n"
        "  SyncWord: 0x12 (private)\n  IQ: normal"
    )
    resp = auth_client.get("/api/satellite/lora_config")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["frequency"] == 915000000
    assert data["sf"] == 7


def test_satellite_lora_config_post(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = "OK"
    resp = auth_client.post(
        "/api/satellite/lora_config",
        json={"frequency": 436703000, "sf": 10, "bw": 250, "power": 22},
        content_type="application/json",
    )
    assert resp.status_code == 200
    calls = [c[0][0] for c in mock_dev.send_shell_command_full.call_args_list]
    assert "lora_freq R0 436703000" in calls
    assert "lora_apply R0" in calls


def test_satellite_mode_mission(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = "OK"
    resp = auth_client.post("/api/satellite/mode", json={"mode": "mission"}, content_type="application/json")
    assert resp.status_code == 200
    calls = [c[0][0] for c in mock_dev.send_shell_command_full.call_args_list]
    assert "mode mission" in calls
    assert "lora_mode ALL stream" in calls


def test_satellite_mode_ground_station(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = "OK"
    resp = auth_client.post("/api/satellite/mode", json={"mode": "ground_station"}, content_type="application/json")
    assert resp.status_code == 200
    calls = [c[0][0] for c in mock_dev.send_shell_command_full.call_args_list]
    assert "mode raw" in calls
    assert "lora_mode ALL command" in calls


def test_satellite_flight_post(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = "flight mode set to: nominal"
    resp = auth_client.post("/api/satellite/flight", json={"flight": "nominal"}, content_type="application/json")
    assert resp.status_code == 200
    mock_dev.send_shell_command_full.assert_called_with("flight nominal")


def test_satellite_difficulty_post(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = "difficulty set to 2"
    resp = auth_client.post("/api/satellite/difficulty", json={"level": 2}, content_type="application/json")
    assert resp.status_code == 200
    mock_dev.send_shell_command_full.assert_called_with("difficulty 2")


def test_satellite_tinygs_spoof(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = "Spoofing Norbi"
    resp = auth_client.post(
        "/api/satellite/tinygs", json={"action": "spoof", "profile": "norbi"}, content_type="application/json"
    )
    assert resp.status_code == 200
    mock_dev.send_shell_command_full.assert_called_with("tinygs spoof norbi")


def test_satellite_tinygs_stop(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = "TinyGS stopped"
    resp = auth_client.post("/api/satellite/tinygs", json={"action": "stop"}, content_type="application/json")
    assert resp.status_code == 200
    mock_dev.send_shell_command_full.assert_called_with("tinygs stop")


def test_satellite_reset(app, auth_client):
    mock_dev = _setup_hardware(app)
    mock_dev.send_shell_command_full.return_value = "Defaults restored"
    resp = auth_client.post("/api/satellite/reset")
    assert resp.status_code == 200
    calls = [c[0][0] for c in mock_dev.send_shell_command_full.call_args_list]
    assert "reset_defaults" in calls
    assert "lora_freq R1 916000000" in calls
    assert "lora_apply R1" in calls
