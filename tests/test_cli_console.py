from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from modules.core.cli import cli


@patch("modules.core.session.get_device_or_exit")
def test_console_exit_commands(mock_get_dev):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev

    for exit_word in ["exit", "quit", "q"]:
        runner = CliRunner()
        result = runner.invoke(cli, ["console"], input=f"{exit_word}\n")

        assert result.exit_code == 0
        assert "Connected to FlatSat interactive console" in result.output
        assert "Closing interactive console session" in result.output


@patch("modules.core.session.get_device_or_exit")
def test_console_eof_and_interrupt(mock_get_dev):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev

    runner = CliRunner()
    # Empty input triggers EOFError in input()
    result = runner.invoke(cli, ["console"], input="")

    assert result.exit_code == 0
    assert "Closing interactive console session" in result.output


@patch("time.sleep", return_value=None)
@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_console_identify_and_custom_cmd(mock_get_dev, mock_send_cmd, mock_sleep):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.side_effect = lambda dev, cmd: "OK" if cmd == "identify" else "State: NOMINAL"

    runner = CliRunner()
    result = runner.invoke(cli, ["console"], input="identify\nstatus\nexit\n")

    assert result.exit_code == 0
    assert "LED identification sequence completed" in result.output
    assert "State: NOMINAL" in result.output
    assert mock_send_cmd.call_count == 2


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_console_no_response_and_exception(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.side_effect = [None, RuntimeError("Serial disconnected")]

    runner = CliRunner()
    result = runner.invoke(cli, ["console"], input="unknown_cmd\nfail_cmd\n")

    assert result.exit_code == 0
    assert "No response received for 'unknown_cmd'" in result.output
    assert "Console error: Serial disconnected" in result.output
