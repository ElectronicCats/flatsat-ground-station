"""Launchers for the web dashboard and the diagnostics.

Both the application (``flatsat_app.py``) and the terminal CLI use these, so
``flatsat web`` and ``flatsat-gs`` behave exactly the same.

Standard library only at import time: Flask is imported lazily, inside
:func:`run_web`, so that the CLI stays fast.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

DEFAULT_PORT = 5000
DEFAULT_HOST = "0.0.0.0"


def app_root() -> Path:
    """Directory that holds the application code."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def writable_root() -> Path:
    """Directory where the database and logs are written.

    When the app is installed that is the installation folder (the one that
    holds the executables), so everything lives in the same place and can be
    moved or deleted as a unit.
    """
    preferred = app_root()
    candidates = [preferred]
    parent = preferred.parent
    if (parent / "install-manifest.json").exists():
        candidates.insert(0, parent)
    candidates.append(Path.home() / ".flatsat-ground-station")

    for candidate in candidates:
        try:
            (candidate / "db").mkdir(parents=True, exist_ok=True)
            probe = candidate / "db" / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return candidate
        except OSError:
            continue
    return preferred


def port_is_free(host: str, port: int) -> bool:
    """Check that nothing is already listening on the port.

    Werkzeug sets ``SO_REUSEADDR``, and on Windows that allows *two*
    processes to bind the same port.  The requests then land on either one
    at random and both write to the same SQLite file, which ends in
    "database is locked" and a 500 on the dashboard.  Better to refuse to
    start than to fight over the port.
    """
    import socket

    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        # Same address the server will use: on Windows a 0.0.0.0 listener
        # does not conflict with a 127.0.0.1 bind when SO_REUSEADDR is
        # set, so the check has to use the very same address.
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _open_browser_later(url: str) -> None:
    def _worker() -> None:
        time.sleep(1.5)
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001 - never fail because of the browser
            pass

    threading.Thread(target=_worker, daemon=True).start()


def _print_banner(port: int, host: str) -> None:
    from modules.utils.bootstrap import C_INFO, C_OFF, C_OK, log

    url = f"http://127.0.0.1:{port}" if host in ("0.0.0.0", "::") else f"http://{host}:{port}"
    log("")
    log(f"{C_OK}  ┌──────────────────────────────────────────────────────┐{C_OFF}")
    log(f"{C_OK}  │  FlatSat Ground Station — WebApp                     │{C_OFF}")
    log(f"{C_OK}  └──────────────────────────────────────────────────────┘{C_OFF}")
    log(f"    URL:        {C_INFO}{url}{C_OFF}")
    log("    Usuarios:   admin / password   ·   operator / operator")
    log(f"    Nivel CTF:  {os.environ.get('FLATSAT_LEVEL', '1')}")
    log("    Ctrl+C para detener.")
    log("")


def _start_background(args, argv: list[str]) -> int:
    """Start the webapp detached and give the prompt back to the user."""
    from modules.utils.bootstrap import dim, err, log, ok, warn

    # The child must NOT get --background, or it would spawn another child
    # and the process tree would multiply.
    child_argv = [arg for arg in argv if arg not in ("-b", "--background")]

    if getattr(sys, "frozen", False):
        # The program name already selects the mode for flatsat-web.exe /
        # flatsat.exe, so the "web" token would be an unknown argument.
        from flatsat_app import program_mode

        named = program_mode()
        command = [sys.executable, *child_argv] if named in ("web", "cli") else [sys.executable, "web", *child_argv]
    else:
        command = [
            sys.executable,
            str(Path(__file__).resolve().parent.parent.parent / "flatsat_app.py"),
            "web",
            *child_argv,
        ]

    data_root = writable_root()
    data_root.mkdir(parents=True, exist_ok=True)
    log_file = data_root / "flatsat-web.log"

    try:
        handle = open(log_file, "ab")  # noqa: SIM115 - the child keeps writing to it
    except OSError as exc:
        err(f"No se pudo abrir el log {log_file}: {exc}")
        return 1

    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    env = dict(os.environ)
    env["FLATSAT_WEB_CHILD"] = "1"
    try:
        subprocess.Popen(
            command,
            stdout=handle,
            stderr=handle,
            stdin=subprocess.DEVNULL,
            env=env,
            creationflags=flags,
            close_fds=True,
        )
    except OSError as exc:
        err(f"No se pudo arrancar la webapp: {exc}")
        handle.close()
        return 1

    url = f"http://127.0.0.1:{args.port}"
    ready = False
    for _ in range(120):  # up to ~30 s (a frozen app needs a moment to unpack)
        time.sleep(0.25)
        try:
            with urllib.request.urlopen(f"{url}/login", timeout=1) as resp:
                if resp.status < 500:
                    ready = True
                    break
        except (urllib.error.URLError, OSError):
            continue

    if args.browser:
        _open_browser_later(url)

    if ready:
        ok(f"WebApp en segundo plano: {url}")
    else:
        warn(f"La webapp se ha lanzado pero aún no responde en {url} (revisa el log)")
    dim(f"Log: {log_file}")
    log("")
    log("    Usa 'flatsat -w <comando>' para hablar con ella desde esta misma terminal.")
    log("    Para pararla:  taskkill /IM flatsat-web.exe /F   (o cierra el proceso)")
    log("")
    return 0 if ready else 1


def run_web(argv: list[str] | None = None) -> int:
    """Start the web dashboard."""
    import argparse

    from modules.utils.bootstrap import dim, err

    parser = argparse.ArgumentParser(
        prog="flatsat web",
        description="FlatSat Ground Station — dashboard web",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="interfaz de escucha (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("FLATSAT_PORT", DEFAULT_PORT)))
    parser.add_argument(
        "--level",
        type=int,
        default=int(os.environ.get("FLATSAT_LEVEL", 1)),
        choices=(1, 2, 3),
        help="nivel CTF (1 fácil, 2 medio, 3 difícil)",
    )
    parser.add_argument(
        "--mock", dest="mock", action="store_true", default=True, help="iniciar telemetría simulada (default)"
    )
    parser.add_argument("--no-mock", dest="mock", action="store_false", help="no iniciar telemetría simulada")
    parser.add_argument("--debug", action="store_true", help="activar el reloader de Flask")
    parser.add_argument(
        "--no-browser", dest="browser", action="store_false", default=True, help="no abrir el navegador automáticamente"
    )
    parser.add_argument(
        "-b", "--background", action="store_true", help="arrancar en segundo plano y devolver el prompt"
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    os.environ.setdefault("FLATSAT_LEVEL", str(args.level))
    os.environ.setdefault("FLATSAT_PORT", str(args.port))
    os.environ.setdefault("FLATSAT_DEBUG", "1" if args.debug else "0")
    os.environ.setdefault("FLATSAT_MOCK", "1" if args.mock else "0")

    if args.background:
        # Second safety net: a child must never spawn another child.
        if os.environ.get("FLATSAT_WEB_CHILD") == "1":
            err("El modo background no puede anidarse.")
            return 1
        return _start_background(args, sys.argv[1:])

    root = writable_root()
    os.chdir(root)

    from modules.webapp.app import create_app, socketio

    if not port_is_free(args.host, args.port):
        err(
            f"El puerto {args.port} ya está en uso: hay otra instancia de la webapp "
            "corriendo (o cualquier otro programa)."
        )
        dim("Ciérrala con 'taskkill /IM flatsat-web.exe /F' o usa otro puerto:")
        dim(f"    flatsat web --port {args.port + 1}")
        return 1

    app = create_app()

    if args.browser:
        _open_browser_later(f"http://127.0.0.1:{args.port}")

    _print_banner(args.port, args.host)
    socketio.run(
        app,
        host=args.host,
        port=args.port,
        debug=args.debug,
        allow_unsafe_werkzeug=True,
    )
    return 0


def run_doctor(argv: list[str] | None = None) -> int:
    """Print an environment + serial port report."""
    from modules.utils.bootstrap import dim, log, ok, warn

    log("")
    log("== Entorno ==")
    log(f"  Python:      {sys.version.split()[0]} ({sys.executable})")
    log(f"  SO:          {sys.platform}")
    log(f"  Directorio:  {app_root()}")

    from modules.utils.bootstrap import APP_MODULES

    missing = []
    for name, package in APP_MODULES.items():
        import importlib.util

        try:
            found = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            found = False
        if not found:
            missing.append((name, package))
    if missing:
        log("")
        log("  Faltan dependencias:")
        for name, package in missing:
            log(f"    - {name}  (pip install {package})")
        warn("Ejecuta 'flatsat_app.py install' o 'pip install -r requirements-app.txt'.")
    else:
        ok("Todas las dependencias de la aplicación están disponibles.")

    try:
        from modules.utils.serial_doctor import diagnose

        report = diagnose()
    except Exception as exc:  # noqa: BLE001 - the report is a nicety, not a blocker
        warn(f"No se pudo generar el informe de puertos serie: {exc}")
        return 0

    log("")
    log(report["report"])
    if not report["flatsat_ports"]:
        warn("Sin placa conectada: el dashboard funciona en modo simulado (--mock).")

    try:
        from modules.utils.shell_integration import describe

        describe(log=log)
    except Exception as exc:  # noqa: BLE001 - informative only
        dim(f"(no se pudo inspeccionar los alias de la shell: {exc})")
    return 0
