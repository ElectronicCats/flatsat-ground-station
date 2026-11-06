# Self-Paced Guide: FlatSat CTF Lab

This document is a step-by-step guide designed for students and aerospace cybersecurity professionals to solve the FlatSat CTF challenges autonomously, understanding the concepts behind each vulnerability without revealing the solutions directly.

---

## Lab Structure
The environment consists of three difficulty levels, controlled by the `FLATSAT_LEVEL` environment variable when starting the Ground Station. Each level introduces additional security controls in both the web stack and the satellite firmware.

```bash
# Change level (1, 2, or 3)
export FLATSAT_LEVEL=1
python -m webapp.app
```

---

## Level 1: Easy (Web and Plaintext)
**Goal:** Compromise Ground Station access controls and communicate directly with the satellite radio transceiver.

### Challenge 1.1: API Enumeration (GS-12)
* **Concept:** Missing access control on internal route documentation and development endpoint listings.
* **Hint:** Web applications often unintentionally expose administrative or debugging routes. Is there a route that lists all server endpoints?
* **Verification:** Query an endpoint on the root API that returns a list of all available system routes and methods.

### Challenge 1.2: SQL Injection (GS-01)
* **Concept:** Database queries concatenating user-supplied input directly are vulnerable to SQL code injection.
* **Hint:** Examine the telemetry search bar. Try submitting a special character like `'` (single quote) and observe the server response.
* **Strategy:** Construct a `UNION SELECT` injection to query system tables (such as `users`). Remember to match the column count of the original query.
* **Outcome:** Extract the administrator account password hash.

### Challenge 1.3: Session Forging (GS-05)
* **Concept:** Weak session management mechanisms (plaintext tokens or unsigned formats).
* **Hint:** Decode your own session token (found in the `session_token` cookie) using Base64 tools. What structure does it follow?
* **Strategy:** Modify the structure of your token to set your role to `admin` and re-encode to Base64. Update your cookie using browser DevTools (`F12`) and navigate to the admin panel.

### Challenge 1.4: Plaintext Radio Commands (GS-08)
* **Concept:** Missing authentication at the physical radio link layer.
* **Hint:** The satellite board in Level 1 accepts raw commands over radio without structural or cryptographic validation.
* **Strategy:** Send the standard test string (`TEST`) using the radio transmission interface.
* **Visual Verification:** The board NeoPixel LED will turn **Green**.

---

## Level 2: Medium (Systems and CCSDS)
**Goal:** Exploit the underlying Ground Station operating system and escalate privileges starting from a low-privileged operator account.

### Challenge 2.1: Local File Inclusion (GS-04)
* **Concept:** User input used directly to resolve local server file paths (Directory Traversal).
* **Hint:** Review the system log reader endpoint. Does it permit relative paths using `../` to traverse outside the log directory?
* **Strategy:** Attempt to read common system configuration files (such as `/etc/passwd` or application source code files).

### Challenge 2.2: Remote Code Execution (GS-03)
* **Concept:** Operating system command execution via unsanitized input concatenated into system diagnostic utilities.
* **Hint:** The network diagnostic endpoint runs system commands in the shell. What happens if you inject command separators like `;` or `&&`?
* **Strategy:** Run operating system commands via the diagnostic endpoint to inspect the server environment.

### Challenge 2.3: Insecure Direct Object Reference - IDOR (GS-06)
* **Concept:** Horizontal access control deficiency allowing low-privileged users to request other users' resources by altering an identifier.
* **Hint:** When viewing your user's radio configuration, note the ID parameter in the URL (e.g. `.../config/radio/2`). What happens when you switch that ID to the administrator's?
* **Strategy:** Read classified administrator configuration records using your operator session.

### Challenge 2.4: CCSDS Protocol (GS-08)
* **Concept:** The satellite rejects raw plaintext strings and enforces standard CCSDS Space Packet framing.
* **Hint:** A CCSDS Space Packet begins with a 6-byte header indicating the APID (Application Process Identifier), sequence counter, and packet length, followed by the payload.
* **Strategy:** Encapsulate the PING command in hexadecimal format with the telemetry and control APID header.
* **Visual Verification:** Upon receiving the valid CCSDS frame, the NeoPixel LED turns **Blue**.

---

## Level 3: Hard (Firmware and Cryptography)
**Goal:** Break session cryptography and exploit a physical memory vulnerability in the RP2040 firmware.

### Challenge 3.1: Signed Token Forging (GS-05 / Lvl 3)
* **Concept:** Weak cryptographic signatures resulting from hardcoded or accessible shared secrets.
* **Hint:** Tokens are now signed with HMAC-SHA256. Where does the server obtain its signing secret?
* **Strategy:** If you read configuration files via Level 2 vulnerabilities, locate `SECRET_KEY` and implement a Python script to forge and sign an administrator token.

### Challenge 3.2: SDLS Cryptography (GS-08 / Lvl 3)
* **Concept:** Application of the Space Data Link Security (SDLS) standard to encrypt space telecommands.
* **Hint:** The satellite requires AES encrypted or authenticated frames. The master key resides in the database or firmware image.
* **Strategy:** Extract the master key from telemetry database dumps and use it to encrypt CCSDS frames prior to RF uplink.

### Challenge 3.3: Firmware Buffer Overflow (Challenge 3.3)
* **Concept:** Missing boundary validation in C firmware input buffers (Stack Buffer Overflow).
* **Hint:** The `DIAG_MEM` diagnostic command processes input payloads without bounds checking.
* **Strategy:** Send a `DIAG_MEM` command accompanied by an overflow payload (padding exceeding 32 bytes) to overwrite the RP2040 stack frame.
* **Visual Verification:** The NeoPixel LED turns **Purple**, confirming that the simulated stack buffer overflow handler executed.

---

## Visual Status Summary (NeoPixel LED)

| Action / Challenge | Hardware LED Color | Significance |
|---|---|---|
| `TEST` Command (Level 1) | **Green** | Successful plaintext command reception. |
| CCSDS PING Command (Level 2) | **Blue** | Successful structured space packet reception. |
| `DIAG_MEM` Overflow Command (Level 3) | **Purple** | Successful physical memory overflow simulation. |
