import os
import tempfile

import pytest

from webapp.config import TestConfig
from webapp.db import get_db, init_db


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


def test_seed_users(app):
    from webapp.seed import seed_db
    with app.app_context():
        seed_db()
        db = get_db()
        users = db.execute("SELECT * FROM users").fetchall()
        assert len(users) == 2
        admin = db.execute("SELECT * FROM users WHERE username='admin'").fetchone()
        assert admin["role"] == "admin"
        assert admin["password_hash"] == "5f4dcc3b5aa765d61d8327deb882cf99"
        operator = db.execute("SELECT * FROM users WHERE username='operator'").fetchone()
        assert operator["role"] == "operator"


def test_seed_telemetry(app):
    from webapp.seed import seed_db
    with app.app_context():
        seed_db()
        db = get_db()
        count = db.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0]
        assert count >= 100


def test_seed_radio_config(app):
    from webapp.seed import seed_db
    with app.app_context():
        seed_db()
        db = get_db()
        configs = db.execute("SELECT * FROM radio_config").fetchall()
        assert len(configs) == 2
        admin_cfg = db.execute("SELECT * FROM radio_config WHERE id=1").fetchone()
        assert admin_cfg["owner"] == "admin"


def test_seed_logs(app):
    from webapp.seed import seed_db
    with app.app_context():
        seed_db()
        db = get_db()
        count = db.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
        assert count >= 10


def test_seed_idempotent(app):
    from webapp.seed import seed_db
    with app.app_context():
        seed_db()
        seed_db()
        db = get_db()
        users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        assert users == 2
