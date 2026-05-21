"""Database seed script. Populates users, telemetry, radio configs, and logs."""

import random
from datetime import datetime, timedelta

from core.constants import RADIO_LABELS
from webapp.auth import _md5
from webapp.db import get_db


def seed_db():
    """Seed the database with CTF data. Each section is independently idempotent."""
    from flask import current_app
    try:
        level = current_app.config.get("CTF_LEVEL", 1)
    except Exception:
        level = 1
        
    db = get_db()
    changed = False

    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        _seed_users(db, level)
        changed = True

    if db.execute("SELECT COUNT(*) FROM secrets").fetchone()[0] == 0:
        _seed_secrets(db, level)
        changed = True

    if db.execute("SELECT COUNT(*) FROM radio_config").fetchone()[0] == 0:
        _seed_radio_config(db, level)
        changed = True

    if db.execute("SELECT COUNT(*) FROM logs").fetchone()[0] == 0:
        _seed_logs(db, level)
        changed = True

    # Backfill: ensure admin has admin_notes populated (migration from older DBs)
    admin_notes = db.execute("SELECT admin_notes FROM users WHERE username = 'admin'").fetchone()
    if admin_notes and ("PWNSAT{" not in (admin_notes[0] or "")):
        db.execute(
            "UPDATE users SET admin_notes = ? WHERE username = 'admin'",
            (f"PWNSAT{{XSS_IN_MISSION_LOGS_LVL{level}}}",),
        )
        changed = True

    admin_cfg = db.execute(
        "SELECT id, notes FROM radio_config WHERE owner = 'admin' AND description LIKE '%CLASSIFIED%'"
    ).fetchone()
    if admin_cfg and ("PWNSAT{" not in (admin_cfg["notes"] or "")):
        db.execute(
            "UPDATE radio_config SET notes = ? WHERE id = ?",
            (f"PWNSAT{{IDOR_ADMIN_CONFIG_LVL{level}}}", admin_cfg["id"]),
        )
        changed = True

    if changed:
        db.commit()


def _seed_users(db, level):
    db.execute(
        "INSERT INTO users (username, password_hash, role, admin_notes) VALUES (?, ?, ?, ?)",
        ("admin", "5f4dcc3b5aa765d61d8327deb882cf99", "admin", f"PWNSAT{{XSS_IN_MISSION_LOGS_LVL{level}}}"),
    )
    db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        ("operator", _md5("operator123"), "operator"),
    )


def _seed_telemetry(db):
    base_time = datetime(2026, 4, 1, 0, 0, 0)
    apids = [0x001, 0x010, 0x011, 0x010, 0x011]
    for i in range(150):
        ts = base_time + timedelta(minutes=i * 10)
        apid = apids[i % len(apids)]
        temp = round(20.0 + random.uniform(-5, 15), 2)
        pressure = round(1013.25 + random.uniform(-5, 5), 2)
        humidity = round(50 + random.uniform(-10, 10), 1)
        ax = round(random.uniform(-50, 50), 1)
        ay = round(random.uniform(-50, 50), 1)
        az = round(random.uniform(950, 1050), 1)
        raw_hex = f"0801C0{i:04X}00{apid:04X}{random.randint(0, 0xFFFF):04X}"
        db.execute(
            "INSERT INTO telemetry "
            "(timestamp, apid, spacecraft_id, temperature, pressure, humidity, "
            "accel_x, accel_y, accel_z, raw_hex) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ts.isoformat(), apid, 0x02, temp, pressure, humidity, ax, ay, az, raw_hex),
        )


def _seed_radio_config(db, level):
    sql = (
        "INSERT INTO radio_config "
        "(owner, frequency, spreading_factor, bandwidth, tx_power, description, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    db.execute(
        sql, ("admin", 436703000, 10, 125000, 22, "TinyGS Norbi downlink — CLASSIFIED", f"PWNSAT{{IDOR_ADMIN_CONFIG_LVL{level}}}")
    )
    db.execute(sql, ("operator", 915000000, 7, 125000, 14, RADIO_LABELS[0], ""))
    db.execute(sql, ("operator", 916000000, 7, 125000, 14, RADIO_LABELS[1], ""))


def _seed_secrets(db, level):
    db.execute(
        "INSERT INTO secrets (name, value, access_level) VALUES (?, ?, ?)",
        ("satellite_master_key", f"PWNSAT{{TELEMETRY_DB_TAMPERED_LVL{level}}}", "classified"),
    )


def _seed_logs(db, level):
    base_time = datetime(2026, 4, 1, 8, 0, 0)
    log_entries = [
        ("INFO", "system", "Ground station initialized"),
        ("INFO", "radio", "Radio 0 connected at 915.000 MHz"),
        ("INFO", "radio", "Radio 1 connected at 436.703 MHz"),
        ("INFO", "auth", "User 'operator' logged in from 192.168.1.100"),
        ("WARN", "telemetry", "Telemetry gap detected: 15 minutes"),
        ("INFO", "telecommand", "TC sent: PING (opcode 0x10)"),
        ("INFO", "telecommand", "TC response: PONG (latency 45ms)"),
        ("ERROR", "radio", "Radio 0: TX timeout after 5000ms"),
        ("INFO", "system", "Database backup completed"),
        ("WARN", "auth", "Failed login attempt for user 'root'"),
        ("INFO", "telemetry", "Received 1247 TM frames today"),
        ("INFO", "system", f"Firmware version: PwnSat2 v{level}.0.1"),
    ]
    for i, (level_str, source, message) in enumerate(log_entries):
        ts = base_time + timedelta(minutes=i * 30)
        db.execute(
            "INSERT INTO logs (timestamp, level, source, message) VALUES (?, ?, ?, ?)",
            (ts.isoformat(), level_str, source, message),
        )
    # Hidden DEBUG flag entry (GS-11)
    db.execute(
        "INSERT INTO logs (timestamp, level, source, message) VALUES (?, ?, ?, ?)",
        ("2026-01-01T00:00:00", "DEBUG", "flag-service", f"PWNSAT{{LOG_INJECTION_SUCCESS_LVL{level}}}"),
    )
