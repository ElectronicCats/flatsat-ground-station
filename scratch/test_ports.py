import serial
import time

ports = ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2']

for p in ports:
    print(f"\n==========================================")
    print(f"Testing Port: {p}")
    print(f"==========================================")
    try:
        ser = serial.Serial(p, 115200, timeout=1.0, write_timeout=1.0, dsrdtr=False, rtscts=False)
        ser.dtr = True
        ser.rts = True
        time.sleep(0.5)
        
        # Drain any initial content
        if ser.in_waiting:
            print(f"[{p}] Initial content in buffer: {ser.read(ser.in_waiting)}")
            
        # Send newline to wake up / sync
        ser.write(b"\r\n")
        ser.flush()
        time.sleep(0.2)
        if ser.in_waiting:
            print(f"[{p}] Response to newline: {ser.read(ser.in_waiting)}")
            
        # Try sending help
        print(f"[{p}] Sending 'help' command...")
        ser.reset_input_buffer()
        ser.write(b"help\r\n")
        ser.flush()
        time.sleep(0.5)
        if ser.in_waiting:
            resp = ser.read(ser.in_waiting).decode('ascii', errors='ignore')
            print(f"[{p}] Response to 'help':\n{resp}")
        else:
            print(f"[{p}] No response to 'help'")
            
        # Try sending status
        print(f"[{p}] Sending 'status' command...")
        ser.reset_input_buffer()
        ser.write(b"status\r\n")
        ser.flush()
        time.sleep(0.5)
        if ser.in_waiting:
            resp = ser.read(ser.in_waiting).decode('ascii', errors='ignore')
            print(f"[{p}] Response to 'status':\n{resp}")
        else:
            print(f"[{p}] No response to 'status'")
            
        ser.close()
    except Exception as e:
        print(f"[{p}] Error: {e}")
