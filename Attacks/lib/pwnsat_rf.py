#!/usr/bin/env python3
"""
pwnsat_rf.py - FlatSat / CatSniffer RF Transmit Helper
Sends telecommand payloads over-the-air via RF (916 MHz / 915 MHz).
Configures target frequency via Cat-Shell (CDC2) and streams raw packets via Cat-Radio (CDC0/CDC1).
"""
import sys
import time
import re
import serial
import serial.tools.list_ports

FLATSAT_VID = 0x1209
FLATSAT_PID = 0xBABC


def _port_sort_key(port):
    """Natural sort for serial ports (COM10 > COM3, ttyACM10 > ttyACM2)."""
    device = getattr(port, "device", "") or ""
    match = re.search(r"(\d+)", device)
    if match:
        return (0, int(match.group(1)))
    return (1, device.lower())


def _normalize_port_path(path):
    """Normalize Windows COM ports >= 10."""
    if sys.platform == "win32" and path:
        path_upper = path.upper()
        if path_upper.startswith("COM") and not path_upper.startswith(r"\\.\COM"):
            try:
                port_num = int(path_upper[3:])
                if port_num >= 10:
                    return rf"\\.\{path_upper}"
            except ValueError:
                pass
    return path


def _map_device_ports(target_ports):
    """Maps a single FlatSat board's serial ports to Cat-Radio0/Cat-Radio1/Cat-Shell."""
    target_ports = sorted(target_ports, key=_port_sort_key)
    endpoints = {}

    # Strategy 1: Description matching
    for p in target_ports:
        desc = (getattr(p, "description", "") or "").lower()
        if "shell" in desc:
            endpoints["Cat-Shell"] = _normalize_port_path(p.device)
        elif "radio0" in desc or "radio 0" in desc:
            endpoints["Cat-Radio0"] = _normalize_port_path(p.device)
        elif "radio1" in desc or "radio 1" in desc:
            endpoints["Cat-Radio1"] = _normalize_port_path(p.device)

    # Strategy 2: Interface / MI matching
    if len(endpoints) < 3:
        for p in target_ports:
            hwid = (getattr(p, "hwid", "") or "").upper()
            location = (getattr(p, "location", "") or "")
            mi = None
            m = re.search(r"MI_(\d+)", hwid) or re.search(r"MI=(\d+)", hwid)
            if m:
                mi = int(m.group(1))
            else:
                for s in [location, hwid]:
                    m2 = re.search(r":[0-9a-zA-Z]+\.(\d+)", s)
                    if m2:
                        mi = int(m2.group(1))
                        break
            if mi is not None:
                if mi in (0, 1) and "Cat-Radio0" not in endpoints:
                    endpoints["Cat-Radio0"] = _normalize_port_path(p.device)
                elif mi in (2, 3) and "Cat-Radio1" not in endpoints:
                    endpoints["Cat-Radio1"] = _normalize_port_path(p.device)
                elif mi in (4, 5) and "Cat-Shell" not in endpoints:
                    endpoints["Cat-Shell"] = _normalize_port_path(p.device)

    # Strategy 3: Positional fallback
    if len(target_ports) >= 3:
        if "Cat-Radio0" not in endpoints:
            endpoints["Cat-Radio0"] = _normalize_port_path(target_ports[0].device)
        if "Cat-Radio1" not in endpoints:
            endpoints["Cat-Radio1"] = _normalize_port_path(target_ports[1].device)
        if "Cat-Shell" not in endpoints:
            endpoints["Cat-Shell"] = _normalize_port_path(target_ports[2].device)
    elif len(target_ports) == 2:
        if "Cat-Radio0" not in endpoints:
            endpoints["Cat-Radio0"] = _normalize_port_path(target_ports[0].device)
        if "Cat-Shell" not in endpoints:
            endpoints["Cat-Shell"] = _normalize_port_path(target_ports[1].device)
    elif len(target_ports) == 1:
        if "Cat-Radio0" not in endpoints:
            endpoints["Cat-Radio0"] = _normalize_port_path(target_ports[0].device)

    return endpoints


def _probe_board_role(shell_port, baudrate=115200):
    """Queries Cat-Shell 'mode' to identify whether a FlatSat is configured as GS or SAT."""
    if not shell_port:
        return None
    try:
        with serial.Serial(shell_port, baudrate, timeout=0.25) as ser:
            ser.dtr = True
            ser.rts = True
            ser.reset_input_buffer()
            ser.write(b"\r\nmode\r\n")
            ser.flush()
            time.sleep(0.15)
            resp = ser.read_all().decode("utf-8", errors="ignore").lower()
            if "ground_station" in resp:
                return "gs"
            if "satellite" in resp:
                return "sat"
    except Exception:
        pass
    return None


def discover_flatsat_endpoints(role="gs"):
    """
    Discovers connected FlatSat serial endpoints.
    Groups interfaces by physical device and selects the appropriate FlatSat board:
    - role="gs" (Ground Station FlatSat transmitter)
    - role="sat" (Satellite FlatSat receiver)
    Returns dict: endpoint_name -> port_path
    """
    all_ports = list(serial.tools.list_ports.comports())
    cat_ports = []
    for p in all_ports:
        is_fs = (getattr(p, "vid", None) == FLATSAT_VID and getattr(p, "pid", None) == FLATSAT_PID)
        if not is_fs:
            hwid = (getattr(p, "hwid", "") or "").upper()
            is_fs = "1209" in hwid and "BABC" in hwid
        if not is_fs:
            desc = (getattr(p, "description", "") or "").upper()
            prod = (getattr(p, "product", "") or "").upper()
            is_fs = any(kw in desc or kw in prod for kw in ("FLATSAT", "FLAT-SAT", "ELECTRONIC CATS", "CAT-SHELL", "CAT-RADIO"))
        if is_fs:
            cat_ports.append(p)

    if not cat_ports:
        return {}

    # Group ports by physical device serial number or location
    devices = {}
    for p in cat_ports:
        sn = getattr(p, "serial_number", None)
        if not sn:
            loc = getattr(p, "location", "") or ""
            sn = loc.split(":")[0] if ":" in loc else "default_device"
        if sn not in devices:
            devices[sn] = []
        devices[sn].append(p)

    mapped_devices = {sn: _map_device_ports(ports) for sn, ports in devices.items()}

    # Determine which physical FlatSat corresponds to GS vs SAT by querying Cat-Shell 'mode'
    selected_sn = None
    if len(mapped_devices) == 1:
        selected_sn = list(mapped_devices.keys())[0]
    else:
        for sn, ep in mapped_devices.items():
            detected_role = _probe_board_role(ep.get("Cat-Shell"))
            if detected_role == role:
                selected_sn = sn
                break

        if not selected_sn:
            sns = list(mapped_devices.keys())
            selected_sn = sns[0] if role == "gs" else sns[-1]

    return mapped_devices[selected_sn]


class FlatSatRF:
    def __init__(self, port=None, shell_port=None, baudrate=115200, timeout=2.0, freq=916000000, role="gs"):
        # Allow CLI override flags
        for i, arg in enumerate(sys.argv):
            if arg == "--port" and i + 1 < len(sys.argv):
                port = sys.argv[i + 1]
            elif arg == "--shell-port" and i + 1 < len(sys.argv):
                shell_port = sys.argv[i + 1]
            elif arg in ("--gs", "--ground-station"):
                role = "gs"
            elif arg in ("--sat", "--satellite"):
                role = "sat"
            elif arg == "--freq" and i + 1 < len(sys.argv):
                freq = int(sys.argv[i + 1])
                if freq < 1000000:
                    freq *= 1000000
            elif arg in ("915", "915000000"):
                freq = 915000000
            elif arg in ("916", "916000000"):
                freq = 916000000
            elif i > 0 and not arg.startswith("-") and (
                arg.startswith("/dev/") or arg.upper().startswith("COM") or arg.startswith(r"\\.\COM")
            ):
                port = arg

        endpoints = discover_flatsat_endpoints(role=role)

        if not shell_port:
            shell_port = endpoints.get("Cat-Shell")

        if not port:
            port = endpoints.get("Cat-Radio0") or endpoints.get("Cat-Radio1") or "/dev/ttyACM0"

        self.port = _normalize_port_path(port)
        self.shell_port = _normalize_port_path(shell_port) if shell_port else None
        self.baudrate = baudrate
        self.timeout = timeout
        self.freq = freq

        self.ser_radio = None
        self.ser_shell = None
        self.configured = False

    def configure_radio(self):
        """Configures frequency and stream mode on Cat-Shell."""
        if self.configured:
            return True

        if self.shell_port:
            try:
                if self.ser_shell is None or not self.ser_shell.is_open:
                    self.ser_shell = serial.Serial(self.shell_port, self.baudrate, timeout=self.timeout)
                    self.ser_shell.dtr = True
                    self.ser_shell.rts = True
                    time.sleep(0.05)

                # Align all LoRa air parameters with FlatSat defaults so GS and SAT always match
                cmds = [
                    f"lora_freq ALL {self.freq}",
                    "lora_sf ALL 7",
                    "lora_bw ALL 125",
                    "lora_cr ALL 5",
                    "lora_preamble ALL 12",
                    "lora_syncword ALL private",
                    "lora_iq ALL normal",
                    "lora_mode ALL stream",
                    "lora_apply ALL",
                ]
                cmd = ("\r\n".join(cmds) + "\r\n").encode("utf-8")
                self.ser_shell.write(cmd)
                self.ser_shell.flush()
                time.sleep(0.8)
                reply = self.ser_shell.read_all().decode("utf-8", errors="ignore")
                self.configured = True
                print(
                    f"[*] FlatSat configured (Shell={self.shell_port}, Radio={self.port}): "
                    f"Freq={self.freq / 1e6:.1f} MHz, SF7, BW125, CR4/5, Private, STREAM"
                )
                if "ERROR" in reply.upper() or "FAILED" in reply.upper():
                    print(f"[!] Shell warning during radio config: {reply.strip()}")
                return True
            except Exception as e:
                print(f"[!] Warning: Could not configure shell port {self.shell_port}: {e}")
                return False
        return True

    def transmit_rf(self, packet: bytes, retries=2):
        """
        Transmits raw CCSDS telecommand over the air via RF.
        Automatically retries if serial port is temporarily disconnected (e.g., due to a RESETC reboot).
        """
        for attempt in range(retries + 1):
            try:
                self.configure_radio()

                if self.ser_radio is None or not self.ser_radio.is_open:
                    self.ser_radio = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
                    self.ser_radio.dtr = True
                    self.ser_radio.rts = True
                    time.sleep(0.05)

                self.ser_radio.reset_input_buffer()
                self.ser_radio.write(packet)
                self.ser_radio.flush()
                time.sleep(0.25)
                tx_feedback = self.ser_radio.read_all().decode("utf-8", errors="ignore").strip()
                if "TX Error" in tx_feedback or "ERROR" in tx_feedback:
                    print(f"[X] Firmware reported TX error on {self.port}: {tx_feedback}")
                    return False
                print(f"[RF {self.freq / 1e6:.1f} MHz] Transmitted {len(packet)} bytes over-the-air via {self.port} (HEX: {packet.hex().upper()}).")
                return True
            except Exception as e:
                print(f"[X] RF Transmission error on {self.port} (attempt {attempt+1}/{retries+1}): {e}")
                if self.ser_radio and self.ser_radio.is_open:
                    try:
                        self.ser_radio.close()
                    except Exception:
                        pass
                self.ser_radio = None
                self.configured = False
                if attempt < retries:
                    time.sleep(1.0)
                    # Re-discover endpoints in case device re-enumerated on new ttyACM
                    endpoints = discover_flatsat_endpoints()
                    if endpoints.get("Cat-Shell"):
                        self.shell_port = endpoints["Cat-Shell"]
                    if endpoints.get("Cat-Radio0"):
                        self.port = endpoints["Cat-Radio0"]
        return False

    def receive_rf(self, timeout_sec=5.0):
        """
        Listens for incoming RF data lines/packets over the air.
        """
        self.configure_radio()
        if self.ser_radio is None or not self.ser_radio.is_open:
            try:
                self.ser_radio = serial.Serial(self.port, self.baudrate, timeout=1.0)
                self.ser_radio.dtr = True
                self.ser_radio.rts = True
            except Exception as e:
                print(f"[X] Could not open radio port {self.port} for RX: {e}")
                return []

        received_lines = []
        end_time = time.time() + timeout_sec
        while time.time() < end_time:
            try:
                line = self.ser_radio.readline().decode('utf-8', errors='ignore')
                if line:
                    received_lines.append(line.strip())
            except Exception:
                pass
        return received_lines

    def close(self):
        """Close opened serial connections."""
        if self.ser_radio and self.ser_radio.is_open:
            try:
                self.ser_radio.close()
            except Exception:
                pass
        if self.ser_shell and self.ser_shell.is_open:
            try:
                self.ser_shell.close()
            except Exception:
                pass

    def __del__(self):
        self.close()
