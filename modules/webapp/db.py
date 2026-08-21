"""SQLite database helpers. Raw sqlite3 — no ORM (deliberate for SQLi vulns)."""

import sqlite3

from flask import current_app, g

from modules.core.constants import RADIO_LABELS

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'operator',
    admin_notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    apid INTEGER NOT NULL,
    spacecraft_id INTEGER NOT NULL DEFAULT 2,
    temperature REAL,
    pressure REAL,
    humidity REAL,
    accel_x REAL,
    accel_y REAL,
    accel_z REAL,
    raw_hex TEXT NOT NULL,
    rssi INTEGER,
    snr INTEGER
);

CREATE TABLE IF NOT EXISTS radio_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner TEXT NOT NULL,
    frequency INTEGER NOT NULL DEFAULT 915000000,
    spreading_factor INTEGER NOT NULL DEFAULT 7,
    bandwidth INTEGER NOT NULL DEFAULT 125000,
    tx_power INTEGER NOT NULL DEFAULT 14,
    description TEXT DEFAULT '',
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS secrets (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    value TEXT NOT NULL,
    access_level TEXT DEFAULT 'classified'
);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'INFO',
    source TEXT NOT NULL DEFAULT 'system',
    message TEXT NOT NULL
);
"""


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=10.0)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    # Migrate: add rssi/snr columns if missing (existing DBs before schema change)
    cols = {row[1] for row in db.execute("PRAGMA table_info(telemetry)").fetchall()}
    if "rssi" not in cols:
        db.execute("ALTER TABLE telemetry ADD COLUMN rssi INTEGER")
    if "snr" not in cols:
        db.execute("ALTER TABLE telemetry ADD COLUMN snr INTEGER")
    # Migrate: add admin_notes column to users if missing
    user_cols = {row[1] for row in db.execute("PRAGMA table_info(users)").fetchall()}
    if "admin_notes" not in user_cols:
        db.execute("ALTER TABLE users ADD COLUMN admin_notes TEXT DEFAULT ''")
    # Migrate: add notes column to radio_config if missing
    rc_cols = {row[1] for row in db.execute("PRAGMA table_info(radio_config)").fetchall()}
    if "notes" not in rc_cols:
        db.execute("ALTER TABLE radio_config ADD COLUMN notes TEXT DEFAULT ''")
    # Migrate legacy radio_config descriptions to Radio 0/Radio 1
    _migrate_radio_config_descriptions(db)
    db.commit()


def _migrate_radio_config_descriptions(db):
    """Rename legacy radio_config descriptions so the config page can find them.

    Old seeds used 'Default ISM 915 MHz' and the first config page revision
    used 'Manual'.  Both need to map to 'Radio 0' (or 'Radio 1' if a second
    legacy row exists for the same owner).
    """
    placeholders = ",".join("?" for _ in RADIO_LABELS)
    legacy = db.execute(
        "SELECT id, owner, description FROM radio_config "  # noqa: S608
        f"WHERE description NOT IN ({placeholders}) "
        "  AND description NOT LIKE '%CLASSIFIED%'",
        RADIO_LABELS,
    ).fetchall()
    # Group by owner so each owner's legacy rows get assigned R0 then R1
    per_owner: dict[str, list[int]] = {}
    for row in legacy:
        per_owner.setdefault(row["owner"], []).append(row["id"])
    for owner, ids in per_owner.items():
        # Check which slots are already taken
        existing = {
            r["description"]
            for r in db.execute(
                f"SELECT description FROM radio_config WHERE owner = ? AND description IN ({placeholders})",  # noqa: S608
                (owner, *RADIO_LABELS),
            ).fetchall()
        }
        slots = [s for s in RADIO_LABELS if s not in existing]
        for row_id in ids:
            if slots:
                db.execute(
                    "UPDATE radio_config SET description = ? WHERE id = ?",
                    (slots.pop(0), row_id),
                )
            else:
                # No free slot — delete the orphan
                db.execute("DELETE FROM radio_config WHERE id = ?", (row_id,))
