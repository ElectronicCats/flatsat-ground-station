from unittest.mock import patch

from click.testing import CliRunner

from modules.core.cli import cli, main
from modules.utils._version import __version__


def test_cli_version():
    runner = CliRunner()
    res1 = runner.invoke(cli, ["--version"])
    assert res1.exit_code == 0
    assert __version__ in res1.output

    res2 = runner.invoke(cli, ["-V"])
    assert res2.exit_code == 0
    assert __version__ in res2.output


def test_cli_help():
    runner = CliRunner()
    res = runner.invoke(cli, ["--help"])
    assert res.exit_code == 0
    assert "FlatSat Host CLI: manage and configure your FlatSat boards easily." in res.output
    # Check that commands are listed
    for cmd_name in ["devices", "status", "sensors", "color", "difficulty", "mode",
                     "flight", "config", "sniff", "replay", "transmit", "tc", "attack"]:
        assert cmd_name in res.output


def test_cli_global_options():
    runner = CliRunner()
    # Using devices command since it doesn't require hardware connection
    with patch("modules.core.cli.flatsat_get_devices", return_value=[]):
        res = runner.invoke(cli, ["-d", "0", "-p", "/dev/ttyACM5", "devices"])
        assert res.exit_code == 0


@patch("modules.core.cli.print_banner")
@patch("modules.core.cli.cli")
def test_main_with_and_without_banner(mock_cli, mock_banner):
    with patch.dict("os.environ", {}, clear=True):
        main()
        mock_banner.assert_called_once()

    mock_banner.reset_mock()
    with patch.dict("os.environ", {"_FLATSAT_COMPLETE": "bash_source"}):
        main()
        mock_banner.assert_not_called()


def test_compatibility_shims():
    import cli.app
    import cli.cli
    import cli.commands
    import cli.session
    import core.cli
    import core.constants
    import core.session

    # Verify functions exist on shims
    assert hasattr(cli.app, "cli")
    assert hasattr(cli.cli, "status")
    assert hasattr(cli.session, "with_device")
    assert hasattr(core.cli, "cli")
    assert hasattr(core.session, "send_cmd")
    assert hasattr(core.constants, "USB_VID")
    assert len(cli.commands.COMMANDS) >= 15


def test_banner_is_deterministic_under_seeded_random():
    """The phrase is chosen per render, so a seeded RNG gives stable output."""
    import random

    from modules.utils.banner import pick_phrase, print_banner

    random.seed(1234)
    first = pick_phrase()
    random.seed(1234)
    assert pick_phrase() == first

    # Rendering must not raise now that the phrase is resolved lazily.
    print_banner(None)


def test_banner_root_label_feature_detects_geteuid(monkeypatch):
    """Root detection must not assume os.geteuid() exists (it does not on Windows)."""
    import os

    from modules.utils import banner

    monkeypatch.delattr(os, "geteuid", raising=False)
    assert banner._running_as_root() is False

    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
    assert banner._running_as_root() is True


def test_cli_version_shim_matches_canonical():
    """cli._version must forward, not duplicate, the version lookup."""
    import cli._version as legacy
    from modules.utils import _version as canonical

    assert legacy.get_version is canonical.get_version
    assert legacy.__version__ == canonical.__version__


def test_output_helpers_exist():
    """Guard the helpers documented in cli/COLLABORATE.md."""
    from modules.utils import output

    for name in (
        "print_success", "print_warning", "print_error", "print_info",
        "print_dim", "print_title", "print_empty_line", "print_response",
    ):
        assert callable(getattr(output, name)), name
