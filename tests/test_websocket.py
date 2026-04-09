import os
import tempfile

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


def test_dashboard_has_socketio_script(auth_client):
    resp = auth_client.get("/dashboard")
    assert resp.status_code == 200
    assert b"socket.io" in resp.data or b"telemetry.js" in resp.data


def test_dashboard_shows_telemetry_area(auth_client):
    resp = auth_client.get("/dashboard")
    assert b"telemetry" in resp.data.lower()
