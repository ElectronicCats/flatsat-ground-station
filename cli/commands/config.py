"""Stage and apply LoRa radio configuration settings."""

from cli.session import send_cmd
from cli.ui.banner import print_title

NAME = "config"
NEEDS_DEVICE = True


def add_parser(subparsers):
    p = subparsers.add_parser(NAME, help="Stage and apply radio configuration settings.")
    p.add_argument("--radio", type=int, choices=[0, 1], default=0, help="Radio index to configure (0 or 1)")
    p.add_argument("--freq", type=int, help="LoRa frequency in Hz (e.g. 915000000)")
    p.add_argument("--sf", type=int, choices=range(7, 13), help="Spreading Factor (7-12)")
    p.add_argument("--bw", type=int, choices=[125, 250, 500], help="Bandwidth in kHz")
    p.add_argument("--cr", type=int, choices=[5, 6, 7, 8], help="Coding Rate (5-8)")
    p.add_argument("--power", type=int, help="TX power in dBm")
    p.add_argument("--syncword", help="Syncword (public, private, or hex value e.g. 0x2D)")
    p.add_argument("--mode", choices=["stream", "command"], help="LoRa output mode (stream or command)")
    p.add_argument("--apply", action="store_true", help="Apply staged changes immediately")


def run(args, dev):
    print_title(f"RADIO CONFIGURATION - RADIO {args.radio}")

    # Select target radio
    select_res = send_cmd(dev, f"radio{args.radio}")
    print(f"[*] Selecting Radio {args.radio}: {select_res.strip()}")

    staged = False
    if args.freq is not None:
        res = send_cmd(dev, f"lora_freq {args.freq}")
        print(f"  - Frequency -> {args.freq} Hz: {res.strip()}")
        staged = True
    if args.sf is not None:
        res = send_cmd(dev, f"lora_sf {args.sf}")
        print(f"  - Spreading Factor -> SF{args.sf}: {res.strip()}")
        staged = True
    if args.bw is not None:
        res = send_cmd(dev, f"lora_bw {args.bw}")
        print(f"  - Bandwidth -> {args.bw} kHz: {res.strip()}")
        staged = True
    if args.cr is not None:
        res = send_cmd(dev, f"lora_cr {args.cr}")
        print(f"  - Coding Rate -> 4/{args.cr}: {res.strip()}")
        staged = True
    if args.power is not None:
        res = send_cmd(dev, f"lora_power {args.power}")
        print(f"  - Power -> {args.power} dBm: {res.strip()}")
        staged = True
    if args.syncword is not None:
        res = send_cmd(dev, f"lora_syncword {args.syncword}")
        print(f"  - Syncword -> {args.syncword}: {res.strip()}")
        staged = True
    if args.mode is not None:
        res = send_cmd(dev, f"lora_mode R{args.radio} {args.mode}")
        print(f"  - Mode -> {args.mode}: {res.strip()}")
        staged = True

    if args.apply or staged:
        if args.apply:
            apply_res = send_cmd(dev, "lora_apply")
            print(f"[+] Applying changes: {apply_res.strip()}")
        else:
            print("[!] Note: Changes are STAGED but not yet applied. Run with --apply to write to hardware.")
    else:
        # No staging parameters, show current config
        cfg_res = send_cmd(dev, "lora_config")
        if cfg_res:
            print(cfg_res.strip())
