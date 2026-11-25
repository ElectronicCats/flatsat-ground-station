# FlatSat Attacks 00–07 (Firmware Internal Test Suite)

Eight attack scripts exploiting the vulnerabilities documented in [flatsat/src/attacks/](flatsat/src/attacks/), each available in two variants:
- `*_rf.py` — physically-realistic version over the air via HackRF (uplink) and RTL-SDR/CatSniffer (downlink).
- `*_usb.py` — delivered over FlatSat's USB serial link instead of RF. Useful to test without an SDR.

## Attack Suite Directory Layout

| Folder | Attack Scenario | APID(s) | USB Variant | RF Variant |
|---|---|---|---|---|
| `00_recon_apid_enum/` | Unauthenticated black-box APID enumeration | various | `apid_enum_usb.py` | `apid_enum_rf.py` |
| `01_eavesdropping/` | Passive downlink decryption (static AES-128 key) | `SEND_TM` | `eavesdrop_usb.py` | `eavesdrop_rf.py` |
| `02_fuzzing_crash/` | `BROADCAST_MSG` integer underflow crash | `0x06` | `fuzz_crash_usb.py` | `fuzz_crash_rf.py` |
| `03_command_injection/` | Unauthenticated `SET_THRUSTER` command injection | `0x04` | `cmd_injection_usb.py` | `cmd_injection_rf.py` |
| `04_gps_spoofing/` | Real GPS L1 spoofing + debug GPS-override demo | — | `gps_spoof_usb.py` | `gps_spoof_rf.py` |
| `05_gs_auth_spoofing/` | Ground-station auth bypass (static XOR key) | `0x12` | `gs_auth_usb.py` | `gs_auth_rf.py` |
| `06_replay/` | Telecommand replay (no anti-replay protection) | `0x01` | `replay_usb.py` | `replay_rf.py` |
| `07_resetc/` | Unauthenticated `RESETC` hardware reboot | `0x02` | `resetc_usb.py` | `resetc_rf.py` |

## Dependencies & Shared Libraries (`lib/`)

- `lib/flatsat_usb.py`: `FlatSatUSB` serial transport wrapper for `*_usb.py` scripts.
- `lib/pwnsat_packets.py`: CCSDS Space Packet building and CRC validation helper.
