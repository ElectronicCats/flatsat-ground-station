"""CCSDS Space Packet Protocol encoder/decoder with SDLS support.

Matches firmware implementation in flatsat/src/ccsds/ccsds_spp.c
and flatsat/src/ccsds/ccsds_sdls.c.
Big-endian headers per CCSDS 133.0-B-2.
"""

import struct
from dataclasses import dataclass

from core.constants import (
    AES_KEY_HARDCODED,
    APID_TM_HEARTBEAT,
    CCSDS_CRC_SIZE,
    CCSDS_HDR_SIZE,
    CCSDS_MAX_PAYLOAD,
    CCSDS_SEC_HDR_SIZE,
    CCSDS_SEQ_STANDALONE,
    CCSDS_SPACECRAFT_ID,
    CCSDS_TYPE_TC,
    CCSDS_TYPE_TM,
    CCSDS_VERSION,
    XOR_KEY,
)


@dataclass
class CcsdsPacket:
    pkt_type: int
    sec_hdr_flag: int
    apid: int
    seq_flags: int
    seq_count: int
    timestamp: int
    payload: bytes
    crc_valid: bool
    raw: bytes = b""


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


def _aes_ecb_encrypt(data: bytes) -> bytes:
    """AES-128-ECB encrypt (no padding). Input must be multiple of 16."""
    try:
        from Crypto.Cipher import AES

        return AES.new(AES_KEY_HARDCODED, AES.MODE_ECB).encrypt(data)
    except ImportError:
        pass
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    enc = Cipher(algorithms.AES(AES_KEY_HARDCODED), modes.ECB()).encryptor()
    return enc.update(data) + enc.finalize()


def _aes_ecb_decrypt(data: bytes) -> bytes:
    """AES-128-ECB decrypt (no padding). Input must be multiple of 16."""
    try:
        from Crypto.Cipher import AES

        return AES.new(AES_KEY_HARDCODED, AES.MODE_ECB).decrypt(data)
    except ImportError:
        pass
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    dec = Cipher(algorithms.AES(AES_KEY_HARDCODED), modes.ECB()).decryptor()
    return dec.update(data) + dec.finalize()


def _aes_ctr_transform(data: bytes, iv: bytes) -> bytes:
    """AES-128-CTR encrypt/decrypt (same operation). IV must be 16 bytes."""
    try:
        from Crypto.Cipher import AES

        cipher = AES.new(AES_KEY_HARDCODED, AES.MODE_CTR, nonce=b"", initial_value=iv)
        return cipher.encrypt(data)
    except ImportError:
        pass
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    cipher = Cipher(algorithms.AES(AES_KEY_HARDCODED), modes.CTR(iv))
    enc = cipher.encryptor()
    return enc.update(data) + enc.finalize()


def _sdls_transform_payload(
    payload: bytearray, difficulty: int, decrypt: bool = False, timestamp: int = 0
) -> bytearray:
    """XOR or AES transform payload in-place, matching firmware block handling.

    Difficulty 2: XOR with PWNSAT key (symmetric).
    Difficulty 3+: AES-128-CTR with IV derived from MET timestamp.
    """
    if difficulty == 2:
        # XOR (symmetric — same op for encrypt and decrypt)
        for i in range(len(payload)):
            payload[i] ^= XOR_KEY[i % len(XOR_KEY)]
    else:
        # AES-128-CTR: IV derived from MET (first 4 bytes), rest zero
        iv = timestamp.to_bytes(4, "big") + b"\x00" * 12
        result = _aes_ctr_transform(bytes(payload), iv)
        payload[:] = result
    return payload


def sdls_protect_frame(frame: bytes, difficulty: int) -> bytes:
    """Encrypt outgoing TC payload to match firmware main.c process_incoming_telecommand().

    Level 0-1: plaintext.  Level 2: XOR.  Level 3+: AES-128-CTR.
    Only payload bytes are encrypted. Per CCSDS 133.0-B-2 and firmware main.c line 356,
    the CRC is recalculated over the transmitted frame (ciphertext payload) so
    expected_crc == actual_crc on the receiving end.
    """
    if difficulty < 2:
        return frame
    payload_start = CCSDS_HDR_SIZE + CCSDS_SEC_HDR_SIZE
    payload_end = len(frame) - CCSDS_CRC_SIZE
    payload = bytearray(frame[payload_start:payload_end])
    # Extract timestamp from secondary header for CTR IV
    timestamp = struct.unpack(">I", frame[CCSDS_HDR_SIZE : CCSDS_HDR_SIZE + 4])[0]
    _sdls_transform_payload(payload, difficulty, decrypt=False, timestamp=timestamp)

    frame_no_crc = frame[:payload_start] + bytes(payload)
    new_crc = ccsds_crc16(frame_no_crc)
    return frame_no_crc + struct.pack(">H", new_crc)


def sdls_unprotect_frame(frame: bytes, difficulty: int) -> bytes:
    """Decrypt incoming TM payload to match firmware sdls_protect_frame().

    Level 0-1: plaintext.  Level 2: XOR.  Level 3+: AES-128-CTR.
    Only payload bytes are decrypted; header and CRC are untouched.

    Note: observed firmware computes the CRC *after* encrypting (encrypt-then-CRC),
    so the CRC authenticates the ciphertext, not the plaintext. Callers should
    therefore validate the CRC on the frame as received and use this function only
    to recover the plaintext payload for decoding. The RX path in
    ``webapp/app.py`` stays robust to both orderings.
    """
    if difficulty < 2:
        return frame
    payload_start = CCSDS_HDR_SIZE + CCSDS_SEC_HDR_SIZE
    payload_end = len(frame) - CCSDS_CRC_SIZE
    payload = bytearray(frame[payload_start:payload_end])
    timestamp = struct.unpack(">I", frame[CCSDS_HDR_SIZE : CCSDS_HDR_SIZE + 4])[0]
    _sdls_transform_payload(payload, difficulty, decrypt=True, timestamp=timestamp)
    frame_no_crc = frame[:payload_start] + bytes(payload)
    new_crc = ccsds_crc16(frame_no_crc)
    return frame_no_crc + struct.pack(">H", new_crc)




def build_packet_id(pkt_type: int, apid: int) -> int:
    """Build 16-bit packet_id: version(3) | type(1) | sec_hdr(1) | apid(11)."""
    return ((CCSDS_VERSION & 0x7) << 13) | ((pkt_type & 0x1) << 12) | (1 << 11) | (apid & 0x7FF)


#: Difficulty levels the TM path may have been encrypted with, most secure first.
SDLS_DIFFICULTY_CANDIDATES = (3, 2, 1)


def detect_tm_difficulty(frame: bytes) -> int | None:
    """Recover the satellite's SDLS difficulty from a heartbeat frame (APID 0x001).

    The ground station holds the keys but cannot read the difficulty field out of
    an encrypted heartbeat without first knowing the difficulty. Instead of
    guessing, trial-decrypt at each candidate level and keep the one whose
    plaintext satisfies the heartbeat's structural invariants:

      * ``sc_id`` equals CCSDS_SPACECRAFT_ID
      * ``uptime`` equals the secondary-header timestamp (firmware assigns both
        from the same ``k_uptime_get() / 1000`` in one loop iteration)
      * ``flight_mode`` is in range, and the reported ``difficulty`` agrees with
        the level that decrypted the frame

    Those checks span ~40 bits, so a false positive is not a practical concern.
    Levels 0 and 1 are both plaintext on the wire, so a single plaintext trial
    covers them and the reported value is returned verbatim.

    Returns None when the frame is not a usable heartbeat or nothing validates
    (e.g. a difficulty the firmware gained after this code was written).
    """
    pkt = parse_frame(frame)
    if pkt is None or pkt.apid != APID_TM_HEARTBEAT or len(pkt.payload) < 13:
        return None

    for level in SDLS_DIFFICULTY_CANDIDATES:
        payload = bytearray(pkt.payload[:13])
        if level >= 2:
            _sdls_transform_payload(payload, level, decrypt=True, timestamp=pkt.timestamp)
        sc_id, uptime, _battery_mv, flight_mode, difficulty = struct.unpack("<BIHBB", bytes(payload)[:9])
        if sc_id != CCSDS_SPACECRAFT_ID or uptime != pkt.timestamp or flight_mode > 3:
            continue
        if level >= 2 and difficulty == level:
            return level
        if level < 2 and difficulty < 2:
            # Plaintext trial: 0 and 1 are indistinguishable on the wire.
            return difficulty
    return None


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


def _build_frame(pkt_type: int, apid: int, payload: bytes, seq_count: int, timestamp: int) -> bytes:
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


def parse_frame(raw: bytes) -> CcsdsPacket | None:
    """Parse a raw CCSDS frame. Returns None if too short or truncated."""
    min_size = CCSDS_HDR_SIZE + CCSDS_SEC_HDR_SIZE + CCSDS_CRC_SIZE
    if len(raw) < min_size:
        return None

    packet_id, seq_ctrl, data_length = struct.unpack(">HHH", raw[:6])
    pkt_type, sec_hdr_flag, apid = parse_packet_id(packet_id)
    seq_flags, seq_count = parse_seq_ctrl(seq_ctrl)

    # Use data_length to determine actual frame boundary
    total_length = CCSDS_HDR_SIZE + data_length + 1
    if len(raw) < total_length:
        return None

    timestamp = struct.unpack(">I", raw[6:10])[0]

    payload_end = total_length - CCSDS_CRC_SIZE
    payload = raw[10:payload_end]

    expected_crc = ccsds_crc16(raw[:payload_end])
    actual_crc = struct.unpack(">H", raw[payload_end:total_length])[0]

    return CcsdsPacket(
        pkt_type=pkt_type,
        sec_hdr_flag=sec_hdr_flag,
        apid=apid,
        seq_flags=seq_flags,
        seq_count=seq_count,
        timestamp=timestamp,
        payload=payload,
        crc_valid=(expected_crc == actual_crc),
        raw=raw[:total_length],
    )
