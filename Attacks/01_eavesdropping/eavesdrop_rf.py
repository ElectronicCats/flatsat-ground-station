#!/usr/bin/env python3
"""
Attack 01: Passive Downlink Decryption (RF Variant)
Monitors 915 MHz RF downlink over-the-air.
"""
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../lib")))
from pwnsat_rf import FlatSatRF

def main():
    print("[+] Attack 01: Passive Downlink Decryption (Over-The-Air RF Variant)")
    rf = FlatSatRF(freq=916000000)
    print("[*] Monitoring 916.0 MHz LoRa downlink stream over-the-air for 5 seconds...")
    lines = rf.receive_rf(timeout_sec=5.0)
    for line in lines:
        print(f" [RF 916 MHz RX] {line}")

    rf.close()
    print("[✓] RF Downlink eavesdropping capture complete.")

if __name__ == "__main__":
    main()
