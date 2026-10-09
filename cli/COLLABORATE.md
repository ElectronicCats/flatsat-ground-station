# Contributor's Guide — FlatSat Ground Station CLI

How to add functionality to the **`flatsat` CLI** while following the
Electronic Cats CLI architecture standard.

---

## Table of Contents

- [Where the code actually lives](#where-the-code-actually-lives)
- [Project Architecture](#project-architecture)
- [Adding a New CLI Command](#adding-a-new-cli-command)
- [Device-backed Commands](#device-backed-commands)
- [Output & UI](#output--ui)
- [Rules the CLI enforces](#rules-the-cli-enforces)
- [Testing, Linting & Packaging](#testing-linting--packaging)

---

## Where the code actually lives

**The `cli/` and `core/` directories at the repo root are backward-compatibility
shims.** They contain no logic — each file just re-exports the real module and
rebinds `sys.modules`. The implementation lives under `modules/`:

| Import path you see | Real file | Status |
|---|---|---|
| `cli.app`, `cli.cli` | `modules/core/cli.py` | shim |
| `cli.session` | `modules/core/session.py` | shim |
| `cli.ui.output`, `cli.ui.banner`, `cli.ui.tables` | `modules/utils/` | shim |
| `cli.commands` | `modules/core/cli.py` | shim |
| `core.*` | `modules/core/*` | shim |
| `modules.*` | — | **canonical** |

> **Never add new code under `cli/` or `core/`.** Put it in `modules/`. A
> single change in `modules/core/cli.py` is visible through every legacy import
> path automatically.

---

## Project Architecture

```
flatsat-ground-station/
├── flatsat_cli.py           # `python flatsat_cli.py ...` launcher
├── flatsat.py               # console_script entry point
├── VERSION                  # single source of truth for the version
├── cli/                     # DEPRECATED shims -> modules/ (do not edit)
├── core/                    # DEPRECATED shims -> modules/core/ (do not edit)
├── modules/
│   ├── core/
│   │   ├── cli.py           # ALL Click commands, groups and options
│   │   ├── session.py       # device discovery, with_device, send_cmd
│   │   ├── device.py        # FlatSatDevice: sync serial I/O
│   │   ├── serial_manager.py# USB enumeration, endpoint mapping, health
│   │   ├── ccsds.py         # CCSDS 133.0-B-2 encoder/decoder + SDLS
│   │   ├── shell_parser.py  # regex parsing of shell responses
│   │   ├── radio_bridge.py  # RF transmit path shared with the webapp
│   │   ├── state.py         # GroundStationState
│   │   ├── constants.py     # USB ids, CCSDS values, APIDs, opcodes
│   │   ├── telecommand.py   # command TC builders
│   │   └── telemetry.py     # TM decoding
│   ├── utils/               # presentation + version
│   │   ├── output.py        # rich console and print helpers
│   │   ├── banner.py        # ASCII art header
│   │   ├── tables.py        # rich table renderers
│   │   └── _version.py      # version resolution
│   ├── firmware/verify.py   # firmware diagnostic checks
│   └── webapp/              # Flask + SocketIO dashboard
├── webapp/                  # webapp shims -> modules/webapp/
├── tests/                   # pytest suite
└── toolkit/                 # standalone RF/security scripts
```

### The single-file command convention

Every Click command, group and option lives in **`modules/core/cli.py`**, split
by banner comments:

```
ROOT CLICK GROUP
DEVICE & SYSTEM COMMANDS
SATELLITE & RADIO CONFIGURATION COMMANDS
RF SNIFFER, REPLAY & TRANSMIT COMMANDS
RAW TELECOMMAND (arbitrary APID) AND CTF ATTACK SUITE
TAB COMPLETION COMMAND GROUP
ENTRY POINT
```

This mirrors CatSniffer's `catnip/modules/core/cli.py`. Add new commands to the
matching section rather than creating a new module.

Imports of `modules.core.ccsds` and `modules.core.radio_bridge` are deliberately
**function-local**: they keep crypto and RF code off the startup path for
commands that never transmit. Keep new heavy imports local too.

---

## Adding a New CLI Command

1. **Add the command to `modules/core/cli.py`** in the relevant section:

```python
@cli.command("ping")
@click.option("-c", "--count", type=click.IntRange(1), default=1, show_default=True)
def ping(count):
    """Ping the connected FlatSat board.

    \b
        flatsat ping -c 3
    """
    for i in range(count):
        print_info(f"Ping {i + 1}/{count}")
```

2. **Add the name to `__all__`** at the bottom of `modules/core/cli.py`, and to
   the `COMMANDS` list in `cli/commands/__init__.py` (kept in sync for the
   legacy import path).

3. **Add a test** in `tests/test_cli_<name>.py` using `CliRunner`.

Subcommand groups follow the same pattern — see `completion` and `attack`:

```python
@cli.group("thing", context_settings={"help_option_names": ["-h", "--help"]})
def thing():
    """Group help text."""


@thing.command("sub")
def thing_sub():
    """Subcommand help text."""
```

---

## Device-backed Commands

Wrap the callback in `with_device` to get board discovery, connection and
teardown for free. **Apply it closest to the function, with Click options
above** — the decorator adds its own `-d/--device` and `-p/--port` options:

```python
@cli.command("color")
@click.argument("r", type=click.IntRange(0, 255))
@click.argument("g", type=click.IntRange(0, 255))
@click.argument("b", type=click.IntRange(0, 255))
@with_device
def color(dev, r, g, b):
    """Set the NeoPixel colour."""
    print_response(send_cmd(dev, f"color {r} {g} {b}"))
```

`with_device` passes the connected device as the first argument and always
calls `dev.disconnect()`, even if the command raises.

Use `send_cmd(dev, "...")` rather than `dev.send_shell_command_full(...)`:
it strips the board's command echo, which is otherwise duplicated in output.

### Commands that transmit over RF

Reuse the existing bridge instead of writing serial code:

```python
from modules.core.radio_bridge import RadioBridge
from modules.core.state import GroundStationState

gs = GroundStationState()
gs.set_hardware(dev)
gs.difficulty = difficulty
result = RadioBridge(gs).send_raw(frame)   # {"status": "sent"|"sent_simulated"|"error"}
```

`RadioBridge` owns dual-radio switching, the TX lock and reverting the radio to
stream mode. Do not reimplement any of that.

---

## Output & UI

Always use the helpers in `modules/utils/output.py`. These are the only ones
that exist:

| Helper | Use for |
|---|---|
| `print_success(msg)` | completed successfully (green ✓) |
| `print_warning(msg)` | non-fatal problem (yellow ⚠) |
| `print_error(msg)` | failure (red ✗) |
| `print_info(msg)` | progress / status (blue ℹ) |
| `print_dim(msg)` | indented secondary detail |
| `print_title(msg)` | section heading |
| `print_empty_line()` | blank separator |
| `print_response(msg)` | raw board output — disables Rich markup |
| `print_devices_table(devs)` | the `devices` table |

`print_response` passes `markup=False, highlight=False`, which is what keeps a
board response containing `[something]` from being swallowed as Rich markup.
Use it for any untrusted string.

---

## Rules the CLI enforces

These are load-bearing. Breaking them reintroduces bugs that were fixed and
regression-tested.

**1. Never return 0 after a failure.** Use `_fail()`, which prints through the
UI and exits 1. Scripts, CI and the installer depend on the exit status:

```python
if not output:
    _fail("No status response received from board.")
```

`devices` with nothing plugged in is the one deliberate exception: "no results"
is a legitimate query outcome, not a failure.

**2. Validate option values that reach the board's shell.** Several commands
build one command string by interpolation, so a value containing whitespace or
control characters could smuggle extra commands to the board. Attach
`_validate_shell_safe`:

```python
@click.option("--syncword", callback=_validate_shell_safe,
              help="Syncword (public, private, or hex value e.g. 0x2D)")
```

**3. APIDs are 11-bit and written in hex.** Use `ApidType()` for APID
arguments; plain `click.IntRange` rejects `0x04`.

**4. Do not guess a board's role.** `_detect_local_role()` returns
`"satellite"`, `"ground_station"` or `"unknown"` — never a default. When it
returns `"unknown"`, fail and tell the user to pass `--role` explicitly.
Failing open to `"ground_station"` would radio-command the satellite when a
query merely timed out.

**5. The MET timestamp is the SDLS AES IV.** The firmware derives the IV from
the secondary header timestamp (`attacks.c`, `attacks_decrypt_payload`), so a
telecommand built with `timestamp=0` will not decrypt. Default to
`int(time.time())`.

**6. Reject truncated frames before decoding them.** `_load_frames` drops
entries that are not even-length hex or shorter than `_MIN_FRAME_BYTES`, and
`_bump_seq` raises `ValueError` instead of letting `struct.unpack` fail. Keep
both guards when touching frame parsing.

---

## Testing, Linting & Packaging

```bash
pytest tests/                      # full suite
pytest tests/test_cli_*.py         # CLI only
ruff check .                       # lint (config in ruff.toml)
ruff format .                      # format
```

Some suites need `pip install flask` (the webapp tests); the CLI tests do not.

**Editable install**: `pip install -e .` or `make install`
**Standalone binary**: `./compile.sh` or `make build`

### Adding tests

Device-backed commands are tested by patching the device, never real hardware:

```python
@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_my_command(mock_get_dev, mock_send_raw):
    dev = MagicMock()
    dev.send_shell_command_full.return_value = "difficulty: 0"
    mock_get_dev.return_value = dev
    mock_send_raw.return_value = {"status": "sent", "bytes": 16, "response": "OK"}

    result = CliRunner().invoke(cli, ["my-command"])

    assert result.exit_code == 0
```

Always assert `exit_code` explicitly — including on failure paths, where it
must be non-zero.