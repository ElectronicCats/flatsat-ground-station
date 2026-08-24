import sys
sys.path.append('/home/omaro/GitHub/flatsat-ground-station')

from core.serial_manager import discover_devices

print("Running discover_devices()...")
devices = discover_devices()
print(f"Found {len(devices)} device(s):")
for d in devices:
    print(f"Serial: {d.identity.serial_number}")
    print(f"Complete: {d.is_complete}")
    print(f"Health: {d.health}")
    print(f"Ports:")
    for name, port in d.ports.items():
        print(f"  {name}: {port}")
