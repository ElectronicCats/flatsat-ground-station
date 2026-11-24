# CLI Dual-Board Testing Guide: RF Uplink and Downlink

Practical guide to verify radio frequency (RF) uplink and downlink transmission between two
FlatSat boards using the `flatsat` CLI. Covers real laboratory workflows: one
board acts as the **ground station** (transmitter) and the other as the **satellite**
(receiver).

> **Read this first.** In dual-board setups, attacks and telecommands travel **over the air**
> from the ground station to the satellite. The `-d` device argument targets the
> **transmitting** board, not the receiver. Visual NeoPixel feedback triggers on the
> **satellite** board, never on the ground station board.

---

## 0. Prerequisites

- Two FlatSat boards connected via USB (VID:PID `1209:babc`).
- Serial permissions: on Linux, ensure membership in `dialout`/`uucp` groups:
  ```bash
  sudo usermod -aG dialout,uucp $USER
  ```
- Python dependencies installed: `pip install -r requirements.txt`.

---

## 1. Board Discovery and Role Assignment

```bash
flatsat devices
```

Sample discovery output:

```text
                 Found 2 FlatSat device(s)
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Device               ┃ Radio 0      ┃ Radio 1      ┃ Shell (CDC2) ┃ Health  ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ [0] 503342353230000E │ /dev/ttyACM6 │ /dev/ttyACM7 │ /dev/ttyACM8 │ HEALTHY │
│ [1] 5033423532300010 │ /dev/ttyACM3 │ /dev/ttyACM4 │ /dev/ttyACM5 │ HEALTHY │
└──────────────────────┴──────────────┴──────────────┴──────────────┴─────────┘
```

Device indices `[0]` and `[1]` are ordered by USB serial number. Always query the role
of each connected board prior to running tests:

```bash
flatsat -d 0 mode      # -> role: ground_station
flatsat -d 1 mode      # -> role: satellite
```

Record the corresponding indices. For this guide:

| Device Index | Configured Role | Operational Function |
|---|---|---|
| `-d 0` | `ground_station` | **Transmits** RF telecommands and attacks |
| `-d 1` | `satellite` | **Receives** and executes commands |

---

## 2. Downlink Telemetry Verification (Satellite → Ground Station)

Before testing uplinks, verify that the satellite is broadcasting telemetry downlinks:

```bash
flatsat -d 0 sniff -r 0 -t 15
```

You should observe `RX:` frames with APID `0x001` (heartbeat) and `0x01F` (sensors):

```text
✓ #1: TM APID=0x01F seq=0 CRC=OK (27 bytes, RSSI -60)
✓ #2: TM APID=0x001 seq=0 CRC=OK (25 bytes, RSSI -60)
✓ #3: TM APID=0x01F seq=0 CRC=OK (27 bytes, RSSI -60)
✓ #4: TM APID=0x001 seq=0 CRC=OK (25 bytes, RSSI -60)
ℹ Captured 4 frames.
```

If no frames arrive, inspect antenna connections and frequency configuration (Section 7).

---

## 3. Verifying Roles and Difficulty Levels

```bash
flatsat -d 0 mode          # role: ground_station
flatsat -d 1 mode          # role: satellite
flatsat -d 0 difficulty    # Ground station level
flatsat -d 1 difficulty    # Satellite level (target security profile)
```

The satellite's SDLS difficulty level dictates expected packet framing and encryption.
The CLI automatically sniffs the target's level or accepts explicit `--difficulty` flags.

---

## 4. Testing Uplinks: Level 1 (Plaintext RF Injection)

Set target satellite difficulty to Level 1:

```bash
flatsat -d 1 difficulty 1
```

Send the plaintext unauthenticated test string from the Ground Station (`-d 0`):

```bash
flatsat -d 0 transmit --text "TEST"
```

**Verification**: The satellite board (`-d 1`) NeoPixel LED illuminates **Green**.

---

## 5. Testing Uplinks: Level 2 (CCSDS Framing & Static XOR)

Set target satellite difficulty to Level 2:

```bash
flatsat -d 1 difficulty 2
```

Transmit a structured CCSDS telecommand with XOR protection:

```bash
flatsat -d 0 tc 0x20 --text "PING" --protect
```

**Verification**: The satellite board (`-d 1`) NeoPixel LED illuminates **Blue**.

---

## 6. Testing Uplinks: Level 3 (SDLS AES-128 & Stack Overflow)

Set target satellite difficulty to Level 3:

```bash
flatsat -d 1 difficulty 3
```

Inject the memory diagnostic stack buffer overflow probe (APID `0x31`):

```bash
flatsat -d 0 attack -d 0 mem-overflow --yes
```

**Verification**: The satellite board (`-d 1`) NeoPixel LED illuminates **Purple**.

---

## 7. Troubleshooting RF Links

| Issue | Root Cause | Fix |
|---|---|---|
| No frames received in `sniff` | Mismatched LoRa carrier frequencies | Align both radios: `flatsat -d 0 config --freq 915000000 --apply` |
| `Device or resource busy` | Webapp owns serial interface | Use web client: `flatsat -w sniff` |
| Low RSSI (< -100 dBm at close range) | Loose SMA antenna or wrong syncword | Inspect hardware antenna connector; verify public syncword |
