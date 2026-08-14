"""Interactive serial console command for persistent board interaction."""

import sys
import click

from cli.session import send_cmd, with_device
from cli.ui.output import print_info, print_success, print_warning, print_response, print_empty_line


@click.command("console")
@with_device
def console(dev):
    """Open a persistent interactive serial console session with the FlatSat board."""
    print_success("Connected to FlatSat interactive console.")
    print_info("Type any command (e.g. status, identify, mode gs, flight nominal) and press Enter.")
    print_info("Type 'exit' or 'quit' to close the session.")
    print_empty_line()

    while True:
        try:
            # Prompt user for input
            prompt_str = "flatsat> "
            try:
                user_input = input(prompt_str)
            except (KeyboardInterrupt, EOFError):
                print_empty_line()
                print_info("Closing interactive console session...")
                break

            cmd_str = user_input.strip()
            if not cmd_str:
                continue

            if cmd_str.lower() in ("exit", "quit", "q"):
                print_info("Closing interactive console session...")
                break

            # Handle identify sleep inside interactive console cleanly
            if cmd_str.lower() == "identify":
                print_info("Identifying FlatSat board (blinking LEDs)...")
                send_cmd(dev, "identify")
                import time
                time.sleep(2.2)
                print_success("LED identification sequence completed.")
                continue

            output = send_cmd(dev, cmd_str)
            if output:
                print_response(output)
            else:
                print_warning(f"No response received for '{cmd_str}'.")


        except Exception as e:
            print_warning(f"Console error: {e}")
            break
