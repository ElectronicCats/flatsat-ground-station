#!/usr/bin/env python3
"""
test_rf_attacks.py - Unit and Integration Tests for FlatSat RF Attack Suite
Tests serial port discovery, shell radio configuration, RF transmission, and all 8 RF attack scripts.
"""

import os
import sys
import unittest
import time
import subprocess

# Ensure Attacks/lib is in python path
LIB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "lib"))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from pwnsat_rf import FlatSatRF, discover_flatsat_endpoints
from pwnsat_packets import build_ccsds_packet


class TestFlatSatRFAttacks(unittest.TestCase):

    def setUp(self):
        self.endpoints = discover_flatsat_endpoints()

    def test_01_endpoint_discovery(self):
        """Verify that connected FlatSat / CatSniffer serial endpoints are detected."""
        print("\n[TEST] 1. Endpoint Discovery")
        self.assertIsNotNone(self.endpoints, "Endpoint discovery returned None")
        self.assertGreater(len(self.endpoints), 0, "No FlatSat serial endpoints discovered!")
        print(f"  Detected endpoints: {self.endpoints}")
        self.assertIn("Cat-Radio0", self.endpoints, "Cat-Radio0 not found in endpoints")

    def test_02_shell_configuration(self):
        """Verify frequency configuration via Cat-Shell (CDC2)."""
        print("\n[TEST] 2. Shell Configuration via CDC2")
        rf = FlatSatRF(freq=916000000)
        success = rf.configure_radio()
        self.assertTrue(success, "Failed to configure radio over shell port")
        self.assertTrue(rf.configured, "FlatSatRF status 'configured' should be True")
        rf.close()

    def test_03_rf_transmission(self):
        """Verify transmitting a raw CCSDS packet over RF link."""
        print("\n[TEST] 3. RF Transmission")
        rf = FlatSatRF(freq=916000000)
        packet = build_ccsds_packet(apid=0x00, payload=b"\x00")
        success = rf.transmit_rf(packet)
        self.assertTrue(success, "RF packet transmission failed")
        rf.close()

    def test_04_all_rf_attack_scripts(self):
        """Execute each of the 8 RF attack scripts to verify end-to-end functionality."""
        print("\n[TEST] 4. Executing all 8 RF Attack Scripts")
        attacks_dir = os.path.dirname(__file__)
        attack_scripts = [
            ("00_recon_apid_enum", "apid_enum_rf.py"),
            ("01_eavesdropping", "eavesdrop_rf.py"),
            ("02_fuzzing_crash", "fuzz_crash_rf.py"),
            ("02_fuzzing_crash", "buf_overflow_rf.py"),
            ("03_command_injection", "cmd_injection_rf.py"),
            ("04_gps_spoofing", "gps_spoof_rf.py"),
            ("05_gs_auth_spoofing", "gs_auth_rf.py"),
            ("06_replay", "replay_rf.py"),
            ("07_resetc", "resetc_rf.py"),
        ]

        for folder, script in attack_scripts:
            script_path = os.path.join(attacks_dir, folder, script)
            self.assertTrue(os.path.exists(script_path), f"Script missing: {script_path}")
            print(f"\n  ---> Running {folder}/{script}...")
            
            # Execute script via subprocess with UTF-8 stdio (Windows compatibility)
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            proc = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=60
            )
            print(proc.stdout)
            if proc.stderr:
                print("ERR:", proc.stderr)
            
            self.assertEqual(proc.returncode, 0, f"Attack script {script} failed with returncode {proc.returncode}")
            time.sleep(3.5 if "resetc" in script else 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
