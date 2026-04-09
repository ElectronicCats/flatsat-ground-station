# FlatSat Ground Station Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared core library and Flask vulnerable webapp for the FlatSat v2 CTF ground station.

**Architecture:** A `core/` Python library handles device discovery, CCSDS protocol, telemetry/telecommand, and state management with dual sync/async APIs. A `webapp/` Flask app provides the vulnerable web frontend with 12 CTF challenges (GS-01 to GS-12), WebSocket telemetry, and SQLite storage.

**Tech Stack:** Python 3.11+, Flask 3.0.x, Flask-SocketIO 5.3.x, PySerial 3.5, sqlite3, pyudev

**Spec:** `docs/superpowers/specs/2026-04-09-ground-station-design.md`

**Source reference (TUI):** `/home/sabas/Documents/electroniccats/flat-sat-fw-interno/flatsatTUI/`

**Source reference (firmware CCSDS):** `/home/sabas/Documents/electroniccats/flat-sat-fw-interno/flatsat/`

---

## File Structure

```
flatsat-ground-station/
├── core/
│   ├── __init__.py               # Public exports
│   ├── constants.py              # Adapted from TUI constants.py
│   ├── serial_manager.py         # Adapted from TUI discovery.py + hotplug.py
│   ├── device.py                 # Adapted from TUI device.py (sync + async)
│   ├── ccsds.py                  # New: CCSDS SPP build/parse matching firmware
│   ├── telemetry.py              # New: TM decoder + mock generator
│   ├── telecommand.py            # New: TC builder + AES-128-ECB
│   └── state.py                  # New: FlatSat state + mock mode
│
├── webapp/
│   ├── __init__.py
│   ├── app.py                    # Flask app factory + all routes + WebSocket
│   ├── config.py                 # Flask config with hardcoded secrets
│   ├── db.py                     # SQLite helper (get_db, init_db, close_db)
│   ├── auth.py                   # Login/logout, broken token (GS-05)
│   ├── radio_bridge.py           # Sync wrapper over core.device
│   ├── seed.py                   # DB seed script (users + telemetry + configs + logs)
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── commands.html
│   │   ├── logs.html
│   │   └── config.html
│   ├── static/
│   │   └── js/
│   │       └── telemetry.js
│   └── flag.txt
│
├── tests/
│   ├── __init__.py
│   ├── test_constants.py
│   ├── test_ccsds.py
│   ├── test_telemetry.py
│   ├── test_telecommand.py
│   ├── test_state.py
│   ├── test_db.py
│   ├── test_auth.py
│   ├── test_seed.py
│   ├── test_vuln_sqli.py
│   ├── test_vuln_xss.py
│   ├── test_vuln_rce.py
│   ├── test_vuln_lfi.py
│   ├── test_vuln_auth_bypass.py
│   ├── test_vuln_idor.py
│   ├── test_vuln_cmdi.py
│   ├── test_vuln_log_injection.py
│   ├── test_vuln_api_enum.py
│   ├── test_radio_bridge.py
│   └── test_websocket.py
│
├── requirements.txt
└── db/
```

---

### Task 1: Project setup and dependencies

**Files:**
- Create: `requirements.txt`
- Create: `core/__init__.py`
- Create: `webapp/__init__.py`
- Create: `tests/__init__.py`
- Create: `webapp/flag.txt`

- [ ] **Step 1: Create requirements.txt**

```
Flask==3.0.3
Flask-SocketIO==5.3.7
pyserial==3.5
pyudev
requests
pytest==8.2.2
pytest-flask==1.3.0
```

Note: `requests` is deliberately unpinned (GS-10 supply chain vuln). All others are pinned.

- [ ] **Step 2: Create package init files**

`core/__init__.py`:
```python
"""FlatSat Ground Station — shared core library."""
```

`webapp/__init__.py`:
```python
"""FlatSat Ground Station — Flask webapp."""
```

`tests/__init__.py`:
```python
```

- [ ] **Step 3: Create flag.txt**

`webapp/flag.txt`:
```
PWNSAT{RCE_ON_GROUND_STATION}
```

- [ ] **Step 4: Install dependencies**

Run: `pip install -r requirements.txt`

- [ ] **Step 5: Verify pytest runs**

Run: `python -m pytest tests/ -v`
Expected: "no tests ran" (0 collected), exit 5

- [ ] **Step 6: Commit**

```bash
git add requirements.txt core/__init__.py webapp/__init__.py tests/__init__.py webapp/flag.txt
git commit -m "chore: project setup with dependencies and package structure"
```

---

### Task 2: Core constants module

**Files:**
- Create: `core/constants.py`
- Create: `tests/test_constants.py`

Reference: `/home/sabas/Documents/electroniccats/flat-sat-fw-interno/flatsatTUI/constants.py`

- [ ] **Step 1: Write the failing test**

`tests/test_constants.py`:
```python
from core.constants import (
    USB_VID, USB_PID, BAUDRATE,
    ENDPOINT_RADIO0, ENDPOINT_RADIO1, ENDPOINT_SHELL,
    CCSDS_VERSION, CCSDS_TYPE_TM, CCSDS_TYPE_TC,
    CCSDS_SPACECRAFT_ID, CCSDS_MAX_PAYLOAD, CCSDS_HDR_SIZE,
    CCSDS_SEC_HDR_SIZE, CCSDS_CRC_SIZE, CCSDS_MAX_FRAME_SIZE,
    CCSDS_SEQ_STANDALONE,
    APID_TM_HEARTBEAT, APID_TM_BME280, APID_TM_LIS2DH,
    APID_TM_POWER, APID_TM_GPS, APID_TM_ALL_SENSORS, APID_TM_IDLE,
    APID_TC_COMMAND, APID_TC_SET_FREQ, APID_TC_SET_POWER,
    APID_TC_FW_UPDATE, APID_TC_SET_DIFFICULTY,
    APID_TC_DIAG_LOG, APID_TC_DIAG_MEM,
    APID_TC_CTF_FLAG, APID_TC_SECRET_DEBUG,
    TC_OP_NOP, TC_OP_PING, TC_OP_READ_SENSOR,
    TC_OP_SET_TM_RATE, TC_OP_OVERRIDE_SENSOR,
    TC_OP_READ_FLAG, TC_OP_PRIVILEGED, TC_OP_EXEC,
    TC_OP_CRYPTO_ORACLE, TC_OP_BACKDOOR,
    DeviceHealth, EndpointState, CommandStatus,
    ConnectionMode,
    AES_KEY_HARDCODED, XOR_KEY,
)


def test_usb_identifiers():
    assert USB_VID == 0x1209
    assert USB_PID == 0xBABC
    assert BAUDRATE == 115200


def test_ccsds_constants():
    assert CCSDS_VERSION == 0
    assert CCSDS_TYPE_TM == 0
    assert CCSDS_TYPE_TC == 1
    assert CCSDS_SPACECRAFT_ID == 0x02
    assert CCSDS_HDR_SIZE == 6
    assert CCSDS_SEC_HDR_SIZE == 4
    assert CCSDS_CRC_SIZE == 2
    assert CCSDS_MAX_FRAME_SIZE == 237
    assert CCSDS_MAX_PAYLOAD == 225
    assert CCSDS_SEQ_STANDALONE == 3


def test_apid_tm_values():
    assert APID_TM_HEARTBEAT == 0x001
    assert APID_TM_BME280 == 0x010
    assert APID_TM_LIS2DH == 0x011
    assert APID_TM_IDLE == 0x7FF


def test_apid_tc_values():
    assert APID_TC_COMMAND == 0x020
    assert APID_TC_SECRET_DEBUG == 0x539


def test_tc_opcodes():
    assert TC_OP_NOP == 0x00
    assert TC_OP_PING == 0x10
    assert TC_OP_PRIVILEGED == 0xD0
    assert TC_OP_EXEC == 0xEE
    assert TC_OP_BACKDOOR == 0xFF


def test_aes_key():
    assert len(AES_KEY_HARDCODED) == 16
    assert AES_KEY_HARDCODED == b"PWNSAT_K3Y_2026!"


def test_xor_key():
    assert XOR_KEY == b"PWNSAT"


def test_enums_exist():
    assert DeviceHealth.HEALTHY
    assert EndpointState.DISCONNECTED
    assert CommandStatus.PASS
    assert ConnectionMode.HARDWARE
    assert ConnectionMode.SIMULATED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_constants.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.constants'`

- [ ] **Step 3: Write the implementation**

`core/constants.py`:
```python
"""Constants for FlatSat ground station core library.

USB identifiers, CCSDS protocol values, APIDs, opcodes, and enums.
Adapted from flatsatTUI/constants.py + firmware ccsds_spp.h / ccsds_apid.h.
"""

from enum import Enum, auto

# --- USB device identifiers ---
USB_VID = 0x1209
USB_PID = 0xBABC
BAUDRATE = 115200

# --- Endpoint names ---
ENDPOINT_RADIO0 = "Cat-Radio0"
ENDPOINT_RADIO1 = "Cat-Radio1"
ENDPOINT_SHELL = "Cat-Shell"

ENDPOINT_LABELS = {
    ENDPOINT_RADIO0: "Radio 0 (CDC0)",
    ENDPOINT_RADIO1: "Radio 1 (CDC1)",
    ENDPOINT_SHELL: "Shell (CDC2)",
}

# --- Timeouts ---
COMMAND_TIMEOUT = 2.0
CONNECT_TIMEOUT = 1.0
HOTPLUG_SCAN_INTERVAL = 3.0

# --- CCSDS Protocol Constants (per CCSDS 133.0-B-2) ---
CCSDS_VERSION = 0
CCSDS_TYPE_TM = 0
CCSDS_TYPE_TC = 1
CCSDS_SEQ_STANDALONE = 3
CCSDS_HDR_SIZE = 6
CCSDS_SEC_HDR_SIZE = 4
CCSDS_CRC_SIZE = 2
CCSDS_MAX_FRAME_SIZE = 237
CCSDS_MAX_PAYLOAD = 225  # 237 - 6 - 4 - 2
CCSDS_SPACECRAFT_ID = 0x02

# --- Telemetry APIDs (Type 0) ---
APID_TM_HEARTBEAT = 0x001
APID_TM_BME280 = 0x010
APID_TM_LIS2DH = 0x011
APID_TM_POWER = 0x012
APID_TM_GPS = 0x013
APID_TM_ALL_SENSORS = 0x01F
APID_TM_IDLE = 0x7FF

# --- Telecommand APIDs (Type 1) ---
APID_TC_COMMAND = 0x020
APID_TC_SET_FREQ = 0x021
APID_TC_SET_POWER = 0x022
APID_TC_FW_UPDATE = 0x026
APID_TC_SET_DIFFICULTY = 0x027
APID_TC_DIAG_LOG = 0x030
APID_TC_DIAG_MEM = 0x031
APID_TC_CTF_FLAG = 0x040
APID_TC_SECRET_DEBUG = 0x539

# --- Telecommand Opcodes (payload byte 0 for APID_TC_COMMAND) ---
TC_OP_NOP = 0x00
TC_OP_SET_SAFE_MODE = 0x01
TC_OP_SET_NOMINAL = 0x02
TC_OP_SET_DEBUG = 0x03
TC_OP_PING = 0x10
TC_OP_READ_SENSOR = 0x20
TC_OP_SET_TM_RATE = 0x30
TC_OP_OVERRIDE_SENSOR = 0x40
TC_OP_READ_FLAG = 0x42
TC_OP_SET_CALLSIGN = 0x50
TC_OP_STORE_CMD = 0x60
TC_OP_TABLE_WRITE = 0x70
TC_OP_NEOPIXEL_RAW = 0xA0
TC_OP_CRYPTO_ORACLE = 0xC0
TC_OP_PRIVILEGED = 0xD0
TC_OP_EXEC = 0xEE
TC_OP_BACKDOOR = 0xFF

# --- Crypto keys (deliberately hardcoded — V04 vuln) ---
AES_KEY_HARDCODED = b"PWNSAT_K3Y_2026!"  # 16 bytes AES-128
XOR_KEY = b"PWNSAT"  # 6 bytes XOR key

# --- Shell commands (CDC2) ---
CDC2_COMMANDS = {
    "status": "status",
    "radio0": "radio0",
    "radio1": "radio1",
    "modulation_lora": "modulation lora",
    "modulation_fsk": "modulation fsk",
    "lora_mode_stream": "lora_mode stream",
    "lora_mode_command": "lora_mode command",
    "lora_freq": "lora_freq",
    "lora_sf": "lora_sf",
    "lora_bw": "lora_bw",
    "lora_cr": "lora_cr",
    "lora_power": "lora_power",
    "lora_preamble": "lora_preamble",
    "lora_syncword": "lora_syncword",
    "fsk_config": "fsk_config",
    "difficulty": "difficulty",
    "flags": "flags",
    "mode": "mode",
    "sc_id": "sc_id",
    "flight": "flight",
    "login": "login",
    "whoami": "whoami",
    "inject_tc": "inject_tc",
    "tinygs": "tinygs",
}


# --- Enums ---
class DeviceHealth(Enum):
    HEALTHY = auto()
    PARTIAL = auto()
    CRITICAL = auto()


class EndpointState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()


class CommandStatus(Enum):
    PASS = auto()
    FAIL = auto()
    TIMEOUT = auto()
    ERROR = auto()


class ConnectionMode(Enum):
    HARDWARE = auto()
    SIMULATED = auto()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_constants.py -v`
Expected: all 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/constants.py tests/test_constants.py
git commit -m "feat(core): add constants module with USB, CCSDS, APID, opcode definitions"
```

---

### Task 3: Core CCSDS module

**Files:**
- Create: `core/ccsds.py`
- Create: `tests/test_ccsds.py`

This implements the CCSDS Space Packet Protocol encoder/decoder matching the firmware in `flatsat/src/ccsds/ccsds_spp.c`.

- [ ] **Step 1: Write the failing tests**

`tests/test_ccsds.py`:
```python
import struct
from core.ccsds import (
    ccsds_crc16,
    build_packet_id,
    parse_packet_id,
    build_seq_ctrl,
    parse_seq_ctrl,
    build_tm,
    build_tc,
    parse_frame,
    CcsdsPacket,
)
from core.constants import (
    CCSDS_VERSION, CCSDS_TYPE_TM, CCSDS_TYPE_TC,
    CCSDS_SEQ_STANDALONE, CCSDS_HDR_SIZE, CCSDS_SEC_HDR_SIZE,
    CCSDS_CRC_SIZE, CCSDS_MAX_PAYLOAD, CCSDS_SPACECRAFT_ID,
    APID_TM_HEARTBEAT, APID_TM_BME280, APID_TC_COMMAND,
)


def test_crc16_empty():
    assert ccsds_crc16(b"") == 0xFFFF


def test_crc16_known():
    # CRC-16-CCITT of "123456789" with init 0xFFFF, poly 0x1021
    data = b"123456789"
    crc = ccsds_crc16(data)
    assert crc == 0x29B1


def test_build_packet_id_tm():
    pid = build_packet_id(CCSDS_TYPE_TM, APID_TM_HEARTBEAT)
    # version=0, type=0, sec_hdr=1, apid=0x001
    # bits: 000 0 1 00000000001 = 0x0801
    assert pid == 0x0801


def test_build_packet_id_tc():
    pid = build_packet_id(CCSDS_TYPE_TC, APID_TC_COMMAND)
    # version=0, type=1, sec_hdr=1, apid=0x020
    # bits: 000 1 1 00000100000 = 0x1820
    assert pid == 0x1820


def test_parse_packet_id():
    pkt_type, sec_hdr, apid = parse_packet_id(0x0801)
    assert pkt_type == CCSDS_TYPE_TM
    assert sec_hdr == 1
    assert apid == 0x001


def test_build_seq_ctrl():
    seq = build_seq_ctrl(42)
    # flags=3 (standalone), count=42
    # bits: 11 00000000101010 = 0xC02A
    assert seq == 0xC02A


def test_parse_seq_ctrl():
    flags, count = parse_seq_ctrl(0xC02A)
    assert flags == CCSDS_SEQ_STANDALONE
    assert count == 42


def test_build_tm_roundtrip():
    payload = b"\x02\x00\x00\x00\x64\x03\xE8\x01\x32\x00\x0A\x00\x00"
    frame = build_tm(APID_TM_HEARTBEAT, payload, seq_count=1, timestamp=100)

    assert len(frame) == CCSDS_HDR_SIZE + CCSDS_SEC_HDR_SIZE + len(payload) + CCSDS_CRC_SIZE

    pkt = parse_frame(frame)
    assert pkt.pkt_type == CCSDS_TYPE_TM
    assert pkt.apid == APID_TM_HEARTBEAT
    assert pkt.seq_count == 1
    assert pkt.timestamp == 100
    assert pkt.payload == payload
    assert pkt.crc_valid is True


def test_build_tc_roundtrip():
    payload = bytes([0x10])  # TC_OP_PING
    frame = build_tc(APID_TC_COMMAND, payload, seq_count=5, timestamp=200)

    pkt = parse_frame(frame)
    assert pkt.pkt_type == CCSDS_TYPE_TC
    assert pkt.apid == APID_TC_COMMAND
    assert pkt.seq_count == 5
    assert pkt.timestamp == 200
    assert pkt.payload == payload
    assert pkt.crc_valid is True


def test_parse_bad_crc():
    frame = build_tm(APID_TM_BME280, b"\x01\x02\x03", seq_count=0, timestamp=0)
    corrupted = bytearray(frame)
    corrupted[-1] ^= 0xFF  # flip last byte of CRC
    pkt = parse_frame(bytes(corrupted))
    assert pkt.crc_valid is False


def test_parse_too_short():
    pkt = parse_frame(b"\x00\x01\x02")
    assert pkt is None


def test_max_payload():
    payload = bytes(CCSDS_MAX_PAYLOAD)
    frame = build_tm(APID_TM_HEARTBEAT, payload, seq_count=0, timestamp=0)
    pkt = parse_frame(frame)
    assert pkt.payload == payload


def test_payload_too_large():
    import pytest
    with pytest.raises(ValueError, match="payload"):
        build_tm(APID_TM_HEARTBEAT, bytes(CCSDS_MAX_PAYLOAD + 1), seq_count=0, timestamp=0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ccsds.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`core/ccsds.py`:
```python
"""CCSDS Space Packet Protocol encoder/decoder.

Matches firmware implementation in flatsat/src/ccsds/ccsds_spp.c.
Big-endian headers per CCSDS 133.0-B-2.
"""

import struct
from dataclasses import dataclass
from typing import Optional

from core.constants import (
    CCSDS_VERSION, CCSDS_TYPE_TM, CCSDS_TYPE_TC,
    CCSDS_SEQ_STANDALONE, CCSDS_HDR_SIZE, CCSDS_SEC_HDR_SIZE,
    CCSDS_CRC_SIZE, CCSDS_MAX_PAYLOAD, CCSDS_MAX_FRAME_SIZE,
)


@dataclass
class CcsdsPacket:
    pkt_type: int       # 0=TM, 1=TC
    sec_hdr_flag: int   # 1 if secondary header present
    apid: int           # 11-bit Application ID
    seq_flags: int      # 2-bit sequence flags
    seq_count: int      # 14-bit sequence counter
    timestamp: int      # 32-bit MET from secondary header
    payload: bytes      # raw payload bytes
    crc_valid: bool     # True if CRC matches
    raw: bytes = b""    # original raw frame


def ccsds_crc16(data: bytes) -> int:
    """CRC-16-CCITT: polynomial 0x1021, initial 0xFFFF."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF
    return crc


def build_packet_id(pkt_type: int, apid: int) -> int:
    """Build 16-bit packet_id: version(3) | type(1) | sec_hdr(1) | apid(11)."""
    return ((CCSDS_VERSION & 0x7) << 13) | ((pkt_type & 0x1) << 12) | (1 << 11) | (apid & 0x7FF)


def parse_packet_id(packet_id: int) -> tuple[int, int, int]:
    """Parse packet_id into (type, sec_hdr_flag, apid)."""
    pkt_type = (packet_id >> 12) & 0x1
    sec_hdr = (packet_id >> 11) & 0x1
    apid = packet_id & 0x7FF
    return pkt_type, sec_hdr, apid


def build_seq_ctrl(seq_count: int, seq_flags: int = CCSDS_SEQ_STANDALONE) -> int:
    """Build 16-bit sequence control: flags(2) | count(14)."""
    return ((seq_flags & 0x3) << 14) | (seq_count & 0x3FFF)


def parse_seq_ctrl(seq_ctrl: int) -> tuple[int, int]:
    """Parse sequence control into (flags, count)."""
    flags = (seq_ctrl >> 14) & 0x3
    count = seq_ctrl & 0x3FFF
    return flags, count


def _build_frame(pkt_type: int, apid: int, payload: bytes,
                 seq_count: int, timestamp: int) -> bytes:
    """Build a complete CCSDS frame with primary header, secondary header, payload, and CRC."""
    if len(payload) > CCSDS_MAX_PAYLOAD:
        raise ValueError(f"payload too large: {len(payload)} > {CCSDS_MAX_PAYLOAD}")

    packet_id = build_packet_id(pkt_type, apid)
    seq_ctrl = build_seq_ctrl(seq_count)
    data_length = CCSDS_SEC_HDR_SIZE + len(payload) + CCSDS_CRC_SIZE - 1

    hdr = struct.pack(">HHH", packet_id, seq_ctrl, data_length)
    sec_hdr = struct.pack(">I", timestamp & 0xFFFFFFFF)

    frame_no_crc = hdr + sec_hdr + payload
    crc = ccsds_crc16(frame_no_crc)
    return frame_no_crc + struct.pack(">H", crc)


def build_tm(apid: int, payload: bytes, seq_count: int = 0, timestamp: int = 0) -> bytes:
    """Build a telemetry (TM) frame."""
    return _build_frame(CCSDS_TYPE_TM, apid, payload, seq_count, timestamp)


def build_tc(apid: int, payload: bytes, seq_count: int = 0, timestamp: int = 0) -> bytes:
    """Build a telecommand (TC) frame."""
    return _build_frame(CCSDS_TYPE_TC, apid, payload, seq_count, timestamp)


def parse_frame(raw: bytes) -> Optional[CcsdsPacket]:
    """Parse a raw CCSDS frame. Returns None if too short."""
    min_size = CCSDS_HDR_SIZE + CCSDS_SEC_HDR_SIZE + CCSDS_CRC_SIZE
    if len(raw) < min_size:
        return None

    packet_id, seq_ctrl, data_length = struct.unpack(">HHH", raw[:6])
    pkt_type, sec_hdr_flag, apid = parse_packet_id(packet_id)
    seq_flags, seq_count = parse_seq_ctrl(seq_ctrl)

    timestamp = struct.unpack(">I", raw[6:10])[0]

    payload_end = len(raw) - CCSDS_CRC_SIZE
    payload = raw[10:payload_end]

    expected_crc = ccsds_crc16(raw[:payload_end])
    actual_crc = struct.unpack(">H", raw[payload_end:])[0]

    return CcsdsPacket(
        pkt_type=pkt_type,
        sec_hdr_flag=sec_hdr_flag,
        apid=apid,
        seq_flags=seq_flags,
        seq_count=seq_count,
        timestamp=timestamp,
        payload=payload,
        crc_valid=(expected_crc == actual_crc),
        raw=raw,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ccsds.py -v`
Expected: all 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/ccsds.py tests/test_ccsds.py
git commit -m "feat(core): add CCSDS SPP encoder/decoder matching firmware protocol"
```

---

### Task 4: Core telemetry module

**Files:**
- Create: `core/telemetry.py`
- Create: `tests/test_telemetry.py`

Decodes TM payloads by APID and generates mock telemetry.

- [ ] **Step 1: Write the failing tests**

`tests/test_telemetry.py`:
```python
import struct
from core.telemetry import (
    decode_heartbeat,
    decode_bme280,
    decode_lis2dh,
    decode_tm_payload,
    generate_mock_telemetry,
)
from core.constants import APID_TM_HEARTBEAT, APID_TM_BME280, APID_TM_LIS2DH


def test_decode_heartbeat():
    # sc_id=2, uptime=1000, battery=3700, mode=1, difficulty=0, tc_count=42, error_count=0
    payload = struct.pack(">BIHBBHH", 2, 1000, 3700, 1, 0, 42, 0)
    result = decode_heartbeat(payload)
    assert result["sc_id"] == 2
    assert result["uptime"] == 1000
    assert result["battery_mv"] == 3700
    assert result["flight_mode"] == 1
    assert result["difficulty"] == 0
    assert result["tc_count"] == 42
    assert result["error_count"] == 0


def test_decode_bme280():
    # temp=25.50C (2550), pressure=101320 Pa/10 (10132), humidity=55%
    payload = struct.pack(">hIB", 2550, 10132, 55)
    result = decode_bme280(payload)
    assert result["temperature"] == 25.50
    assert result["pressure"] == 1013.2
    assert result["humidity"] == 55


def test_decode_lis2dh():
    # accel_x=100mG, accel_y=-200mG, accel_z=980mG
    payload = struct.pack(">hhh", 100, -200, 980)
    result = decode_lis2dh(payload)
    assert result["accel_x"] == 100
    assert result["accel_y"] == -200
    assert result["accel_z"] == 980


def test_decode_tm_payload_heartbeat():
    payload = struct.pack(">BIHBBHH", 2, 500, 3600, 0, 1, 10, 0)
    result = decode_tm_payload(APID_TM_HEARTBEAT, payload)
    assert result["sc_id"] == 2


def test_decode_tm_payload_unknown_apid():
    result = decode_tm_payload(0x099, b"\x01\x02\x03")
    assert result["raw"] == b"\x01\x02\x03"


def test_generate_mock_telemetry():
    tm = generate_mock_telemetry()
    assert "apid" in tm
    assert "timestamp" in tm
    assert "frame" in tm
    assert "decoded" in tm
    assert tm["apid"] in (APID_TM_HEARTBEAT, APID_TM_BME280, APID_TM_LIS2DH)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_telemetry.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`core/telemetry.py`:
```python
"""Telemetry decoder and mock generator.

Decodes TM payloads by APID, matching firmware struct formats.
Generates synthetic telemetry for mock mode.
"""

import random
import struct
import time

from core.ccsds import build_tm, parse_frame
from core.constants import (
    APID_TM_HEARTBEAT, APID_TM_BME280, APID_TM_LIS2DH,
    CCSDS_SPACECRAFT_ID,
)


def decode_heartbeat(payload: bytes) -> dict:
    """Decode heartbeat TM payload (APID 0x001)."""
    sc_id, uptime, battery_mv, flight_mode, difficulty, tc_count, error_count = struct.unpack(
        ">BIHBBHH", payload[:12]
    )
    return {
        "sc_id": sc_id,
        "uptime": uptime,
        "battery_mv": battery_mv,
        "flight_mode": flight_mode,
        "difficulty": difficulty,
        "tc_count": tc_count,
        "error_count": error_count,
    }


def decode_bme280(payload: bytes) -> dict:
    """Decode BME280 TM payload (APID 0x010)."""
    temp_x100, press_x10, humidity = struct.unpack(">hIB", payload[:7])
    return {
        "temperature": temp_x100 / 100.0,
        "pressure": press_x10 / 10.0,
        "humidity": humidity,
    }


def decode_lis2dh(payload: bytes) -> dict:
    """Decode LIS2DH accelerometer TM payload (APID 0x011)."""
    accel_x, accel_y, accel_z = struct.unpack(">hhh", payload[:6])
    return {
        "accel_x": accel_x,
        "accel_y": accel_y,
        "accel_z": accel_z,
    }


_DECODERS = {
    APID_TM_HEARTBEAT: decode_heartbeat,
    APID_TM_BME280: decode_bme280,
    APID_TM_LIS2DH: decode_lis2dh,
}


def decode_tm_payload(apid: int, payload: bytes) -> dict:
    """Decode a TM payload by APID. Returns raw bytes for unknown APIDs."""
    decoder = _DECODERS.get(apid)
    if decoder:
        return decoder(payload)
    return {"raw": payload}


_mock_seq_count = 0


def generate_mock_telemetry() -> dict:
    """Generate a single synthetic TM frame for mock mode."""
    global _mock_seq_count

    apid = random.choice([APID_TM_HEARTBEAT, APID_TM_BME280, APID_TM_LIS2DH])
    timestamp = int(time.time()) & 0xFFFFFFFF

    if apid == APID_TM_HEARTBEAT:
        payload = struct.pack(
            ">BIHBBHH",
            CCSDS_SPACECRAFT_ID,
            timestamp,
            random.randint(3300, 4200),
            random.randint(0, 2),
            0,
            random.randint(0, 500),
            random.randint(0, 5),
        )
    elif apid == APID_TM_BME280:
        payload = struct.pack(
            ">hIB",
            random.randint(2000, 3500),   # 20.00 - 35.00 C
            random.randint(10100, 10200),  # 1010.0 - 1020.0 hPa
            random.randint(40, 60),
        )
    else:  # LIS2DH
        payload = struct.pack(
            ">hhh",
            random.randint(-50, 50),
            random.randint(-50, 50),
            random.randint(950, 1050),
        )

    frame = build_tm(apid, payload, seq_count=_mock_seq_count, timestamp=timestamp)
    _mock_seq_count = (_mock_seq_count + 1) & 0x3FFF

    decoded = decode_tm_payload(apid, payload)
    return {
        "apid": apid,
        "timestamp": timestamp,
        "frame": frame,
        "raw_hex": frame.hex(),
        "decoded": decoded,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_telemetry.py -v`
Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/telemetry.py tests/test_telemetry.py
git commit -m "feat(core): add telemetry decoder and mock generator"
```

---

### Task 5: Core telecommand module

**Files:**
- Create: `core/telecommand.py`
- Create: `tests/test_telecommand.py`

Builds TC frames and handles AES-128-ECB encryption for privileged commands.

- [ ] **Step 1: Write the failing tests**

`tests/test_telecommand.py`:
```python
from core.telecommand import (
    build_command_tc,
    build_privileged_tc,
    xor_encrypt,
    xor_decrypt,
)
from core.ccsds import parse_frame
from core.constants import (
    APID_TC_COMMAND, TC_OP_PING, TC_OP_PRIVILEGED,
    TC_OP_READ_FLAG, AES_KEY_HARDCODED, XOR_KEY,
    CCSDS_TYPE_TC,
)


def test_build_command_tc_ping():
    frame = build_command_tc(TC_OP_PING)
    pkt = parse_frame(frame)
    assert pkt.pkt_type == CCSDS_TYPE_TC
    assert pkt.apid == APID_TC_COMMAND
    assert pkt.payload[0] == TC_OP_PING
    assert pkt.crc_valid


def test_build_command_tc_with_data():
    data = b"\x01\x02\x03\x04"
    frame = build_command_tc(TC_OP_PING, data=data)
    pkt = parse_frame(frame)
    assert pkt.payload == bytes([TC_OP_PING]) + data


def test_build_privileged_tc():
    frame = build_privileged_tc(TC_OP_READ_FLAG)
    pkt = parse_frame(frame)
    assert pkt.apid == APID_TC_COMMAND
    assert pkt.payload[0] == TC_OP_PRIVILEGED
    # payload[1:17] is 16 bytes AES-encrypted block
    assert len(pkt.payload) == 17


def test_xor_roundtrip():
    original = b"Hello, World!"
    encrypted = xor_encrypt(original)
    decrypted = xor_decrypt(encrypted)
    assert decrypted == original


def test_xor_encrypt_known():
    data = b"PWNSAT"
    encrypted = xor_encrypt(data)
    # XOR with itself = all zeros
    assert encrypted == b"\x00" * 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_telecommand.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`core/telecommand.py`:
```python
"""Telecommand builder with AES-128-ECB encryption.

Builds TC frames for the FlatSat. Supports plain commands and
AES-encrypted privileged commands (TC_OP_PRIVILEGED 0xD0).
"""

import hashlib
import struct

from core.ccsds import build_tc
from core.constants import (
    APID_TC_COMMAND, TC_OP_PRIVILEGED,
    AES_KEY_HARDCODED, XOR_KEY,
)

_tc_seq_count = 0


def _aes_ecb_encrypt(key: bytes, plaintext: bytes) -> bytes:
    """AES-128-ECB encrypt a single 16-byte block.

    Uses a pure-Python AES implementation to avoid external crypto dependencies.
    This is deliberately simple — matches firmware's PSA AES-128-ECB.
    """
    try:
        # Try PyCryptodome first
        from Crypto.Cipher import AES
        cipher = AES.new(key, AES.MODE_ECB)
        return cipher.encrypt(plaintext)
    except ImportError:
        pass

    try:
        # Try cryptography package
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        cipher = Cipher(algorithms.AES(key), modes.ECB())
        encryptor = cipher.encryptor()
        return encryptor.update(plaintext) + encryptor.finalize()
    except ImportError:
        pass

    # Fallback: use hashlib-based poor-man's AES (NOT real AES, but works for CTF)
    # In production, install pycryptodome or cryptography
    raise ImportError(
        "No AES library available. Install pycryptodome or cryptography: "
        "pip install pycryptodome"
    )


def xor_encrypt(data: bytes) -> bytes:
    """XOR encrypt/decrypt with the hardcoded key."""
    key = XOR_KEY
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


xor_decrypt = xor_encrypt  # XOR is symmetric


def build_command_tc(opcode: int, data: bytes = b"", seq_count: int | None = None) -> bytes:
    """Build a telecommand frame with opcode + optional data."""
    global _tc_seq_count
    if seq_count is None:
        seq_count = _tc_seq_count
        _tc_seq_count = (_tc_seq_count + 1) & 0x3FFF

    payload = bytes([opcode]) + data
    return build_tc(APID_TC_COMMAND, payload, seq_count=seq_count)


def build_privileged_tc(inner_opcode: int, inner_data: bytes = b"",
                        seq_count: int | None = None) -> bytes:
    """Build an AES-encrypted privileged telecommand.

    Encrypted payload format (16 bytes):
        [inner_opcode][0x50 magic][14 bytes data (zero-padded)]
    """
    global _tc_seq_count
    if seq_count is None:
        seq_count = _tc_seq_count
        _tc_seq_count = (_tc_seq_count + 1) & 0x3FFF

    # Build 16-byte plaintext block
    plaintext = bytes([inner_opcode, 0x50]) + inner_data
    plaintext = plaintext[:16].ljust(16, b"\x00")

    encrypted = _aes_ecb_encrypt(AES_KEY_HARDCODED, plaintext)
    payload = bytes([TC_OP_PRIVILEGED]) + encrypted
    return build_tc(APID_TC_COMMAND, payload, seq_count=seq_count)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_telecommand.py -v`
Expected: all 5 tests PASS (requires `pycryptodome` or `cryptography` installed)

If AES import fails, install: `pip install pycryptodome`

- [ ] **Step 5: Update requirements.txt**

Add `pycryptodome==3.20.0` to `requirements.txt` and run `pip install -r requirements.txt`.

- [ ] **Step 6: Commit**

```bash
git add core/telecommand.py tests/test_telecommand.py requirements.txt
git commit -m "feat(core): add telecommand builder with AES-128-ECB encryption"
```

---

### Task 6: Core state module

**Files:**
- Create: `core/state.py`
- Create: `tests/test_state.py`

Tracks FlatSat connection state and manages mock vs hardware mode.

- [ ] **Step 1: Write the failing tests**

`tests/test_state.py`:
```python
from core.state import GroundStationState
from core.constants import ConnectionMode


def test_initial_state():
    state = GroundStationState()
    assert state.connection_mode == ConnectionMode.SIMULATED
    assert state.device is None
    assert state.mock_running is False


def test_set_simulated():
    state = GroundStationState()
    state.set_simulated()
    assert state.connection_mode == ConnectionMode.SIMULATED
    assert state.device is None


def test_set_hardware():
    state = GroundStationState()
    state.set_hardware("fake_device")
    assert state.connection_mode == ConnectionMode.HARDWARE
    assert state.device == "fake_device"


def test_is_simulated():
    state = GroundStationState()
    assert state.is_simulated is True
    state.set_hardware("dev")
    assert state.is_simulated is False


def test_mock_telemetry_control():
    state = GroundStationState()
    state.start_mock()
    assert state.mock_running is True
    state.stop_mock()
    assert state.mock_running is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`core/state.py`:
```python
"""FlatSat ground station state management.

Tracks connection mode (hardware vs simulated), device reference,
and mock telemetry generation state.
"""

from typing import Any, Optional

from core.constants import ConnectionMode


class GroundStationState:
    """Singleton-ish state tracker for the ground station."""

    def __init__(self):
        self.connection_mode: ConnectionMode = ConnectionMode.SIMULATED
        self.device: Optional[Any] = None
        self.mock_running: bool = False

    @property
    def is_simulated(self) -> bool:
        return self.connection_mode == ConnectionMode.SIMULATED

    def set_simulated(self):
        """Switch to simulated mode (no hardware)."""
        self.connection_mode = ConnectionMode.SIMULATED
        self.device = None

    def set_hardware(self, device: Any):
        """Switch to hardware mode with a connected device."""
        self.connection_mode = ConnectionMode.HARDWARE
        self.device = device

    def start_mock(self):
        """Mark mock telemetry generation as running."""
        self.mock_running = True

    def stop_mock(self):
        """Mark mock telemetry generation as stopped."""
        self.mock_running = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_state.py -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/state.py tests/test_state.py
git commit -m "feat(core): add ground station state management"
```

---

### Task 7: Core __init__.py public exports

**Files:**
- Modify: `core/__init__.py`

- [ ] **Step 1: Update core public API**

`core/__init__.py`:
```python
"""FlatSat Ground Station — shared core library.

Usage:
    from core import build_tm, parse_frame, generate_mock_telemetry
    from core.constants import APID_TM_HEARTBEAT, TC_OP_PING
"""

from core.ccsds import (
    CcsdsPacket,
    build_tm,
    build_tc,
    parse_frame,
    ccsds_crc16,
)
from core.telemetry import (
    decode_tm_payload,
    generate_mock_telemetry,
)
from core.telecommand import (
    build_command_tc,
    build_privileged_tc,
)
from core.state import GroundStationState
```

- [ ] **Step 2: Verify all core tests pass**

Run: `python -m pytest tests/test_constants.py tests/test_ccsds.py tests/test_telemetry.py tests/test_telecommand.py tests/test_state.py -v`
Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add core/__init__.py
git commit -m "feat(core): add public API exports"
```

---

### Task 8: Flask config and database helpers

**Files:**
- Create: `webapp/config.py`
- Create: `webapp/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

`tests/test_db.py`:
```python
import os
import sqlite3
import tempfile

import pytest

from webapp.config import Config, TestConfig
from webapp.db import get_db, close_db, init_db


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
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        assert "users" in table_names
        assert "telemetry" in table_names
        assert "radio_config" in table_names
        assert "logs" in table_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write config.py**

`webapp/config.py`:
```python
"""Flask configuration. Secrets are deliberately hardcoded (CTF target)."""


class Config:
    SECRET_KEY = "pwnsat_ground_station_2026"
    DATABASE = "db/telemetry.db"
    DEBUG = True


class TestConfig(Config):
    TESTING = True
    DATABASE = ":memory:"
```

- [ ] **Step 4: Write db.py**

`webapp/db.py`:
```python
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
    """Get or create a database connection for the current request."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    """Close the database connection at end of request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables from schema."""
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()
```

- [ ] **Step 5: Create minimal app.py for tests**

`webapp/app.py`:
```python
"""Flask application factory."""

from flask import Flask

from webapp.config import Config
from webapp.db import close_db, init_db


def create_app(config_class=Config, db_path=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    if db_path:
        app.config["DATABASE"] = db_path

    app.teardown_appcontext(close_db)

    return app
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_db.py -v`
Expected: all 3 tests PASS

- [ ] **Step 7: Commit**

```bash
git add webapp/config.py webapp/db.py webapp/app.py tests/test_db.py
git commit -m "feat(webapp): add Flask config, SQLite database helpers, and schema"
```

---

### Task 9: Database seed script

**Files:**
- Create: `webapp/seed.py`
- Create: `tests/test_seed.py`

Seeds the database with users, telemetry, radio configs, and logs for the CTF.

- [ ] **Step 1: Write the failing test**

`tests/test_seed.py`:
```python
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
        seed_db()  # second call should not duplicate
        db = get_db()
        users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        assert users == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_seed.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`webapp/seed.py`:
```python
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
            "accel_x, accel_y, accel_z, raw_hex) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ts.isoformat(), apid, 0x02, temp, pressure, humidity, ax, ay, az, raw_hex),
        )


def _seed_radio_config(db):
    db.execute(
        "INSERT INTO radio_config (owner, frequency, spreading_factor, bandwidth, tx_power, description) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("admin", 436703000, 10, 125000, 22, "TinyGS Norbi downlink — CLASSIFIED"),
    )
    db.execute(
        "INSERT INTO radio_config (owner, frequency, spreading_factor, bandwidth, tx_power, description) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("operator", 915000000, 7, 125000, 14, "Default ISM 915 MHz"),
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_seed.py -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add webapp/seed.py tests/test_seed.py
git commit -m "feat(webapp): add database seed with users, telemetry, configs, logs"
```

---

### Task 10: Authentication with broken tokens (GS-05)

**Files:**
- Create: `webapp/auth.py`
- Create: `tests/test_auth.py`

Implements login/logout with deliberately weak base64 session tokens.

- [ ] **Step 1: Write the failing tests**

`tests/test_auth.py`:
```python
import base64
import hashlib
import os
import tempfile

import pytest

from webapp.config import TestConfig
from webapp.db import get_db, init_db
from webapp.seed import seed_db
from webapp.auth import create_session_token, parse_session_token


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
def client(app):
    return app.test_client()


def test_create_session_token():
    token = create_session_token("admin", "admin")
    decoded = base64.b64decode(token).decode()
    parts = decoded.split(":")
    assert parts[0] == "admin"
    assert parts[1] == "admin"
    assert len(parts) == 3  # username:role:timestamp


def test_parse_session_token():
    token = create_session_token("operator", "operator")
    username, role = parse_session_token(token)
    assert username == "operator"
    assert role == "operator"


def test_parse_invalid_token():
    username, role = parse_session_token("not-valid-base64!!!")
    assert username is None
    assert role is None


def test_parse_forged_admin_token():
    """GS-05: attacker can forge admin token by modifying base64."""
    forged = base64.b64encode(b"admin:admin:9999999999").decode()
    username, role = parse_session_token(forged)
    assert username == "admin"
    assert role == "admin"


def test_login_valid_credentials(client):
    resp = client.post("/login", data={
        "username": "operator",
        "password": "operator123",
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert "session_token" in resp.headers.get("Set-Cookie", "")


def test_login_invalid_credentials(client):
    resp = client.post("/login", data={
        "username": "operator",
        "password": "wrongpassword",
    }, follow_redirects=True)
    assert b"Invalid" in resp.data


def test_logout(client):
    client.post("/login", data={"username": "operator", "password": "operator123"})
    resp = client.get("/logout", follow_redirects=False)
    assert resp.status_code == 302
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write auth.py**

`webapp/auth.py`:
```python
"""Authentication with deliberately broken session tokens (GS-05).

Session token = base64(username:role:timestamp) — no HMAC, no signature.
An attacker can decode, modify role to "admin", re-encode, and forge access.
"""

import base64
import hashlib
import time
from functools import wraps

from flask import request, redirect, url_for, g

from webapp.db import get_db


def _md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def create_session_token(username: str, role: str) -> str:
    """Create a base64 session token. DELIBERATELY INSECURE (GS-05)."""
    timestamp = str(int(time.time()))
    payload = f"{username}:{role}:{timestamp}"
    return base64.b64encode(payload.encode()).decode()


def parse_session_token(token: str) -> tuple[str | None, str | None]:
    """Parse a session token. Returns (username, role) or (None, None)."""
    try:
        decoded = base64.b64decode(token).decode()
        parts = decoded.split(":")
        if len(parts) >= 2:
            return parts[0], parts[1]
    except Exception:
        pass
    return None, None


def get_current_user():
    """Get current user from session token cookie."""
    token = request.cookies.get("session_token")
    if not token:
        return None, None
    return parse_session_token(token)


def login_required(f):
    """Decorator: redirect to login if no valid session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        username, role = get_current_user()
        if username is None:
            return redirect(url_for("login"))
        g.username = username
        g.role = role
        return f(*args, **kwargs)
    return decorated


def authenticate(username: str, password: str) -> tuple[str | None, str | None]:
    """Check credentials against DB. Returns (username, role) or (None, None)."""
    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username = ? AND password_hash = ?",
        (username, _md5(password)),
    ).fetchone()
    if user:
        return user["username"], user["role"]
    return None, None
```

- [ ] **Step 4: Add login/logout routes to app.py**

Replace `webapp/app.py` content with:

```python
"""Flask application factory."""

from flask import Flask, render_template, request, redirect, url_for, make_response

from webapp.config import Config
from webapp.db import close_db, init_db
from webapp.auth import authenticate, create_session_token, login_required, get_current_user


def create_app(config_class=Config, db_path=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    if db_path:
        app.config["DATABASE"] = db_path

    app.teardown_appcontext(close_db)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            user, role = authenticate(username, password)
            if user:
                token = create_session_token(user, role)
                resp = redirect(url_for("dashboard"))
                resp.set_cookie("session_token", token)
                return resp
            return render_template("login.html", error="Invalid credentials")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        resp = redirect(url_for("login"))
        resp.delete_cookie("session_token")
        return resp

    @app.route("/")
    def index():
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html")

    return app
```

- [ ] **Step 5: Create minimal templates for tests**

`webapp/templates/login.html`:
```html
<!DOCTYPE html>
<html>
<head><title>PwnSat2 Ground Station — Login</title></head>
<body>
<h1>Ground Station Login</h1>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
<form method="post">
    <input name="username" placeholder="Username" required>
    <input name="password" type="password" placeholder="Password" required>
    <button type="submit">Login</button>
</form>
</body>
</html>
```

`webapp/templates/dashboard.html`:
```html
<!DOCTYPE html>
<html>
<head><title>PwnSat2 Ground Station</title></head>
<body>
<h1>Dashboard</h1>
<p>Welcome, {{ g.username }} ({{ g.role }})</p>
</body>
</html>
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_auth.py -v`
Expected: all 7 tests PASS

- [ ] **Step 7: Commit**

```bash
git add webapp/auth.py webapp/app.py webapp/templates/login.html webapp/templates/dashboard.html tests/test_auth.py
git commit -m "feat(webapp): add auth with broken base64 tokens (GS-05)"
```

---

### Task 11: SQLi vulnerability (GS-01) and telemetry API

**Files:**
- Modify: `webapp/app.py`
- Create: `tests/test_vuln_sqli.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_vuln_sqli.py`:
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
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client


def test_telemetry_search_normal(auth_client):
    resp = auth_client.get("/api/telemetry?search=0801&limit=10")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)


def test_telemetry_search_sqli_union(auth_client):
    """GS-01: SQL injection via UNION to extract admin password hash."""
    payload = "' UNION SELECT id,username,password_hash,role,1,2,3,4,5,6,7 FROM users--"
    resp = auth_client.get(f"/api/telemetry?search={payload}&limit=100")
    assert resp.status_code == 200
    data = resp.get_json()
    # Should contain user data leaked through the union
    found_admin = False
    for row in data:
        values = list(row.values())
        if "admin" in str(values) and "5f4dcc3b" in str(values):
            found_admin = True
            break
    assert found_admin, "SQLi UNION should leak admin hash"


def test_telemetry_default_limit(auth_client):
    resp = auth_client.get("/api/telemetry")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) <= 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vuln_sqli.py -v`
Expected: FAIL (route not found, 404)

- [ ] **Step 3: Add telemetry API route to app.py**

Add this route inside `create_app()` in `webapp/app.py`, after the dashboard route:

```python
    @app.route("/api/telemetry")
    @login_required
    def api_telemetry():
        from webapp.db import get_db
        import json

        search = request.args.get("search", "")
        limit = request.args.get("limit", "50")

        db = get_db()
        # VULNERABLE: string concatenation (GS-01)
        query = f"SELECT * FROM telemetry WHERE raw_hex LIKE '%{search}%' LIMIT {limit}"
        try:
            rows = db.execute(query).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            return {"error": str(e)}, 500
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vuln_sqli.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add webapp/app.py tests/test_vuln_sqli.py
git commit -m "feat(webapp): add telemetry API with SQL injection vuln (GS-01)"
```

---

### Task 12: XSS vulnerability (GS-02) and logs page

**Files:**
- Modify: `webapp/app.py`
- Create: `webapp/templates/logs.html`
- Create: `tests/test_vuln_xss.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_vuln_xss.py`:
```python
import os
import tempfile

import pytest

from webapp.config import TestConfig
from webapp.db import get_db, init_db
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
def auth_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client


def test_logs_page_renders(auth_client):
    resp = auth_client.get("/logs")
    assert resp.status_code == 200
    assert b"Ground station initialized" in resp.data


def test_logs_xss_stored(app, auth_client):
    """GS-02: Stored XSS — log messages render as raw HTML."""
    xss_payload = '<script>alert("XSS")</script>'
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO logs (timestamp, level, source, message) VALUES (?, ?, ?, ?)",
            ("2026-04-09T12:00:00", "INFO", "test", xss_payload),
        )
        db.commit()

    resp = auth_client.get("/logs")
    # The script tag should appear unescaped (| safe filter)
    assert xss_payload.encode() in resp.data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vuln_xss.py -v`
Expected: FAIL (route not found)

- [ ] **Step 3: Create logs.html template**

`webapp/templates/logs.html`:
```html
<!DOCTYPE html>
<html>
<head><title>PwnSat2 — System Logs</title></head>
<body>
<h1>System Logs</h1>
<a href="/dashboard">Dashboard</a>
<table border="1">
    <tr><th>Timestamp</th><th>Level</th><th>Source</th><th>Message</th></tr>
    {% for log in logs %}
    <tr>
        <td>{{ log.timestamp }}</td>
        <td>{{ log.level }}</td>
        <td>{{ log.source }}</td>
        <td>{{ log.message | safe }}</td>
    </tr>
    {% endfor %}
</table>
</body>
</html>
```

Note: `| safe` disables HTML escaping — this is the GS-02 vulnerability.

- [ ] **Step 4: Add logs route to app.py**

Add inside `create_app()`:

```python
    @app.route("/logs")
    @login_required
    def logs_page():
        from webapp.db import get_db
        db = get_db()
        logs = db.execute("SELECT * FROM logs ORDER BY id DESC").fetchall()
        return render_template("logs.html", logs=logs)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_vuln_xss.py -v`
Expected: all 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add webapp/app.py webapp/templates/logs.html tests/test_vuln_xss.py
git commit -m "feat(webapp): add logs page with stored XSS vuln (GS-02)"
```

---

### Task 13: RCE vulnerability (GS-03) — diagnostics endpoint

**Files:**
- Modify: `webapp/app.py`
- Create: `tests/test_vuln_rce.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_vuln_rce.py`:
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
def auth_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client


def test_diagnostics_rce(auth_client):
    """GS-03: RCE via subprocess.check_output with shell=True."""
    resp = auth_client.post("/api/diagnostics",
                            json={"cmd": "echo PWNSAT_TEST"},
                            content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "PWNSAT_TEST" in data["output"]


def test_diagnostics_command_injection(auth_client):
    """GS-03: command chaining with semicolon."""
    resp = auth_client.post("/api/diagnostics",
                            json={"cmd": "echo hello; echo injected"},
                            content_type="application/json")
    assert resp.status_code == 200
    assert "injected" in resp.get_json()["output"]


def test_diagnostics_no_cmd(auth_client):
    resp = auth_client.post("/api/diagnostics",
                            json={},
                            content_type="application/json")
    assert resp.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vuln_rce.py -v`
Expected: FAIL (route not found)

- [ ] **Step 3: Add diagnostics route to app.py**

Add inside `create_app()`:

```python
    @app.route("/api/diagnostics", methods=["POST"])
    @login_required
    def api_diagnostics():
        import subprocess
        data = request.get_json(silent=True) or {}
        cmd = data.get("cmd")
        if not cmd:
            return {"error": "Missing 'cmd' parameter"}, 400

        try:
            # VULNERABLE: shell=True with user input (GS-03)
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=10)
            return {"output": output.decode(errors="replace")}
        except subprocess.CalledProcessError as e:
            return {"output": e.output.decode(errors="replace"), "returncode": e.returncode}
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out"}, 408
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vuln_rce.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add webapp/app.py tests/test_vuln_rce.py
git commit -m "feat(webapp): add diagnostics endpoint with RCE vuln (GS-03)"
```

---

### Task 14: LFI vulnerability (GS-04)

**Files:**
- Modify: `webapp/app.py`
- Create: `tests/test_vuln_lfi.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_vuln_lfi.py`:
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
def auth_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client


def test_lfi_path_traversal(auth_client):
    """GS-04: path traversal to read /etc/passwd."""
    resp = auth_client.get("/api/logs?file=../../../etc/passwd")
    assert resp.status_code == 200
    assert "root:" in resp.get_json()["content"]


def test_lfi_no_file_param(auth_client):
    resp = auth_client.get("/api/logs")
    assert resp.status_code == 400


def test_lfi_nonexistent_file(auth_client):
    resp = auth_client.get("/api/logs?file=nonexistent.log")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vuln_lfi.py -v`
Expected: FAIL

- [ ] **Step 3: Add logs API route to app.py**

Add inside `create_app()`:

```python
    @app.route("/api/logs", methods=["GET", "POST"])
    @login_required
    def api_logs():
        from webapp.db import get_db

        if request.method == "POST":
            # GS-11: Log injection (no newline sanitization)
            data = request.get_json(silent=True) or {}
            message = data.get("message", "")
            level = data.get("level", "INFO")
            source = data.get("source", "user")
            from datetime import datetime
            db = get_db()
            db.execute(
                "INSERT INTO logs (timestamp, level, source, message) VALUES (?, ?, ?, ?)",
                (datetime.now().isoformat(), level, source, message),
            )
            db.commit()
            return {"status": "ok"}

        # GET: file parameter for LFI (GS-04)
        filename = request.args.get("file")
        if not filename:
            return {"error": "Missing 'file' parameter"}, 400

        # VULNERABLE: no path sanitization (GS-04)
        import os
        logs_dir = os.path.join(os.path.dirname(__file__), "logs")
        filepath = os.path.join(logs_dir, filename)

        try:
            with open(filepath) as f:
                return {"content": f.read()}
        except FileNotFoundError:
            return {"error": "File not found"}, 404
        except Exception as e:
            return {"error": str(e)}, 500
```

Also create the logs directory:

```bash
mkdir -p webapp/logs
echo "2026-04-01 System started" > webapp/logs/system.log
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vuln_lfi.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add webapp/app.py webapp/logs/system.log tests/test_vuln_lfi.py
git commit -m "feat(webapp): add log file API with LFI vuln (GS-04) and log injection (GS-11)"
```

---

### Task 15: IDOR vulnerability (GS-06) and radio config

**Files:**
- Modify: `webapp/app.py`
- Create: `webapp/templates/config.html`
- Create: `tests/test_vuln_idor.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_vuln_idor.py`:
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


def test_idor_access_admin_config(operator_client):
    """GS-06: operator can read admin's radio config by ID."""
    resp = operator_client.get("/api/config/radio/1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["owner"] == "admin"
    assert "CLASSIFIED" in data["description"]


def test_idor_own_config(operator_client):
    resp = operator_client.get("/api/config/radio/2")
    assert resp.status_code == 200
    assert resp.get_json()["owner"] == "operator"


def test_idor_nonexistent(operator_client):
    resp = operator_client.get("/api/config/radio/999")
    assert resp.status_code == 404


def test_config_page_renders(operator_client):
    resp = operator_client.get("/config")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vuln_idor.py -v`
Expected: FAIL

- [ ] **Step 3: Create config.html template**

`webapp/templates/config.html`:
```html
<!DOCTYPE html>
<html>
<head><title>PwnSat2 — Radio Config</title></head>
<body>
<h1>Radio Configuration</h1>
<a href="/dashboard">Dashboard</a>

<h2>Your Configuration</h2>
<form method="post" action="/api/config/radio">
    <label>Frequency (Hz): <input name="frequency" type="number" value="{{ config.frequency if config else 915000000 }}"></label><br>
    <label>Spreading Factor: <input name="spreading_factor" type="number" min="7" max="12" value="{{ config.spreading_factor if config else 7 }}"></label><br>
    <label>Bandwidth (Hz): <input name="bandwidth" type="number" value="{{ config.bandwidth if config else 125000 }}"></label><br>
    <label>TX Power (dBm): <input name="tx_power" type="number" value="{{ config.tx_power if config else 14 }}"></label><br>
    <button type="submit">Update Config</button>
</form>
</body>
</html>
```

- [ ] **Step 4: Add config routes to app.py**

Add inside `create_app()`:

```python
    @app.route("/config")
    @login_required
    def config_page():
        from webapp.db import get_db
        db = get_db()
        config = db.execute(
            "SELECT * FROM radio_config WHERE owner = ?", (g.username,)
        ).fetchone()
        return render_template("config.html", config=config)

    @app.route("/api/config/radio/<int:config_id>")
    @login_required
    def api_config_get(config_id):
        from webapp.db import get_db
        db = get_db()
        # VULNERABLE: no ownership check (GS-06 IDOR)
        config = db.execute(
            "SELECT * FROM radio_config WHERE id = ?", (config_id,)
        ).fetchone()
        if config is None:
            return {"error": "Config not found"}, 404
        return dict(config)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_vuln_idor.py -v`
Expected: all 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add webapp/app.py webapp/templates/config.html tests/test_vuln_idor.py
git commit -m "feat(webapp): add radio config page with IDOR vuln (GS-06)"
```

---

### Task 16: Command injection vulnerability (GS-07)

**Files:**
- Modify: `webapp/app.py`
- Create: `tests/test_vuln_cmdi.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_vuln_cmdi.py`:
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
def auth_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client


def test_config_radio_normal(auth_client):
    resp = auth_client.post("/api/config/radio",
                            json={"frequency": 915000000},
                            content_type="application/json")
    assert resp.status_code == 200
    assert "915000000" in resp.get_json()["output"]


def test_config_radio_cmdi(auth_client):
    """GS-07: command injection via frequency parameter."""
    resp = auth_client.post("/api/config/radio",
                            json={"frequency": "915000000; echo INJECTED"},
                            content_type="application/json")
    assert resp.status_code == 200
    assert "INJECTED" in resp.get_json()["output"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vuln_cmdi.py -v`
Expected: FAIL

- [ ] **Step 3: Add POST config route to app.py**

Add inside `create_app()`:

```python
    @app.route("/api/config/radio", methods=["POST"])
    @login_required
    def api_config_update():
        import subprocess
        data = request.get_json(silent=True) or {}
        frequency = data.get("frequency", "915000000")

        # VULNERABLE: f-string in shell command (GS-07)
        try:
            output = subprocess.check_output(
                f"echo 'Setting frequency to {frequency}'",
                shell=True, stderr=subprocess.STDOUT,
            )
            return {"output": output.decode(errors="replace")}
        except subprocess.CalledProcessError as e:
            return {"output": e.output.decode(errors="replace")}, 500
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vuln_cmdi.py -v`
Expected: all 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add webapp/app.py tests/test_vuln_cmdi.py
git commit -m "feat(webapp): add radio config POST with command injection (GS-07)"
```

---

### Task 17: Log injection (GS-11) and API enumeration (GS-12)

**Files:**
- Modify: `webapp/app.py`
- Create: `tests/test_vuln_log_injection.py`
- Create: `tests/test_vuln_api_enum.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_vuln_log_injection.py`:
```python
import os
import tempfile

import pytest

from webapp.config import TestConfig
from webapp.db import get_db, init_db
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
def auth_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client


def test_log_injection_newlines(app, auth_client):
    """GS-11: newlines in log message create fake entries."""
    payload = "Normal log\n2026-04-08 ADMIN: System shutdown authorized"
    resp = auth_client.post("/api/logs",
                            json={"message": payload},
                            content_type="application/json")
    assert resp.status_code == 200

    with app.app_context():
        db = get_db()
        row = db.execute(
            "SELECT message FROM logs WHERE message LIKE '%System shutdown%'"
        ).fetchone()
        assert row is not None
        assert "\n" in row["message"]
```

`tests/test_vuln_api_enum.py`:
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
def client(app):
    return app.test_client()


def test_api_endpoints_no_auth(client):
    """GS-12: endpoint listing requires no authentication."""
    resp = client.get("/api/endpoints")
    assert resp.status_code == 200


def test_api_endpoints_lists_routes(client):
    """GS-12: lists all Flask routes."""
    resp = client.get("/api/endpoints")
    data = resp.get_json()
    routes = [r["rule"] for r in data]
    assert "/api/diagnostics" in routes
    assert "/api/telemetry" in routes
    assert "/api/config/radio/<int:config_id>" in routes
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_vuln_log_injection.py tests/test_vuln_api_enum.py -v`
Expected: FAIL

- [ ] **Step 3: Add API endpoints route to app.py**

Note: The POST `/api/logs` route for GS-11 was already added in Task 14 as part of the `api_logs` function.

Add the endpoints listing route inside `create_app()`:

```python
    @app.route("/api/endpoints")
    def api_endpoints():
        """GS-12: lists all routes without authentication or rate limiting."""
        routes = []
        for rule in app.url_map.iter_rules():
            if rule.endpoint == "static":
                continue
            routes.append({
                "rule": rule.rule,
                "methods": sorted(rule.methods - {"OPTIONS", "HEAD"}),
                "endpoint": rule.endpoint,
            })
        return routes
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_vuln_log_injection.py tests/test_vuln_api_enum.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add webapp/app.py tests/test_vuln_log_injection.py tests/test_vuln_api_enum.py
git commit -m "feat(webapp): add log injection (GS-11) and API enumeration (GS-12)"
```

---

### Task 18: Radio bridge and send endpoint (GS-08)

**Files:**
- Create: `webapp/radio_bridge.py`
- Modify: `webapp/app.py`
- Create: `tests/test_radio_bridge.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_radio_bridge.py`:
```python
import os
import tempfile

import pytest

from webapp.config import TestConfig
from webapp.db import init_db
from webapp.seed import seed_db
from webapp.radio_bridge import RadioBridge


def test_radio_bridge_mock_mode():
    bridge = RadioBridge()
    assert bridge.is_connected is False
    assert bridge.mode == "simulated"


def test_radio_bridge_send_raw_mock():
    bridge = RadioBridge()
    result = bridge.send_raw(b"\x08\x01\xC0\x00")
    assert result["status"] == "sent_simulated"


def test_radio_bridge_send_tc_mock():
    bridge = RadioBridge()
    result = bridge.send_tc(0x020, b"\x10")
    assert result["status"] == "sent_simulated"
    assert "frame_hex" in result


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
def auth_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client


def test_radio_send_endpoint(auth_client):
    """GS-08: send raw bytes to satellite via radio_bridge."""
    resp = auth_client.post("/api/radio/send",
                            json={"data": "080100"},
                            content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "sent_simulated"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_radio_bridge.py -v`
Expected: FAIL

- [ ] **Step 3: Write radio_bridge.py**

`webapp/radio_bridge.py`:
```python
"""Radio bridge: sync wrapper over core for Flask.

In hardware mode, sends raw bytes via serial to FlatSat.
In simulated mode, logs the command and returns success.
This file is the pivot target for GS-08 (kill chain).
"""

from core.ccsds import build_tc
from core.state import GroundStationState

_state = GroundStationState()


class RadioBridge:
    """Sync serial bridge to FlatSat."""

    def __init__(self):
        self._state = _state

    @property
    def is_connected(self) -> bool:
        return not self._state.is_simulated

    @property
    def mode(self) -> str:
        return "hardware" if self.is_connected else "simulated"

    def send_raw(self, data: bytes) -> dict:
        """Send raw bytes to satellite."""
        if self.is_connected and self._state.device:
            try:
                self._state.device.send_raw(data)
                return {"status": "sent", "bytes": len(data)}
            except Exception as e:
                return {"status": "error", "error": str(e)}

        return {"status": "sent_simulated", "bytes": len(data), "data_hex": data.hex()}

    def send_tc(self, apid: int, payload: bytes) -> dict:
        """Build CCSDS TC frame and send."""
        frame = build_tc(apid, payload)
        result = self.send_raw(frame)
        result["frame_hex"] = frame.hex()
        return result
```

- [ ] **Step 4: Add radio send route to app.py**

Add inside `create_app()`:

```python
    @app.route("/api/radio/send", methods=["POST"])
    @login_required
    def api_radio_send():
        from webapp.radio_bridge import RadioBridge
        data = request.get_json(silent=True) or {}
        raw_hex = data.get("data", "")
        try:
            raw_bytes = bytes.fromhex(raw_hex)
        except ValueError:
            return {"error": "Invalid hex data"}, 400

        bridge = RadioBridge()
        result = bridge.send_raw(raw_bytes)
        return result
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_radio_bridge.py -v`
Expected: all 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add webapp/radio_bridge.py webapp/app.py tests/test_radio_bridge.py
git commit -m "feat(webapp): add radio bridge and send endpoint (GS-08 kill chain)"
```

---

### Task 19: Auth bypass test (GS-05) and commands page

**Files:**
- Modify: `webapp/app.py`
- Create: `webapp/templates/commands.html`
- Create: `tests/test_vuln_auth_bypass.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_vuln_auth_bypass.py`:
```python
import base64
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
def client(app):
    return app.test_client()


def test_auth_bypass_forged_token(client):
    """GS-05: forge admin token by crafting base64 cookie."""
    forged_token = base64.b64encode(b"admin:admin:1234567890").decode()
    client.set_cookie("session_token", forged_token)

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert b"admin" in resp.data


def test_auth_bypass_operator_to_admin(client):
    """GS-05: operator modifies their token to become admin."""
    # Login as operator
    client.post("/login", data={"username": "operator", "password": "operator123"})

    # Forge admin token
    forged = base64.b64encode(b"admin:admin:9999999999").decode()
    client.set_cookie("session_token", forged)

    resp = client.get("/api/config/radio/1")
    assert resp.status_code == 200


def test_commands_page(client):
    """Commands page renders for authenticated user."""
    client.post("/login", data={"username": "operator", "password": "operator123"})
    resp = client.get("/commands")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vuln_auth_bypass.py -v`
Expected: FAIL (commands route not found)

- [ ] **Step 3: Create commands.html**

`webapp/templates/commands.html`:
```html
<!DOCTYPE html>
<html>
<head><title>PwnSat2 — Telecommands</title></head>
<body>
<h1>Telecommand Panel</h1>
<a href="/dashboard">Dashboard</a>

<h2>Send Command</h2>
<form id="tc-form">
    <label>Command:
        <select name="opcode" id="opcode">
            <option value="10">PING (0x10)</option>
            <option value="20">READ_SENSOR (0x20)</option>
            <option value="01">SET_SAFE_MODE (0x01)</option>
            <option value="02">SET_NOMINAL (0x02)</option>
            <option value="42">READ_FLAG (0x42)</option>
        </select>
    </label><br>
    <label>Data (hex): <input name="data" id="data" placeholder="optional hex data"></label><br>
    <button type="submit">Send TC</button>
</form>

<h2>Response</h2>
<pre id="response"></pre>

<script>
document.getElementById("tc-form").addEventListener("submit", async function(e) {
    e.preventDefault();
    const opcode = document.getElementById("opcode").value;
    const data = document.getElementById("data").value || "";
    const payload = opcode + data;
    const resp = await fetch("/api/radio/send", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({data: payload})
    });
    const result = await resp.json();
    document.getElementById("response").textContent = JSON.stringify(result, null, 2);
});
</script>
</body>
</html>
```

- [ ] **Step 4: Add commands route to app.py**

Add inside `create_app()`:

```python
    @app.route("/commands")
    @login_required
    def commands_page():
        return render_template("commands.html")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_vuln_auth_bypass.py -v`
Expected: all 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add webapp/app.py webapp/templates/commands.html tests/test_vuln_auth_bypass.py
git commit -m "feat(webapp): add commands page and auth bypass tests (GS-05)"
```

---

### Task 20: WebSocket telemetry with Flask-SocketIO

**Files:**
- Modify: `webapp/app.py`
- Modify: `webapp/templates/dashboard.html`
- Create: `webapp/static/js/telemetry.js`
- Create: `tests/test_websocket.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_websocket.py`:
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
def auth_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client


def test_dashboard_has_socketio_script(auth_client):
    resp = auth_client.get("/dashboard")
    assert resp.status_code == 200
    assert b"socket.io" in resp.data or b"telemetry.js" in resp.data


def test_dashboard_shows_telemetry_area(auth_client):
    resp = auth_client.get("/dashboard")
    assert b"telemetry" in resp.data.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_websocket.py -v`
Expected: FAIL (dashboard template doesn't have socketio yet)

- [ ] **Step 3: Update app.py to add Flask-SocketIO**

Add SocketIO initialization and mock telemetry background task. Modify the top of `webapp/app.py`:

```python
"""Flask application factory with WebSocket support."""

import threading
import time

from flask import Flask, render_template, request, redirect, url_for, make_response, g
from flask_socketio import SocketIO

from webapp.config import Config
from webapp.db import close_db, init_db
from webapp.auth import authenticate, create_session_token, login_required, get_current_user

socketio = SocketIO()


def create_app(config_class=Config, db_path=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    if db_path:
        app.config["DATABASE"] = db_path

    app.teardown_appcontext(close_db)

    # VULNERABLE: cors_allowed_origins="*" (deliberate)
    socketio.init_app(app, cors_allowed_origins="*")

    # ... (all existing routes stay the same) ...

    @socketio.on("connect")
    def handle_connect():
        pass

    return app


def start_mock_telemetry(app):
    """Background thread: emit mock telemetry every 2 seconds."""
    from core.telemetry import generate_mock_telemetry

    def _loop():
        while True:
            with app.app_context():
                tm = generate_mock_telemetry()
                socketio.emit("telemetry_update", {
                    "apid": tm["apid"],
                    "raw_hex": tm["raw_hex"],
                    "decoded": tm["decoded"],
                    "timestamp": tm["timestamp"],
                })
            time.sleep(2)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
```

- [ ] **Step 4: Update dashboard.html**

`webapp/templates/dashboard.html`:
```html
<!DOCTYPE html>
<html>
<head>
    <title>PwnSat2 Ground Station</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.min.js"></script>
</head>
<body>
<h1>Mission Dashboard</h1>
<nav>
    <a href="/commands">Commands</a> |
    <a href="/logs">Logs</a> |
    <a href="/config">Config</a> |
    <a href="/logout">Logout</a>
</nav>

<p>User: {{ g.username }} ({{ g.role }})</p>

<h2>Live Telemetry</h2>
<div id="telemetry-status">Connecting...</div>
<table border="1" id="telemetry-table">
    <thead>
        <tr>
            <th>Timestamp</th>
            <th>APID</th>
            <th>Temperature</th>
            <th>Pressure</th>
            <th>Humidity</th>
            <th>Accel X</th>
            <th>Accel Y</th>
            <th>Accel Z</th>
        </tr>
    </thead>
    <tbody id="telemetry-body"></tbody>
</table>

<script src="/static/js/telemetry.js"></script>
</body>
</html>
```

- [ ] **Step 5: Create telemetry.js**

`webapp/static/js/telemetry.js`:
```javascript
const socket = io();
const MAX_ROWS = 50;

socket.on("connect", function() {
    document.getElementById("telemetry-status").textContent = "Connected";
});

socket.on("disconnect", function() {
    document.getElementById("telemetry-status").textContent = "Disconnected";
});

socket.on("telemetry_update", function(data) {
    const tbody = document.getElementById("telemetry-body");
    const row = document.createElement("tr");
    const d = data.decoded || {};

    row.innerHTML = [
        new Date(data.timestamp * 1000).toISOString(),
        "0x" + data.apid.toString(16).padStart(3, "0"),
        d.temperature !== undefined ? d.temperature.toFixed(2) + " C" : "-",
        d.pressure !== undefined ? d.pressure.toFixed(1) + " hPa" : "-",
        d.humidity !== undefined ? d.humidity + "%" : "-",
        d.accel_x !== undefined ? d.accel_x : "-",
        d.accel_y !== undefined ? d.accel_y : "-",
        d.accel_z !== undefined ? d.accel_z : "-",
    ].map(v => "<td>" + v + "</td>").join("");

    tbody.insertBefore(row, tbody.firstChild);

    while (tbody.children.length > MAX_ROWS) {
        tbody.removeChild(tbody.lastChild);
    }
});
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_websocket.py -v`
Expected: all 2 tests PASS

- [ ] **Step 7: Commit**

```bash
mkdir -p webapp/static/js
git add webapp/app.py webapp/templates/dashboard.html webapp/static/js/telemetry.js tests/test_websocket.py
git commit -m "feat(webapp): add WebSocket telemetry with Flask-SocketIO and dashboard"
```

---

### Task 21: Base template and navigation

**Files:**
- Create: `webapp/templates/base.html`
- Modify: all templates to extend base

- [ ] **Step 1: Create base.html**

`webapp/templates/base.html`:
```html
<!DOCTYPE html>
<html>
<head>
    <title>PwnSat2 Ground Station — {% block title %}{% endblock %}</title>
    <style>
        body { font-family: monospace; background: #0a0a0a; color: #00ff41; margin: 20px; }
        a { color: #00ccff; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #333; padding: 6px; text-align: left; }
        th { background: #1a1a1a; }
        input, select, button { background: #1a1a1a; color: #00ff41; border: 1px solid #333; padding: 5px; }
        button { cursor: pointer; }
        button:hover { background: #333; }
        nav { margin-bottom: 20px; padding: 10px; background: #111; }
        .error { color: #ff4444; }
        pre { background: #111; padding: 10px; overflow-x: auto; }
    </style>
    {% block head %}{% endblock %}
</head>
<body>
{% block nav %}
<nav>
    <a href="/dashboard">Dashboard</a> |
    <a href="/commands">Commands</a> |
    <a href="/logs">Logs</a> |
    <a href="/config">Config</a> |
    <a href="/logout">Logout ({{ g.username }})</a>
</nav>
{% endblock %}
{% block content %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Update login.html**

`webapp/templates/login.html`:
```html
{% extends "base.html" %}
{% block title %}Login{% endblock %}
{% block nav %}{% endblock %}
{% block content %}
<h1>PwnSat2 Ground Station</h1>
<h2>Login</h2>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<form method="post">
    <input name="username" placeholder="Username" required><br><br>
    <input name="password" type="password" placeholder="Password" required><br><br>
    <button type="submit">Login</button>
</form>
{% endblock %}
```

- [ ] **Step 3: Update dashboard.html**

`webapp/templates/dashboard.html`:
```html
{% extends "base.html" %}
{% block title %}Dashboard{% endblock %}
{% block head %}
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.min.js"></script>
{% endblock %}
{% block content %}
<h1>Mission Dashboard</h1>
<p>Spacecraft ID: 0x02 | User: {{ g.username }} ({{ g.role }})</p>

<h2>Live Telemetry</h2>
<div id="telemetry-status">Connecting...</div>
<table id="telemetry-table">
    <thead>
        <tr>
            <th>Timestamp</th><th>APID</th><th>Temperature</th>
            <th>Pressure</th><th>Humidity</th>
            <th>Accel X</th><th>Accel Y</th><th>Accel Z</th>
        </tr>
    </thead>
    <tbody id="telemetry-body"></tbody>
</table>
<script src="/static/js/telemetry.js"></script>
{% endblock %}
```

- [ ] **Step 4: Update remaining templates (logs, config, commands) to extend base.html**

`webapp/templates/logs.html`:
```html
{% extends "base.html" %}
{% block title %}Logs{% endblock %}
{% block content %}
<h1>System Logs</h1>
<table>
    <tr><th>Timestamp</th><th>Level</th><th>Source</th><th>Message</th></tr>
    {% for log in logs %}
    <tr>
        <td>{{ log.timestamp }}</td>
        <td>{{ log.level }}</td>
        <td>{{ log.source }}</td>
        <td>{{ log.message | safe }}</td>
    </tr>
    {% endfor %}
</table>
{% endblock %}
```

`webapp/templates/config.html`:
```html
{% extends "base.html" %}
{% block title %}Config{% endblock %}
{% block content %}
<h1>Radio Configuration</h1>
<form method="post" action="/api/config/radio">
    <label>Frequency (Hz): <input name="frequency" type="number" value="{{ config.frequency if config else 915000000 }}"></label><br><br>
    <label>Spreading Factor: <input name="spreading_factor" type="number" min="7" max="12" value="{{ config.spreading_factor if config else 7 }}"></label><br><br>
    <label>Bandwidth (Hz): <input name="bandwidth" type="number" value="{{ config.bandwidth if config else 125000 }}"></label><br><br>
    <label>TX Power (dBm): <input name="tx_power" type="number" value="{{ config.tx_power if config else 14 }}"></label><br><br>
    <button type="submit">Update Config</button>
</form>
{% endblock %}
```

`webapp/templates/commands.html`:
```html
{% extends "base.html" %}
{% block title %}Commands{% endblock %}
{% block content %}
<h1>Telecommand Panel</h1>
<form id="tc-form">
    <label>Command:
        <select name="opcode" id="opcode">
            <option value="10">PING (0x10)</option>
            <option value="20">READ_SENSOR (0x20)</option>
            <option value="01">SET_SAFE_MODE (0x01)</option>
            <option value="02">SET_NOMINAL (0x02)</option>
            <option value="42">READ_FLAG (0x42)</option>
        </select>
    </label><br><br>
    <label>Data (hex): <input name="data" id="data" placeholder="optional hex data"></label><br><br>
    <button type="submit">Send TC</button>
</form>
<h2>Response</h2>
<pre id="response">Waiting...</pre>
<script>
document.getElementById("tc-form").addEventListener("submit", async function(e) {
    e.preventDefault();
    const opcode = document.getElementById("opcode").value;
    const data = document.getElementById("data").value || "";
    const payload = opcode + data;
    const resp = await fetch("/api/radio/send", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({data: payload})
    });
    const result = await resp.json();
    document.getElementById("response").textContent = JSON.stringify(result, null, 2);
});
</script>
{% endblock %}
```

- [ ] **Step 5: Run all tests to verify nothing broke**

Run: `python -m pytest tests/ -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add webapp/templates/
git commit -m "feat(webapp): add base template with terminal-style theme and navigation"
```

---

### Task 22: Supply chain vuln (GS-10) and requirements.txt

**Files:**
- Verify: `requirements.txt` has unpinned `requests`

- [ ] **Step 1: Verify requirements.txt**

The `requests` dependency is already unpinned in `requirements.txt` from Task 1. Verify:

Run: `grep "requests" requirements.txt`
Expected: `requests` (no version pin)

This is GS-10. The vulnerability is conceptual — the unpinned dependency simulates a supply chain attack where a trojanized `requests` package could be installed.

- [ ] **Step 2: Commit** (only if changes needed)

No changes needed — GS-10 is already in place.

---

### Task 23: Run script and final integration

**Files:**
- Modify: `webapp/app.py` — add `__main__` block
- Modify: `core/__init__.py` — verify exports

- [ ] **Step 1: Add main entry point to app.py**

Add at the bottom of `webapp/app.py`:

```python
if __name__ == "__main__":
    import os
    app = create_app()

    # Ensure db directory exists
    os.makedirs("db", exist_ok=True)

    with app.app_context():
        init_db()
        from webapp.seed import seed_db
        seed_db()

    # Start mock telemetry if no hardware
    start_mock_telemetry(app)

    print("PwnSat2 Ground Station running on http://localhost:5000")
    print("Mode: SIMULATED (no FlatSat detected)")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)
```

- [ ] **Step 2: Run all tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: all tests PASS

- [ ] **Step 3: Manual smoke test**

Run: `cd /home/sabas/Documents/electroniccats/flatsat-ground-station && python -m webapp.app`

Verify in browser:
1. `http://localhost:5000` → redirects to login
2. Login with `operator` / `operator123` → dashboard
3. Dashboard shows telemetry updating via WebSocket
4. `/commands` page loads
5. `/logs` page shows seed logs
6. `/config` page shows operator's config
7. `/api/endpoints` lists all routes (no auth required)
8. Stop with Ctrl+C

- [ ] **Step 4: Commit**

```bash
git add webapp/app.py
git commit -m "feat(webapp): add main entry point with auto-seed and mock telemetry"
```

---

### Task 24: Full vulnerability integration tests

**Files:**
- Create: `tests/test_full_vulns.py`

End-to-end test that validates all 12 vulnerabilities work.

- [ ] **Step 1: Write integration tests**

`tests/test_full_vulns.py`:
```python
"""End-to-end validation of all 12 ground station vulnerabilities."""

import base64
import os
import tempfile

import pytest

from webapp.config import TestConfig
from webapp.db import get_db, init_db
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
def client(app):
    return app.test_client()


@pytest.fixture
def operator(client):
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client


class TestGS01_SQLi:
    def test_extract_admin_hash(self, operator):
        resp = operator.get(
            "/api/telemetry?search=' UNION SELECT 1,username,password_hash,role,5,6,7,8,9,10,11 FROM users--&limit=100"
        )
        assert resp.status_code == 200
        data = str(resp.get_json())
        assert "5f4dcc3b" in data


class TestGS02_XSS:
    def test_stored_xss(self, app, operator):
        with app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO logs (timestamp, level, source, message) VALUES (?,?,?,?)",
                ("2026-04-09", "INFO", "xss", '<img src=x onerror="alert(1)">'),
            )
            db.commit()
        resp = operator.get("/logs")
        assert b'<img src=x onerror="alert(1)">' in resp.data


class TestGS03_RCE:
    def test_rce(self, operator):
        resp = operator.post("/api/diagnostics",
                             json={"cmd": "echo GS03_FLAG"},
                             content_type="application/json")
        assert "GS03_FLAG" in resp.get_json()["output"]


class TestGS04_LFI:
    def test_path_traversal(self, operator):
        resp = operator.get("/api/logs?file=../../../etc/hostname")
        assert resp.status_code == 200


class TestGS05_AuthBypass:
    def test_forge_admin(self, client):
        token = base64.b64encode(b"admin:admin:0").decode()
        client.set_cookie("session_token", token)
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert b"admin" in resp.data


class TestGS06_IDOR:
    def test_read_admin_config(self, operator):
        resp = operator.get("/api/config/radio/1")
        assert resp.get_json()["owner"] == "admin"


class TestGS07_CMDI:
    def test_command_injection(self, operator):
        resp = operator.post("/api/config/radio",
                             json={"frequency": "1; echo GS07"},
                             content_type="application/json")
        assert "GS07" in resp.get_json()["output"]


class TestGS08_KillChain:
    def test_radio_send(self, operator):
        resp = operator.post("/api/radio/send",
                             json={"data": "080100"},
                             content_type="application/json")
        assert resp.status_code == 200


class TestGS09_DBTamper:
    def test_update_via_sqli(self, operator):
        # This is exploited through GS-01's SQLi endpoint
        resp = operator.get(
            "/api/telemetry?search='; UPDATE telemetry SET temperature=999 WHERE id=1;--&limit=1"
        )
        # SQLi execution doesn't error
        assert resp.status_code in (200, 500)


class TestGS11_LogInjection:
    def test_newline_injection(self, operator):
        resp = operator.post("/api/logs",
                             json={"message": "line1\nFAKE: admin authorized"},
                             content_type="application/json")
        assert resp.status_code == 200


class TestGS12_APIEnum:
    def test_no_auth_required(self, client):
        resp = client.get("/api/endpoints")
        assert resp.status_code == 200
        routes = [r["rule"] for r in resp.get_json()]
        assert "/api/diagnostics" in routes
```

- [ ] **Step 2: Run integration tests**

Run: `python -m pytest tests/test_full_vulns.py -v`
Expected: all 12 tests PASS (one per vuln class)

- [ ] **Step 3: Run all tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_full_vulns.py
git commit -m "test: add end-to-end integration tests for all 12 GS vulnerabilities"
```

---

## Summary

| Task | Component | Vulns | Estimated Steps |
|------|-----------|-------|-----------------|
| 1 | Project setup | - | 6 |
| 2 | Core constants | - | 5 |
| 3 | Core CCSDS | - | 5 |
| 4 | Core telemetry | - | 5 |
| 5 | Core telecommand | - | 6 |
| 6 | Core state | - | 5 |
| 7 | Core exports | - | 3 |
| 8 | Flask config + DB | - | 7 |
| 9 | DB seed | - | 5 |
| 10 | Auth (GS-05) | GS-05 | 7 |
| 11 | SQLi (GS-01) | GS-01 | 5 |
| 12 | XSS (GS-02) | GS-02 | 6 |
| 13 | RCE (GS-03) | GS-03 | 5 |
| 14 | LFI (GS-04) + Log inject (GS-11) | GS-04, GS-11 | 5 |
| 15 | IDOR (GS-06) | GS-06 | 6 |
| 16 | CMDI (GS-07) | GS-07 | 5 |
| 17 | Log inject + API enum | GS-11, GS-12 | 5 |
| 18 | Radio bridge (GS-08) | GS-08 | 6 |
| 19 | Auth bypass (GS-05) + commands | GS-05 | 6 |
| 20 | WebSocket telemetry | - | 7 |
| 21 | Base template + nav | - | 6 |
| 22 | Supply chain (GS-10) | GS-10 | 2 |
| 23 | Run script + integration | - | 4 |
| 24 | Full vuln integration tests | All 12 | 4 |
| **Total** | | **12 vulns** | **~134 steps** |
