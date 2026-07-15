"""Reboot the board (forces it into BOOTSEL mode)."""

NAME = "reboot"
NEEDS_DEVICE = True


def add_parser(subparsers):
    subparsers.add_parser(NAME, help="Reboot the board (forces it into BOOTSEL mode).")


def run(args, dev):
    print("[*] Rebooting device into BOOTSEL bootloader mode...")
    dev.send_shell_command("reboot")
    print("[+] Command sent. Device should disconnect shortly.")
