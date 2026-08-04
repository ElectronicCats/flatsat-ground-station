"""Install shell tab completion for the `flatsat` CLI.

Generates the Click completion script for the user's shell and post-processes
it so completion also works when the CLI is launched as
`python flatsat_cli.py ...` / `./flatsat_cli.py ...`, not only when `flatsat`
is on PATH.
"""

import os
import platform
import subprocess
import sys
from pathlib import Path

import click

from cli.ui.output import (
    console,
    print_error,
    print_info,
    print_success,
)

# Click derives these names from the root group's prog_name ("flatsat").
PROG_NAME = "flatsat"
ENV_VAR = "_FLATSAT_COMPLETE"
COMPLETION_FUNC = "_flatsat_completion"
SCRIPT_BASENAME = "flatsat_cli.py"


@click.group("completion", context_settings={"help_option_names": ["-h", "--help"]})
def completion():
    """Install shell tab completion for flatsat."""


@completion.command("install")
@click.option(
    "--shell",
    type=click.Choice(["bash", "zsh", "fish"]),
    default=None,
    help="Shell to install completion for (auto-detected if omitted).",
)
def completion_install(shell):
    """Install tab completion for your shell.

    Run this once, then restart your shell (or source your rc file).

    \b
        flatsat completion install          # auto-detect shell
        flatsat completion install --shell zsh
    """
    if platform.system() == "Windows":
        print_error("Shell completion is not supported on Windows.")
        sys.exit(1)

    if shell is None:
        shell_env = os.environ.get("SHELL", "")
        if "zsh" in shell_env:
            shell = "zsh"
        elif "fish" in shell_env:
            shell = "fish"
        elif "bash" in shell_env:
            shell = "bash"
        else:
            print_error("Could not detect shell. Use --shell bash|zsh|fish.")
            sys.exit(1)
        print_info(f"Detected shell: {shell}")

    # Absolute paths so completion works regardless of PATH: we want it to call
    # "python /abs/path/flatsat_cli.py".
    script_abs = str(Path(sys.argv[0]).resolve())
    python_abs = sys.executable
    cmd_to_call = f"{python_abs} {script_abs}"

    if shell == "bash":
        target = (
            Path.home()
            / ".local"
            / "share"
            / "bash-completion"
            / "completions"
            / PROG_NAME
        )
        source_flag = "bash_source"
        rc_note = None
    elif shell == "zsh":
        target = Path.home() / ".zfunc" / f"_{PROG_NAME}"
        source_flag = "zsh_source"
        rc_note = "fpath=(~/.zfunc $fpath)\nautoload -Uz compinit && compinit"
    elif shell == "fish":
        target = (
            Path.home() / ".config" / "fish" / "completions" / f"{PROG_NAME}.fish"
        )
        source_flag = "fish_source"
        rc_note = None

    try:
        result = subprocess.run(  # noqa: S603 — fixed interpreter + our own script
            [python_abs, script_abs],
            env={**os.environ, ENV_VAR: source_flag},
            capture_output=True,
            text=True,
        )
        script = result.stdout
    except Exception as e:  # noqa: BLE001
        print_error(f"Failed to generate completion script: {e}")
        sys.exit(1)

    if not script.strip():
        print_error(
            "Empty completion script generated.\n"
            "Make sure you are running this command via:\n"
            f"  python {script_abs} completion install"
        )
        sys.exit(1)

    # Post-process: make the bare `flatsat` program name also match the
    # `python flatsat_cli.py` invocation used during development.
    if shell == "zsh":
        script = script.replace(
            f"#compdef {PROG_NAME}",
            f"#compdef {PROG_NAME} {SCRIPT_BASENAME} ./{SCRIPT_BASENAME}",
        )
        # Neutralise the guard that aborts when the command is not on PATH; we
        # call an absolute path instead.
        script = script.replace(
            f"(( ! $+commands[{PROG_NAME}] ))",
            "false",
        )
        script = script.replace(
            f"{ENV_VAR}=zsh_complete {PROG_NAME}",
            f"{ENV_VAR}=zsh_complete {cmd_to_call}",
        )
        script = script.replace(
            f"compdef {COMPLETION_FUNC} {PROG_NAME}",
            f"compdef {COMPLETION_FUNC} {PROG_NAME} {SCRIPT_BASENAME} ./{SCRIPT_BASENAME}",
        )
        # Trigger completion for "python flatsat_cli.py <TAB>" as well.
        script += (
            "\n"
            f"# Enable completion when invoked as 'python {SCRIPT_BASENAME}'\n"
            f"{COMPLETION_FUNC}_python_wrapper() {{\n"
            "  local script_name=${words[2]:t}  # basename of the script argument\n"
            f"  if [[ $script_name == {SCRIPT_BASENAME} ]]; then\n"
            f"    (( ! $+functions[{COMPLETION_FUNC}] )) && source {target}\n"
            f'    words=({PROG_NAME} "${{words[@]:2}}")\n'
            "    (( CURRENT-- ))\n"
            f"    {COMPLETION_FUNC}\n"
            "  else\n"
            "    _files\n"
            "  fi\n"
            "}\n"
            f"compdef {COMPLETION_FUNC}_python_wrapper python python3\n"
        )
    elif shell == "bash":
        # Click 8.x's bash function execs "$1" (whatever command name it is
        # registered under), so it is PATH-independent as long as that name is
        # runnable. We therefore append our own registrations instead of
        # rewriting Click's internal `complete` line (whose exact flags vary by
        # version): the script name resolves via its shebang, and the python
        # wrapper passes the absolute interpreter+script for `python … .py`.
        script += (
            "\n"
            f"# Also complete when invoked as './{SCRIPT_BASENAME}'\n"
            f"complete -o nosort -F {COMPLETION_FUNC} "
            f"{SCRIPT_BASENAME} ./{SCRIPT_BASENAME}\n"
            "\n"
            f"# Enable completion when invoked as 'python {SCRIPT_BASENAME}'.\n"
            "# Click's own function sets IFS=$'\\n', so we can't reuse it here\n"
            "# with a space-joined command; call the app with both paths as\n"
            "# separate literal words and parse the response ourselves.\n"
            f"{COMPLETION_FUNC}_python_wrapper() {{\n"
            '    local script_arg="${COMP_WORDS[1]}"\n'
            f'    if [[ "$(basename "$script_arg")" != "{SCRIPT_BASENAME}" ]]; then\n'
            '        COMPREPLY=( $(compgen -f -- "${COMP_WORDS[COMP_CWORD]}") )\n'
            "        return 0\n"
            "    fi\n"
            "    local IFS=$'\\n'\n"
            f'    local words=({PROG_NAME} "${{COMP_WORDS[@]:2}}")\n'
            "    local cword=$(( COMP_CWORD - 1 ))\n"
            "    local response\n"
            '    response=$(env COMP_WORDS="${words[*]}" COMP_CWORD="$cword" '
            f'{ENV_VAR}=bash_complete "{python_abs}" "{script_abs}")\n'
            "    COMPREPLY=()\n"
            "    local completion type value\n"
            '    for completion in $response; do\n'
            "        IFS=',' read type value <<< \"$completion\"\n"
            "        if [[ $type == 'dir' ]]; then\n"
            "            COMPREPLY=(); compopt -o dirnames\n"
            "        elif [[ $type == 'file' ]]; then\n"
            "            COMPREPLY=(); compopt -o default\n"
            "        elif [[ $type == 'plain' ]]; then\n"
            "            COMPREPLY+=($value)\n"
            "        fi\n"
            "    done\n"
            "}\n"
            f"complete -o default -F {COMPLETION_FUNC}_python_wrapper "
            "python python3\n"
        )
    elif shell == "fish":
        script = script.replace(
            f"{ENV_VAR}=fish_complete {PROG_NAME}",
            f"{ENV_VAR}=fish_complete {cmd_to_call}",
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(script)
    print_success(f"Completion script written to: {target}")

    # zsh needs a fpath entry in .zshrc so the function is picked up.
    if rc_note:
        zshrc = Path.home() / ".zshrc"
        existing = zshrc.read_text() if zshrc.exists() else ""
        if ".zfunc" not in existing:
            with zshrc.open("a") as f:
                f.write(f"\n# flatsat tab completion\n{rc_note}\n")
            print_success(f"Added fpath entry to {zshrc}")
        else:
            console.print(
                "[dim]  ~/.zfunc already in fpath — skipping .zshrc edit[/dim]"
            )

    console.print("")
    if shell == "bash":
        console.print("Restart your shell or run:")
        console.print(f"  [green]source {target}[/green]")
    elif shell == "zsh":
        console.print("Restart your shell or run:")
        console.print("  [green]source ~/.zshrc && compinit -u[/green]")
    elif shell == "fish":
        console.print("Completion is active immediately in new fish sessions.")
