"""Rich table rendering for device listings."""

from rich import box
from rich.table import Table

from modules.utils.output import console


_HEALTH_STYLE = {
    "HEALTHY": "green",
    "PARTIAL": "yellow",
    "CRITICAL": "red",
}


def print_devices_table(devices):
    """Render connected FlatSat boards as a rich table (catnip-style)."""
    table = Table(title=f"Found {len(devices)} FlatSat device(s)", box=box.ROUNDED)
    table.add_column("Device", style="magenta bold", justify="left", no_wrap=True)
    table.add_column("Radio 0 (CDC0)", style="cyan", justify="left")
    table.add_column("Radio 1 (CDC1)", style="cyan", justify="left")
    table.add_column("Shell (CDC2)", style="cyan", justify="left")
    table.add_column("Health", justify="left")

    for i, d in enumerate(devices):
        radio0 = d.radio0_port or "[red]Not found[/red]"
        radio1 = d.radio1_port or "[red]Not found[/red]"
        shell = d.shell_port or "[red]Not found[/red]"
        health_style = _HEALTH_STYLE.get(d.health.name, "white")
        health = f"[{health_style}]{d.health.name}[/{health_style}]"

        table.add_row(f"[{i}] {d.identity.serial_number}", radio0, radio1, shell, health)

    console.print()
    console.print(table)
