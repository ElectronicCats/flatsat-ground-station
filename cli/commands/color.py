"""Set custom RGB color on the NeoPixel LED."""

from cli.session import send_cmd

NAME = "color"
NEEDS_DEVICE = True


def add_parser(subparsers):
    p = subparsers.add_parser(NAME, help="Set custom RGB color on the NeoPixel LED.")
    p.add_argument("r", type=int, help="Red channel (0-255)")
    p.add_argument("g", type=int, help="Green channel (0-255)")
    p.add_argument("b", type=int, help="Blue channel (0-255)")


def run(args, dev):
    output = send_cmd(dev, f"color {args.r} {args.g} {args.b}")
    print(f"[*] {output.strip()}")
