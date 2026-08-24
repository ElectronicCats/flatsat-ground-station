from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from modules.core.cli import cli, main, main_cli
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
    for cmd_name in ["devices", "status", "sensors", "color", "difficulty", "mode", "flight", "config", "sniff", "replay", "transmit"]:
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
    import cli.session
    import cli.commands
    import core.cli
    import core.session
    import core.constants

    # Verify functions exist on shims
    assert hasattr(cli.app, "cli")
    assert hasattr(cli.cli, "status")
    assert hasattr(cli.session, "with_device")
    assert hasattr(core.cli, "cli")
    assert hasattr(core.session, "send_cmd")
    assert hasattr(core.constants, "USB_VID")
    assert len(cli.commands.COMMANDS) >= 15
