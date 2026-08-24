"""Edge-case tests for short inputs, malformed frames, telemetry truncation, and import parity."""

import pytest

from core.ccsds import (
    build_tc,
    detect_tm_difficulty,
    parse_frame,
    sdls_protect_frame,
    sdls_unprotect_frame,
)
from core.constants import APID_TC_COMMAND, TC_OP_PING
from core.telemetry import (
    decode_all_sensors,
    decode_bme280,
    decode_gps_sim,
    decode_heartbeat,
    decode_lis2dh,
    decode_power,
    decode_tm_payload,
)


@pytest.mark.parametrize("diff", [0, 1, 2, 3])
@pytest.mark.parametrize(
    "short_input",
    [
        b"",
        b"\x00",
        b"\x08\x01\xc0\x00",
        b"123456789",
        b"\x00" * 10,
        b"\x00" * 11,
    ],
)
def test_sdls_protect_short_inputs(short_input, diff):
    """Ensure sdls_protect_frame raises ValueError on inputs shorter than 12 bytes for diff >= 2."""
    if diff < 2:
        assert sdls_protect_frame(short_input, difficulty=diff) == short_input
    else:
        with pytest.raises(ValueError):
            sdls_protect_frame(short_input, difficulty=diff)


@pytest.mark.parametrize("diff", [0, 1, 2, 3])
@pytest.mark.parametrize(
    "short_input",
    [
        b"",
        b"\x00",
        b"123456789",
        b"\x00" * 10,
        b"\x00" * 11,
    ],
)
def test_sdls_unprotect_short_inputs(short_input, diff):
    """Ensure sdls_unprotect_frame safely falls back on short inputs without raising struct.error."""
    result = sdls_unprotect_frame(short_input, difficulty=diff)
    assert result == short_input


def test_parse_frame_edge_cases():
    assert parse_frame(b"") is None
    assert parse_frame(b"\x00" * 5) is None
    assert parse_frame(b"\x00" * 11) is None
    # Truncated payload against primary header data_length
    truncated = b"\x08\x01\xc0\x00\x00\x50\x00\x00\x00\x01\x00\x00"
    assert parse_frame(truncated) is None


def test_detect_tm_difficulty_edge_cases():
    assert detect_tm_difficulty(b"") is None
    assert detect_tm_difficulty(b"\x00" * 5) is None
    assert detect_tm_difficulty(b"\x00" * 12) is None


def test_decode_telemetry_truncated_payloads():
    hb = decode_heartbeat(b"\x02\x00\x00")
    assert hb == {}

    bme = decode_bme280(b"\x01\x02")
    assert bme == {}

    lis = decode_lis2dh(b"\x01\x02\x03")
    assert lis == {}

    pwr = decode_power(b"\x01\x02")
    assert pwr == {}

    gps = decode_gps_sim(b"\x01\x02")
    assert gps == {}

    all_sens = decode_all_sensors(b"\x01\x02")
    assert all_sens == {}

    tm = decode_tm_payload(0x001, b"\x02\x00")
    assert tm == {}


def test_legacy_and_canonical_import_equivalence():
    """Verify that both legacy (core.*) and canonical (modules.core.*) imports yield identical objects."""
    import core.ccsds as legacy_ccsds
    import modules.core.ccsds as canonical_ccsds

    assert legacy_ccsds.build_tm is canonical_ccsds.build_tm
    assert legacy_ccsds.parse_frame is canonical_ccsds.parse_frame

    import core.constants as legacy_const
    import modules.core.constants as canonical_const

    assert legacy_const.APID_TM_HEARTBEAT == canonical_const.APID_TM_HEARTBEAT
    assert legacy_const.AES_KEY_HARDCODED == canonical_const.AES_KEY_HARDCODED

    import modules.webapp.auth as canonical_auth
    import webapp.auth as legacy_auth

    assert legacy_auth.create_session_token is canonical_auth.create_session_token
