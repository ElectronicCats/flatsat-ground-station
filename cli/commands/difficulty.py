"""Get or set workshop security/difficulty level."""

from cli.session import send_cmd

NAME = "difficulty"
NEEDS_DEVICE = True


def add_parser(subparsers):
    p = subparsers.add_parser(NAME, help="Get or set workshop security/difficulty level.")
    p.add_argument("value", nargs="?", type=int, choices=[1, 2, 3], help="Difficulty level")


def run(args, dev):
    if args.value is not None:
        output = send_cmd(dev, f"difficulty {args.value}")
        print(f"[*] {output.strip()}")
    else:
        output = send_cmd(dev, "difficulty")
        print(f"[*] Security Level: {output.strip()}")
