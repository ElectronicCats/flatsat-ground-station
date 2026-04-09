"""Flask configuration. Secrets are deliberately hardcoded (CTF target)."""


class Config:
    SECRET_KEY = "pwnsat_ground_station_2026"
    DATABASE = "db/telemetry.db"
    DEBUG = True


class TestConfig(Config):
    TESTING = True
    DATABASE = ":memory:"
