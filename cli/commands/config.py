"""Stage and apply LoRa radio configuration settings."""

import click

from cli.session import send_cmd, with_device
from cli.ui.output import print_dim, print_info, print_response, print_success, print_title, print_warning


def _fmt(res):
    """Shell replies are optional: send_cmd() returns None on timeout.

    `lora_apply` in particular reconfigures the SX126x and can stay silent past
    the 2 s shell timeout even when the command did land on the board.
    """
    return res.strip() if res else "OK"


@click.command("config")
@click.option("--radio", type=click.Choice(["0", "1"]), default="0", show_default=True, help="Radio index to configure")
@click.option("--freq", type=int, help="LoRa frequency in Hz (e.g. 915000000)")
@click.option("--sf", type=click.IntRange(7, 12), help="Spreading Factor (7-12)")
@click.option("--bw", type=click.Choice(["125", "250", "500"]), help="Bandwidth in kHz")
@click.option("--cr", type=click.IntRange(5, 8), help="Coding Rate (5-8)")
@click.option("--power", type=int, help="TX power in dBm")
@click.option("--syncword", help="Syncword (public, private, or hex value e.g. 0x2D)")
@click.option("--mode", type=click.Choice(["stream", "command"]), help="LoRa output mode")
@click.option("--apply", is_flag=True, help="Apply staged changes immediately")
@with_device
def config(dev, radio, freq, sf, bw, cr, power, syncword, mode, apply):
    """Stage and apply LoRa radio configuration settings

    Without any parameter it prints the radio's current configuration.
    Parameters are staged on the board and only written to the hardware
    once --apply is passed:

    \b
        flatsat config --radio 0 --freq 915000000 --sf 7 --apply
    """
    print_title(f"RADIO CONFIGURATION - RADIO {radio}")

    # Address every sub-command to the radio EXPLICITLY (R0/R1). Do NOT rely on
    # a prior `radio{radio}` selection + implicit active-radio targeting: in
    # satellite mode the firmware's radio_manager forces active_radio back to
    # rx_radio on every tick (radio_manager.c), so an implicit `lora_freq <hz>`
    # can race and land on the wrong radio (e.g. R1's 916 MHz applied to R0).
    # The firmware accepts an optional R0|R1|ALL prefix on all lora_* commands.
    rp = f"R{radio}"
    print_info(f"Configuring Radio {radio} (explicit {rp} addressing)")

    staged = False
    if freq is not None:
        res = send_cmd(dev, f"lora_freq {rp} {freq}")
        print_dim(f"Frequency        -> {freq} Hz: {_fmt(res)}")
        staged = True
    if sf is not None:
        res = send_cmd(dev, f"lora_sf {rp} {sf}")
        print_dim(f"Spreading Factor -> SF{sf}: {_fmt(res)}")
        staged = True
    if bw is not None:
        res = send_cmd(dev, f"lora_bw {rp} {bw}")
        print_dim(f"Bandwidth        -> {bw} kHz: {_fmt(res)}")
        staged = True
    if cr is not None:
        res = send_cmd(dev, f"lora_cr {rp} {cr}")
        print_dim(f"Coding Rate      -> 4/{cr}: {_fmt(res)}")
        staged = True
    if power is not None:
        res = send_cmd(dev, f"lora_power {rp} {power}")
        print_dim(f"Power            -> {power} dBm: {_fmt(res)}")
        staged = True
    if syncword is not None:
        res = send_cmd(dev, f"lora_syncword {rp} {syncword}")
        print_dim(f"Syncword         -> {syncword}: {_fmt(res)}")
        staged = True
    if mode is not None:
        res = send_cmd(dev, f"lora_mode {rp} {mode}")
        print_dim(f"Mode             -> {mode}: {_fmt(res)}")
        staged = True

    if apply or staged:
        if apply:
            apply_res = send_cmd(dev, f"lora_apply {rp}")
            print_success(f"Applying changes: {_fmt(apply_res)}")
        else:
            print_warning("Changes are STAGED but not yet applied. Run with --apply to write to hardware.")
    else:
        # No staging parameters, show current config for this radio
        cfg_res = send_cmd(dev, f"lora_config {rp}")
        if cfg_res:
            print_response(cfg_res.strip())
