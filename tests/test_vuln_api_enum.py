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

def test_api_endpoints_no_auth(client):
    resp = client.get("/api/endpoints")
    assert resp.status_code == 200

def test_api_endpoints_lists_routes(client):
    resp = client.get("/api/endpoints")
    data = resp.get_json()
    routes = [r["rule"] for r in data]
    assert "/api/diagnostics" in routes
    assert "/api/telemetry" in routes
    assert "/api/config/radio/<int:config_id>" in routes
