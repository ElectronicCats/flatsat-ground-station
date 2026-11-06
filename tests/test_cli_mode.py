from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from modules.core.cli import cli


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_mode_query_no_args(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "role: ground_station"

    runner = CliRunner()
    result = runner.invoke(cli, ["mode"])

    assert result.exit_code == 0
    assert "Current role: role: ground_station" in result.output
    mock_send_cmd.assert_called_once_with(mock_dev, "mode")


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_mode_mission_sequence(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "OK"

    runner = CliRunner()
    result = runner.invoke(cli, ["mode", "mission"])

    assert result.exit_code == 0
    assert "Mode set to 'mission'." in result.output
    expected_calls = ["mode sat", "lora_mode ALL stream", "lora_apply ALL", "identify"]
    actual_cmds = [call[0][1] for call in mock_send_cmd.call_args_list]
    assert actual_cmds == expected_calls


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_mode_ground_station_sequence(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "OK"

    runner = CliRunner()
    result = runner.invoke(cli, ["mode", "ground_station"])

    assert result.exit_code == 0
    assert "Mode set to 'ground_station'." in result.output
    expected_calls = ["mode gs", "lora_mode ALL command", "lora_apply ALL", "identify"]
    actual_cmds = [call[0][1] for call in mock_send_cmd.call_args_list]
    assert actual_cmds == expected_calls


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_mode_raw_sequence(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "OK"

    runner = CliRunner()
    result = runner.invoke(cli, ["mode", "raw"])

    assert result.exit_code == 0
    assert "Mode set to 'raw'." in result.output
    expected_calls = ["mode gs", "lora_mode ALL stream", "lora_apply ALL", "identify"]
    actual_cmds = [call[0][1] for call in mock_send_cmd.call_args_list]
    assert actual_cmds == expected_calls


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_mode_tinygs(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "OK"

    runner = CliRunner()
    result = runner.invoke(cli, ["mode", "tinygs", "--profile", "my_sat"])

    assert result.exit_code == 0
    assert "TinyGS spoofing 'my_sat'" in result.output
    expected_cmds = ["lora_mode ALL stream", "tinygs spoof my_sat", "identify"]
    actual_cmds = [call[0][1] for call in mock_send_cmd.call_args_list]
    assert actual_cmds == expected_cmds


def test_mode_invalid_choice():
    runner = CliRunner()
    result = runner.invoke(cli, ["mode", "invalid_role"])
    assert result.exit_code == 2


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_mode_sat_alias_matches_mission(mock_get_dev, mock_send_cmd):
    """`sat` is an alias of `mission` and must issue the same shell sequence."""
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "OK"

    result = CliRunner().invoke(cli, ["mode", "sat"])

    assert result.exit_code == 0
    assert "Mode set to 'sat'." in result.output
    actual_cmds = [c[0][1] for c in mock_send_cmd.call_args_list]
    assert actual_cmds == ["mode sat", "lora_mode ALL stream", "lora_apply ALL", "identify"]


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_mode_gs_alias_matches_ground_station(mock_get_dev, mock_send_cmd):
    """`gs` is an alias of `ground_station`."""
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "OK"

    result = CliRunner().invoke(cli, ["mode", "gs"])

    assert result.exit_code == 0
    assert "Mode set to 'gs'." in result.output
    actual_cmds = [c[0][1] for c in mock_send_cmd.call_args_list]
    assert actual_cmds == ["mode gs", "lora_mode ALL command", "lora_apply ALL", "identify"]


def test_mode_sequences_have_no_duplicate_aliases():
    """MODE_SEQUENCES must hold one entry per canonical role, aliases live elsewhere."""
    from modules.core.cli import MODE_ALIASES, MODE_SEQUENCES

    assert set(MODE_SEQUENCES) == {"mission", "ground_station", "raw"}
    for alias, canonical in MODE_ALIASES.items():
        assert alias not in MODE_SEQUENCES, f"{alias} should only exist in MODE_ALIASES"
        assert canonical in MODE_SEQUENCES
