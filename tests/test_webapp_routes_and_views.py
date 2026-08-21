import os
import tempfile
import pytest

from modules.webapp.config import TestConfig
from modules.webapp.db import init_db
from modules.webapp.seed import seed_db
from modules.webapp.app import create_app


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app_instance = create_app(TestConfig, db_path=db_path)
    with app_instance.app_context():
        init_db()
        seed_db()
        yield app_instance
    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_operator(app):
    client = app.test_client()
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client


@pytest.fixture
def auth_admin(app):
    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "password"})
    return client


def test_index_redirects_to_login(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_login_page_get(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"Login" in resp.data or b"password" in resp.data


def test_login_invalid_credentials(client):
    resp = client.post("/login", data={"username": "invalid_user", "password": "bad_password"})
    assert resp.status_code == 200
    assert b"Invalid credentials" in resp.data


def test_login_and_logout_flow(client):
    resp_login = client.post("/login", data={"username": "operator", "password": "operator123"})
    assert resp_login.status_code == 302
    assert "/dashboard" in resp_login.headers["Location"]

    resp_dash = client.get("/dashboard")
    assert resp_dash.status_code == 200
    assert b"Ground Station" in resp_dash.data or b"Dashboard" in resp_dash.data

    resp_logout = client.get("/logout")
    assert resp_logout.status_code == 302
    assert "/login" in resp_logout.headers["Location"]

    # Subsequent access without token should redirect
    resp_unauth = client.get("/dashboard")
    assert resp_unauth.status_code == 302


def test_dashboard_requires_login(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_logs_page(auth_operator):
    resp = auth_operator.get("/logs")
    assert resp.status_code == 200
    assert b"System Logs" in resp.data or b"logs" in resp.data


def test_satellite_page(auth_operator):
    resp = auth_operator.get("/satellite")
    assert resp.status_code == 200
    assert b"Satellite" in resp.data or b"Controls" in resp.data


def test_config_page_role_restriction(auth_operator, auth_admin):
    # Operator is redirected away from /config to /dashboard
    resp_op = auth_operator.get("/config")
    assert resp_op.status_code == 302
    assert "/dashboard" in resp_op.headers["Location"]

    # Admin is granted access to /config
    resp_adm = auth_admin.get("/config")
    assert resp_adm.status_code == 200
    assert b"Radio Configuration" in resp_adm.data or b"Config" in resp_adm.data


def test_404_error_page(client):
    resp = client.get("/nonexistent_route_12345")
    assert resp.status_code == 404
    assert b"404" in resp.data or b"Not Found" in resp.data
