import os
import sqlite3
import tempfile

import pytest

from webapp.config import Config, TestConfig
from webapp.db import get_db, close_db, init_db


@pytest.fixture
def app():
    from webapp.app import create_app
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app = create_app(TestConfig, db_path=db_path)

    with app.app_context():
        init_db()
        yield app

    os.close(db_fd)
    os.unlink(db_path)


def test_get_db_returns_connection(app):
    with app.app_context():
        db = get_db()
        assert isinstance(db, sqlite3.Connection)


def test_get_db_same_connection(app):
    with app.app_context():
        db1 = get_db()
        db2 = get_db()
        assert db1 is db2


def test_init_db_creates_tables(app):
    with app.app_context():
        db = get_db()
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        assert "users" in table_names
        assert "telemetry" in table_names
        assert "radio_config" in table_names
        assert "logs" in table_names
