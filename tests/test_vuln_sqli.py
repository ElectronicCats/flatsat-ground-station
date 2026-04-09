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


def test_telemetry_search_normal(auth_client):
    resp = auth_client.get("/api/telemetry?search=0801&limit=10")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)


def test_telemetry_search_sqli_union(auth_client):
    payload = "' UNION SELECT id,username,password_hash,role,1,2,3,4,5,6,7 FROM users--"
    resp = auth_client.get(f"/api/telemetry?search={payload}&limit=100")
    assert resp.status_code == 200
    data = resp.get_json()
    found_admin = False
    for row in data:
        values = list(row.values())
        if "admin" in str(values) and "5f4dcc3b" in str(values):
            found_admin = True
            break
    assert found_admin, "SQLi UNION should leak admin hash"


def test_telemetry_default_limit(auth_client):
    resp = auth_client.get("/api/telemetry")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) <= 50
