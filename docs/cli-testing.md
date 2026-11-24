# Testing the CLI — FlatSat Ground Station

Verification checklist to validate that the CLI operates correctly, both with and without the web application connected.

---

## 1. Two Operational Modes

| Mode | When to Use | Command |
|---|---|---|
| **Direct** | Webapp is **not** connected to the board | `flatsat status` |
| **Via Webapp** (`-w`) | Webapp **holds** the board connection | `flatsat -w status` |

Direct mode accesses the serial ports directly. Web mode (`-w`) communicates with the running webapp's REST API, which manages the physical hardware. **They cannot access serial ports simultaneously**: on Windows CDC-ACM endpoints are locked exclusively, and on POSIX processes would compete for incoming bytes.

---

## 2. Pre-Check: Is Another Process Accessing the Board?

```bash
flatsat devices
```

If the board appears as `HEALTHY` with all three endpoints, proceed to Section 3.
If it reports *"No FlatSat devices detected"*, see Section 6.

> **Tip**: If a command fails with
> `✗ Failed to open Shell serial interface`, another process almost certainly
> holds the ports open (typically the webapp). Either terminate it or use
> `-w` web mode.

---

## 3. CLI Direct Mode Checklist

```bash
flatsat --help              # List available commands (or 'flatsat help')
flatsat version             # Show installed version
flatsat devices             # Detect board and 3 endpoints (Radio0/Radio1/Shell)
flatsat status              # Firmware version, operational mode, radio state
flatsat mode                # Current satellite role
flatsat flight              # Flight operational state (idle/nominal/safe/debug)
flatsat difficulty          # SDLS security level (0-3)
flatsat sensors             # Live sensors (BME280 + LIS2DH)
flatsat sniff -n 3 -t 15    # Capture 3 CCSDS frames within 15 seconds
flatsat sniff -n 3 -o cap.json   # Capture frames and export to JSON
flatsat cmd status          # Send raw shell command
flatsat install             # Install application (CLI on PATH, shortcuts)
flatsat uninstall           # Remove application and restore PATH
```

Expected output of `flatsat status` with the board connected:

```text
SYSTEM STATUS
FW: dev-3aa4142-dirty
Git: 3aa4142 (dirty)
Built: 2026-10-06T17:46:47Z
Compiler: GNU 12.2.0
Flat-Sat FW: dev-3aa4142-dirty  Active Radio: 0 (TX: 1, RX: 0)
  RadioManager State: LISTENING
  Radio0: LoRa  mode=stream  lora_init=1  fsk_init=0  (Ready)
  Radio1: LoRa  mode=stream  lora_init=1  fsk_init=0  (Ready)
```

And `flatsat sniff`:

```text
✓ #1: TM APID=0x01F seq=0 CRC=OK (27 bytes, RSSI -20)
✓ #2: TM APID=0x001 seq=0 CRC=OK (25 bytes, RSSI -20)
```

---

## 4. Testing the CLI with the Webapp Connected

`-w` is an HTTP REST client: it works seamlessly across CMD, PowerShell, macOS Terminal, and Linux shells (bash/zsh/fish). The only requirement is that the webapp is running and the `flatsat` command is accessible.

### Running the Webapp in the Background (Same Terminal)

To run both the webapp and CLI in a single terminal session:

```bash
flatsat-web --background
```

```text
[+] WebApp in background: http://127.0.0.1:5000
    Log: .../FlatSatGroundStation/bin/flatsat-web.log

    Use 'flatsat -w <command>' to query it from this terminal.
    To terminate: taskkill /IM flatsat-web.exe /F (Windows) or pkill -f flatsat-web (POSIX)
```

The shell prompt returns immediately, and you can invoke the CLI:

```bash
flatsat -w status
flatsat -w sniff -n 3 -t 15
```

### Running the Webapp in the Foreground (Dual Terminal)

```text
TERMINAL A (or desktop shortcut)
─────────────────────────────────────────
    flatsat-web
    → Dashboard accessible at http://127.0.0.1:5000
    → Dashboard UI: Scan → Connect to your board

TERMINAL B (CMD, PowerShell, Terminal, bash…)
─────────────────────────────────────────────
    flatsat -w status
    flatsat -w sniff -n 3 -t 15
```

Equivalent invocation syntaxes:

```bash
flatsat -w status                        # Target local webapp (127.0.0.1:5000)
flatsat status -w                        # Flag appended
flatsat status --web-url http://ip:5000  # Custom endpoint URL
flatsat -w --web-url http://ip:5000 status
```

> `-w` is a **boolean flag**, not an option requiring a parameter. Custom URLs are passed with `--web-url <URL>`.

If the webapp is bound to an alternate port (for example port 5001 to avoid AirPlay collisions on macOS):

```bash
flatsat-web --port 5001                                  # Terminal A
flatsat -w --web-url http://127.0.0.1:5001 status        # Terminal B
```

---

## 5. CTF Attack Commands

```bash
flatsat attack --help              # List available attack scenarios
flatsat attack resetc --yes        # Unauthenticated hardware reboot
flatsat attack gs-auth --help
```

These require the board to be configured at the matching difficulty level (`flatsat difficulty 0|1|2|3`).

---

## 6. Common Issues and Troubleshooting

| Symptom | Probable Cause | Resolution |
|---|---|---|
| `No FlatSat devices detected` | Board disconnected or missing permissions | Run `flatsat doctor`; on Linux run `sudo usermod -aG dialout $USER` |
| `Failed to open Shell serial interface` | Another process holds the serial endpoints | Terminate the webapp or use `-w` web mode |
| `sniff` captures no packets | Radio transceiver in TX mode or idle | Check `flatsat status` (`Active Radio` and `RadioManager State`) |
| `sniff` reports *"No CCSDS frames captured"* | Non-CCSDS frames or invalid CRC | Review webapp logs for `[RADIO0 CRC] bad CRC` |
| Logs not written to disk | Python stdout buffering | Launch with `python -u flatsat_app.py web` |
| `flatsat` command not recognized (Windows) | Terminal inherited a stale environment | Launch terminal via Start Menu; `%LOCALAPPDATA%\Microsoft\WindowsApps` shims provide immediate path resolution |
| `flatsat` command not recognized (Linux/macOS) | `~/.local/bin` not exported in current shell PATH | Run `export PATH="$HOME/.local/bin:$PATH"` or open a fresh terminal |

---

## 7. Installing and Uninstalling the CLI

```bash
flatsat-gs install      # Adds flatsat, flatsat-web, and flatsat-gs to user PATH
flatsat-gs uninstall    # Removes binaries, restores PATH, and cleans aliases
```

Once installed, `flatsat` is globally available. In PowerShell verify the binary location with:

```powershell
(Get-Command flatsat).Source
```

This returns the path to the installed executable.

---

## 8. Running the CLI without Installation

Directly from a cloned repository checkout using the virtual environment:

```bash
python flatsat.py devices
python flatsat.py status
```

Or on Windows using the native launcher:

```bat
run.cmd cli devices
```
