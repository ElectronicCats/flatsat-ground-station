"""Telecommand builder with AES-128-ECB encryption.

Builds TC frames for the FlatSat. Supports plain commands and
AES-encrypted privileged commands (TC_OP_PRIVILEGED 0xD0).
"""

from core.ccsds import build_tc
from core.constants import (
    AES_KEY_HARDCODED,
    APID_TC_COMMAND,
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
    """Build a telecommand frame with opcode + optional data."""
    global _tc_seq_count
    if seq_count is None:
        seq_count = _tc_seq_count
        _tc_seq_count = (_tc_seq_count + 1) & 0x3FFF

    payload = bytes([opcode]) + data
    return build_tc(APID_TC_COMMAND, payload, seq_count=seq_count)


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
    return build_tc(APID_TC_COMMAND, payload, seq_count=seq_count)
