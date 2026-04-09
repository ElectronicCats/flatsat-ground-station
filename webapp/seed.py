"""Database seed script. Populates users, telemetry, radio configs, and logs."""

import hashlib
import random
from datetime import datetime, timedelta

from webapp.db import get_db


def _md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def seed_db():
    """Seed the database with CTF data. Idempotent — skips if users exist."""
    db = get_db()
    existing = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing > 0:
        return

    _seed_users(db)
    _seed_telemetry(db)
    _seed_radio_config(db)
    _seed_logs(db)
    db.commit()


def _seed_users(db):
    db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        ("admin", "5f4dcc3b5aa765d61d8327deb882cf99", "admin"),
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


def _seed_radio_config(db):
    sql = (
        "INSERT INTO radio_config "
        "(owner, frequency, spreading_factor, bandwidth, tx_power, description) "
        "VALUES (?, ?, ?, ?, ?, ?)"
    )
    db.execute(sql, ("admin", 436703000, 10, 125000, 22, "TinyGS Norbi downlink — CLASSIFIED"))
    db.execute(sql, ("operator", 915000000, 7, 125000, 14, "Default ISM 915 MHz"))


def _seed_logs(db):
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
        ("INFO", "system", "Firmware version: PwnSat2 v2.0.1"),
    ]
    for i, (level, source, message) in enumerate(log_entries):
        ts = base_time + timedelta(minutes=i * 30)
        db.execute(
            "INSERT INTO logs (timestamp, level, source, message) VALUES (?, ?, ?, ?)",
            (ts.isoformat(), level, source, message),
        )
