#!/usr/bin/env python3
"""FlatSat Host CLI: root click group and command registration.

Holds the global options every command shares (`--device` / `--port`) in the
click context, registers the cli.commands registry on the root group, and
prints the header before dispatching.
"""

import os
import sys

# Force UTF-8 encoding on Windows to prevent UnicodeEncodeError in terminals with legacy code pages
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import click

from cli import __version__, commands
from cli.session import DEVICE_HELP, PORT_HELP
from cli.ui.banner import print_banner


@click.group("flatsat", context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version", prog_name="flatsat")
@click.option("-d", "--device", default=None, help=DEVICE_HELP)
@click.option("-p", "--port", default=None, help=PORT_HELP)
@click.pass_context
def cli(ctx, device, port):
    """FlatSat Host CLI: manage and configure your FlatSat boards easily."""
    ctx.obj = {"device": device, "port": port}


def main() -> None:
    if not os.environ.get("_FLATSAT_COMPLETE"):
        module = next((a for a in sys.argv[1:] if not a.startswith("-")), None)
        print_banner(module)

    for command in commands.COMMANDS:
        cli.add_command(command)

    cli(prog_name="flatsat")


if __name__ == "__main__":
    main()
