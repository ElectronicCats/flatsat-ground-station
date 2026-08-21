"""
modules.firmware - Firmware verification and diagnostic suite.
Mirrors CatSniffer-Tools / catnip module structure.
"""

from modules.firmware.verify import run_full_verification, test_basic_commands, test_lora_configuration

__all__ = ["run_full_verification", "test_basic_commands", "test_lora_configuration"]
