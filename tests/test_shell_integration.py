"""Tests for the shell alias / completion management."""

from pathlib import Path

from modules.utils import shell_integration as si

LEGACY_BLOCK = """
$FLATSAT_DIR = "C:\\Projects"

function flatsat {
    $python_path = "python"
    & $python_path "flatsat.py" $args
}

function flatsat-web {
    $python_path = "python"
    & $python_path "flatsat.py" web $args
}

Write-Host "Atajos de FlatSat cargados exitosamente" -ForegroundColor Green
"""

MARKED_BLOCK = """
# --- FlatSat Global Shortcuts (Auto-generated) ---
$FLATSAT_DIR = "C:\\Projects"
function flatsat { & "python" "flatsat.py" @args }
# --- End FlatSat Global Shortcuts ---
"""

OTHER_CONTENT = """
function Get-Something { Write-Host "keep me" }
"""


def test_strip_marked_block():
    content = MARKED_BLOCK + OTHER_CONTENT
    cleaned = si._strip_powershell_block(content)
    assert "FlatSat Global Shortcuts" not in cleaned
    assert "Get-Something" in cleaned


def test_strip_legacy_block():
    cleaned = si._strip_legacy_powershell_aliases(LEGACY_BLOCK + OTHER_CONTENT)
    assert "function flatsat" not in cleaned
    assert "$FLATSAT_DIR" not in cleaned
    assert "Atajos de FlatSat" not in cleaned
    assert "Get-Something" in cleaned


def test_strip_legacy_block_handles_bom():
    """A UTF-8 BOM must not hide the first line from the cleaner."""
    content = "﻿" + LEGACY_BLOCK
    cleaned = si._strip_legacy_powershell_aliases(content)
    assert "$FLATSAT_DIR" not in cleaned
    assert "function flatsat" not in cleaned


def test_strip_legacy_block_removes_every_function():
    """The old script injected the block twice; both copies must go."""
    content = LEGACY_BLOCK + LEGACY_BLOCK
    cleaned = si._strip_legacy_powershell_aliases(content)
    assert "function flatsat" not in cleaned
    assert "$FLATSAT_DIR" not in cleaned


def test_strip_keeps_unrelated_content():
    content = OTHER_CONTENT
    assert si._strip_legacy_powershell_aliases(content) == content
    assert si._strip_powershell_block(content) == content


def test_completion_files_are_inside_the_home(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    for path in si.completion_files():
        assert str(path).startswith(str(tmp_path))


def test_remove_shell_completions(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    target = tmp_path / ".local" / "share" / "bash-completion" / "completions" / "flatsat"
    target.parent.mkdir(parents=True)
    target.write_text("# completion script", encoding="utf-8")

    zshrc = tmp_path / ".zshrc"
    zshrc.write_text("export FOO=1\n" + si.ZSH_RC_LINES[0] + "\n", encoding="utf-8")

    removed = si.remove_shell_completions(log=lambda *a: None)
    assert target not in [p for p in removed if p.exists()]
    assert not target.exists()
    assert "fpath=(~/.zfunc" not in zshrc.read_text(encoding="utf-8")
    assert "export FOO=1" in zshrc.read_text(encoding="utf-8")
