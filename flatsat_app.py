#!/usr/bin/env python3
"""FlatSat Ground Station — aplicación unificada (webapp + CLI).

Un único punto de entrada que hace las dos cosas:

    flatsat_app.py              → dashboard web (abre el navegador)
    flatsat_app.py web          → dashboard web con opciones
    flatsat_app.py cli          → CLI interactivo de la estación
    flatsat_app.py doctor       → diagnóstico del entorno y de los puertos serie
    flatsat_app.py install      → instala la app en el perfil del usuario
    flatsat_app.py uninstall    → la desinstala limpiamente
    flatsat_app.py version      → versión

No necesita Docker ni una máquina virtual: la primera ejecución crea un
entorno virtual local e instala las dependencias (todas con ruedas
precompiladas); las siguientes reutilizan ese entorno.

Este archivo sólo usa la biblioteca estándar hasta que las dependencias
están listas, de modo que puede bootstraparse a sí mismo.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Force UTF-8 on Windows consoles (cp1252 would choke on the accents below).
if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - not every stream supports reconfigure
            pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

from modules.utils.bootstrap import (  # noqa: E402
    APP_MODULES,
    BOOTSTRAP_ENV,
    CLI_MODULES,
    WEB_MODULES,
    ensure_environment,
    err,
    log,
    ok,
    relaunch,
)

IS_FROZEN = getattr(sys, "frozen", False)

# ── Program-name dispatch ───────────────────────────────────────────────────
# A single binary behaves differently depending on the name it is invoked
# with, so the installer can expose real executables:
#
#   flatsat-gs.exe   → the whole application (dashboard + CLI + diagnostics)
#   flatsat-web.exe  → the dashboard
#   flatsat.exe      → the interactive CLI
#
# On POSIX the aliases are symlinks, on Windows hard links: all of them
# share the same file.

_PROGRAM_MODES = (
    ("flatsat-web", "web"),
    ("flatsat-dashboard", "web"),
    ("flatsat-cli", "cli"),
    ("flatsat-gs", "gs"),
    ("flatsat-app", "gs"),
)


def program_name() -> str:
    """Base name of the executable (or script) that is running."""
    argv0 = sys.argv[0] if sys.argv else ""
    return Path(argv0).stem.lower()


def program_mode() -> str | None:
    """Mode implied by the program name, or None for the generic launcher."""
    name = program_name()
    if name == "flatsat" or name.startswith("flatsat."):
        return "cli"
    for prefix, mode in _PROGRAM_MODES:
        if name.startswith(prefix):
            return mode
    return None


def app_root() -> Path:
    """Directory that holds the application code."""
    if IS_FROZEN:
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def requirements_file() -> Path:
    return app_root() / "requirements-app.txt"


# ── Modes ────────────────────────────────────────────────────────────────────


def mode_web(argv: list[str]) -> int:
    """Start the web dashboard."""
    from modules.webapp.launcher import run_web

    return run_web(argv)


def mode_doctor(argv: list[str]) -> int:
    """Print an environment + serial port report."""
    from modules.webapp.launcher import run_doctor

    return run_doctor(argv)


def mode_cli(argv: list[str]) -> int:
    """Run the interactive ground station CLI."""
    from modules.core.cli import main

    # The CLI parses sys.argv itself: present the arguments it expects.
    sys.argv = ["flatsat", *argv]
    main()
    return 0


def _ensure_installed() -> None:
    """Install on the first run so the CLI alias is always available.

    The user should not have to remember a second command: running the
    application once sets everything up (CLI in the PATH, shortcuts, data
    folder) and then it just works.
    """
    from modules.utils.installer import install, is_installed

    if is_installed():
        return

    from modules.utils.bootstrap import dim, log, ok, warn

    log("")
    ok("Primera ejecución: instalando FlatSat Ground Station...")
    dim("  (crea el comando 'flatsat' para el CLI, los accesos directos y la carpeta de datos)")
    try:
        install(
            source_root=app_root(),
            frozen=IS_FROZEN,
            requirements_file=requirements_file(),
            modules=APP_MODULES,
            log=log,
        )
    except Exception as exc:  # noqa: BLE001 - never block the app for this
        warn(f"No se pudo completar la instalación automática: {exc}")
        dim("  Puedes instalarla más tarde con: flatsat-gs install")
        return
    log("")
    ok("Instalado. El comando 'flatsat' ya está disponible en cualquier terminal.")
    dim("  Ábrela de nuevo si tu terminal no lo encuentra todavía.")


def mode_install(argv: list[str]) -> int:
    """Install the application (no admin rights needed)."""
    parser = argparse.ArgumentParser(prog="flatsat install")
    parser.parse_args(argv)

    from modules.utils.installer import install

    install(
        source_root=app_root(),
        frozen=IS_FROZEN,
        requirements_file=requirements_file(),
        modules=APP_MODULES,
        log=log,
    )
    log("")
    ok("Instalación completada")
    log("")
    log("    Ya puedes usar FlatSat Ground Station desde cualquier terminal:")
    log("")
    log("      flatsat web            → abre el dashboard en el navegador")
    log("      flatsat devices        → la placa y sus puertos")
    log("      flatsat status         → firmware, modo y estado del radio")
    log("      flatsat sniff -n 3     → capturar tramas CCSDS")
    log("      flatsat doctor         → diagnóstico del entorno")
    log("")
    log("    Accesos directos creados en el menú Inicio.")
    log("    Para desinstalar: flatsat-gs uninstall")
    return 0


def mode_uninstall(argv: list[str]) -> int:
    """Remove the application from the user profile."""
    parser = argparse.ArgumentParser(prog="flatsat uninstall")
    parser.add_argument("--keep-data", action="store_true", help="conservar la base de datos")
    args = parser.parse_args(argv)

    from modules.utils.installer import uninstall

    uninstall(keep_data=args.keep_data, log=log)
    return 0


def mode_version(argv: list[str]) -> int:
    from modules.utils._version import __version__

    log(f"FlatSat Ground Station {__version__}")
    return 0


def console_web() -> int:
    """Entry point for the ``flatsat-web`` console script."""
    return mode_web(sys.argv[1:])


def console_app() -> int:
    """Entry point for the ``flatsat-gs`` console script."""
    return main()


MODES = {
    "web": (mode_web, WEB_MODULES),
    "cli": (mode_cli, CLI_MODULES),
    "doctor": (mode_doctor, WEB_MODULES),
    "install": (mode_install, APP_MODULES),
    "uninstall": (mode_uninstall, set()),
    "version": (mode_version, set()),
}

USAGE = """FlatSat Ground Station

  flatsat_app.py [web]     Dashboard web (abre el navegador)
  flatsat_app.py cli       CLI interactivo de la estación
  flatsat_app.py doctor    Diagnóstico del entorno y los puertos serie
  flatsat_app.py install   Instala la app en el perfil del usuario
  flatsat_app.py uninstall Desinstala la app
  flatsat_app.py version   Muestra la versión
"""


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Bare --help belongs to the application, not to a sub-mode.
    named = program_mode()
    if argv and all(arg in ("-h", "--help") for arg in argv) and named in (None, "gs"):
        log(USAGE)
        return 0

    # ── Program-name dispatch ───────────────────────────────────────────
    # flatsat.exe → CLI, flatsat-web.exe → dashboard, flatsat-gs.exe → app.
    if named == "cli":
        return mode_cli(argv)
    if named == "web":
        _ensure_installed()
        return mode_web(argv)

    mode = "web"
    rest: list[str] = []
    if argv and not argv[0].startswith("-"):
        candidate = argv[0]
        if candidate in MODES:
            mode = candidate
            rest = argv[1:]
        else:
            # Unknown first token: assume it belongs to the CLI, which has
            # many subcommands (devices, status, sniff, ...).
            mode = "cli"
            rest = argv
    elif argv:
        rest = argv

    # First run: set everything up so the CLI alias is always there.
    if mode in ("web", "gs"):
        _ensure_installed()

    handler, modules = MODES[mode]

    # ── Bootstrap ────────────────────────────────────────────────────────
    if not IS_FROZEN and not os.environ.get(BOOTSTRAP_ENV) and modules:
        missing = [name for name in modules if not _importable(name)]
        if missing:
            try:
                python = ensure_environment(
                    modules=modules,
                    requirements_file=requirements_file(),
                    project_root=app_root(),
                    label="La aplicación",
                )
            except RuntimeError as exc:
                err(f"No se pudo preparar el entorno: {exc}")
                return 1
            relaunch(python, Path(__file__).resolve(), argv)

    return handler(rest)


def _importable(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("\nInterrumpido.")
        raise SystemExit(0) from None
