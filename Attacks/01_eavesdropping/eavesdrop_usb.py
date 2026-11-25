#!/usr/bin/env python3
"""
Attack 01: Passive Downlink Decryption (USB Variant)
Monitors Cat-Radio0 downlink telemetry and decrypts AES-128 static key payloads.
"""
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../lib")))
from flatsat_usb import FlatSatUSB

def main():
    print("[+] Attack 01: Passive Downlink Decryption (flat-sat-fw-interno USB Variant)")
    usb = FlatSatUSB()
    if not usb.connect():
        print("[X] Failed to connect to FlatSat USB serial port.")
        sys.exit(1)

    print("[*] Listening on Cat-Radio0 downlink stream for 5 seconds...")
    end_time = time.time() + 5
    while time.time() < end_time:
        line = usb.read_line()
        if line:
            print(f" [Downlink RX] {line.strip()}")

    print("[✓] Downlink eavesdropping capture complete.")
    usb.close()

if __name__ == "__main__":
    main()
