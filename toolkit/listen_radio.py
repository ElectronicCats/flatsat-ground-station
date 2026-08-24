import sys
import serial
import time

try:
    port = "/dev/ttyACM0"
    if sys.platform == "win32":
        try:
            # Try to auto-discover the first FlatSat board's Radio 0 port
            from core.serial_manager import discover_devices
            devs = discover_devices()
            if devs and devs[0].radio0_port:
                port = devs[0].radio0_port
            else:
                port = "COM3"
        except Exception:
            port = "COM3"

    ser = serial.Serial(port, 115200, timeout=1)
    print(f"Listening to {port} for 15 seconds...")
    start = time.time()
    while time.time() - start < 15:
        line = ser.readline()
        if line:
            print(line.decode("utf-8", errors="ignore").strip())
    ser.close()
except Exception as e:
    print("Error:", e)
