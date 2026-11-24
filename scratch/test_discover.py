from pathlib import Path
import sys

# Ensure repository root is on sys.path dynamically
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from core.serial_manager import discover_devices

print("Running discover_devices()...")
devices = discover_devices()
print(f"Found {len(devices)} device(s):")
for d in devices:
    print(f"Serial: {d.identity.serial_number}")
    print(f"Complete: {d.is_complete}")
    print(f"Health: {d.health}")
    print("Ports:")
    for name, port in d.ports.items():
        print(f"  {name}: {port}")
