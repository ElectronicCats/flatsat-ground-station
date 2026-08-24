import base64
import hmac
import hashlib
import time

secret_key = "pwnsat_ground_station_2026"
username = "admin"
role = "admin"
timestamp = str(int(time.time()))

payload = f"{username}:{role}:{timestamp}"

signature = hmac.new(
    secret_key.encode(),
    payload.encode(),
    hashlib.sha256
).hexdigest()

full_token = f"{payload}|{signature}"
token_b64 = base64.b64encode(full_token.encode()).decode()

print(f"Generated Token (B64): {token_b64}")
