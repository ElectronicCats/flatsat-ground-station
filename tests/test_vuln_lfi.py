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

def test_lfi_path_traversal(auth_client):
    resp = auth_client.get("/api/logs?file=../../../../../../../../../../etc/passwd")
    assert resp.status_code == 200
    assert "root:" in resp.get_json()["content"]

def test_lfi_no_file_param(auth_client):
    resp = auth_client.get("/api/logs")
    assert resp.status_code == 400

def test_lfi_nonexistent_file(auth_client):
    resp = auth_client.get("/api/logs?file=nonexistent.log")
    assert resp.status_code == 404
