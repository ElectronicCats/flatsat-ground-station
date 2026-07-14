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
def client(app):
    c = app.test_client()
    c.post("/login", data={"username": "admin", "password": "password"})
    return c


def test_config_update_all_fields(client, app):
    """POST /api/config/radio sends all 4 fields and persists them."""
    resp = client.post(
        "/api/config/radio",
        json={
            "frequency": "433000000",
            "spreading_factor": "10",
            "bandwidth": "250000",
            "tx_power": "20",
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["config"]["frequency"] == 433000000
    assert data["config"]["spreading_factor"] == 10
    assert data["config"]["bandwidth"] == 250000
    assert data["config"]["tx_power"] == 20


def test_config_update_persists_to_db(client, app):
    """Config is upserted for the logged-in user."""
    client.post(
        "/api/config/radio",
        json={
            "frequency": "868000000",
            "spreading_factor": "12",
            "bandwidth": "125000",
            "tx_power": "14",
        },
    )
    with app.app_context():
        db = get_db()
        row = db.execute(
            "SELECT * FROM radio_config WHERE owner = ? AND description = ?",
            ("admin", "Radio 0"),
        ).fetchone()
        assert row is not None
        assert row["frequency"] == 868000000
        assert row["spreading_factor"] == 12


def test_config_update_upserts(client, app):
    """Second POST updates existing row, not inserts a new one."""
    client.post("/api/config/radio", json={"frequency": "100"})
    client.post("/api/config/radio", json={"frequency": "200"})
    with app.app_context():
        db = get_db()
        rows = db.execute(
            "SELECT * FROM radio_config WHERE owner = ? AND description = ?",
            ("admin", "Radio 0"),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["frequency"] == 200


def test_config_update_shell_injection_surface(client):
    """GS-07: f-string shell injection works for all 4 fields."""
    resp = client.post(
        "/api/config/radio",
        json={"frequency": "915000000; echo pwned"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "pwned" in data.get("shell_output", "")


def test_config_update_defaults(client):
    """Missing fields use defaults."""
    resp = client.post("/api/config/radio", json={})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["config"]["frequency"] == 915000000
    assert data["config"]["spreading_factor"] == 7
    assert data["config"]["bandwidth"] == 125000
    assert data["config"]["tx_power"] == 14


def test_config_update_radio1(client, app):
    """POST with radio='Radio 1' persists separately from Radio 0."""
    client.post("/api/config/radio", json={"radio": "Radio 0", "frequency": "915000000"})
    client.post("/api/config/radio", json={"radio": "Radio 1", "frequency": "916000000"})
    with app.app_context():
        db = get_db()
        r0 = db.execute(
            "SELECT * FROM radio_config WHERE owner = ? AND description = ?",
            ("admin", "Radio 0"),
        ).fetchone()
        r1 = db.execute(
            "SELECT * FROM radio_config WHERE owner = ? AND description = ?",
            ("admin", "Radio 1"),
        ).fetchone()
        assert r0["frequency"] == 915000000
        assert r1["frequency"] == 916000000


def test_config_page_renders_both_radios(client):
    """Config page renders with configs dict for both radios."""
    resp = client.get("/config")
    assert resp.status_code == 200
    assert b"Radio 0" in resp.data
    assert b"Radio 1" in resp.data
