"""Session layer: discover/select FlatSat devices and exchange shell commands.

This is the only CLI module that talks to the shared `core/` package, keeping
device I/O out of the command and UI layers.
"""

import functools
import sys

import click

from modules.core.device import FlatSatDevice
from modules.core.serial_manager import discover_devices
from modules.utils.output import print_dim, print_error, print_info


DEVICE_HELP = "Target FlatSat board: index from 'flatsat devices' or its serial number."
PORT_HELP = "Force direct connection to a custom shell port (e.g. /dev/ttyACM3)."


def flatsat_get_devices():
    """Return all connected FlatSat boards with their ACM port mapping.

    Mirrors catnip_get_devices() from CatSniffer: a thin, importable wrapper
    around the discovery routine so callers don't need to know it lives in
    core.serial_manager.
    """
    return discover_devices()


def _match_device(devices, selector):
    """Find a device by its list index or serial number. None if no match."""
    sel_str = str(selector)
    if sel_str.isdigit() and int(sel_str) < len(devices):
        return devices[int(sel_str)]
    return next((d for d in devices if d.identity.serial_number.lower() == sel_str.lower()), None)


def _print_available(devices):
    print_info("Available devices:")
    for i, d in enumerate(devices):
        print_dim(f"[{i}] Serial: {d.identity.serial_number} | Shell: {d.shell_port} | Health: {d.health.name}")


def get_selected_device(device=None, port=None):
    """Resolve which device to connect to."""
    if port:
        from modules.core.serial_manager import (
            ENDPOINT_SHELL,
            DeviceIdentity,
            DiscoveredDevice,
            _normalize_port_path,
        )

        norm_port = _normalize_port_path(port)
        print_info(f"Attempting direct shell connection on: {norm_port}")
        identity = DeviceIdentity(serial_number="direct")
        ports = {ENDPOINT_SHELL: norm_port}
        return FlatSatDevice(DiscoveredDevice(identity=identity, ports=ports))

    devices = flatsat_get_devices()

    if not devices:
        print_error("No FlatSat boards detected. Is it plugged in?")
        sys.exit(1)

    if device is not None:
        match = _match_device(devices, device)
        if match is None:
            print_error(f"FlatSat device '{device}' not found.")
            _print_available(devices)
            sys.exit(1)
        return FlatSatDevice(match)

    if len(devices) == 1:
        return FlatSatDevice(devices[0])

    # Multiple devices, none specified
    print_error("Multiple FlatSat devices connected. Please specify one with -d/--device:")
    _print_available(devices)
    sys.exit(1)


def get_device_or_exit(device=None, port=None):
    """Resolve and connect a FlatSat device, or exit with an error."""
    dev = get_selected_device(device=device, port=port)

    # Connect WITHOUT forcing a role (forced_role=None): each CLI command is a
    # separate process that connects and disconnects, so forcing a mode here
    # would flip the board's role on every command (e.g. a satellite would be
    # knocked back to ground station and stop beaconing telemetry). Commands
    # that need a specific mode (e.g. `mode`) set it explicitly themselves.
    if not dev.connect().get("shell"):
        print_error("Failed to open Shell serial interface.")
        sys.exit(1)

    return dev


def with_device(func):
    """Connect the target board and pass it to the command as first argument.

    Adds `-d/--device` and `-p/--port` to the command, so they work after the
    subcommand (`flatsat status -d 0`). The root group declares the same
    options, so they also work before it (`flatsat -d 0 status`); when both are
    given, the one on the subcommand wins. The port is closed even if the
    command raises. Apply it closest to the function, with click options above:

        @click.command("color")
        @click.argument("r", type=int)
        @with_device
        def color(dev, r): ...
    """

    @click.pass_context
    def wrapper(ctx, *args, device=None, port=None, **kwargs):
        opts = ctx.obj or {}
        dev = get_device_or_exit(
            device=device if device is not None else opts.get("device"),
            port=port if port is not None else opts.get("port"),
        )
        try:
            return func(dev, *args, **kwargs)
        finally:
            dev.disconnect()

    wrapper = functools.update_wrapper(wrapper, func)
    try:
        del wrapper.__wrapped__
    except AttributeError:
        pass

    wrapper = click.option("-p", "--port", default=None, help=PORT_HELP)(wrapper)
    wrapper = click.option("-d", "--device", default=None, help=DEVICE_HELP)(wrapper)
    return wrapper


def send_cmd(dev, cmd):
    """Send a shell command and return the response with the echo stripped."""
    resp = dev.send_shell_command_full(cmd)
    if not resp:
        return None

    resp = resp.strip()
    cmd_stripped = cmd.strip()

    # Split into lines to strip echo cleanly across Windows/Linux line endings
    lines = resp.splitlines()
    if not lines:
        return ""

    first_line_clean = lines[0].strip()
    if first_line_clean == cmd_stripped:
        lines = lines[1:]
    elif first_line_clean.startswith(cmd_stripped) and not first_line_clean.startswith(f"{cmd_stripped}:"):
        remainder = first_line_clean[len(cmd_stripped):].lstrip()
        if remainder:
            lines[0] = remainder
        else:
            lines = lines[1:]

    return "\n".join(lines).strip()
