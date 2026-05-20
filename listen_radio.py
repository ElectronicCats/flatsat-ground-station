import serial
import time

try:
    ser = serial.Serial("/dev/ttyACM0", 115200, timeout=1)
    print("Listening to /dev/ttyACM0 for 15 seconds...")
    start = time.time()
    while time.time() - start < 15:
        line = ser.readline()
        if line:
            print(line.decode("utf-8", errors="ignore").strip())
    ser.close()
except Exception as e:
    print("Error:", e)
