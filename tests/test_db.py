import os
import sqlite3
import tempfile

import pytest

from webapp.config import TestConfig
from webapp.db import _migrate_radio_config_descriptions, get_db, init_db


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
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {t["name"] for t in tables}
        assert "users" in table_names
        assert "telemetry" in table_names
        assert "radio_config" in table_names
        assert "logs" in table_names


def test_migrate_legacy_descriptions(app):
    """Legacy descriptions like 'Default ISM 915 MHz' and 'Manual' get renamed."""
    with app.app_context():
        db = get_db()
        # Insert legacy rows
        db.execute(
            "INSERT INTO radio_config (owner, frequency, spreading_factor, bandwidth, tx_power, description) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("testuser", 915000000, 7, 125000, 14, "Default ISM 915 MHz"),
        )
        db.execute(
            "INSERT INTO radio_config (owner, frequency, spreading_factor, bandwidth, tx_power, description) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("testuser", 916000000, 7, 125000, 14, "Manual"),
        )
        db.commit()
        _migrate_radio_config_descriptions(db)
        db.commit()
        rows = db.execute(
            "SELECT description FROM radio_config WHERE owner = ? ORDER BY id",
            ("testuser",),
        ).fetchall()
        descs = [r["description"] for r in rows]
        assert "Radio 0" in descs
        assert "Radio 1" in descs
        assert "Default ISM 915 MHz" not in descs
        assert "Manual" not in descs


def test_migrate_preserves_classified(app):
    """CLASSIFIED configs (admin CTF data) are not touched by migration."""
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO radio_config (owner, frequency, spreading_factor, bandwidth, tx_power, description) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("admin", 436703000, 10, 125000, 22, "TinyGS Norbi downlink — CLASSIFIED"),
        )
        db.commit()
        _migrate_radio_config_descriptions(db)
        db.commit()
        row = db.execute("SELECT description FROM radio_config WHERE owner = 'admin'").fetchone()
        assert "CLASSIFIED" in row["description"]


def test_migrate_skips_already_correct(app):
    """Rows already named Radio 0/Radio 1 are not duplicated."""
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO radio_config (owner, frequency, spreading_factor, bandwidth, tx_power, description) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("testuser", 915000000, 7, 125000, 14, "Radio 0"),
        )
        db.execute(
            "INSERT INTO radio_config (owner, frequency, spreading_factor, bandwidth, tx_power, description) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("testuser", 916000000, 7, 125000, 14, "Radio 1"),
        )
        db.commit()
        _migrate_radio_config_descriptions(db)
        db.commit()
        count = db.execute("SELECT COUNT(*) FROM radio_config WHERE owner = 'testuser'").fetchone()[0]
        assert count == 2


def test_migrate_orphan_deleted(app):
    """Third legacy row with no free slot gets deleted."""
    with app.app_context():
        db = get_db()
        for desc in ("Radio 0", "Radio 1", "Manual"):
            db.execute(
                "INSERT INTO radio_config (owner, frequency, spreading_factor, bandwidth, tx_power, description) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("testuser", 915000000, 7, 125000, 14, desc),
            )
        db.commit()
        _migrate_radio_config_descriptions(db)
        db.commit()
        count = db.execute("SELECT COUNT(*) FROM radio_config WHERE owner = 'testuser'").fetchone()[0]
        assert count == 2
        descs = [
            r["description"]
            for r in db.execute("SELECT description FROM radio_config WHERE owner = 'testuser'").fetchall()
        ]
        assert "Manual" not in descs
