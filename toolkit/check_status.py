
import os

import requests

BASE = os.environ.get("FLATSAT_BASE_URL", "http://localhost:5000")

# Admin session token. Prefer FLATSAT_SESSION_TOKEN or a cookies file; the
# literal below is a local-CTF convenience default and expires, so it is only a
# last resort. Decode with: base64 -d
_DEFAULT_TOKEN = (
    "YWRtaW46YWRtaW46MTc3OTIyMDE3NHw3"
    "YjBhNzdhZTZkZmU1OGRmMTk2ZmEzMThmMzYxNDRkYzlmOTUxMmVhZmRjYTFjYzkxYzc5NzJjNWYxZjllMzU0"
)
token = os.environ.get("FLATSAT_SESSION_TOKEN") or _DEFAULT_TOKEN

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
