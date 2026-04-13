# GS Flag Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all 12 ground station CTF flags discoverable by participants through natural exploitation.

**Architecture:** Plant flags where each vulnerability naturally finds them — files for filesystem vulns, DB records for data-access vulns, endpoints for access-control vulns. No centralized flag endpoint.

**Tech Stack:** Python 3.11+, Flask 3.0.x, sqlite3, pytest

**Spec:** `docs/superpowers/specs/2026-04-13-gs-flag-delivery-design.md`

---

## File Structure

```
flatsat-ground-station/
├── webapp/
│   ├── db.py                  # Modify: add admin_notes, notes, secrets table
│   ├── seed.py                # Modify: plant flags in DB
│   ├── app.py                 # Modify: 4 new endpoints + DEBUG filter
│   ├── lfi_flag.txt           # Create: GS-04 flag
│   └── radio_flag.txt         # Create: GS-07 flag
├── requirements.txt           # Modify: add GS-10 flag comment
└── tests/
    ├── test_vuln_idor.py      # Modify: add flag assertion
    ├── test_vuln_sqli.py      # Modify: add secrets table test
    └── test_flag_delivery.py  # Create: comprehensive flag delivery tests
```

---

### Task 1: Schema changes — admin_notes, notes, secrets table

**Files:**
- Modify: `webapp/db.py:10-50`

- [ ] **Step 1: Write the failing test**

Create `tests/test_flag_delivery.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_flag_delivery.py::test_schema_has_admin_notes tests/test_flag_delivery.py::test_schema_has_radio_config_notes tests/test_flag_delivery.py::test_schema_has_secrets_table -v`
Expected: FAIL — columns and table don't exist yet

- [ ] **Step 3: Update schema in db.py**

In `webapp/db.py`, replace the `SCHEMA` string (lines 9-50) with:

```python
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

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'INFO',
    source TEXT NOT NULL DEFAULT 'system',
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS secrets (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    value TEXT NOT NULL,
    access_level TEXT DEFAULT 'classified'
);
"""
```

Also add migration logic in `init_db()` after the existing rssi/snr migration:

```python
    # Migrate: add admin_notes column if missing
    user_cols = {row[1] for row in db.execute("PRAGMA table_info(users)").fetchall()}
    if "admin_notes" not in user_cols:
        db.execute("ALTER TABLE users ADD COLUMN admin_notes TEXT DEFAULT ''")
    # Migrate: add notes column to radio_config if missing
    rc_cols = {row[1] for row in db.execute("PRAGMA table_info(radio_config)").fetchall()}
    if "notes" not in rc_cols:
        db.execute("ALTER TABLE radio_config ADD COLUMN notes TEXT DEFAULT ''")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_flag_delivery.py::test_schema_has_admin_notes tests/test_flag_delivery.py::test_schema_has_radio_config_notes tests/test_flag_delivery.py::test_schema_has_secrets_table -v`
Expected: 3 passed

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `python -m pytest tests/ -v`
Expected: All tests pass (163+)

- [ ] **Step 6: Commit**

```bash
git add webapp/db.py tests/test_flag_delivery.py
git commit -m "feat: add admin_notes, radio_config notes, secrets table for CTF flag delivery"
```

---

### Task 2: Seed flags into DB

**Files:**
- Modify: `webapp/seed.py`
- Modify: `tests/test_flag_delivery.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_flag_delivery.py`:

```python
def test_seed_admin_notes_flag(app):
    from webapp.db import get_db

    with app.app_context():
        db = get_db()
        admin = db.execute("SELECT admin_notes FROM users WHERE username = 'admin'").fetchone()
        assert admin["admin_notes"] == "PWNSAT{XSS_IN_MISSION_LOGS}"


def test_seed_admin_radio_config_notes_flag(app):
    from webapp.db import get_db

    with app.app_context():
        db = get_db()
        config = db.execute("SELECT notes FROM radio_config WHERE owner = 'admin'").fetchone()
        assert config["notes"] == "PWNSAT{IDOR_ADMIN_CONFIG}"


def test_seed_secrets_flag(app):
    from webapp.db import get_db

    with app.app_context():
        db = get_db()
        secret = db.execute("SELECT * FROM secrets WHERE name = 'satellite_master_key'").fetchone()
        assert secret["value"] == "PWNSAT{TELEMETRY_DB_TAMPERED}"
        assert secret["access_level"] == "classified"


def test_seed_debug_log_flag(app):
    from webapp.db import get_db

    with app.app_context():
        db = get_db()
        log = db.execute("SELECT * FROM logs WHERE level = 'DEBUG'").fetchone()
        assert log is not None
        assert log["message"] == "PWNSAT{LOG_INJECTION_SUCCESS}"
        assert log["source"] == "flag-service"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_flag_delivery.py::test_seed_admin_notes_flag tests/test_flag_delivery.py::test_seed_admin_radio_config_notes_flag tests/test_flag_delivery.py::test_seed_secrets_flag tests/test_flag_delivery.py::test_seed_debug_log_flag -v`
Expected: FAIL — seeds don't contain flags yet

- [ ] **Step 3: Update seed.py**

In `webapp/seed.py`, modify `_seed_users` to include `admin_notes`:

```python
def _seed_users(db):
    db.execute(
        "INSERT INTO users (username, password_hash, role, admin_notes) VALUES (?, ?, ?, ?)",
        ("admin", "5f4dcc3b5aa765d61d8327deb882cf99", "admin", "PWNSAT{XSS_IN_MISSION_LOGS}"),
    )
    db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        ("operator", _md5("operator123"), "operator"),
    )
```

Modify `_seed_radio_config` to add notes to admin's config:

```python
def _seed_radio_config(db):
    sql = (
        "INSERT INTO radio_config "
        "(owner, frequency, spreading_factor, bandwidth, tx_power, description, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    db.execute(sql, ("admin", 436703000, 10, 125000, 22, "TinyGS Norbi downlink — CLASSIFIED", "PWNSAT{IDOR_ADMIN_CONFIG}"))
    db.execute(sql, ("operator", 915000000, 7, 125000, 14, RADIO_LABELS[0], ""))
    db.execute(sql, ("operator", 916000000, 7, 125000, 14, RADIO_LABELS[1], ""))
```

Add new function `_seed_secrets` and modify `_seed_logs` to include the DEBUG flag entry. Update `seed_db` to call both:

```python
def seed_db():
    """Seed the database with CTF data. Idempotent — skips if users exist."""
    db = get_db()
    existing = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing > 0:
        return

    _seed_users(db)
    _seed_radio_config(db)
    _seed_secrets(db)
    _seed_logs(db)
    db.commit()


def _seed_secrets(db):
    db.execute(
        "INSERT INTO secrets (name, value, access_level) VALUES (?, ?, ?)",
        ("satellite_master_key", "PWNSAT{TELEMETRY_DB_TAMPERED}", "classified"),
    )


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
    # Hidden DEBUG flag entry (GS-11)
    db.execute(
        "INSERT INTO logs (timestamp, level, source, message) VALUES (?, ?, ?, ?)",
        ("2026-01-01T00:00:00", "DEBUG", "flag-service", "PWNSAT{LOG_INJECTION_SUCCESS}"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_flag_delivery.py -v`
Expected: All 7 tests pass

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass. Watch for seed-dependent tests that may need updating.

- [ ] **Step 6: Commit**

```bash
git add webapp/seed.py tests/test_flag_delivery.py
git commit -m "feat: seed CTF flags into DB for GS-02, GS-06, GS-09, GS-11"
```

---

### Task 3: Flag files — lfi_flag.txt, radio_flag.txt, requirements.txt

**Files:**
- Create: `webapp/lfi_flag.txt`
- Create: `webapp/radio_flag.txt`
- Modify: `requirements.txt`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_flag_delivery.py`:

```python
import os


def test_lfi_flag_file_exists():
    flag_path = os.path.join(os.path.dirname(__file__), "..", "webapp", "lfi_flag.txt")
    assert os.path.exists(flag_path)
    with open(flag_path) as f:
        assert f.read().strip() == "PWNSAT{LFI_TRAVERSAL_SUCCESS}"


def test_radio_flag_file_exists():
    flag_path = os.path.join(os.path.dirname(__file__), "..", "webapp", "radio_flag.txt")
    assert os.path.exists(flag_path)
    with open(flag_path) as f:
        assert f.read().strip() == "PWNSAT{CMDI_IN_RADIO_CONFIG}"


def test_supply_chain_flag_in_requirements():
    req_path = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
    with open(req_path) as f:
        content = f.read()
    assert "PWNSAT{SUPPLY_CHAIN_COMPROMISED}" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_flag_delivery.py::test_lfi_flag_file_exists tests/test_flag_delivery.py::test_radio_flag_file_exists tests/test_flag_delivery.py::test_supply_chain_flag_in_requirements -v`
Expected: FAIL — files don't exist yet

- [ ] **Step 3: Create flag files and update requirements.txt**

Create `webapp/lfi_flag.txt`:
```
PWNSAT{LFI_TRAVERSAL_SUCCESS}
```

Create `webapp/radio_flag.txt`:
```
PWNSAT{CMDI_IN_RADIO_CONFIG}
```

Update `requirements.txt` — add the flag comment above the unpinned `requests` line:

```
Flask==3.0.3
Flask-SocketIO==5.3.7
pycryptodome==3.20.0
pyserial==3.5
pyudev
# PWNSAT{SUPPLY_CHAIN_COMPROMISED}
# TODO: pin all dependencies before production deployment
requests
pytest==8.2.2
pytest-flask==1.3.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_flag_delivery.py::test_lfi_flag_file_exists tests/test_flag_delivery.py::test_radio_flag_file_exists tests/test_flag_delivery.py::test_supply_chain_flag_in_requirements -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add webapp/lfi_flag.txt webapp/radio_flag.txt requirements.txt tests/test_flag_delivery.py
git commit -m "feat: add flag files for GS-04 (LFI), GS-07 (CMDi), GS-10 (supply chain)"
```

---

### Task 4: New endpoints — /api/users/me, /api/admin/panel, /api/radio/status, /api/debug/flags

**Files:**
- Modify: `webapp/app.py`
- Modify: `tests/test_flag_delivery.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_flag_delivery.py`:

```python
import base64


def test_gs05_admin_panel_as_admin(admin_client):
    resp = admin_client.get("/api/admin/panel")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["flag"] == "PWNSAT{SESSION_TOKEN_FORGED}"


def test_gs05_admin_panel_as_operator(operator_client):
    resp = operator_client.get("/api/admin/panel")
    assert resp.status_code == 403


def test_gs05_admin_panel_forged_token(app):
    client = app.test_client()
    forged = base64.b64encode(b"admin:admin:0").decode()
    client.set_cookie("session_token", forged)
    resp = client.get("/api/admin/panel")
    assert resp.status_code == 200
    assert resp.get_json()["flag"] == "PWNSAT{SESSION_TOKEN_FORGED}"


def test_gs02_users_me_as_admin(admin_client):
    resp = admin_client.get("/api/users/me")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["username"] == "admin"
    assert data["admin_notes"] == "PWNSAT{XSS_IN_MISSION_LOGS}"


def test_gs02_users_me_as_operator(operator_client):
    resp = operator_client.get("/api/users/me")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["username"] == "operator"
    assert data["admin_notes"] == ""


def test_gs08_radio_status(operator_client):
    resp = operator_client.get("/api/radio/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["bridge_key"] == "PWNSAT{WEB_TO_SPACE_LINK}"


def test_gs12_debug_flags_no_auth(app):
    client = app.test_client()
    resp = client.get("/api/debug/flags")
    assert resp.status_code == 200
    assert resp.get_json()["flag"] == "PWNSAT{API_NO_RATE_LIMIT}"


def test_gs12_debug_flags_listed_in_endpoints(app):
    client = app.test_client()
    resp = client.get("/api/endpoints")
    rules = [r["rule"] for r in resp.get_json()]
    assert "/api/debug/flags" in rules
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_flag_delivery.py::test_gs05_admin_panel_as_admin tests/test_flag_delivery.py::test_gs08_radio_status tests/test_flag_delivery.py::test_gs12_debug_flags_no_auth -v`
Expected: FAIL — endpoints don't exist

- [ ] **Step 3: Add 4 new endpoints to app.py**

Add after the `api_endpoints` route (around line 286) in `webapp/app.py`:

```python
    @app.route("/api/users/me")
    @login_required
    def api_users_me():
        """Returns current user's profile. Flag in admin_notes (GS-02 XSS target)."""
        from webapp.db import get_db

        db = get_db()
        user = db.execute(
            "SELECT id, username, role, admin_notes FROM users WHERE username = ?",
            (g.username,),
        ).fetchone()
        if user is None:
            return {"error": "User not found"}, 404
        return dict(user)

    @app.route("/api/admin/panel")
    @login_required
    def api_admin_panel():
        """Admin-only panel. Flag reward for auth bypass (GS-05)."""
        if g.role != "admin":
            return {"error": "Forbidden"}, 403
        return {
            "message": "Ground Station Admin Panel",
            "flag": "PWNSAT{SESSION_TOKEN_FORGED}",
            "connected_satellites": [],
            "system_status": "operational",
        }

    @app.route("/api/radio/status")
    @login_required
    def api_radio_status():
        """Radio bridge status. Flag for kill chain discovery (GS-08)."""
        gs_state = app.config.get("GS_STATE")
        connected = gs_state is not None and gs_state.mode.name != "IDLE"
        return {
            "connected": connected,
            "mode": gs_state.mode.name if gs_state else "IDLE",
            "bridge_key": "PWNSAT{WEB_TO_SPACE_LINK}",
        }

    @app.route("/api/debug/flags")
    def api_debug_flags():
        """Unprotected debug endpoint. Flag for API enumeration (GS-12)."""
        return {
            "flag": "PWNSAT{API_NO_RATE_LIMIT}",
            "hint": "This endpoint should not be public",
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_flag_delivery.py::test_gs05_admin_panel_as_admin tests/test_flag_delivery.py::test_gs05_admin_panel_as_operator tests/test_flag_delivery.py::test_gs05_admin_panel_forged_token tests/test_flag_delivery.py::test_gs02_users_me_as_admin tests/test_flag_delivery.py::test_gs02_users_me_as_operator tests/test_flag_delivery.py::test_gs08_radio_status tests/test_flag_delivery.py::test_gs12_debug_flags_no_auth tests/test_flag_delivery.py::test_gs12_debug_flags_listed_in_endpoints -v`
Expected: 8 passed

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add webapp/app.py tests/test_flag_delivery.py
git commit -m "feat: add endpoints for GS-02, GS-05, GS-08, GS-12 flag delivery"
```

---

### Task 5: DEBUG filter on logs page for GS-11

**Files:**
- Modify: `webapp/app.py:117-124`
- Modify: `tests/test_flag_delivery.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_flag_delivery.py`:

```python
def test_gs11_logs_page_hides_debug(operator_client):
    resp = operator_client.get("/logs")
    assert resp.status_code == 200
    assert b"PWNSAT{LOG_INJECTION_SUCCESS}" not in resp.data
    assert b"flag-service" not in resp.data


def test_gs11_debug_log_exists_in_db(app):
    from webapp.db import get_db

    with app.app_context():
        db = get_db()
        row = db.execute("SELECT * FROM logs WHERE level = 'DEBUG'").fetchone()
        assert row is not None
        assert row["message"] == "PWNSAT{LOG_INJECTION_SUCCESS}"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_flag_delivery.py::test_gs11_logs_page_hides_debug -v`
Expected: FAIL — logs page currently shows ALL entries including DEBUG

- [ ] **Step 3: Add DEBUG filter to logs page query**

In `webapp/app.py`, modify the `logs_page` route (around line 117-124):

```python
    @app.route("/logs")
    @login_required
    def logs_page():
        from webapp.db import get_db

        db = get_db()
        # Filter out DEBUG entries (GS-11: hidden flag only reachable via injection/SQLi)
        logs = db.execute("SELECT * FROM logs WHERE level != 'DEBUG' ORDER BY id DESC").fetchall()
        return render_template("logs.html", logs=logs)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_flag_delivery.py::test_gs11_logs_page_hides_debug tests/test_flag_delivery.py::test_gs11_debug_log_exists_in_db -v`
Expected: 2 passed

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add webapp/app.py tests/test_flag_delivery.py
git commit -m "feat: filter DEBUG logs from /logs page for GS-11 flag hiding"
```

---

### Task 6: Exploitation tests — verify each flag is discoverable

**Files:**
- Modify: `tests/test_flag_delivery.py`
- Modify: `tests/test_vuln_idor.py`

- [ ] **Step 1: Write exploitation tests**

Add to `tests/test_flag_delivery.py`:

```python
def test_gs04_lfi_flag_via_traversal(auth_client):
    """GS-04: LFI reads lfi_flag.txt via path traversal."""
    resp = auth_client.get("/api/logs?file=../lfi_flag.txt")
    assert resp.status_code == 200
    assert "PWNSAT{LFI_TRAVERSAL_SUCCESS}" in resp.get_json()["content"]


def test_gs06_idor_flag_via_admin_config(operator_client):
    """GS-06: Operator accesses admin's radio config and finds flag."""
    resp = operator_client.get("/api/config/radio/1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["notes"] == "PWNSAT{IDOR_ADMIN_CONFIG}"


def test_gs09_secrets_via_sqli(operator_client):
    """GS-09: SQLi UNION SELECT on secrets table reveals flag."""
    payload = "' UNION SELECT name,value,access_level,1,2,3,4,5,6,7,8,9,10 FROM secrets--"
    resp = operator_client.get(f"/api/telemetry?search={payload}&limit=100")
    assert resp.status_code == 200
    data = resp.get_json()
    found = any("PWNSAT{TELEMETRY_DB_TAMPERED}" in str(row.values()) for row in data)
    assert found, "SQLi UNION on secrets should reveal GS-09 flag"


def test_gs11_debug_log_via_sqli(operator_client):
    """GS-11: SQLi UNION SELECT on logs table reveals hidden DEBUG flag."""
    payload = "' UNION SELECT id,timestamp,level,source,message,6,7,8,9,10,11,12,13 FROM logs WHERE level='DEBUG'--"
    resp = operator_client.get(f"/api/telemetry?search={payload}&limit=100")
    assert resp.status_code == 200
    data = resp.get_json()
    found = any("PWNSAT{LOG_INJECTION_SUCCESS}" in str(row.values()) for row in data)
    assert found, "SQLi UNION on logs should reveal GS-11 DEBUG flag"
```

Add `auth_client` fixture if not already present (it uses operator login, matching the existing pattern in other test files):

```python
@pytest.fixture
def auth_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client
```

- [ ] **Step 2: Update test_vuln_idor.py to verify flag**

In `tests/test_vuln_idor.py`, update `test_idor_access_admin_config`:

```python
def test_idor_access_admin_config(operator_client):
    resp = operator_client.get("/api/config/radio/1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["owner"] == "admin"
    assert "CLASSIFIED" in data["description"]
    assert data["notes"] == "PWNSAT{IDOR_ADMIN_CONFIG}"
```

- [ ] **Step 3: Run all exploitation tests**

Run: `python -m pytest tests/test_flag_delivery.py -v`
Expected: All tests pass

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass (should be 163 + ~20 new = ~183 tests)

- [ ] **Step 5: Commit**

```bash
git add tests/test_flag_delivery.py tests/test_vuln_idor.py
git commit -m "test: add exploitation tests verifying all 12 GS flags are discoverable"
```

---

### Task 7: Final verification and spec commit

**Files:**
- Modify: `docs/superpowers/specs/2026-04-13-gs-flag-delivery-design.md` (already written)

- [ ] **Step 1: Run full test suite one final time**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All pass, 0 failures

- [ ] **Step 2: Verify flag count**

Run: `python -m pytest tests/test_flag_delivery.py -v --tb=short`
Expected: ~20 tests covering all 12 flags

- [ ] **Step 3: Commit spec and plan**

```bash
git add docs/superpowers/specs/2026-04-13-gs-flag-delivery-design.md docs/superpowers/plans/2026-04-13-gs-flag-delivery-plan.md
git commit -m "docs: add GS flag delivery design spec and implementation plan"
```
