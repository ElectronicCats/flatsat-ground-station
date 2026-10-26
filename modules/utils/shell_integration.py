"""Shell integration: the aliases and completions the CLI registers.

The CLI is meant to be used from a plain terminal (cmd, PowerShell, macOS
Terminal, any POSIX shell).  Two things get registered on the user's system
and both must disappear when the application is uninstalled:

* **PowerShell profile functions** — ``setup_windows.ps1`` injects
  ``flatsat`` / ``flatsat-web`` / ``flatsat-tui`` functions into the
  PowerShell profile.  A function *shadows* the installed executable, so
  the stale ones are removed when the app is installed (the real ``.exe``
  takes over) and when it is uninstalled.

* **Shell tab completion** — ``flatsat completion install`` drops a script
  in the completion directory of bash/zsh/fish (and, for zsh, a couple of
  lines in ``~/.zshrc``).

Standard library only: this runs before any dependency is available.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Marker used by setup_windows.ps1 around the block it injects.
PS_BLOCK_START = "# --- FlatSat Global Shortcuts (Auto-generated) ---"
PS_BLOCK_END = "# --- End FlatSat Global Shortcuts ---"

# The zsh completion needs these lines in ~/.zshrc.
ZSH_RC_LINES = (
    "fpath=(~/.zfunc $fpath)",
    "autoload -Uz compinit && compinit",
)


# ── PowerShell ──────────────────────────────────────────────────────────────


def powershell_profiles() -> list[Path]:
    """Candidate PowerShell profile paths.

    The Documents folder is often redirected (OneDrive, a company share),
    so the shell itself is asked where the profiles really live.
    """
    candidates: list[Path] = []
    docs = Path.home() / "Documents"
    candidates += [
        docs / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1",
        docs / "PowerShell" / "Microsoft.PowerShell_profile.ps1",
        docs / "WindowsPowerShell" / "profile.ps1",
        docs / "PowerShell" / "profile.ps1",
    ]
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "$PROFILE.CurrentUserAllHosts; $PROFILE.CurrentUserCurrentHost",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if line.lower().endswith(".ps1"):
                candidates.append(Path(line))
    except (OSError, subprocess.SubprocessError):
        pass

    seen: set[str] = set()
    unique: list[Path] = []
    for candidate in candidates:
        key = str(candidate).lower()
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _strip_powershell_block(content: str) -> str:
    """Remove the auto-generated block (and any legacy copy of it)."""
    lines = content.splitlines(keepends=True)
    out: list[str] = []
    inside = False
    for line in lines:
        stripped = line.strip()
        if stripped == PS_BLOCK_START:
            inside = True
            continue
        if inside:
            if stripped == PS_BLOCK_END:
                inside = False
            continue
        out.append(line)
    return "".join(out)


def _strip_legacy_powershell_aliases(content: str) -> str:
    """Remove the alias functions written by older versions of setup_windows.ps1.

    That version did not mark its block, so the pieces are detected by
    their contents: the ``$FLATSAT_DIR``/``$TUI_DIR`` variables, the
    ``flatsat*`` functions and the "Atajos de FlatSat" message.
    """
    lines = content.splitlines(keepends=True)
    out: list[str] = []
    depth = 0
    for line in lines:
        # The file may start with a UTF-8 BOM: it is not part of the code.
        stripped = line.strip().lstrip("﻿")

        if depth > 0:
            # Inside a function body: drop everything until it closes.
            depth += stripped.count("{") - stripped.count("}")
            if depth <= 0:
                depth = 0
            continue

        if stripped.startswith("function flatsat"):
            depth = stripped.count("{") - stripped.count("}")
            if depth <= 0:
                depth = 0
            continue

        if stripped.startswith("$FLATSAT_DIR") or stripped.startswith("$TUI_DIR"):
            continue

        if "Atajos de FlatSat" in stripped or "FlatSat Shortcuts" in stripped:
            continue

        out.append(line)
    return "".join(out)


def remove_powershell_aliases(log=print) -> list[Path]:
    """Delete the FlatSat alias functions from the PowerShell profile(s)."""
    removed: list[Path] = []
    for profile in powershell_profiles():
        if not profile.exists():
            continue
        try:
            raw = profile.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "flatsat" not in raw.lower():
            continue

        # Windows PowerShell reads .ps1 as ANSI without a BOM: keep it.
        has_bom = raw.startswith("﻿")
        content = raw.lstrip("﻿")

        cleaned = _strip_powershell_block(content)
        cleaned = _strip_legacy_powershell_aliases(cleaned)
        if cleaned == content:
            continue
        if not cleaned.strip():
            # Nothing left but whitespace: start from a clean file.
            cleaned = ""
            has_bom = False
        elif has_bom:
            cleaned = "﻿" + cleaned
        try:
            profile.write_text(cleaned, encoding="utf-8")
        except OSError as exc:
            log(f"[!] No se pudo limpiar {profile}: {exc}")
            continue
        removed.append(profile)
        log(f"[-] Alias de PowerShell eliminados de {profile}")
    return removed


def powershell_aliases_present() -> list[Path]:
    """Profiles that still define the FlatSat alias functions."""
    found = []
    for profile in powershell_profiles():
        if not profile.exists():
            continue
        try:
            content = profile.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        if "function flatsat" in content:
            found.append(profile)
    return found


# ── Shell completions ───────────────────────────────────────────────────────


def completion_files() -> list[Path]:
    """Completion scripts installed by 'flatsat completion install'."""
    home = Path.home()
    return [
        home / ".local" / "share" / "bash-completion" / "completions" / "flatsat",
        home / ".zfunc" / "_flatsat",
        home / ".config" / "fish" / "completions" / "flatsat.fish",
    ]


def remove_shell_completions(log=print) -> list[Path]:
    """Delete the tab completion scripts and the zsh wiring."""
    removed: list[Path] = []
    for path in completion_files():
        if not path.exists():
            continue
        try:
            path.unlink()
        except OSError as exc:
            log(f"[!] No se pudo borrar {path}: {exc}")
            continue
        removed.append(path)
        log(f"[-] Completado de shell eliminado: {path}")

    zshrc = Path.home() / ".zshrc"
    if zshrc.exists():
        try:
            content = zshrc.read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""
        lines = content.splitlines(keepends=True)
        kept = [line for line in lines if line.strip() not in ZSH_RC_LINES]
        if len(kept) != len(lines):
            try:
                zshrc.write_text("".join(kept), encoding="utf-8")
                removed.append(zshrc)
                log(f"[-] Configuración de zsh eliminada de {zshrc}")
            except OSError as exc:
                log(f"[!] No se pudo limpiar {zshrc}: {exc}")
    return removed


# ── Reporting ───────────────────────────────────────────────────────────────


def describe(log=print) -> None:
    """Print where the CLI is registered on this machine."""
    log("")
    log("== Alias de la CLI ==")
    for profile in powershell_aliases_present():
        log(f"  PowerShell: {profile} (define 'flatsat' como función)")
    for path in completion_files():
        if path.exists():
            log(f"  Completado: {path}")
    if not powershell_aliases_present() and not any(p.exists() for p in completion_files()):
        log("  (ninguno: la CLI se usa directamente desde el PATH)")
    log("")


if __name__ == "__main__":
    describe()
    sys.exit(0)
