import base64
import os
import tempfile

import pytest

from webapp.auth import create_session_token, parse_session_token
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


def test_create_session_token(app):
    with app.app_context():
        token = create_session_token("admin", "admin")
        decoded = base64.b64decode(token).decode()
        parts = decoded.split(":")
        assert parts[0] == "admin"
        assert parts[1] == "admin"
        assert len(parts) == 3


def test_parse_session_token(app):
    with app.app_context():
        token = create_session_token("operator", "operator")
        username, role = parse_session_token(token)
        assert username == "operator"
        assert role == "operator"


def test_parse_invalid_token(app):
    with app.app_context():
        username, role = parse_session_token("not-valid-base64!!!")
        assert username is None
        assert role is None


def test_parse_forged_admin_token(app):
    with app.app_context():
        forged = base64.b64encode(b"admin:admin:9999999999").decode()
        username, role = parse_session_token(forged)
        assert username == "admin"
        assert role == "admin"


def test_login_valid_credentials(client):
    resp = client.post(
        "/login",
        data={
            "username": "operator",
            "password": "operator123",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "session_token" in resp.headers.get("Set-Cookie", "")


def test_login_invalid_credentials(client):
    resp = client.post(
        "/login",
        data={
            "username": "operator",
            "password": "wrongpassword",
        },
        follow_redirects=True,
    )
    assert b"Invalid" in resp.data


def test_logout(client):
    client.post("/login", data={"username": "operator", "password": "operator123"})
    resp = client.get("/logout", follow_redirects=False)
    assert resp.status_code == 302
