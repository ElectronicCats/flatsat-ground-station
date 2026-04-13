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
def operator_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client


@pytest.fixture
def admin_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "password"})
    return client


def test_schema_has_admin_notes(app):
    from webapp.db import get_db

    with app.app_context():
        db = get_db()
        cols = {row[1] for row in db.execute("PRAGMA table_info(users)").fetchall()}
        assert "admin_notes" in cols


def test_schema_has_radio_config_notes(app):
    from webapp.db import get_db

    with app.app_context():
        db = get_db()
        cols = {row[1] for row in db.execute("PRAGMA table_info(radio_config)").fetchall()}
        assert "notes" in cols


def test_schema_has_secrets_table(app):
    from webapp.db import get_db

    with app.app_context():
        db = get_db()
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "secrets" in tables


def test_seed_admin_notes_flag(app):
    from webapp.db import get_db

    with app.app_context():
        db = get_db()
        admin = db.execute("SELECT admin_notes FROM users WHERE username = 'admin'").fetchone()
        assert admin["admin_notes"] == "PWNSAT{XSS_IN_MISSION_LOGS}"


def test_seed_admin_radio_config_notes_flag(app):
    from webapp.db import get_db

    with app.app_context():
        db = get_db()
        config = db.execute("SELECT notes FROM radio_config WHERE owner = 'admin'").fetchone()
        assert config["notes"] == "PWNSAT{IDOR_ADMIN_CONFIG}"


def test_seed_secrets_flag(app):
    from webapp.db import get_db

    with app.app_context():
        db = get_db()
        secret = db.execute("SELECT * FROM secrets WHERE name = 'satellite_master_key'").fetchone()
        assert secret["value"] == "PWNSAT{TELEMETRY_DB_TAMPERED}"
        assert secret["access_level"] == "classified"


def test_seed_debug_log_flag(app):
    from webapp.db import get_db

    with app.app_context():
        db = get_db()
        log = db.execute("SELECT * FROM logs WHERE level = 'DEBUG'").fetchone()
        assert log is not None
        assert log["message"] == "PWNSAT{LOG_INJECTION_SUCCESS}"
        assert log["source"] == "flag-service"


def test_lfi_flag_file_exists():
    flag_path = os.path.join(os.path.dirname(__file__), "..", "webapp", "lfi_flag.txt")
    assert os.path.exists(flag_path)
    with open(flag_path) as f:
        assert f.read().strip() == "PWNSAT{LFI_TRAVERSAL_SUCCESS}"


def test_radio_flag_file_exists():
    flag_path = os.path.join(os.path.dirname(__file__), "..", "webapp", "radio_flag.txt")
    assert os.path.exists(flag_path)
    with open(flag_path) as f:
        assert f.read().strip() == "PWNSAT{CMDI_IN_RADIO_CONFIG}"


def test_supply_chain_flag_in_requirements():
    req_path = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
    with open(req_path) as f:
        content = f.read()
    assert "PWNSAT{SUPPLY_CHAIN_COMPROMISED}" in content


def test_gs05_admin_panel_as_admin(admin_client):
    resp = admin_client.get("/api/admin/panel")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["flag"] == "PWNSAT{SESSION_TOKEN_FORGED}"


def test_gs05_admin_panel_as_operator(operator_client):
    resp = operator_client.get("/api/admin/panel")
    assert resp.status_code == 403


def test_gs05_admin_panel_forged_token(app):
    client = app.test_client()
    forged = base64.b64encode(b"admin:admin:0").decode()
    client.set_cookie("session_token", forged)
    resp = client.get("/api/admin/panel")
    assert resp.status_code == 200
    assert resp.get_json()["flag"] == "PWNSAT{SESSION_TOKEN_FORGED}"


def test_gs02_users_me_as_admin(admin_client):
    resp = admin_client.get("/api/users/me")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["username"] == "admin"
    assert data["admin_notes"] == "PWNSAT{XSS_IN_MISSION_LOGS}"


def test_gs02_users_me_as_operator(operator_client):
    resp = operator_client.get("/api/users/me")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["username"] == "operator"
    assert data["admin_notes"] == ""


def test_gs08_radio_status(operator_client):
    resp = operator_client.get("/api/radio/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["bridge_key"] == "PWNSAT{WEB_TO_SPACE_LINK}"


def test_gs12_debug_flags_no_auth(app):
    client = app.test_client()
    resp = client.get("/api/debug/flags")
    assert resp.status_code == 200
    assert resp.get_json()["flag"] == "PWNSAT{API_NO_RATE_LIMIT}"


def test_gs12_debug_flags_listed_in_endpoints(app):
    client = app.test_client()
    resp = client.get("/api/endpoints")
    rules = [r["rule"] for r in resp.get_json()]
    assert "/api/debug/flags" in rules
