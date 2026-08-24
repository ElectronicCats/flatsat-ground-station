import requests
import base64
import hmac
import hashlib
import time

BASE = "http://localhost:5000"

# Decoded token from admin_cookies.txt
# admin:admin:1779220174|7b0a77ae6dfe58df196fa318f36144dc9f9512eafdca1cc91c7972c5f1f9e354
token = "YWRtaW46YWRtaW46MTc3OTIyMDE3NHw3YjBhNzdhZTZkZmU1OGRmMTk2ZmEzMThmMzYxNDRkYzlmOTUxMmVhZmRjYTFjYzkxYzc5NzJjNWYxZjllMzU0"

session = requests.Session()
session.cookies.set("session_token", token)

print("1. Querying /api/hardware/status...")
try:
    r = session.get(f"{BASE}/api/hardware/status")
    print(f"Status Code: {r.status_code}")
    print(r.json())
except Exception as e:
    print(f"Error: {e}")

print("\n2. Querying /api/satellite/status...")
try:
    r = session.get(f"{BASE}/api/satellite/status")
    print(f"Status Code: {r.status_code}")
    print(r.json())
except Exception as e:
    print(f"Error: {e}")

print("\n3. Querying /api/admin/panel...")
try:
    r = session.get(f"{BASE}/api/admin/panel")
    print(f"Status Code: {r.status_code}")
    print(r.json())
except Exception as e:
    print(f"Error: {e}")
