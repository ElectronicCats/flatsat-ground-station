"""SQLite database helpers. Raw sqlite3 — no ORM (deliberate for SQLi vulns)."""

import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'operator'
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
    raw_hex TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS radio_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner TEXT NOT NULL,
    frequency INTEGER NOT NULL DEFAULT 915000000,
    spreading_factor INTEGER NOT NULL DEFAULT 7,
    bandwidth INTEGER NOT NULL DEFAULT 125000,
    tx_power INTEGER NOT NULL DEFAULT 14,
    description TEXT DEFAULT ''
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
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()
