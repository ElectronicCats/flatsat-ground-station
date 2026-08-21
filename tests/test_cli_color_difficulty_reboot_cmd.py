from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from modules.core.cli import cli


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_color_valid(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "Color set."

    runner = CliRunner()
    result = runner.invoke(cli, ["color", "255", "128", "0"])

    assert result.exit_code == 0
    mock_send_cmd.assert_called_once_with(mock_dev, "color 255 128 0")
    assert "Color set." in result.output


def test_color_invalid_range():
    runner = CliRunner()
    result = runner.invoke(cli, ["color", "256", "0", "0"])
    assert result.exit_code == 2

    result_neg = runner.invoke(cli, ["color", "-1", "0", "0"])
    assert result_neg.exit_code == 2


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_difficulty_get(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "difficulty: 1 (normal)"

    runner = CliRunner()
    result = runner.invoke(cli, ["difficulty"])

    assert result.exit_code == 0
    mock_send_cmd.assert_called_once_with(mock_dev, "difficulty")
    assert "Security Level: difficulty: 1 (normal)" in result.output


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_difficulty_set_valid(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "Difficulty set to 2"

    runner = CliRunner()
    result = runner.invoke(cli, ["difficulty", "2"])

    assert result.exit_code == 0
    mock_send_cmd.assert_called_once_with(mock_dev, "difficulty 2")
    assert "Difficulty set to 2" in result.output


def test_difficulty_set_invalid_range():
    runner = CliRunner()
    result = runner.invoke(cli, ["difficulty", "5"])
    assert result.exit_code == 2


@patch("modules.core.session.get_device_or_exit")
def test_reboot_command(mock_get_dev):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev

    runner = CliRunner()
    result = runner.invoke(cli, ["reboot"])

    assert result.exit_code == 0
    assert "Rebooting device into BOOTSEL" in result.output
    mock_dev.send_shell_command.assert_called_once_with("reboot", timeout=0.2)


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_cmd_raw_execution(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "lora_freq: 915000000"

    runner = CliRunner()
    result = runner.invoke(cli, ["cmd", "lora_config R0"])

    assert result.exit_code == 0
    mock_send_cmd.assert_called_once_with(mock_dev, "lora_config R0")
    assert "lora_freq: 915000000" in result.output


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_cmd_raw_empty_response(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = None

    runner = CliRunner()
    result = runner.invoke(cli, ["cmd", "silent_command"])

    assert result.exit_code == 0
    assert "No response received" in result.output
