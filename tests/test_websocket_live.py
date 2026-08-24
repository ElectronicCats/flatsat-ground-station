import tempfile
import os
import pytest
from flask_socketio import SocketIO

from modules.webapp.config import TestConfig
from modules.webapp.db import init_db
from modules.webapp.seed import seed_db
from modules.webapp.app import create_app, socketio


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


def test_websocket_connect_and_disconnect(app):
    client = socketio.test_client(app)
    assert client.is_connected()
    client.disconnect()
    assert not client.is_connected()


def test_websocket_telemetry_broadcast(app):
    client = socketio.test_client(app)
    assert client.is_connected()

    # Emit telemetry update from within application context
    with app.app_context():
        socketio.emit(
            "telemetry_update",
            {
                "apid": 1,
                "raw_hex": "0801C000000401020304",
                "decoded": {"battery_mv": 4200, "state": "NOMINAL"},
                "timestamp": "2026-08-19T13:00:00Z",
            },
        )

    received = client.get_received()
    assert len(received) >= 1
    event = received[0]
    assert event["name"] == "telemetry_update"
    assert event["args"][0]["apid"] == 1
    assert event["args"][0]["decoded"]["battery_mv"] == 4200
    client.disconnect()
