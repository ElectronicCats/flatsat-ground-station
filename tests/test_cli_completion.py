import os
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from modules.core.cli import cli


@patch("platform.system", return_value="Windows")
def test_completion_windows_unsupported(mock_platform):
    runner = CliRunner()
    result = runner.invoke(cli, ["completion", "install"])
    assert result.exit_code == 1
    assert "Shell completion is not supported on Windows" in result.output


@patch("subprocess.run")
@patch("pathlib.Path.home")
def test_completion_install_bash(mock_home, mock_subproc, tmp_path):
    mock_home.return_value = tmp_path
    mock_subproc.return_value = MagicMock(stdout="_complete_flatsat() { :; }")

    runner = CliRunner(env={"SHELL": "/bin/bash"})
    result = runner.invoke(cli, ["completion", "install", "--shell", "bash"])

    assert result.exit_code == 0
    assert "Completion script written to" in result.output
    target = tmp_path / ".local" / "share" / "bash-completion" / "completions" / "flatsat"
    assert target.exists()
    assert target.read_text() == "_complete_flatsat() { :; }"


@patch("subprocess.run")
@patch("pathlib.Path.home")
def test_completion_install_zsh(mock_home, mock_subproc, tmp_path):
    mock_home.return_value = tmp_path
    mock_subproc.return_value = MagicMock(stdout="#compdef flatsat")

    runner = CliRunner()
    result = runner.invoke(cli, ["completion", "install", "--shell", "zsh"])

    assert result.exit_code == 0
    target = tmp_path / ".zfunc" / "_flatsat"
    assert target.exists()
    zshrc = tmp_path / ".zshrc"
    assert zshrc.exists()
    assert ".zfunc" in zshrc.read_text()


@patch("subprocess.run")
@patch("pathlib.Path.home")
def test_completion_install_fish(mock_home, mock_subproc, tmp_path):
    mock_home.return_value = tmp_path
    mock_subproc.return_value = MagicMock(stdout="complete -c flatsat")

    runner = CliRunner()
    result = runner.invoke(cli, ["completion", "install", "--shell", "fish"])

    assert result.exit_code == 0
    target = tmp_path / ".config" / "fish" / "completions" / "flatsat.fish"
    assert target.exists()


def test_completion_unknown_shell():
    runner = CliRunner(env={"SHELL": "/bin/unknownsh"})
    result = runner.invoke(cli, ["completion", "install"])

    assert result.exit_code == 1
    assert "Could not detect shell" in result.output


@patch("subprocess.run", side_effect=RuntimeError("Subprocess failed"))
def test_completion_subprocess_error(mock_subproc):
    runner = CliRunner()
    result = runner.invoke(cli, ["completion", "install", "--shell", "bash"])

    assert result.exit_code == 1
    assert "Failed to generate completion script" in result.output
