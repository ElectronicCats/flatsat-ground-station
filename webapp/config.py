"""Flask configuration. Secrets are deliberately hardcoded (CTF target)."""


import os

class Config:
    SECRET_KEY = "pwnsat_ground_station_2026"
    DATABASE = "db/telemetry.db"
    DEBUG = True
    # CTF Difficulty Level: 1 (Easy), 2 (Medium), 3 (Hard)
    CTF_LEVEL = int(os.environ.get("FLATSAT_LEVEL", 1))


class TestConfig(Config):
    TESTING = True
    DATABASE = ":memory:"
    CTF_LEVEL = 1 # Always easy for tests unless overridden
