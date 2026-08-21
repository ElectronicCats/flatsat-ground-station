from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from modules.core.cli import cli


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_config_query_default_r0(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "freq: 915000000 | sf: 7 | bw: 125"

    runner = CliRunner()
    result = runner.invoke(cli, ["config"])

    assert result.exit_code == 0
    assert "RADIO CONFIGURATION - TARGET R0" in result.output
    assert "freq: 915000000" in result.output
    mock_send_cmd.assert_called_once_with(mock_dev, "lora_config R0")


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_config_stage_parameters_with_warning(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "OK"

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "--radio", "1", "--freq", "916000000", "--sf", "8"])

    assert result.exit_code == 0
    assert "RADIO CONFIGURATION - TARGET R1" in result.output
    assert "Changes are STAGED but not yet applied" in result.output
    actual_cmds = [call[0][1] for call in mock_send_cmd.call_args_list]
    assert "lora_freq R1 916000000" in actual_cmds
    assert "lora_sf R1 8" in actual_cmds
    assert "lora_apply R1" not in actual_cmds


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_config_stage_and_apply(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "OK"

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "--radio", "ALL", "--freq", "915000000", "--apply"])

    assert result.exit_code == 0
    assert "Applying changes: OK" in result.output
    actual_cmds = [call[0][1] for call in mock_send_cmd.call_args_list]
    assert "lora_freq ALL 915000000" in actual_cmds
    assert "lora_apply ALL" in actual_cmds


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_config_all_parameters(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "OK"

    runner = CliRunner()
    result = runner.invoke(cli, [
        "config",
        "--radio", "0",
        "--freq", "915000000",
        "--sf", "7",
        "--bw", "250",
        "--cr", "5",
        "--power", "14",
        "--preamble", "8",
        "--iq", "normal",
        "--syncword", "0x2D",
        "--mode", "stream",
        "--apply",
    ])

    assert result.exit_code == 0
    actual_cmds = [call[0][1] for call in mock_send_cmd.call_args_list]
    assert "lora_freq R0 915000000" in actual_cmds
    assert "lora_sf R0 7" in actual_cmds
    assert "lora_bw R0 250" in actual_cmds
    assert "lora_cr R0 5" in actual_cmds
    assert "lora_power R0 14" in actual_cmds
    assert "lora_preamble R0 8" in actual_cmds
    assert "lora_iq R0 normal" in actual_cmds
    assert "lora_syncword R0 0x2D" in actual_cmds
    assert "lora_mode R0 stream" in actual_cmds
    assert "lora_apply R0" in actual_cmds


def test_config_invalid_options():
    runner = CliRunner()
    # Invalid SF (range is 7-12)
    res_sf = runner.invoke(cli, ["config", "--sf", "13"])
    assert res_sf.exit_code == 2

    # Invalid BW (choices: 125, 250, 500)
    res_bw = runner.invoke(cli, ["config", "--bw", "100"])
    assert res_bw.exit_code == 2

    # Invalid Power (range: -9 to 22)
    res_pwr = runner.invoke(cli, ["config", "--power", "30"])
    assert res_pwr.exit_code == 2
