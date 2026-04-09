import os
import tempfile
import pytest
from webapp.config import TestConfig
from webapp.db import init_db
from webapp.seed import seed_db
from webapp.radio_bridge import RadioBridge

def test_radio_bridge_mock_mode():
    bridge = RadioBridge()
    assert bridge.is_connected is False
    assert bridge.mode == "simulated"

def test_radio_bridge_send_raw_mock():
    bridge = RadioBridge()
    result = bridge.send_raw(b"\x08\x01\xC0\x00")
    assert result["status"] == "sent_simulated"

def test_radio_bridge_send_tc_mock():
    bridge = RadioBridge()
    result = bridge.send_tc(0x020, b"\x10")
    assert result["status"] == "sent_simulated"
    assert "frame_hex" in result

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

def test_radio_send_endpoint(auth_client):
    resp = auth_client.post("/api/radio/send", json={"data": "080100"}, content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "sent_simulated"
