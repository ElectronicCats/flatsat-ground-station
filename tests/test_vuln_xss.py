import os
import tempfile

import pytest

from webapp.config import TestConfig
from webapp.db import get_db, init_db
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


def test_logs_page_renders(auth_client):
    resp = auth_client.get("/logs")
    assert resp.status_code == 200
    assert b"Ground station initialized" in resp.data


def test_logs_xss_stored(app, auth_client):
    xss_payload = '<script>alert("XSS")</script>'
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO logs (timestamp, level, source, message) VALUES (?, ?, ?, ?)",
            ("2026-04-09T12:00:00", "INFO", "test", xss_payload),
        )
        db.commit()
    resp = auth_client.get("/logs")
    assert xss_payload.encode() in resp.data
