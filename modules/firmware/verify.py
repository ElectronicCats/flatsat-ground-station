"""
verify.py - Diagnostic and hardware verification suite for FlatSat Ground Station.
Mirrors CatSniffer-Tools / catnip hardware verification architecture (modules/firmware/verify.py).
"""

import time
from typing import Dict, Any, List

from modules.core.shell_parser import parse_fw_version, parse_mode, parse_flight, parse_difficulty, parse_sensors
from modules.utils.output import print_info, print_success, print_warning, print_error, print_title


def test_basic_commands(dev) -> Dict[str, Any]:
    """Test basic response from CDC2 shell endpoint."""
    print_title("DIAGNOSTIC TEST: BASIC SHELL COMMANDS")
    results = {}
    
    commands = ["help", "status", "fw_version", "mode", "flight", "difficulty", "sensors"]
    for cmd in commands:
        output = dev.send_shell_command_full(cmd, timeout=1.5)
        success = output is not None and len(output.strip()) > 0
        results[cmd] = {
            "success": success,
            "response": output.strip() if output else None
        }
        if success:
            print_success(f"Command '{cmd}': OK")
        else:
            print_warning(f"Command '{cmd}': No response")
            
    return results


def test_lora_configuration(dev) -> Dict[str, Any]:
    """Test LoRa radio configuration parameters."""
    print_title("DIAGNOSTIC TEST: LORA RADIO CONFIGURATION")
    results = {}
    
    for r in [0, 1]:
        cmd = f"lora_config R{r}"
        output = dev.send_shell_command_full(cmd, timeout=1.5)
        success = output is not None and ("LoRa" in output or "Radio" in output or "OK" in output)
        results[f"radio{r}"] = {
            "success": success,
            "response": output.strip() if output else None
        }
        if success:
            print_success(f"Radio {r} config: OK")
        else:
            print_warning(f"Radio {r} config: No response")
            
    return results


def run_full_verification(dev) -> bool:
    """Run all hardware diagnostic verification tests on a connected board."""
    print_title(f"FLATSAT HARDWARE DIAGNOSTIC SUITE ({dev.serial_number})")
    
    basic = test_basic_commands(dev)
    radio = test_lora_configuration(dev)
    
    all_basic = all(r["success"] for r in basic.values())
    all_radio = all(r["success"] for r in radio.values())
    
    passed = all_basic and all_radio
    if passed:
        print_success("All diagnostic tests passed successfully.")
    else:
        print_error("Some diagnostic tests failed or returned partial responses.")
        
    return passed
