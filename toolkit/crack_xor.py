#!/usr/bin/env python3
"""CR-02: Recover XOR encryption key via known-plaintext attack."""

import sys

sys.path.insert(0, sys.path[0] or ".")


def recover_xor_key(encrypted: bytes, known_plaintext: bytes) -> bytes:
    """XOR encrypted data with known plaintext to recover key"""
    key_stream = bytes(e ^ p for e, p in zip(encrypted, known_plaintext, strict=False))
    # Find repeating key pattern
    for key_len in range(1, 17):
        candidate = key_stream[:key_len]
        if all(key_stream[i] == candidate[i % key_len] for i in range(min(len(key_stream), key_len * 3))):
            return candidate
    return key_stream


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: crack_xor.py <encrypted_hex> <known_plaintext_hex>")
        print("Example: crack_xor.py <captured_payload> <known_ccsds_header>")
        sys.exit(1)

    encrypted = bytes.fromhex(sys.argv[1])
    known = bytes.fromhex(sys.argv[2])

    key = recover_xor_key(encrypted, known)
    print(f"[*] Recovered key ({len(key)} bytes): {key.hex()}")
    print(f"[*] ASCII: {key.decode('ascii', errors='replace')}")

    # Decrypt full payload
    decrypted = bytes(encrypted[i] ^ key[i % len(key)] for i in range(len(encrypted)))
    print(f"[*] Decrypted: {decrypted.hex()}")
    print(f"[*] ASCII: {decrypted.decode('ascii', errors='replace')}")
