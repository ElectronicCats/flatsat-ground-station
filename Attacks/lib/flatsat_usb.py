#!/usr/bin/env python3
"""
FlatSatUSB - USB Serial Transport for FlatSat *_usb.py Attack Scripts
Handles single and multi-CDC serial communication over /dev/ttyACM* ports.
"""
import sys
import time
import serial
import glob
from pwnsat_rf import discover_flatsat_endpoints, _normalize_port_path

class FlatSatUSB:
    def __init__(self, port=None, baudrate=115200, timeout=2.0):
        self.port = _normalize_port_path(port) if port else None
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None

    def find_ports(self):
        endpoints = discover_flatsat_endpoints(role="sat") or discover_flatsat_endpoints(role="gs")
        ports = []
        for key in ("Cat-Radio0", "Cat-Radio1"):
            if endpoints.get(key):
                ports.append(endpoints[key])
        if not ports:
            ports = glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")
            ports.sort()
        return ports if ports else ["/dev/ttyACM0"]

    def connect(self, target_port=None):
        found = self.find_ports()
        port_to_open = _normalize_port_path(target_port) if target_port else (self.port or (found[0] if found else "/dev/ttyACM0"))
        try:
            self.ser = serial.Serial(port_to_open, self.baudrate, timeout=self.timeout)
            self.ser.dtr = True
            self.ser.rts = True
            time.sleep(0.15)
            return True
        except Exception:
            return False

    def send_raw(self, data: bytes):
        """
        Sends raw packet data across open or detected FlatSat CDC serial ports
        to ensure Single FlatSat mode reception on Cat-Radio0 or Cat-Radio1.
        """
        for attempt in range(3):
            if self.ser and self.ser.is_open:
                try:
                    self.ser.write(data)
                    self.ser.flush()
                    return True
                except Exception:
                    try:
                        self.ser.close()
                    except Exception:
                        pass
                    self.ser = None

            ports = self.find_ports()
            sent_any = False
            for p in ports:
                try:
                    s = serial.Serial(p, self.baudrate, timeout=self.timeout)
                    s.dtr = True
                    s.rts = True
                    time.sleep(0.05)
                    s.write(data)
                    s.flush()
                    s.close()
                    sent_any = True
                    break
                except Exception:
                    pass
            if sent_any:
                return True
            time.sleep(1.2)
        return False

    def read_line(self):
        if self.ser and self.ser.is_open:
            try:
                line = self.ser.readline().decode('utf-8', errors='ignore')
                if line:
                    return line
            except Exception:
                pass

        ports = self.find_ports()
        for p in ports:
            try:
                s = serial.Serial(p, self.baudrate, timeout=self.timeout)
                line = s.readline().decode('utf-8', errors='ignore')
                s.close()
                if line:
                    return line
            except Exception:
                pass
        return ""

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
