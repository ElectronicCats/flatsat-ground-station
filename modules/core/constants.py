"""Constants for FlatSat ground station core library.

USB identifiers, CCSDS protocol values, APIDs, opcodes, and enums.
Adapted from flatsatTUI/constants.py + firmware ccsds_spp.h / ccsds_apid.h.
"""

from enum import Enum, auto

# --- USB device identifiers ---
USB_VID = 0x1209
USB_PID = 0xBABC
BAUDRATE = 115200

# --- Endpoint names ---
ENDPOINT_RADIO0 = "Cat-Radio0"
ENDPOINT_RADIO1 = "Cat-Radio1"
ENDPOINT_SHELL = "Cat-Shell"

# --- Radio config labels (canonical DB descriptions) ---
RADIO_LABELS = ("Radio 0", "Radio 1")

ENDPOINT_LABELS = {
    ENDPOINT_RADIO0: "Radio 0 (CDC0)",
    ENDPOINT_RADIO1: "Radio 1 (CDC1)",
    ENDPOINT_SHELL: "Shell (CDC2)",
}

# --- Timeouts ---
COMMAND_TIMEOUT = 2.0
CONNECT_TIMEOUT = 1.0
HOTPLUG_SCAN_INTERVAL = 3.0

# --- CCSDS Protocol Constants (per CCSDS 133.0-B-2) ---
CCSDS_VERSION = 0
CCSDS_TYPE_TM = 0
CCSDS_TYPE_TC = 1
CCSDS_SEQ_STANDALONE = 3
CCSDS_HDR_SIZE = 6
CCSDS_SEC_HDR_SIZE = 4
CCSDS_CRC_SIZE = 2
CCSDS_MAX_FRAME_SIZE = 237
CCSDS_MAX_PAYLOAD = 225  # 237 - 6 - 4 - 2
CCSDS_SPACECRAFT_ID = 0x02

# --- Telemetry APIDs (Type 0) ---
APID_TM_HEARTBEAT = 0x001
APID_TM_BME280 = 0x010
APID_TM_LIS2DH = 0x011
APID_TM_POWER = 0x012
APID_TM_GPS = 0x013
APID_TM_ALL_SENSORS = 0x01F
APID_TM_IDLE = 0x7FF

# --- Telecommand APIDs (Type 1) ---
APID_TC_COMMAND = 0x020
APID_TC_SET_FREQ = 0x021
APID_TC_SET_POWER = 0x022
APID_TC_FW_UPDATE = 0x026
APID_TC_SET_DIFFICULTY = 0x027
APID_TC_DIAG_LOG = 0x030
APID_TC_DIAG_MEM = 0x031
APID_TC_CTF_FLAG = 0x040
APID_TC_SECRET_DEBUG = 0x539

# --- CTF attack-suite telecommand APIDs (Type 1) ---
# Dispatched by flatsat/src/attacks/attacks.c and named in attacks.h. These do
# not overlap the APIDs above; APID_TC_DIAG_MEM (0x031) is shared, being both a
# diagnostic telecommand and the Reto 3.3 overflow challenge. Values mirror
# flat-sat-fw-interno/Attacks/attacks.h and the scenario table in its README.
APID_TC_RECON_ENUM = 0x000     # 00_recon_apid_enum
APID_TC_REPLAY = 0x001         # 06_replay
APID_TC_RESETC = 0x002         # 07_resetc
APID_TC_SET_THRUSTER = 0x004   # 03_command_injection
APID_TC_BROADCAST = 0x006      # 02_fuzzing_crash (integer underflow)
APID_TC_GS_AUTH_XOR = 0x012    # 05_gs_auth_spoofing
# APID_TC_DIAG_MEM (0x031) above also covers the Reto 3.3 memory overflow.
# Attack 04 (gps_spoofing) has no APID of its own: attacks.h defines none, and
# the suite's script reuses 0x004, which the firmware routes to the thruster
# handler. Treat it as an NMEA payload probe on APID_TC_SET_THRUSTER.

# --- RF uplink/downlink plan (LoRa) ---
# Telecommands leave the ground station on the uplink TX radio at the uplink
# frequency; telemetry comes back on Radio 0 at the same frequency. Every LoRa
# parameter below must match on BOTH boards or the receiver never demodulates
# the frame: a mismatched sync word in particular looks like a dead TX, because
# the SX126x still reports "Success" after queueing the packet into its FIFO.
LORA_UPLINK_HZ = 916_000_000
LORA_DOWNLINK_HZ = 915_000_000
#: Both FlatSat boards ship their radios on the public LoRaWAN sync word (0x34).
LORA_SYNCWORD_TX = "public"
LORA_SYNCWORD_RX = "private"
#: Rest frequency for the TX radio between transmissions.
LORA_TX_SETTLE_S = 0.3

# --- CTF attack-suite NeoPixel feedback ---
# The firmware lights the NeoPixel from the *plaintext* APID in the CCSDS
# primary header (attacks.c runs before any SDLS decryption on the RX path), so
# this colour is what the target board shows regardless of SDLS level. Entries
# mirror led_rgb_set() calls in flatsat/src/attacks/attacks.c; the firmware
# holds the colour for ATTACK_LED_HOLD_MS and then returns to its idle heartbeat.
ATTACK_LED_HOLD_MS = 4000
ATTACK_LED_FEEDBACK: dict[int, tuple[str, tuple[int, int, int]]] = {
    APID_TC_RECON_ENUM: ("soft cyan", (0, 20, 20)),
    APID_TC_REPLAY: ("blue", (0, 0, 50)),
    APID_TC_RESETC: ("red", (50, 0, 0)),
    APID_TC_SET_THRUSTER: ("yellow", (50, 50, 0)),
    APID_TC_BROADCAST: ("magenta", (50, 0, 50)),
    APID_TC_GS_AUTH_XOR: ("cyan", (0, 50, 50)),
    APID_TC_DIAG_MEM: ("purple", (50, 0, 50)),
}

# --- Telecommand Opcodes (payload byte 0 for APID_TC_COMMAND) ---
TC_OP_NOP = 0x00
TC_OP_SET_SAFE_MODE = 0x01
TC_OP_SET_NOMINAL = 0x02
TC_OP_SET_DEBUG = 0x03
TC_OP_PING = 0x10
TC_OP_READ_SENSOR = 0x20
TC_OP_SET_TM_RATE = 0x30
TC_OP_OVERRIDE_SENSOR = 0x40
TC_OP_READ_FLAG = 0x42
TC_OP_SET_CALLSIGN = 0x50
TC_OP_STORE_CMD = 0x60
TC_OP_TABLE_WRITE = 0x70
TC_OP_NEOPIXEL_RAW = 0xA0
TC_OP_CRYPTO_ORACLE = 0xC0
TC_OP_PRIVILEGED = 0xD0
TC_OP_EXEC = 0xEE
TC_OP_BACKDOOR = 0xFF

# --- Crypto keys (deliberately hardcoded — V04 vuln) ---
AES_KEY_HARDCODED = b"PWNSAT_K3Y_2026!"  # 16 bytes AES-128
XOR_KEY = b"PWNSAT"  # 6 bytes XOR key

# --- Shell commands (CDC2) ---
CDC2_COMMANDS = {
    "status": "status",
    "radio0": "radio0",
    "radio1": "radio1",
    "modulation_lora": "modulation lora",
    "modulation_fsk": "modulation fsk",
    "lora_mode_stream": "lora_mode stream",
    "lora_mode_command": "lora_mode command",
    "lora_freq": "lora_freq",
    "lora_sf": "lora_sf",
    "lora_bw": "lora_bw",
    "lora_cr": "lora_cr",
    "lora_power": "lora_power",
    "lora_preamble": "lora_preamble",
    "lora_syncword": "lora_syncword",
    "fsk_config": "fsk_config",
    "difficulty": "difficulty",
    "flags": "flags",
    "mode": "mode",
    "sc_id": "sc_id",
    "flight": "flight",
    "login": "login",
    "whoami": "whoami",
    "inject_tc": "inject_tc",
    "tinygs": "tinygs",
}


# --- Enums ---
class DeviceHealth(Enum):
    HEALTHY = auto()
    PARTIAL = auto()
    CRITICAL = auto()


class EndpointState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()


class CommandStatus(Enum):
    PASS = auto()
    FAIL = auto()
    TIMEOUT = auto()
    ERROR = auto()


class ConnectionMode(Enum):
    IDLE = auto()
    HARDWARE = auto()
    SIMULATED = auto()
