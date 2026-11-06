#!/usr/bin/env python3
"""FlatSat CTF Individual Attack Runner.

Usage: python3 run_individual_attack.py --attack <number 1-8>
"""

import argparse
import os
import subprocess
import sys

ATTACKS = {
    1: ("API Enumeration", "attacks/attack_1_api_enum.py"),
    2: ("SQL Injection (SQLi)", "attacks/attack_2_sqli.py"),
    3: ("Session Forging (Session Cookie Tampering)", "attacks/attack_3_session_forging.py"),
    4: ("Local File Inclusion (LFI)", "attacks/attack_4_lfi.py"),
    5: ("Remote Code Execution (RCE)", "attacks/attack_5_rce.py"),
    6: ("Insecure Direct Object Reference (IDOR)", "attacks/attack_6_idor.py"),
    7: ("Plaintext Radio Command Injection (TEST Spoofing)", "attacks/attack_7_rf_plaintext.py"),
    8: ("Firmware Stack Buffer Overflow (DIAG_MEM)", "attacks/attack_8_fw_overflow.py"),
}


def main():
    parser = argparse.ArgumentParser(description="Run one of the 8 FlatSat attacks individually.")
    parser.add_argument("-a", "--attack", type=int, choices=range(1, 9), help="Attack scenario number (1 to 8)")
    args = parser.parse_args()

    attack_num = args.attack

    if attack_num is None:
        print("=== FlatSat Individual Attack Scenarios Menu ===")
        for num, (name, _script) in ATTACKS.items():
            print(f"  [{num}] Attack {num}: {name}")
        print("================================================")
        try:
            val = input("Select the attack number to test (1-8): ").strip()
            attack_num = int(val)
        except (ValueError, KeyboardInterrupt):
            print("\n[!] Invalid input or cancelled.")
            sys.exit(1)

    if attack_num not in ATTACKS:
        print(f"[X] Invalid attack number: {attack_num}")
        sys.exit(1)

    name, script = ATTACKS[attack_num]
    script_path = os.path.join(os.path.dirname(__file__), script)

    print(f"\n>>> Running Attack {attack_num}: {name} <<<\n")
    # noqa comment: fixed argv list, no shell; script_path comes from ATTACKS above.
    subprocess.run([sys.executable, script_path])  # noqa: S603


if __name__ == "__main__":
    main()
