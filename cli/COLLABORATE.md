# Contributor's Guide — FlatSat Ground Station CLI

This guide provides instructions for adding new functionalities to the **FlatSat Ground Station CLI** following the **Electronic Cats** CLI architecture standard.

---

## Table of Contents

- [Project Architecture](#project-architecture)
- [CLI Command Structure](#cli-command-structure)
  - [Adding a New CLI Command](#adding-a-new-cli-command)
  - [Device-backed Commands](#device-backed-commands)
- [UI & Output System](#ui--output-system)
- [Packaging & Compilation](#packaging--compilation)

---

## Project Architecture

```
flatsat-ground-station/
├── flatsat_cli.py        # Python launcher entry point
├── setup.py              # Packaging configuration (pip install -e .)
├── pyproject.toml        # PEP 517 build metadata
├── flatsat.spec          # PyInstaller bundle specification
├── Makefile              # Build and installation automation
├── compile.sh            # Linux/macOS executable compiler
├── build_windows.bat     # Windows executable compiler
├── VERSION               # Centralized version string
└── cli/
    ├── app.py            # Root Click group and command registry loader
    ├── session.py        # Board connection & session context manager
    ├── _version.py       # Dynamic version loader
    ├── commands/         # Individual Click command definitions
    │   ├── __init__.py   # COMMANDS list registry
    │   ├── devices.py
    │   ├── sniff.py
    │   └── ...
    └── ui/               # Presentation layer
        ├── banner.py     # Terminal header & ascii art
        ├── output.py     # Rich console output helpers (print_success, etc.)
        └── tables.py     # Rich table formatters
```

---

## CLI Command Structure

### Adding a New CLI Command

1. **Create a module in `cli/commands/<name>.py`**:

```python
import click
from cli.ui.output import print_success, print_error

@click.command("example")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
def example(verbose: bool) -> None:
    """Example command description for --help."""
    print_success("Command executed successfully!")
```

2. **Register the command in `cli/commands/__init__.py`**:

```python
from .example import example

COMMANDS = [
    ...
    example,
]
```

### Device-backed Commands

If your command requires a connected FlatSat board over serial/USB, wrap the callback using `cli.session.with_device`:

```python
import click
from cli.session import with_device
from cli.ui.output import print_response

@click.command("ping")
@with_device
def ping(dev) -> None:
    """Ping the connected FlatSat board."""
    resp = dev.cmd("PING")
    print_response(resp)

```

---

## UI & Output System

Always use standard helper functions from `cli.ui.output` for outputting text:

- `print_success("Message")` -> Green checkmark (✓)
- `print_warning("Message")` -> Yellow warning (⚠)
- `print_error("Message")` -> Red error cross (✗)
- `print_info("Message")` -> Blue info icon (ℹ)
- `print_section("Title")` -> Formatted divider section
- `print_panel("Content", title="Panel")` -> Rich border box panel

---

## Packaging & Compilation

- **Editable Install**: `pip install -e .` or `make install`
- **Compile Standalone Executable**: `./compile.sh` or `make build`
- **Run Tests**: `pytest tests/`
