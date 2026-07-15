"""Trigger board LED identification blink."""

from cli.session import send_cmd

NAME = "identify"
NEEDS_DEVICE = True


def add_parser(subparsers):
    subparsers.add_parser(NAME, help="Trigger board LED identification blink.")


def run(args, dev):
    print("[*] Identifying FlatSat board (blinking LEDs)...")
    output = send_cmd(dev, "identify")
    if output:
        print(f"[*] {output.strip()}")
