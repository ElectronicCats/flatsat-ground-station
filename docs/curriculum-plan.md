# FlatSat v2 CTF — Curriculum Plan

## Hardware Setup

| Nivel | Hardware | Modulos |
|-------|----------|---------|
| **Base** | 2 FlatSats + laptop + webapp | 0, 2, 3, 6, 7, 8, 9, 12 |
| **Recomendado** | + CatSniffer o SDR | 1, 4, 11 |
| **Avanzado** | + SWD probe (Pico como debugger) | 5 |
| **Especializado** | + Logic analyzer + osciloscopio | 10 |

---

## Training Modules (13)

Cada modulo tiene dos modos de entrega:
- **Home Lab:** Self-paced con guia, checkpoints, sin presion de tiempo
- **Workshop:** Version condensada, instructor-led

| # | Modulo | Duracion (home/workshop) | Hardware extra | Flag objetivo |
|---|--------|--------------------------|---------------|---------------|
| 0 | Setup & Fundamentals | 1h / 30min | Ninguno | fw_version del shell |
| 1 | RF Reconnaissance | 2h / 45min | SDR opcional | `PWNSAT{915.000}` |
| 2 | Satcomm Interception | 2h / 1h | Ninguno | `PWNSAT{CCSDS_HEADER_PARSED}` |
| 3 | CCSDS Protocol Attacks | 3h / 1.5h | Ninguno | `PWNSAT{TC_FORGED_SUCCESSFULLY}` |
| 4 | Active RF Attacks | 3h / 1.5h | HackRF opcional | `PWNSAT{REPLAY_ACCEPTED}` |
| 5 | Firmware Hacking | 4h / 2h | SWD probe | `PWNSAT{PASSWORD_IS_FLATSAT}` |
| 6 | Firmware Exploitation | 4h / 2h | Ninguno | `PWNSAT{BUFFER_OVERFLOW_CCSDS}` |
| 7 | Crypto Breaking | 3h / 1.5h | Ninguno | `PWNSAT{XOR_KEY_IS_PWNSAT}` |
| 8 | Ground Station Hacking | 3h / 1.5h | Ninguno | `PWNSAT{ADMIN_HASH_5F4DCC3B}` |
| 9 | Kill Chain | 4h / 2h | Ninguno | `PWNSAT{WEB_TO_SPACE_LINK}` |
| 10 | Hardware Side Channels | 3h / 1.5h | Logic analyzer, osciloscopio | `PWNSAT{SPI_RADIO_CONFIG_CAPTURED}` |
| 11 | TinyGS Integration | 2h / 1h | Ninguno | `PWNSAT{SATELLITE_SPOOFED}` |
| 12 | Blue Team | 4h / 2h | Ninguno | Hardened firmware + security policy |

**Total: ~38h home lab / ~19h workshop**

### Formato de cada modulo

- **Teoria** — Conceptos necesarios
- **Practica** — Pasos con el FlatSat real (2 FlatSats setup)
- **Challenges** — IDs de retos CTFd que se cubren
- **Tools** — Software/hardware necesario
- **Flag** — Que flag obtienen al completar
- **Blue Team** (donde aplique) — Como defender

### Orden de produccion

| Prioridad | Modulos | Razon |
|-----------|---------|-------|
| 1 (ahora) | 0, 8, 9 | Setup + lo que funciona 100% hoy |
| 2 | 2, 3, 7 | Protocolo + crypto — core del CTF |
| 3 | 5, 6 | Firmware — SWD acceso dificil pero contenido solido |
| 4 | 1, 4, 11 | RF — funciona con 2 FlatSats |
| 5 | 10, 12 | Hardware + Blue Team — cierre del curriculum |

---

## Mission Narratives (7)

Todas ejecutables con el setup base de 2 FlatSats.

| # | Mision | Nivel | Pts | Tiempo | Depende de | Status |
|---|--------|-------|-----|--------|-----------|--------|
| 1 | First Contact | Beginner | 500 | ~1h | RF-01, RF-09, RF-02, RF-08, PR-01, PR-02, PR-03, CD-01 | Ejecutable — LoRa real entre FlatSats, SDR opcional |
| 2 | Unauthorized Access | Intermediate | 1000 | ~2h | PR-01, CD-01, CR-01, CR-07, PR-04, CD-02, RF-03, RF-05, PR-10, CD-03 | Ejecutable — forge/replay con toolkit |
| 3 | Cryptobreak | Advanced | 1500 | ~3h | CR-01, CR-02, CR-03, CR-07, PR-04, PR-07, FW-06 | Ejecutable — crack_xor.py + firmware vulns |
| 4 | Rootkit | Expert | 2000 | ~4h | FW-01, FW-02, FW-03, FW-04, FW-05, FW-06, FW-07, FW-10, CD-03, MS-06 | Ejecutable — shell CDC, SWD con probe, Ghidra |
| 5 | Viasat Sim | Expert | 2500 | ~6h | GS-12, GS-06, GS-01, GS-05, GS-03, GS-08, FW-04, CD-08, FW-10, MS-02 | Ejecutable — 12 GS flags + radio bridge |
| 6 | Satelite Fantasma | Medium | 800 | ~2h | RF-12, MS-04, RF-11 | Ejecutable — TinyGS spoof con FlatSat |
| 7 | Blue Team | All | 1500 | ~4h | Defensas contra todo | Ejecutable — difficulty 3 + hardening |

### Modos de juego

| Modo | Descripcion |
|------|-------------|
| Jeopardy | Retos independientes, puntos fijos |
| Sequential | Completar Mision N antes de N+1 |
| Attack/Defend | Equipos con FlatSats identicos |
| Mixed | Misiones 1-3 training + retos abiertos + final attack/defend |

### Modulo → Mision mapping

| Modulos | Alimentan mision |
|---------|-----------------|
| 0 | Todas (prerequisito) |
| 1 | Mission 1 — RF Reconnaissance |
| 2, 3 | Missions 1-2 — Protocol analysis & attacks |
| 4 | Mission 2 — Active RF attacks |
| 5, 6 | Mission 4 — Firmware hacking |
| 7 | Mission 3 — Cryptography |
| 8, 9 | Mission 5 — Ground station + kill chain |
| 10 | Standalone — Hardware side channels |
| 11 | Mission 6 — TinyGS |
| 12 | Mission 7 — Blue Team |

### Hardware extra por mision

| Setup | Misiones optimas |
|-------|-----------------|
| 2 FlatSats + laptop | Todas (1-7) |
| + CatSniffer/SDR | 1, 4, 6 mejoran mucho |
| + SWD probe | 4 experiencia completa |
| + Logic analyzer | Modulo 10 side channels |

---

## Pendientes de produccion

| Item | Cantidad | Status |
|------|----------|--------|
| Training modules | 0/13 | No empezado |
| Mission narratives | 0/7 | No empezado |
| CTFd YAML challenges | 0/86 | No empezado |
| Toolkit scripts | 3/12 | 9 faltantes |
| Docker deployment | 0/1 | No empezado |
