"""
output.py - Shared Rich console and output helpers for all CLI modules.
Mirrors the Electronic Cats / catnip design system for CLI output formatting.
"""

from rich.console import Console
from rich.style import Style
from rich.panel import Panel

STYLES = {
    "header": Style(color="cyan", bold=True),
    "success": Style(color="green", bold=True),
    "warning": Style(color="yellow", bold=True),
    "error": Style(color="red", bold=True),
    "info": Style(color="blue", bold=True),
    "dim": Style(dim=True),
    "prompt": Style(color="magenta", bold=True),
    "device": Style(color="cyan"),
}

console = Console()


def print_success(message: str) -> None:
    console.print(f"[green]✓[/green] {message}", style=STYLES["success"])


def print_warning(message: str) -> None:
    console.print(f"[yellow]⚠[/yellow] {message}", style=STYLES["warning"])


def print_error(message: str) -> None:
    console.print(f"[red]✗[/red] {message}", style=STYLES["error"])


def print_info(message: str) -> None:
    console.print(f"[blue]ℹ[/blue] {message}", style=STYLES["info"])


def print_dim(message: str) -> None:
    console.print(f"  {message}", style=STYLES["dim"])


def print_step(step: int, total: int, message: str) -> None:
    console.print(f"[bold]Step {step}/{total}: {message}[/bold]")


def print_section(title: str) -> None:
    sep = "═" * 51
    console.print("")
    console.print(f"[bold]{sep}[/bold]")
    console.print(f"[bold]  {title}[/bold]")
    console.print(f"[bold]{sep}[/bold]")
    console.print("")


def print_error_section(title: str) -> None:
    sep = "═" * 51
    console.print("")
    console.print(f"[bold red]{sep}[/bold red]")
    console.print(f"[bold red]  ⚠  {title}[/bold red]")
    console.print(f"[bold red]{sep}[/bold red]")
    console.print("")


def print_success_section(title: str) -> None:
    sep = "═" * 51
    console.print("")
    console.print(f"[green bold]{sep}[/green bold]")
    console.print(f"[green bold]  ✓  {title}[/green bold]")
    console.print(f"[green bold]{sep}[/green bold]")
    console.print("")


def print_empty_line() -> None:
    console.print("")


def print_title(message: str) -> None:
    console.print(f"\n[cyan bold]{message}[/cyan bold]")


def print_subtitle(message: str) -> None:
    console.print(f"\n  [yellow]{message}[/yellow]")


def print_example(command: str, description: str = "") -> None:
    if description:
        console.print(f"  [green]{command}[/green] {description}")
    else:
        console.print(f"  [green]{command}[/green]")


def print_alias_item(aliases: str, description: str, pad: int = 15) -> None:
    parts = [p.strip() for p in aliases.split("/")]
    colored_aliases = " / ".join(f"[green]{p}[/green]" for p in parts)
    visible_len = sum(len(p) for p in parts) + 3 * (len(parts) - 1)
    padding = " " * max(0, pad - visible_len)
    console.print(f"    {colored_aliases}{padding} → {description}")


def print_response(message: str) -> None:
    """Echo a raw response coming back from the board's shell."""
    console.print(message, style=STYLES["dim"])


def print_panel(content: str, title: str = "", border_style: str = "cyan") -> None:
    """Print a rich panel block."""
    console.print(Panel(content, title=title, border_style=border_style))
