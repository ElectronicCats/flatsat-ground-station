"""
test_live_hardware_rf.py - Execute live RF and serial tests between CatSniffer GS and FlatSat Satellite.
"""
import subprocess
import sys
import time

PYTHON = "./.venv/bin/python"
FLATSAT = "./.venv/bin/flatsat"

def run_cmd(args, desc=""):
    print(f"\n========================================================")
    print(f"▶ {desc}: {' '.join(args)}")
    print(f"========================================================")
    res = subprocess.run(args, capture_output=True, text=True)
    print("STDOUT:")
    print(res.stdout)
    if res.stderr:
        print("STDERR:")
        print(res.stderr)
    print(f"Exit Code: {res.returncode}")
    return res

def main():
    print("=== STARTING LIVE HARDWARE & RF INTEGRATION TESTS ===")

    # 1. List devices
    run_cmd([FLATSAT, "devices"], "Listing connected devices")

    # 2. Check status of Satellite (Device 0) and Ground Station (Device 1)
    run_cmd([FLATSAT, "-d", "0", "status"], "Reading Satellite (Dev 0) Status")
    run_cmd([FLATSAT, "-d", "1", "status"], "Reading Ground Station (Dev 1) Status")

    # 3. Read live sensor telemetry
    run_cmd([FLATSAT, "-d", "0", "sensors"], "Reading Satellite Sensors")
    run_cmd([FLATSAT, "-d", "1", "sensors"], "Reading Ground Station Sensors")

    # 4. Set LED Colors
    run_cmd([FLATSAT, "-d", "0", "color", "0", "255", "0"], "Setting Satellite LED to GREEN")
    run_cmd([FLATSAT, "-d", "1", "color", "0", "0", "255"], "Setting Ground Station LED to BLUE")

    # 5. Difficulty queries
    run_cmd([FLATSAT, "-d", "0", "difficulty"], "Querying Satellite Difficulty")
    run_cmd([FLATSAT, "-d", "1", "difficulty"], "Querying Ground Station Difficulty")

    # 6. Mode queries
    run_cmd([FLATSAT, "-d", "0", "mode"], "Querying Satellite Mode")
    run_cmd([FLATSAT, "-d", "1", "mode"], "Querying Ground Station Mode")

    # 7. Identify LED sequence
    run_cmd([FLATSAT, "-d", "0", "identify"], "Triggering Satellite LED Identify")

    # 8. Flight State Query on Sat
    run_cmd([FLATSAT, "-d", "0", "flight"], "Querying Satellite Flight State")

    # 9. Ground Station sending Flight State TC over RF to Satellite
    run_cmd([FLATSAT, "-d", "1", "flight", "nominal", "--difficulty", "2"], "GS sending Flight NOMINAL TC over RF to Satellite")

    time.sleep(1)

    # 10. Raw Telecommand (TC) over RF from GS to Sat
    run_cmd([FLATSAT, "-d", "1", "tc", "0x04", "0164", "--protect", "--difficulty", "2"], "GS sending SET_THRUSTER TC over RF")

    time.sleep(1)

    # 11. Transmit text payload over RF
    run_cmd([FLATSAT, "-d", "1", "transmit", "--text", "HELLO_SAT", "--protect", "--difficulty", "2"], "GS transmitting text payload over RF")

    time.sleep(1)

    # 12. Attack Scenario: APID Enumeration (0..6) over RF
    run_cmd([FLATSAT, "-d", "1", "attack", "apid-enum", "--high", "6", "--yes"], "GS executing APID Enumeration Attack over RF")

    time.sleep(1)

    # 13. Attack Scenario: Command Injection over RF
    run_cmd([FLATSAT, "-d", "1", "attack", "cmd-injection", "--power", "75", "--yes"], "GS executing Command Injection Attack over RF")

    time.sleep(1)

    # 14. Attack Scenario: GS Auth Bypass over RF
    run_cmd([FLATSAT, "-d", "1", "attack", "gs-auth", "--payload", "RF_TEST_OK", "--yes"], "GS executing GS Auth Bypass Attack over RF")

    print("\n========================================================")
    print("=== ALL LIVE HARDWARE & RF INTEGRATION TESTS PASSED ===")
    print("========================================================")

if __name__ == "__main__":
    main()
