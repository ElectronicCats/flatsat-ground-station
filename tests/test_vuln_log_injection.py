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


def test_log_injection_newlines(app, auth_client):
    payload = "Normal log\n2026-04-08 ADMIN: System shutdown authorized"
    resp = auth_client.post("/api/logs", json={"message": payload}, content_type="application/json")
    assert resp.status_code == 200
    with app.app_context():
        db = get_db()
        row = db.execute("SELECT message FROM logs WHERE message LIKE '%System shutdown%'").fetchone()
        assert row is not None
        assert "\n" in row["message"]
