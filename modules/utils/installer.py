"""User-space installer / uninstaller for the FlatSat Ground Station app.

Design goals:

* **No Docker, no virtual machine, no administrator rights.** Everything
  lands in the user profile, so the app can be installed on a lab machine,
  a borrowed laptop or a conference room PC.
* **Install once.** The first run creates a virtual environment and installs
  the pinned wheels; later runs reuse it.
* **Clean uninstall.** Every path that was created is recorded in a
  manifest, so uninstalling removes exactly those and nothing else.

Standard library only: the installer must run before any dependency is
available.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path

from modules.utils.bootstrap import ok, warn
from modules.utils.shell_integration import (
    remove_powershell_aliases,
    remove_shell_completions,
)

IS_WINDOWS = os.name == "nt"

APP_NAME = "FlatSatGroundStation"
APP_TITLE = "FlatSat Ground Station"
MANIFEST_NAME = "install-manifest.json"

# ── Layout ───────────────────────────────────────────────────────────────────

# Name of the folder created inside the project (or next to the binary).
INSTALL_FOLDER = "flatsat-gs"


def app_root() -> Path:
    """Directory that holds the application code.

    The repository when running from source, the directory of the executable
    when running from a frozen build.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def _user_install_root() -> Path:
    """Classic per-user location, used when there is no project around."""
    if IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "Programs" / APP_NAME
    return Path.home() / ".local" / "share" / "flatsat-ground-station"


def find_project_root(start: Path) -> Path | None:
    """Walk up from ``start`` looking for the project markers."""
    try:
        start = start.resolve()
    except OSError:
        return None
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "flatsat_app.py").exists():
            return candidate
    return None


def install_root() -> Path:
    """Base directory where the application is installed.

    It lives **inside the project folder**, so the whole installation —
    executables, database and logs — can be moved, copied to another machine
    or deleted with a single ``rm -rf``.

    * running from the repository  → ``<project>/flatsat-gs``
    * running a binary in ``dist/`` → ``<project>/flatsat-gs`` (the project
      is detected by walking up)
    * a binary downloaded on its own → the classic per-user location

    Override it with the ``FLATSAT_INSTALL_DIR`` environment variable.
    """
    override = os.environ.get("FLATSAT_INSTALL_DIR")
    if override:
        return Path(override).expanduser().resolve()

    root = app_root()
    if not getattr(sys, "frozen", False):
        return root / INSTALL_FOLDER

    # An installed app lives in <root>/bin/<exe>: it IS the installation.
    if (root.parent / MANIFEST_NAME).exists():
        return root.parent

    # A binary inside a project (typically dist/) installs in the project.
    project = find_project_root(root)
    if project is not None:
        return project / INSTALL_FOLDER

    return _user_install_root()


def bin_dir() -> Path:
    """Directory that holds the user-facing commands."""
    return install_root() / "bin"


def path_dir() -> Path:
    """Directory that must be in the PATH for the commands to be found.

    On Windows the executables themselves live in the installation folder
    and that folder is added to the user PATH.  On POSIX the conventional
    place is ``~/.local/bin`` (already in the PATH), so symlinks are
    created there pointing to the installation.
    """
    if IS_WINDOWS:
        return bin_dir()
    return Path.home() / ".local" / "bin"


def venv_dir() -> Path:
    """Virtual environment of the installed application."""
    return install_root() / "venv"


def data_dir() -> Path:
    """Directory that holds the telemetry database."""
    return install_root() / "db"


def manifest_path() -> Path:
    return install_root() / MANIFEST_NAME


# ── Windows PATH handling ────────────────────────────────────────────────────


def _windows_user_path() -> str | None:
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_READ | winreg.KEY_WRITE,
        ) as key:
            value, _ = winreg.QueryValueEx(key, "Path")
            return value
    except OSError:
        return None


def _windows_set_user_path(value: str) -> bool:
    try:
        import winreg
    except ImportError:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_READ | winreg.KEY_WRITE,
        ) as key:
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, value)
        return True
    except OSError:
        return False


def _windows_remove_from_user_path(bindir: Path) -> bool:
    """Drop our bin directory from the user PATH, keeping the rest intact.

    Also removes entries that point to a *previous* installation folder
    (the app may have been installed in another place before), so the PATH
    does not keep pointing at a directory that no longer exists.
    """
    current = _windows_user_path()
    if current is None:
        return False
    entries = current.split(";")
    kept = []
    changed = False
    for entry in entries:
        if not entry:
            continue
        normalised = entry.replace("/", "\\").rstrip("\\")
        if normalised.lower() == str(bindir).replace("/", "\\").rstrip("\\").lower():
            changed = True
            continue
        # A previous installation of the same app, somewhere else.
        if normalised.lower().endswith(f"\\{INSTALL_FOLDER}\\bin"):
            changed = True
            continue
        kept.append(entry)
    if not changed:
        return False
    return _windows_set_user_path(";".join(kept))


def _broadcast_path_change() -> None:
    """Tell Explorer that PATH changed, so new shells pick it up."""
    if not IS_WINDOWS:
        return
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                'Add-Type -Namespace W -Name N -MemberDefinition \'[DllImport("user32.dll")] '
                "public static extern int SendMessageTimeout(int hWnd, int Msg, IntPtr wParam, "
                "IntPtr lParam, int fuFlags, int uTimeout, out IntPtr lpdwResult);'; "
                "$r = [IntPtr]::Zero; "
                "[W.N]::SendMessageTimeout(0xffff, 0x1A, [IntPtr]::Zero, [IntPtr]::Zero, 2, 5000, [ref]$r) | Out-Null",
            ],
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        pass


# ── Desktop / menu integration ──────────────────────────────────────────────


def _write_desktop_file(target: Path, exec_path: Path, args: str = "") -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_TITLE}\n"
        "Comment=FlatSat / CatSniffer ground station dashboard and CLI\n"
        f'Exec="{exec_path}" {args}\n'.rstrip()
        + "\n"
        "Icon=flatsat-gs\n"
        "Terminal=false\n"
        "Categories=Science;Electronics;\n"
        "StartupNotify=true\n",
        encoding="utf-8",
    )


def _write_macos_command_file(target: Path, exec_path: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f'#!/bin/sh\n"{exec_path}"\n',
        encoding="utf-8",
    )
    target.chmod(0o755)


def _write_windows_shortcut(target: Path, exec_path: Path, arguments: str = "") -> None:
    """Create a .lnk shortcut through PowerShell (no third-party dependency)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}'); "
        "$s.TargetPath = '{exe}'; "
        "$s.Arguments = '{args}'; "
        "$s.WorkingDirectory = '{cwd}'; "
        "$s.Description = 'FlatSat Ground Station'; "
        "$s.Save()"
    ).format(
        lnk=str(target),
        exe=str(exec_path),
        args=arguments.replace("'", "''"),
        cwd=str(exec_path.parent),
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _force_remove(func, path, _exc_info) -> None:
    """rmtree error handler: clear read-only flags and retry once."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def _remove_tree(path: Path, skip: tuple[Path, ...] = ()) -> bool:
    """Remove a file or directory tree.

    Returns True only when everything could be deleted.  ``skip`` lists
    sub-directories that must be left alone (for example the folder holding
    the script that is currently running).
    """
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        try:
            path.unlink()
            return True
        except OSError:
            return False
    if not path.is_dir():
        return True

    complete = True
    for item in path.iterdir():
        if any(item == s for s in skip):
            complete = False
            continue
        if not _remove_tree(item):
            complete = False
    try:
        path.rmdir()
    except OSError:
        return False
    return complete


def remove_path(path: Path, *, retries: int = 3, skip: tuple[Path, ...] = ()) -> bool:
    """Delete a file or directory, retrying on Windows sharing violations."""
    for attempt in range(retries):
        if _remove_tree(path, skip=skip):
            return True
        if not path.exists():
            return True
        if attempt < retries - 1:
            time.sleep(0.4)
    return not path.exists()


# ── Manifest ─────────────────────────────────────────────────────────────────


def load_manifest() -> dict:
    path = manifest_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_manifest(manifest: dict) -> None:
    path = manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Install ──────────────────────────────────────────────────────────────────


def _shim_body(runner: list[str], mode: str, extra_args: str = "") -> str:
    """POSIX shim that runs the app with the prepared interpreter."""
    parts = " ".join(f'"{part}"' for part in runner)
    args = " ".join(part for part in (mode, extra_args) if part)
    return f'#!/bin/sh\n# FlatSat Ground Station launcher (generated)\nexec {parts} {args} "$@"\n'.replace("  ", " ")


def _windows_shim_body(runner: list[str], mode: str, extra_args: str = "") -> str:
    parts = " ".join(f'"{part}"' for part in runner)
    args = " ".join(part for part in (mode, extra_args) if part)
    return f"@echo off\r\n{parts} {args} %*\r\n"


# Names of the executables the installer exposes.  They are all the same
# file: the behaviour depends on the name it is invoked with.
EXE_ALIASES = ("flatsat-gs", "flatsat-web", "flatsat")

# Carriage return + line feed, for the generated Windows scripts.
CR = chr(13) + chr(10)


def _binary_is_runnable(path: Path) -> bool:
    """Check that the executable can actually be launched.

    Corporate Application Control (Windows Defender Application Control /
    Device Guard / AppLocker) refuses unsigned executables and the launch
    fails with *WinError 4551 - An Application Control policy has blocked this
    file*.  Installing such a binary would leave a broken application
    behind, so the installer falls back to the source code, which only needs
    the (already allowed) Python interpreter.
    """
    if not path.exists():
        return False
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            [str(path), "version"],
            capture_output=True,
            timeout=60,
            check=False,
            creationflags=flags,
        )
    except OSError as exc:
        winerror = getattr(exc, "winerror", None)
        if winerror == 4551:
            raise
        return False
    return result.returncode == 0


def _standalone_binary(source_root: Path, frozen: bool) -> Path | None:
    """Locate a self-contained binary to install, if there is one.

    A frozen build is always usable (it is running).  From the source tree
    the binary in ``dist/`` is used only if the security policy of the
    machine allows running it.
    """
    if frozen:
        return Path(sys.executable)

    for name in ("flatsat-gs.exe", "flatsat-gs", "flatsat-gs.AppImage"):
        candidate = source_root / "dist" / name
        if candidate.exists():
            return candidate
    return None


def _same_file(a: Path, b: Path) -> bool:
    """True when both paths point to the same file."""
    try:
        return a.exists() and b.exists() and a.samefile(b)
    except OSError:
        return False


def _schedule_windows_replace(jobs: list[tuple[Path, Path]], attempts: int = 15) -> bool:
    """Replace busy files once the processes holding them exit.

    A running executable cannot be overwritten on Windows.  The new files
    are staged next to their targets and a **single** detached script swaps
    them all in as soon as the locks are released (one script, not one per
    file: otherwise the user sees a bunch of console windows appear).
    """
    if not jobs:
        return False
    import tempfile

    try:
        handle, script_name = tempfile.mkstemp(suffix=".bat", prefix="flatsat-replace-")
        script = Path(script_name)
        crlf = "\r\n"
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as fh:
            fh.write("@echo off" + crlf)
            fh.write("ping -n 3 127.0.0.1 > nul" + crlf)
            fh.write(f"for /L %%i in (1,1,{attempts}) do (" + crlf)
            for staged, target in jobs:
                fh.write(f'  move /y "{staged}" "{target}" >nul 2>&1' + crlf)
            fh.write("  ping -n 2 127.0.0.1 > nul" + crlf)
            fh.write(")" + crlf)
            fh.write('del "%~f0"' + crlf)
        subprocess.Popen(
            ["cmd.exe", "/c", str(script)],
            creationflags=(getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)),
            close_fds=True,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _link_alias(source: Path, alias: Path) -> bool:
    """Create ``alias`` pointing at ``source`` (hard link, symlink or copy)."""
    if alias.exists() or alias.is_symlink():
        if not remove_path(alias):
            # Busy: a running executable cannot be replaced on Windows.
            return False
    if IS_WINDOWS:
        try:
            os.link(source, alias)  # NTFS hard link: same file, no extra space
            return True
        except OSError:
            pass
    else:
        try:
            alias.symlink_to(source)
            return True
        except OSError:
            pass

    try:
        shutil.copy2(source, alias)
        return True
    except OSError:
        return False


def is_installed() -> bool:
    """True when the application is already installed (manifest present)."""
    return manifest_path().exists()


def _remove_stale_commands(bindir: Path, keep_suffixes: tuple[str, ...]) -> None:
    """Drop the commands of a previous installation.

    The app can be installed either as real executables or as launcher
    scripts; the leftovers of the other kind would shadow the new ones.
    """
    if not bindir.is_dir():
        return
    for stale in list(bindir.iterdir()):
        if not stale.is_file() or stale.stem not in EXE_ALIASES:
            continue
        if stale.suffix.lower() in keep_suffixes:
            continue
        remove_path(stale)


def install(
    *,
    source_root: Path,
    frozen: bool,
    requirements_file: Path,
    modules: dict[str, str],
    log=print,
) -> dict:
    """Install the application into the user profile.

    ``source_root`` is the directory that contains the application code (the
    repository when running from source, or the directory of the frozen
    executable).

    When a self-contained binary is available (the running one, or a build
    in ``dist/``) the installation is made of **real executables** named
    ``flatsat-gs``, ``flatsat-web`` and ``flatsat`` that share the same
    file.  Otherwise the source tree plus a virtual environment is
    installed and the commands are small launcher scripts.
    """
    root = install_root()
    manifest = load_manifest()
    created: list[str] = manifest.get("created", [])

    root.mkdir(parents=True, exist_ok=True)
    if root not in [Path(p) for p in created]:
        created.append(str(root))

    commands: dict[str, Path] = {}
    runner: list[str] = []
    pending_replace: list[tuple[Path, Path]] = []
    binary = _standalone_binary(source_root, frozen)
    if binary is not None and not frozen:
        # The machine may refuse to run unsigned executables.  Check before
        # installing it, so the user never ends up with a broken app.
        try:
            runnable = _binary_is_runnable(binary)
        except OSError as exc:
            warn(f"El ejecutable {binary.name} está bloqueado por la política de seguridad del sistema.")
            warn(f"  ({exc})")
            warn("  Se instala la versión con Python: los mismos comandos, el mismo comportamiento.")
            binary = None
        else:
            if not runnable:
                warn(f"El ejecutable {binary.name} no se puede ejecutar en este equipo.")
                warn("  Se instala la versión con Python: los mismos comandos, el mismo comportamiento.")
                binary = None
    canonical: Path | None = None
    suffix = ".exe" if IS_WINDOWS else ""

    # When the installation lives inside the project folder there is no
    # point in copying the code into it: the commands can point at the
    # sources that are already there.
    in_place = _is_inside(root, source_root)

    if binary is not None:
        # ── Standalone: real executables that share one file ──────────────
        target_dir = root / "bin"
        target_dir.mkdir(parents=True, exist_ok=True)
        if binary.suffix in (".exe", ".AppImage"):
            suffix = binary.suffix
        canonical = target_dir / f"flatsat-gs{suffix}"

        # Reinstalling from the installed app means the source IS the
        # destination: copying it onto itself would fail (and deleting it
        # first would remove the running executable).
        if _same_file(binary, canonical):
            log(f"[+] Ejecutable ya en su sitio: {canonical}")
        else:
            if canonical.exists():
                remove_path(canonical)
            if canonical.exists():
                # Busy: stage the new file and swap it in later.
                staged = canonical.with_name(canonical.name + ".new")
                shutil.copy2(binary, staged)
                pending_replace.append((staged, canonical))
            else:
                shutil.copy2(binary, canonical)
            canonical.chmod(0o755)
            log(f"[+] Ejecutable copiado a {canonical}")
        runner = [str(canonical)]
    else:
        # ── Source: point at the code and build a dedicated virtual env ────
        from modules.utils.bootstrap import ensure_environment, venv_python

        if in_place:
            app_dir = source_root
            log(f"[+] Instalación dentro del proyecto: {root}")
        else:
            app_dir = root / "app"
            preserved_db = root / "db-preserved"
            if app_dir.exists():
                # Keep the telemetry database across reinstalls.
                src_db = app_dir / "db"
                if src_db.exists() and any(src_db.glob("*.db")):
                    if preserved_db.exists():
                        remove_path(preserved_db)
                    shutil.move(str(src_db), str(preserved_db))
                remove_path(app_dir)
            app_dir.mkdir(parents=True, exist_ok=True)
            for item in ("modules", "webapp", "cli", "core", "db", "flatsat.py", "flatsat_app.py", "VERSION"):
                src = source_root / item
                if not src.exists():
                    continue
                dst = app_dir / item
                if src.is_dir():
                    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                else:
                    shutil.copy2(src, dst)
            if preserved_db.exists():
                target_db = app_dir / "db"
                target_db.mkdir(parents=True, exist_ok=True)
                for db_file in preserved_db.glob("*.db"):
                    shutil.copy2(db_file, target_db / db_file.name)
                remove_path(preserved_db)
                log("[+] Base de datos de telemetría conservada")
            shutil.copy2(requirements_file, app_dir / requirements_file.name)
            log(f"[+] Código copiado a {app_dir}")

        req = app_dir / requirements_file.name
        if not req.exists():
            shutil.copy2(requirements_file, req)

        python = ensure_environment(
            modules=modules,
            requirements_file=req,
            project_root=root,
            venv_dirs=("venv",),
            label="La aplicación",
            always_create=True,
        )
        # ensure_environment may have chosen the current interpreter; make the
        # install self-contained by pointing at the project venv when present.
        local_python = venv_python(venv_dir())
        if local_python.exists():
            python = local_python
        commands["flatsat-gs"] = app_dir / "flatsat_app.py"
        runner = [str(python), str(app_dir / "flatsat_app.py")]

    # ── Commands ─────────────────────────────────────────────────────────
    bindir = bin_dir()
    bindir.mkdir(parents=True, exist_ok=True)
    if str(bindir) not in created:
        created.append(str(bindir))

    if canonical is not None:
        # Real executables: the same file exposed under three names.  The
        # behaviour follows the name it is invoked with.
        # Remove the launcher scripts of a previous installation: they would
        # shadow the executables we are about to create.
        _remove_stale_commands(bindir, keep_suffixes=(".exe", ".AppImage"))
        for name in EXE_ALIASES:
            alias = bindir / f"{name}{suffix}"
            if _same_file(alias, canonical):
                commands[name] = alias
                continue
            if _link_alias(canonical, alias):
                commands[name] = alias
                continue
            # Busy (the app is running): stage it and swap it in later.
            commands[name] = alias
            staged = alias.with_name(alias.name + ".new")
            try:
                shutil.copy2(canonical, staged)
            except OSError:
                commands[name] = canonical
                continue
            pending_replace.append((staged, alias))
            warn(f"{alias.name} está en uso: se actualizará al cerrar la app.")
        log("[+] Alias creados: " + ", ".join(sorted(p.name for p in commands.values())))

        # A single detached script replaces every busy alias at once.
        if pending_replace and _schedule_windows_replace(pending_replace):
            log("[+] Se actualizarán al cerrar la aplicación que los tiene abiertos.")

        # Shims in WindowsApps: already on the PATH, so the commands work in
        # terminals that are already open (they inherit a stale environment).
        if IS_WINDOWS:
            shims = _install_windows_apps_shims(commands, log=log)
            for shim in shims:
                if str(shim) not in created:
                    created.append(str(shim))
    else:
        # Source install: small launcher scripts that call the app with the
        # right sub-command.  Remove the executables of a previous
        # installation: they would shadow the scripts.
        _remove_stale_commands(bindir, keep_suffixes=(".cmd", ".bat", ".sh", ""))
        shims = {
            "flatsat-gs": "",
            "flatsat-web": "web",
            "flatsat": "cli",
        }
        for name, mode in shims.items():
            if IS_WINDOWS:
                shim = bindir / f"{name}.cmd"
                shim.write_text(_windows_shim_body(runner, mode), encoding="utf-8")
            else:
                shim = bindir / name
                shim.write_text(_shim_body(runner, mode), encoding="utf-8")
                shim.chmod(0o755)
            commands[name] = shim

    log(f"[+] Comandos instalados en {bindir}")

    # ── Expose the commands in the PATH ───────────────────────────────────
    # Windows: the bin folder itself is added to the user PATH.
    # POSIX: symlinks in ~/.local/bin, which is already in the PATH.
    exposed = path_dir()
    if exposed != bindir:
        exposed.mkdir(parents=True, exist_ok=True)
        if str(exposed) not in created:
            created.append(str(exposed))
        for name, target in commands.items():
            link = exposed / name
            if link.exists() or link.is_symlink():
                remove_path(link)
            try:
                link.symlink_to(target)
            except OSError:
                log(f"[!] No se pudo crear el enlace {link}")
        log(f"[+] Comandos enlazados en {exposed}")

    # ── Desktop / menu entries ───────────────────────────────────────────
    entry = commands["flatsat-gs"]
    if IS_WINDOWS:
        start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        if start_menu.exists():
            _write_windows_shortcut(start_menu / f"{APP_TITLE}.lnk", entry)
            # The CLI is interactive: keep the console window open.
            _write_windows_shortcut(
                start_menu / f"{APP_TITLE} CLI.lnk",
                commands["flatsat"],
                arguments=f'/k ""{commands["flatsat"]}""',
            )
            for path in (start_menu / f"{APP_TITLE}.lnk", start_menu / f"{APP_TITLE} CLI.lnk"):
                if path not in [Path(p) for p in created]:
                    created.append(str(path))
    else:
        apps_dir = Path.home() / ".local" / "share" / "applications"
        _write_desktop_file(apps_dir / "flatsat-gs.desktop", entry)
        _write_desktop_file(apps_dir / "flatsat-gs-cli.desktop", commands["flatsat"])
        for path in (apps_dir / "flatsat-gs.desktop", apps_dir / "flatsat-gs-cli.desktop"):
            if path not in [Path(p) for p in created]:
                created.append(str(path))
        if sys.platform == "darwin":
            desktop = Path.home() / "Desktop"
            if desktop.is_dir():
                _write_macos_command_file(desktop / f"{APP_TITLE}.command", entry)
                created.append(str(desktop / f"{APP_TITLE}.command"))

    # ── PATH ─────────────────────────────────────────────────────────────
    # On Windows the bin folder of the installation is added to the user
    # PATH; on POSIX the symlinks in ~/.local/bin already do the job.
    if IS_WINDOWS:
        current = _windows_user_path() or ""
        if str(bindir).lower() not in current.lower():
            new_path = f"{current};{bindir}" if current else str(bindir)
            if _windows_set_user_path(new_path):
                # Keep the very first backup: a re-install must not overwrite
                # the original PATH with one that already contains our entry.
                manifest.setdefault("path_backup", current)
                _broadcast_path_change()
                log(f"[+] PATH actualizado: {bindir}")
        else:
            log(f"[*] {bindir} ya estaba en el PATH")
    else:
        if str(exposed) not in os.environ.get("PATH", "").split(os.pathsep):
            manifest["path_note"] = f"add {exposed} to your PATH"

    # ── Alias del shell ──────────────────────────────────────────────────
    # Una función de PowerShell o un alias antiguo tapa al ejecutable
    # instalado, así que se retiran: a partir de aquí 'flatsat' es el
    # ejecutable de verdad, en cualquier terminal.
    stale = remove_powershell_aliases(log=log)
    if stale:
        log("[+] Los alias antiguos de PowerShell se han retirado: ahora manda el ejecutable")

    manifest["created"] = [str(p) for p in created]
    # Unique id: the scheduled cleanup checks it so that a reinstall is
    # not deleted by the cleanup of the previous installation.
    manifest["id"] = uuid.uuid4().hex
    manifest["commands"] = {name: str(path) for name, path in commands.items()}
    manifest["version"] = _read_version(source_root)
    save_manifest(manifest)
    return manifest


def _schedule_windows_removal(path: Path, delay_seconds: int = 3, install_id: str = "") -> bool:
    """Delete a tree once this process has exited.

    Windows locks running executables, so the virtual environment that is
    currently running the uninstaller cannot be deleted from inside it.
    Hand the job over to a detached script that waits a moment and then
    removes the directory.

    The script checks the installation id first: if the app was reinstalled
    in the meantime, the folder belongs to the *new* installation and must
    not be deleted.
    """
    import tempfile

    manifest = path / MANIFEST_NAME
    guard = ""
    if install_id:
        guard = (
            f'if exist "{manifest}" ('
            + CR
            + f'  findstr /C:"{install_id}" "{manifest}" >nul 2>&1 || goto :done'
            + CR
            + ")"
            + CR
        )
    try:
        handle, script_name = tempfile.mkstemp(suffix=".bat", prefix="flatsat-uninstall-")
        script = Path(script_name)
        # newline="" keeps the CRLF we write: with the default translation
        # Python would double the carriage returns and cmd would read the
        # trailing one as part of the path.
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as fh:
            fh.write("@echo off" + CR)
            fh.write("ping -n 3 127.0.0.1 > nul" + CR)
            fh.write(guard)
            # Retry: the executables are hard links of the same file, so
            # a running webapp keeps the whole tree locked until it is closed.
            fh.write("for /L %%i in (1,1,15) do (" + CR)
            fh.write(f'  rmdir /s /q "{path}" >nul 2>&1' + CR)
            fh.write(f'  if not exist "{path}" goto :done' + CR)
            fh.write("  ping -n 2 127.0.0.1 > nul" + CR)
            fh.write(")" + CR)
            fh.write(":done" + CR)
            fh.write('del "%~f0"' + CR)
        subprocess.Popen(
            ["cmd.exe", "/c", str(script)],
            creationflags=(getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)),
            close_fds=True,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _read_version(source_root: Path) -> str:
    version_file = source_root / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return "0.0.0"


# ── Uninstall ────────────────────────────────────────────────────────────────


def _is_inside(path: Path, parent: Path) -> bool:
    """True when ``path`` is ``parent`` or lives inside it."""
    try:
        path = path.resolve()
        parent = parent.resolve()
    except OSError:
        return False
    return path == parent or parent in path.parents


def _windows_apps_dir() -> Path:
    """%LOCALAPPDATA%/Microsoft/WindowsApps - always on the user PATH."""
    return Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps"


def _install_windows_apps_shims(commands: dict[str, Path], log) -> list[Path]:
    """Drop tiny launchers in WindowsApps so the commands work right away.

    A terminal that was already open inherits the environment of its parent,
    so a PATH change in the registry is not seen until it is restarted.  The
    WindowsApps folder is already in the user PATH, so putting the shims
    there makes ``flatsat`` work in every terminal, without any restart.
    """
    created: list[Path] = []
    apps = _windows_apps_dir()
    if not apps.is_dir() or not os.access(apps, os.W_OK):
        return created

    for name, target in commands.items():
        shim = apps / f"{name}.cmd"
        try:
            shim.write_text(f'@echo off\r\n"{target}" %*\r\n', encoding="utf-8")
        except OSError:
            continue
        created.append(shim)
    if created:
        log(f"[+] Atajos en WindowsApps (funcionan sin reiniciar la terminal): {len(created)}")
    return created


def _known_shortcuts() -> list[Path]:
    """Shortcuts and desktop entries the installer creates."""
    if IS_WINDOWS:
        start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        return [
            start_menu / f"{APP_TITLE}.lnk",
            start_menu / f"{APP_TITLE} CLI.lnk",
            _windows_apps_dir() / "flatsat-gs.cmd",
            _windows_apps_dir() / "flatsat-web.cmd",
            _windows_apps_dir() / "flatsat.cmd",
        ]
    apps_dir = Path.home() / ".local" / "share" / "applications"
    return [
        apps_dir / "flatsat-gs.desktop",
        apps_dir / "flatsat-gs-cli.desktop",
    ]


def _remove_install_root(root: Path, log=print) -> list[Path]:
    """Delete the installation folder.

    Returns the paths that could not be removed because something was
    running (Windows locks running executables).
    """
    pending: list[Path] = []
    if not root.exists():
        return pending

    # When the uninstaller runs from the installed app, the executable that
    # launched it is inside the folder: leave it alone and let the scheduled
    # cleanup take care of the tree once this process is gone.
    skip: tuple[Path, ...] = ()
    if IS_WINDOWS and str(root).lower() in str(Path(sys.executable).resolve()).lower():
        skip = (root / "bin", root / "venv")
    if remove_path(root, skip=skip):
        log(f"[-] {root}")
    else:
        pending.append(root)
    return pending


def _schedule_pending_removal(pending: list[Path], log=print, install_id: str = "") -> None:
    """Schedule the deletion of the folders that were busy."""
    if not pending:
        return
    if IS_WINDOWS:
        for path in dict.fromkeys(pending):
            if _schedule_windows_removal(path, install_id=install_id):
                log(f"[*] {path} se borrará en unos segundos (lo tenía abierto el desinstalador)")
        warn(
            "Si la carpeta sigue ahí, es que la webapp o el CLI están corriendo. "
            "Ciérralos y ejecuta 'flatsat-gs uninstall' de nuevo."
        )
    else:
        for path in dict.fromkeys(pending):
            if not remove_path(path):
                warn(f"No se pudo borrar {path}")


def uninstall(*, log=print, keep_data: bool = False) -> bool:
    """Remove everything the installer created.  Returns True on success."""
    manifest = load_manifest()
    root = install_root()

    if not manifest:
        # The app folder was deleted by hand (or the install never finished).
        # There is no manifest, but the PATH entry and the shortcuts may
        # still be there: clean them up anyway.
        log("[!] No hay manifiesto: se limpian los restos conocidos.")
        if IS_WINDOWS and _windows_remove_from_user_path(bin_dir()):
            _broadcast_path_change()
            log("[+] PATH restaurado")
        for shortcut in _known_shortcuts():
            if shortcut.exists():
                if remove_path(shortcut):
                    log(f"[-] {shortcut}")
        remove_powershell_aliases(log=log)
        remove_shell_completions(log=log)
        if root.exists():
            pending = _remove_install_root(root, log=log)
            _schedule_pending_removal(pending, log=log, install_id=manifest.get("id", ""))
        ok("Desinstalación completada")
        return True

    # Restore the Windows user PATH: prefer the original backup, otherwise
    # simply drop our bin directory from the current PATH.
    if IS_WINDOWS:
        restored = False
        if "path_backup" in manifest:
            restored = _windows_set_user_path(manifest["path_backup"])
        else:
            restored = _windows_remove_from_user_path(bin_dir())
        if restored:
            _broadcast_path_change()
            log("[+] PATH restaurado")

    failures = []
    pending: list[Path] = []
    seen: set[str] = set()

    # 1. Everything outside the install root (shortcuts, .desktop entries).
    for item in manifest.get("created", []):
        path = Path(item)
        if str(path) in seen:
            continue
        seen.add(str(path))
        if path == root or root in path.parents:
            continue  # handled together with the install root
        if not path.exists() and not path.is_symlink():
            continue
        if remove_path(path):
            log(f"[-] {path}")
        else:
            failures.append(path)
            warn(f"No se pudo borrar {path} (¿está en uso?)")

    # 2. The install root as a whole: it holds the shims and the virtual
    #    environment, and the interpreter running this uninstaller may live
    #    inside it (Windows locks running executables).
    if keep_data:
        data_dir = Path.home() / ".flatsat-ground-station" / "db"
        src_db = root / "app" / "db"
        if src_db.exists() and any(src_db.glob("*.db")):
            data_dir.mkdir(parents=True, exist_ok=True)
            for db_file in src_db.glob("*.db"):
                shutil.copy2(db_file, data_dir / db_file.name)
            log(f"[*] Base de datos conservada en {data_dir}")

    pending.extend(_remove_install_root(root, log=log))
    remove_path(manifest_path())

    # Los alias del shell (funciones de PowerShell, completados de bash/zsh/fish)
    # se eliminan siempre: si se quedan, tapan al ejecutable instalado.
    remove_powershell_aliases(log=log)
    remove_shell_completions(log=log)

    if not keep_data:
        ok("Desinstalación completada")
    else:
        manifest.pop("created", None)
        manifest.pop("path_backup", None)
        save_manifest(manifest)
        ok("Desinstalación completada (se conservan los datos)")

    _schedule_pending_removal(pending, log=log, install_id=manifest.get("id", ""))

    if failures:
        warn(f"Quedaron {len(failures)} rutas sin borrar; ciérralas y ejecuta el desinstalador de nuevo.")
        return False
    return True
