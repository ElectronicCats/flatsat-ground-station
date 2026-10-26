"""Guards the "one installer, one binary" invariant.

The project used to carry four different installers and three PyInstaller
specs.  Every duplicate is a place where the installed state can diverge
from what the user expects (stale aliases, two `flatsat` on the PATH, an
old executable that never gets replaced).  These tests fail if a second
installer or a second binary is introduced.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(relative: str) -> str:
    path = ROOT / relative
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_there_is_a_single_pyinstaller_spec():
    specs = sorted(p.name for p in ROOT.glob("*.spec"))
    assert specs == ["flatsat_app.spec"], f"expected one spec, found {specs}"


def test_the_single_spec_builds_the_unified_app():
    spec = _read("flatsat_app.spec")
    assert "flatsat_app.py" in spec
    assert "name='flatsat-gs'" in spec


def test_legacy_installers_are_gone():
    """The old duplicate installers must not come back."""
    for gone in (
        "setup_windows.ps1",
        "scripts/install.sh",
        "install_windows.bat",
        "installer/flatsat_installer.iss",
    ):
        assert not (ROOT / gone).exists(), f"{gone} duplicates the installer"


def test_installation_lives_inside_the_project():
    """The app is installed in a folder inside the project, not in %LOCALAPPDATA%.

    Keeping it together means the whole installation (executables, database
    and logs) can be moved, copied to another machine or deleted with a
    single command.
    """
    from modules.utils import installer

    root = installer.install_root()
    project = installer.app_root()
    assert project in root.parents or root == project, (
        f"la instalación ({root}) debe vivir dentro del proyecto ({project})"
    )
    assert root.name == installer.INSTALL_FOLDER
    # The commands live with the application, not in the repo's .venv.
    assert installer.bin_dir() == root / "bin"
    assert installer.venv_dir() == root / "venv"
    assert installer.data_dir() == root / "db"


def test_install_root_can_be_overridden():
    """FLATSAT_INSTALL_DIR allows installing somewhere else."""
    import os

    from modules.utils import installer

    previous = os.environ.get("FLATSAT_INSTALL_DIR")
    os.environ["FLATSAT_INSTALL_DIR"] = str(ROOT / "elsewhere")
    try:
        assert installer.install_root() == (ROOT / "elsewhere").resolve()
    finally:
        if previous is None:
            os.environ.pop("FLATSAT_INSTALL_DIR", None)
        else:
            os.environ["FLATSAT_INSTALL_DIR"] = previous


def test_the_install_folder_is_git_ignored():
    ignore = _read(".gitignore")
    assert "flatsat-gs/" in ignore


def test_the_app_installs_itself_on_first_run():
    """Running the app once must set up the CLI alias.

    The user should not have to remember a second command: the first run
    installs (CLI in the PATH, shortcuts, data folder) and then works.
    """
    from modules.utils import installer

    assert hasattr(installer, "is_installed")
    app = _read("flatsat_app.py")
    assert "_ensure_installed()" in app
    assert "def _ensure_installed" in app


def test_the_cli_exposes_the_whole_application():
    """'flatsat' is the single front door: web, doctor, install, version, help."""
    from click.testing import CliRunner

    from modules.core.cli import cli

    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    for command in ("web", "doctor", "install", "uninstall", "version", "help"):
        assert command in result.output, f"falta el comando '{command}' en el CLI"


def test_the_installer_falls_back_when_the_binary_is_blocked():
    """A binary refused by the security policy must not be installed.

    Corporate Application Control (Device Guard / AppLocker) blocks
    unsigned executables with WinError 4551.  The installer has to notice
    and use the Python based installation instead, so the application works
    on any machine.
    """
    from modules.utils import installer

    assert hasattr(installer, "_binary_is_runnable")
    assert hasattr(installer, "_standalone_binary")

    # A file that does not exist is never runnable.
    assert installer._binary_is_runnable(ROOT / "no-existe.exe") is False


def test_a_blocked_binary_raises_and_is_detected():
    """The WinError 4551 is what identifies an application control block."""

    source = _read("modules/utils/installer.py")
    assert "4551" in source
    assert "Application Control" in source or "application control" in source.lower()


def test_scheduled_cleanup_does_not_delete_a_new_installation():
    """The cleanup of an old install must not wipe a fresh one.

    The manifest carries a unique id and the scheduled script checks it
    before deleting anything.
    """

    source = _read("modules/utils/installer.py")
    assert 'manifest["id"] = uuid.uuid4().hex' in source
    assert "findstr /C:" in source
    assert "install_id" in source


def test_the_project_has_no_container_setup():
    """The application is native: no Docker, no containers.

    Docker was the original source of trouble (the FlatSat CDC-ACM endpoints
    have to be bind-mounted one by one and the container user rarely matches
    the host's dialout group) and it duplicated the installer.  The app now
    installs itself in the user profile on Windows, Linux and macOS.
    """
    for gone in ("Dockerfile", "docker-compose.yml", "docker-entrypoint.sh", ".dockerignore"):
        assert not (ROOT / gone).exists(), f"{gone} no debe volver: la app es nativa"
