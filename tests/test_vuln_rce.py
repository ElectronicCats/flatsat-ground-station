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

def test_diagnostics_rce(auth_client):
    resp = auth_client.post("/api/diagnostics", json={"cmd": "echo PWNSAT_TEST"}, content_type="application/json")
    assert resp.status_code == 200
    assert "PWNSAT_TEST" in resp.get_json()["output"]

def test_diagnostics_command_injection(auth_client):
    resp = auth_client.post("/api/diagnostics", json={"cmd": "echo hello; echo injected"}, content_type="application/json")
    assert resp.status_code == 200
    assert "injected" in resp.get_json()["output"]

def test_diagnostics_no_cmd(auth_client):
    resp = auth_client.post("/api/diagnostics", json={}, content_type="application/json")
    assert resp.status_code == 400
