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
