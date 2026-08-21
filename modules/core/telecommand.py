"""Telecommand builder with AES encryption.

Builds TC frames for the FlatSat. Supports plain commands and
AES-encrypted privileged commands (TC_OP_PRIVILEGED 0xD0).
SDLS Level 3 uses AES-128-CTR with IV derived from frame MET timestamp.
"""

import struct
import time as _time

from modules.core.ccsds import build_tc
from modules.core.constants import (
    AES_KEY_HARDCODED,
    APID_TC_COMMAND,
    APID_TC_SET_DIFFICULTY,
    APID_TC_SET_FREQ,
    APID_TC_SET_POWER,
    TC_OP_PRIVILEGED,
    XOR_KEY,
)

_tc_seq_count = 1  # Start at 1: firmware anti-replay at difficulty=3 rejects seq_count=0


def _aes_ecb_encrypt(key: bytes, plaintext: bytes) -> bytes:
    """AES-128-ECB encrypt a single 16-byte block."""
    try:
        from Crypto.Cipher import AES

        cipher = AES.new(key, AES.MODE_ECB)
        return cipher.encrypt(plaintext)
    except ImportError:
        pass

    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

        cipher = Cipher(algorithms.AES(key), modes.ECB())
        encryptor = cipher.encryptor()
        return encryptor.update(plaintext) + encryptor.finalize()
    except ImportError:
        pass

    raise ImportError("No AES library available. Install pycryptodome or cryptography: pip install pycryptodome")


def xor_encrypt(data: bytes) -> bytes:
    """XOR encrypt/decrypt with the hardcoded key."""
    key = XOR_KEY
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


xor_decrypt = xor_encrypt


def build_command_tc(opcode: int, data: bytes = b"", seq_count: int | None = None) -> bytes:
    """Build a telecommand frame with opcode + optional data.

    Timestamp is set to current epoch (truncated to uint32) so the SDLS
    CTR IV is unique per frame.
    """
    global _tc_seq_count
    if seq_count is None:
        seq_count = _tc_seq_count
        _tc_seq_count = (_tc_seq_count + 1) & 0x3FFF

    payload = bytes([opcode]) + data
    timestamp = int(_time.time()) & 0xFFFFFFFF
    return build_tc(APID_TC_COMMAND, payload, seq_count=seq_count, timestamp=timestamp)


def build_privileged_tc(inner_opcode: int, inner_data: bytes = b"", seq_count: int | None = None) -> bytes:
    """Build an AES-encrypted privileged telecommand.

    Encrypted payload format (16 bytes):
        [inner_opcode][0x50 magic][14 bytes data (zero-padded)]
    """
    global _tc_seq_count
    if seq_count is None:
        seq_count = _tc_seq_count
        _tc_seq_count = (_tc_seq_count + 1) & 0x3FFF

    plaintext = bytes([inner_opcode, 0x50]) + inner_data
    plaintext = plaintext[:16].ljust(16, b"\x00")

    encrypted = _aes_ecb_encrypt(AES_KEY_HARDCODED, plaintext)
    payload = bytes([TC_OP_PRIVILEGED]) + encrypted
    timestamp = int(_time.time()) & 0xFFFFFFFF
    return build_tc(APID_TC_COMMAND, payload, seq_count=seq_count, timestamp=timestamp)


def build_difficulty_tc(level: int, seq_count: int | None = None) -> bytes:
    """Build a difficulty telecommand frame (APID 0x027) with difficulty level."""
    global _tc_seq_count
    if seq_count is None:
        seq_count = _tc_seq_count
        _tc_seq_count = (_tc_seq_count + 1) & 0x3FFF

    payload = bytes([level])
    timestamp = int(_time.time()) & 0xFFFFFFFF
    return build_tc(APID_TC_SET_DIFFICULTY, payload, seq_count=seq_count, timestamp=timestamp)


def build_frequency_tc(radio_idx: int, frequency_hz: int, seq_count: int | None = None) -> bytes:
    """Build a frequency setting telecommand frame (APID 0x021) with radio index and frequency."""
    global _tc_seq_count
    if seq_count is None:
        seq_count = _tc_seq_count
        _tc_seq_count = (_tc_seq_count + 1) & 0x3FFF

    # Payload format: [radio_idx (1 byte)][frequency_hz (4 bytes, little-endian uint32)]
    payload = struct.pack("<BI", radio_idx, frequency_hz)
    timestamp = int(_time.time()) & 0xFFFFFFFF
    return build_tc(APID_TC_SET_FREQ, payload, seq_count=seq_count, timestamp=timestamp)


def build_power_tc(radio_idx: int, power_dbm: int, seq_count: int | None = None) -> bytes:
    """Build a power setting telecommand frame (APID 0x022) with radio index and power."""
    global _tc_seq_count
    if seq_count is None:
        seq_count = _tc_seq_count
        _tc_seq_count = (_tc_seq_count + 1) & 0x3FFF

    # Payload format: [radio_idx (1 byte)][power_dbm (1 byte, signed int8)]
    payload = struct.pack("<Bb", radio_idx, power_dbm)
    timestamp = int(_time.time()) & 0xFFFFFFFF
    return build_tc(APID_TC_SET_POWER, payload, seq_count=seq_count, timestamp=timestamp)

