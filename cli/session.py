"""Session layer: discover/select FlatSat devices and exchange shell commands.

This is the only CLI module that talks to the shared `core/` package, keeping
device I/O out of the command and UI layers.
"""

import functools
import sys

import click

from cli.ui.output import print_dim, print_error, print_info
from core.device import FlatSatDevice
from core.serial_manager import discover_devices


def flatsat_get_devices():
    """Return all connected FlatSat boards with their ACM port mapping.

    Mirrors catnip_get_devices() from CatSniffer: a thin, importable wrapper
    around the discovery routine so callers don't need to know it lives in
    core.serial_manager.
    """
    return discover_devices()


def get_selected_device(serial_number=None, port=None):
    """Resolve which device to connect to."""
    devices = flatsat_get_devices()

    if not devices:
        if port:
            # Fallback to direct port if provided, mock a DiscoveredDevice structure
            from core.serial_manager import ENDPOINT_RADIO0, ENDPOINT_SHELL, DeviceIdentity, DiscoveredDevice

            print_info(f"No devices auto-discovered. Attempting direct shell connection on: {port}")
            identity = DeviceIdentity(serial_number="direct")
            ports = {ENDPOINT_SHELL: port, ENDPOINT_RADIO0: port}  # Minimal endpoints mapping
            return FlatSatDevice(DiscoveredDevice(identity=identity, ports=ports))
        print_error("No FlatSat boards detected. Is it plugged in?")
        sys.exit(1)

    if len(devices) == 1:
        device = devices[0]
        if serial_number and device.serial_number != serial_number:
            print_error(f"Requested device {serial_number} not found. Found: {device.serial_number}")
            sys.exit(1)
        return FlatSatDevice(device)

    if serial_number:
        for d in devices:
            if d.identity.serial_number == serial_number:
                return FlatSatDevice(d)
        print_error(f"Device with serial number {serial_number} not found.")
        print_info("Available devices:")
        for d in devices:
            print_dim(f"{d.identity.serial_number} (Shell: {d.shell_port})")
        sys.exit(1)

    # Multiple devices, none specified
    print_error("Multiple FlatSat devices connected. Please specify one with --serial:")
    for d in devices:
        print_dim(f"Serial: {d.identity.serial_number} | Shell: {d.shell_port} | Health: {d.health.name}")
    sys.exit(1)


def get_device_or_exit(serial_number=None, port=None):
    """Resolve and connect a FlatSat device, or exit with an error."""
    dev = get_selected_device(serial_number=serial_number, port=port)

    if not dev.connect().get("shell"):
        print_error("Failed to open Shell serial interface.")
        sys.exit(1)

    return dev


def with_device(func):
    """Connect the target board and pass it to the command as first argument.

    Reads `--serial` / `--port` from the root group's context so each command
    only declares its own options. The port is closed even if the command
    raises. Apply it closest to the function, with click options above it:

        @click.command("color")
        @click.argument("r", type=int)
        @with_device
        def color(dev, r): ...
    """

    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        opts = ctx.obj or {}
        dev = get_device_or_exit(serial_number=opts.get("serial"), port=opts.get("port"))
        try:
            return func(dev, *args, **kwargs)
        finally:
            dev.disconnect()

    return wrapper


def send_cmd(dev, cmd):
    """Send a shell command and return the response with the echo stripped."""
    resp = dev.send_shell_command_full(cmd)
    if resp:
        resp = resp.strip()
        cmd_stripped = cmd.strip()
        if resp.startswith(cmd_stripped):
            resp = resp[len(cmd_stripped) :].strip()
        return resp
    return None
