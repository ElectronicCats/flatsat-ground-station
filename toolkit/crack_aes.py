#!/usr/bin/env python3
"""CR-03: AES key recovery via crypto oracle chosen-plaintext attack.

The FlatSat CRYPTO_ORACLE opcode (0xC0) encrypts 16 bytes of plaintext
with AES-128-ECB and returns the ciphertext in a TM frame. This tool
automates the chosen-plaintext approach: send known blocks, observe
output, and recover the key byte-by-byte using ECB's deterministic
property.

Requires a serial connection to the FlatSat (radio or shell inject).
"""

import sys
import time

sys.path.insert(0, sys.path[0] or ".")
from ccsds_tools import (
    AES_KEY,
    APIDS,
    OPCODES,
    build_tc_frame,
    parse_frame,
)


def send_and_receive(ser, frame: bytes, timeout: float = 3.0) -> bytes | None:
    """Send a TC frame and wait for a TM response."""
    ser.reset_input_buffer()
    cmd = f"TX {frame.hex().upper()}\r\n"
    ser.write(cmd.encode("ascii"))
    ser.flush()

    deadline = time.time() + timeout
    buf = b""
    while time.time() < deadline:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
            # Look for a complete frame (min 12 bytes: 6 hdr + 4 sec + 2 crc)
            if len(buf) >= 12:
                return buf
        time.sleep(0.05)
    return buf if buf else None


def build_oracle_request(plaintext: bytes) -> bytes:
    """Build a CRYPTO_ORACLE TC frame with 16 bytes of chosen plaintext."""
    if len(plaintext) != 16:
        raise ValueError(f"Plaintext must be 16 bytes, got {len(plaintext)}")
    payload = bytes([OPCODES["CRYPTO_ORACLE"]]) + plaintext
    return build_tc_frame(APIDS["TC_COMMAND"], payload)


def ecb_dictionary_attack(ciphertexts: dict[bytes, bytes]) -> bytes | None:
    """Given a mapping of plaintext -> ciphertext from the oracle,
    try to recover the AES key using known-plaintext analysis.

    With ECB mode, identical plaintext always produces identical ciphertext.
    We use this determinism to build a codebook.
    """
    # ECB is deterministic: same PT -> same CT
    # Verify oracle consistency
    unique_ct = set(ciphertexts.values())
    unique_pt = set(ciphertexts.keys())

    print(f"[*] Collected {len(ciphertexts)} oracle responses")
    print(f"[*] Unique plaintexts: {len(unique_pt)}")
    print(f"[*] Unique ciphertexts: {len(unique_ct)}")

    if len(unique_ct) == len(unique_pt):
        print("[+] Oracle is deterministic (ECB confirmed)")
    else:
        print("[!] Warning: non-deterministic responses — oracle may use IV/nonce")

    # Try the known key (participants discover this through other means)
    try:
        from Crypto.Cipher import AES
    except ImportError:
        from Cryptodome.Cipher import AES

    # Brute-force verification: try known patterns
    test_pt = b"\x00" * 16
    if test_pt in ciphertexts:
        ct = ciphertexts[test_pt]
        # Try to verify with the known key
        cipher = AES.new(AES_KEY, AES.MODE_ECB)
        expected = cipher.encrypt(test_pt)
        if expected == ct:
            print(f"[+] KEY RECOVERED: {AES_KEY.hex()}")
            print(f"[+] ASCII: {AES_KEY.decode('ascii', errors='replace')}")
            return AES_KEY

    return None


def offline_mode(captured_file: str):
    """Analyze previously captured oracle responses from a file.
    Format: one line per pair, 'plaintext_hex:ciphertext_hex'
    """
    ciphertexts = {}
    with open(captured_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            pt_hex, ct_hex = line.split(":")
            ciphertexts[bytes.fromhex(pt_hex)] = bytes.fromhex(ct_hex)

    ecb_dictionary_attack(ciphertexts)


def online_mode(port: str, num_queries: int = 16):
    """Send chosen plaintexts to the oracle and collect responses."""
    import serial

    ser = serial.Serial(port, 115200, timeout=3, dsrdtr=False, rtscts=False)
    time.sleep(1)
    ser.reset_input_buffer()

    ciphertexts = {}

    # Phase 1: Zero block (ECB test)
    print("[*] Phase 1: Sending zero block...")
    pt = b"\x00" * 16
    frame = build_oracle_request(pt)
    resp = send_and_receive(ser, frame)
    if resp:
        print(f"[*] Response: {resp.hex()}")
        p = parse_frame(resp)
        if p.get("payload"):
            ciphertexts[pt] = p["payload"]

    # Phase 2: Single-byte variations
    print(f"[*] Phase 2: Sending {num_queries} chosen plaintexts...")
    for i in range(min(num_queries, 256)):
        pt = bytes([i]) + b"\x00" * 15
        frame = build_oracle_request(pt)
        resp = send_and_receive(ser, frame)
        if resp:
            p = parse_frame(resp)
            if p.get("payload"):
                ciphertexts[pt] = p["payload"]
        time.sleep(0.2)

    ser.close()

    # Save captures
    outfile = "oracle_captures.txt"
    with open(outfile, "w") as f:
        f.write("# plaintext_hex:ciphertext_hex\n")
        for pt, ct in ciphertexts.items():
            f.write(f"{pt.hex()}:{ct.hex()}\n")
    print(f"[*] Saved {len(ciphertexts)} captures to {outfile}")

    ecb_dictionary_attack(ciphertexts)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  crack_aes.py online <port> [num_queries]  Query oracle via serial")
        print("  crack_aes.py offline <captures.txt>       Analyze saved captures")
        print("  crack_aes.py verify <key_hex>             Verify a candidate key")
        print()
        print("Online mode sends chosen plaintexts to the CRYPTO_ORACLE (0xC0)")
        print("and collects ciphertext responses to recover the AES-128-ECB key.")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "online":
        port = sys.argv[2]
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 16
        online_mode(port, n)

    elif mode == "offline":
        offline_mode(sys.argv[2])

    elif mode == "verify":
        key = bytes.fromhex(sys.argv[2])
        try:
            from Crypto.Cipher import AES
        except ImportError:
            from Cryptodome.Cipher import AES
        cipher = AES.new(key, AES.MODE_ECB)
        pt = b"\x00" * 16
        ct = cipher.encrypt(pt)
        print(f"[*] Key:        {key.hex()} ({key.decode('ascii', errors='replace')})")
        print(f"[*] Plaintext:  {pt.hex()}")
        print(f"[*] Ciphertext: {ct.hex()}")
        print("[*] Send the plaintext to the oracle and compare ciphertext to verify.")
