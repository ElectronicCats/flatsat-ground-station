"""Dependency bootstrap helpers shared by every launcher.

This module is deliberately **standard library only**: the launchers must be
able to run before Flask, click or rich are installed, because installing
them is exactly what this module does.

The goal is a "install once" experience without Docker and without a virtual
machine: a project-local virtual environment (``.venv``) is created on demand
and reused afterwards.  Every package involved ships pre-built wheels, so no
compiler is required on any platform.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

# ── Dependency sets ──────────────────────────────────────────────────────────
# Import name -> pip package name. The check uses the exact submodules the
# application imports, so a half-installed environment is not mistaken for a
# working one.

WEB_MODULES: dict[str, str] = {
    "flask": "Flask",
    "flask_socketio": "Flask-SocketIO",
    "simple_websocket": "simple-websocket",
    "serial.tools.list_ports": "pyserial",
    "Crypto.Cipher.AES": "pycryptodome",
}

CLI_MODULES: dict[str, str] = {
    "click": "click",
    "rich": "rich",
    "serial.tools.list_ports": "pyserial",
    "Crypto.Cipher.AES": "pycryptodome",
}

APP_MODULES: dict[str, str] = {**WEB_MODULES, **CLI_MODULES}

# Candidate virtual environment directories, relative to the project root.
VENV_DIRS = (".venv", ".venv-webapp")

BOOTSTRAP_ENV = "FLATSAT_APP_BOOTSTRAPPED"

IS_WINDOWS = os.name == "nt"


# ── Colours ──────────────────────────────────────────────────────────────────
def _colour_enabled() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


if _colour_enabled():
    C_OK = "\033[92m"
    C_WARN = "\033[93m"
    C_ERR = "\033[91m"
    C_INFO = "\033[96m"
    C_DIM = "\033[90m"
    C_OFF = "\033[0m"
else:
    C_OK = C_WARN = C_ERR = C_INFO = C_DIM = C_OFF = ""


def log(message: str) -> None:
    print(message, flush=True)


def step(message: str) -> None:
    log(f"{C_INFO}[*]{C_OFF} {message}")


def ok(message: str) -> None:
    log(f"{C_OK}[+]{C_OFF} {message}")


def warn(message: str) -> None:
    log(f"{C_WARN}[!]{C_OFF} {message}")


def err(message: str) -> None:
    log(f"{C_ERR}[x]{C_OFF} {message}")


def dim(message: str) -> None:
    log(f"{C_DIM}    {message}{C_OFF}")


# ── Detection ────────────────────────────────────────────────────────────────


def missing_modules(modules: dict[str, str]) -> list[str]:
    """Return the import names that are not importable in this interpreter."""
    missing = []
    for module in modules:
        try:
            found = importlib.util.find_spec(module) is not None
        except (ImportError, ValueError):
            found = False
        if not found:
            missing.append(module)
    return missing


def venv_python(venv_dir: Path) -> Path:
    """Interpreter path inside a virtual environment."""
    if IS_WINDOWS:
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def venv_has_deps(python: Path, modules: dict[str, str]) -> bool:
    """Check whether an interpreter can import every requested module."""
    probe = "import " + ", ".join(modules)
    try:
        result = subprocess.run(
            [str(python), "-c", probe],
            capture_output=True,
            timeout=180,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def user_venv_dir() -> Path:
    """Fallback virtual environment location for read-only installs."""
    base = Path(os.environ.get("LOCALAPPDATA", "")) if IS_WINDOWS else Path.home()
    if not base or not str(base):
        base = Path.home()
    return base / ".flatsat-ground-station" / "venv"


# ── Environment preparation ──────────────────────────────────────────────────


def create_venv(venv_dir: Path) -> Path:
    """Create a virtual environment and return its interpreter path."""
    step(f"Creando entorno virtual en {venv_dir}")
    venv_dir.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        if "ensurepip" in detail.lower():
            raise RuntimeError("python3-venv no está instalado. En Debian/Ubuntu: 'sudo apt install python3-venv'")
        raise RuntimeError(detail or "venv falló")
    return venv_python(venv_dir)


def install_requirements(python: Path, requirements_file: Path) -> None:
    """Install the pinned requirements into the given interpreter."""
    if not requirements_file.exists():
        raise RuntimeError(f"no se encuentra {requirements_file}")
    step(f"Instalando dependencias ({requirements_file.name})...")
    result = subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(requirements_file),
        ],
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("pip install falló")


def ensure_environment(
    *,
    modules: dict[str, str],
    requirements_file: Path,
    project_root: Path,
    venv_dirs: tuple[str, ...] = VENV_DIRS,
    label: str = "la aplicación",
    always_create: bool = False,
) -> Path:
    """Return an interpreter able to run the app, creating a venv if needed.

    The current interpreter is returned untouched when it already satisfies
    the requirements.  Otherwise a project-local virtual environment is
    created (or completed) and returned.

    ``always_create`` forces a dedicated virtual environment even when the
    current interpreter would do — that is what the installer needs, so the
    installed app does not depend on an interpreter that may disappear.
    """
    if not always_create and not missing_modules(modules):
        return Path(sys.executable)

    candidates = [project_root / name for name in venv_dirs]

    # 1. Reuse an environment that is already complete.
    for venv_dir in candidates:
        python = venv_python(venv_dir)
        if python.exists() and venv_has_deps(python, modules):
            ok(f"Reutilizando entorno virtual: {venv_dir}")
            return python

    # 2. Complete an environment that exists but is missing packages.
    for venv_dir in candidates:
        python = venv_python(venv_dir)
        if not python.exists():
            continue
        step(f"Completando el entorno virtual: {venv_dir}")
        try:
            install_requirements(python, requirements_file)
        except RuntimeError as exc:
            warn(f"La instalación falló ({exc}).")
            continue
        if venv_has_deps(python, modules):
            ok("Dependencias instaladas")
            return python

    # 3. Create a fresh environment.
    last_error: Exception | None = None
    for venv_dir in (*candidates, user_venv_dir()):
        try:
            python = create_venv(venv_dir)
        except Exception as exc:  # noqa: BLE001 - try the next location
            last_error = exc
            warn(f"No se pudo crear el venv en {venv_dir} ({exc}).")
            continue
        try:
            install_requirements(python, requirements_file)
        except RuntimeError as exc:
            last_error = exc
            warn(f"No se pudieron instalar las dependencias ({exc}).")
            continue
        if venv_has_deps(python, modules):
            ok(f"{label} lista para usar")
            return python

    raise RuntimeError(
        f"no se pudo preparar el entorno: {last_error}. Prueba manualmente: pip install -r {requirements_file}"
    )


def relaunch(python: Path, script: Path, argv: list[str], extra_env: dict[str, str] | None = None) -> None:
    """Re-exec the app with the prepared interpreter (does not return)."""
    env = dict(os.environ)
    env[BOOTSTRAP_ENV] = "1"
    env["PYTHONPATH"] = os.pathsep.join([str(script.parent), env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    if extra_env:
        env.update(extra_env)
    step("Reiniciando con el entorno preparado...")
    if IS_WINDOWS:
        result = subprocess.run([str(python), str(script), *argv], env=env, check=False)
        raise SystemExit(result.returncode)
    os.execve(str(python), [str(python), str(script), *argv], env)
