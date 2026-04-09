import base64
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
def client(app):
    return app.test_client()


def test_auth_bypass_forged_token(client):
    forged_token = base64.b64encode(b"admin:admin:1234567890").decode()
    client.set_cookie("session_token", forged_token)
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert b"admin" in resp.data


def test_auth_bypass_operator_to_admin(client):
    client.post("/login", data={"username": "operator", "password": "operator123"})
    forged = base64.b64encode(b"admin:admin:9999999999").decode()
    client.set_cookie("session_token", forged)
    resp = client.get("/api/config/radio/1")
    assert resp.status_code == 200


def test_commands_page(client):
    client.post("/login", data={"username": "operator", "password": "operator123"})
    resp = client.get("/commands")
    assert resp.status_code == 200
