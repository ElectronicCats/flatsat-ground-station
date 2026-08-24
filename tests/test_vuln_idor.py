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
def operator_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client


def test_idor_access_admin_config(app, operator_client):
    resp = operator_client.get("/api/config/radio/1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["owner"] == "admin"
    assert "CLASSIFIED" in data["description"]
    level = app.config["CTF_LEVEL"]
    assert data["notes"] == f"PWNSAT{{IDOR_ADMIN_CONFIG_LVL{level}}}"


def test_idor_own_config(operator_client):
    resp = operator_client.get("/api/config/radio/2")
    assert resp.status_code == 200
    assert resp.get_json()["owner"] == "operator"


def test_idor_nonexistent(operator_client):
    resp = operator_client.get("/api/config/radio/999")
    assert resp.status_code == 404


def test_config_page_renders(operator_client):
    resp = operator_client.get("/config")
    assert resp.status_code == 302
    assert "/dashboard" in resp.headers["Location"]
