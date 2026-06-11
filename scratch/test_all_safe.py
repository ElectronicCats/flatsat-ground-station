import serial
import time

ports = ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2']

for p in ports:
    print(f"\n==========================================")
    print(f"Testing Port: {p}")
    print(f"==========================================")
    try:
        # Open with short timeouts
        ser = serial.Serial(p, 115200, timeout=0.5, write_timeout=0.5, dsrdtr=False, rtscts=False)
        try:
            ser.dtr = True
            ser.rts = True
        except Exception as e:
            print(f"[{p}] Failed to set DTR/RTS: {e}")
            
        time.sleep(0.2)
        
        # Check for initial data
        if ser.in_waiting:
            try:
                data = ser.read(ser.in_waiting)
                print(f"[{p}] Initial buffer data: {data}")
            except Exception as e:
                print(f"[{p}] Error reading initial data: {e}")
                
        # Send newline
        print(f"[{p}] Sending newline...")
        try:
            ser.write(b"\r\n")
            time.sleep(0.1)
        except Exception as e:
            print(f"[{p}] Error writing newline: {e}")
            
        # Try reading anything
        if ser.in_waiting:
            try:
                data = ser.read(ser.in_waiting)
                print(f"[{p}] Data after newline: {data}")
            except Exception as e:
                print(f"[{p}] Error reading after newline: {e}")
                
        # Send command 'status'
        print(f"[{p}] Sending 'status' command...")
        try:
            ser.write(b"status\r\n")
            time.sleep(0.3)
        except Exception as e:
            print(f"[{p}] Error writing 'status': {e}")
            
        # Try reading response
        if ser.in_waiting:
            try:
                data = ser.read(ser.in_waiting).decode('ascii', errors='ignore')
                print(f"[{p}] Response to 'status':\n{data}")
            except Exception as e:
                print(f"[{p}] Error reading 'status' response: {e}")
        else:
            print(f"[{p}] No response to 'status'")
            
        # Send command 'help'
        print(f"[{p}] Sending 'help' command...")
        try:
            ser.write(b"help\r\n")
            time.sleep(0.3)
        except Exception as e:
            print(f"[{p}] Error writing 'help': {e}")
            
        # Try reading response
        if ser.in_waiting:
            try:
                data = ser.read(ser.in_waiting).decode('ascii', errors='ignore')
                print(f"[{p}] Response to 'help':\n{data}")
            except Exception as e:
                print(f"[{p}] Error reading 'help' response: {e}")
        else:
            print(f"[{p}] No response to 'help'")
            
        ser.close()
        print(f"[{p}] Done.")
    except Exception as e:
        print(f"[{p}] Connection error: {e}")
