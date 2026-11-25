#!/usr/bin/env python3
"""
Attack 00: Unauthenticated Black-Box APID Enumeration (RF Variant via Radio 1 RF Uplink)
Transmits APID probe packets over 916 MHz RF uplink.
"""
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../lib")))
from pwnsat_packets import build_ccsds_packet
from pwnsat_rf import FlatSatRF

def main():
    print("[+] Attack 00: APID Enumeration (Over-The-Air RF 916 MHz Variant)")
    rf = FlatSatRF()
    print("[*] Scanning APIDs 0x00 to 0x1F over-the-air via Radio 1 (916.0 MHz)...")
    for apid in range(0x00, 0x20):
        packet = build_ccsds_packet(apid=apid, payload=b"\x00")
        print(f" -> [RF 916.0 MHz] Transmitting APID probe 0x{apid:02X}...")
        rf.transmit_rf(packet)
        time.sleep(0.1)

    print("[✓] RF APID Enumeration complete.")

if __name__ == "__main__":
    main()
