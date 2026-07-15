#!/usr/bin/env python3
"""FlatSat Host CLI: root click group and command registration.

Holds the global options every command shares (`--serial` / `--port`) in the
click context, registers the cli.commands registry on the root group, and
prints the header before dispatching.
"""

import os
import sys

import click

from cli import __version__, commands
from cli.ui.banner import print_banner


@click.group("flatsat", context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version", prog_name="flatsat")
@click.option("-s", "--serial", default=None, help="Serial number of the target FlatSat board.")
@click.option("-p", "--port", default=None, help="Force direct connection to a custom shell port (e.g. /dev/ttyACM3).")
@click.pass_context
def cli(ctx, serial, port):
    """FlatSat Host CLI: manage and configure your FlatSat boards easily."""
    ctx.obj = {"serial": serial, "port": port}


def main() -> None:
    if not os.environ.get("_FLATSAT_COMPLETE"):
        module = next((a for a in sys.argv[1:] if not a.startswith("-")), None)
        print_banner(module)

    for command in commands.COMMANDS:
        cli.add_command(command)

    cli(prog_name="flatsat")


if __name__ == "__main__":
    main()
