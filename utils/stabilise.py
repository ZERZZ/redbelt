"""
utils/stabilise.py — shell stabilisation for reverse-shell listener sessions.


THIS MODULE IS EXPERIMENTAL AND SUBJECT TO CHANGE. SOME ITERATIONS MADE BY AI HAVE BEEN INCORPORATED, BUT THE MODULE IS STILL UNDER ACTIVE DEVELOPMENT.

Once a raw reverse shell lands (nc / rlwrap nc / pwncat), this module upgrades
it to a fully interactive TTY using one of two well-known techniques. Both
methods run the same terminal-fixup tail (Ctrl-Z / stty raw -echo / fg /
reset / export TERM / stty rows) after getting a real shell in place:

  "python"  — pty-spawn stabilisation:
                which <python3-or-python>      (probed live, see below)
                <resolved path> -c 'import pty; pty.spawn("<shell>")'
                <Ctrl-Z>
                stty raw -echo; fg
                reset
                export TERM=<term>
                stty rows <R> columns <C>

  "script"  — wrapper method that needs no python on the target:
                script -qc <shell> /dev/null
                <Ctrl-Z>
                stty raw -echo; fg
                reset
                export TERM=<term>
                stty rows <R> columns <C>

Everything (which method, which python to prefer, what TERM to export,
whether to sync local terminal size, which shell to spawn, whether to run
at all) is driven by config.SHELL_STABILISATION — nothing here is
hardcoded, so changing settings in the GUI changes behaviour with no code
edits.

Python discovery is done *live* against the remote pane rather than by
stuffing an OR-chained one-liner into the target's shell: we send a plain
`which <binary>` for each candidate (in configured preference order),
read the pane back with `tmux capture-pane`, and use whatever absolute
path comes back. If neither candidate resolves, we fall back to the
"script" method automatically. This keeps what actually gets typed into
the session clean and matches what you'd type by hand.

listener.py calls `maybe_stabilise(tmux_session_name)` right after a new
session is recorded, passing the *name* of the tmux session the shell is
running in (not a Popen handle — the shell lives inside a tmux pane, and
tmux is the only thing holding its stdin, so we drive it via
`tmux send-keys` instead of writing to a pipe).
"""

from __future__ import annotations

import os
import shlex
import subprocess
import time
import traceback
from typing import Callable

import config.config as config


# ─── tmux helpers (mirrors listener.py's private helpers; kept local here
#     to avoid a circular import between listener.py and stabilise.py) ────────

def _tmux_has_session(name: str) -> bool:
    result = subprocess.run(
        ["tmux", "has-session", "-t", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _tmux_send(session_name: str, keys: str, literal: bool = True, enter: bool = True) -> bool:
    """
    Send a line of input into the listener's tmux pane.
    """
    if not _tmux_has_session(session_name):
        return False

    cmd = ["tmux", "send-keys", "-t", session_name]
    if literal:
        cmd += ["-l", keys]
    else:
        cmd += [keys]

    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if result.returncode != 0:
        return False

    if enter:
        enter_result = subprocess.run(
            ["tmux", "send-keys", "-t", session_name, "Enter"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if enter_result.returncode != 0:
            return False

    return True


def _tmux_send_ctrl_z(session_name: str, settle_delay: float = 0.3) -> bool:
    """
    Attempt to suspend the foreground process in the pane (nc / rlwrap /
    whatever is holding stdin) so `fg` can resume it in raw mode.
    """
    if not _tmux_has_session(session_name):
        return False

    key_name_result = subprocess.run(
        ["tmux", "send-keys", "-t", session_name, "C-z"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    time.sleep(settle_delay)

    literal_result = subprocess.run(
        ["tmux", "send-keys", "-t", session_name, "-l", "\x1a"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    return key_name_result.returncode == 0 and literal_result.returncode == 0


def _ctrl_z_suspend_confirmed(
    session_name: str,
    log: Callable[[str], None],
    poll_attempts: int = 5,
    poll_delay: float = 0.4,
) -> bool:

    for _ in range(poll_attempts):
        time.sleep(poll_delay)
        output = _tmux_capture_pane(session_name, history_lines=6)
        if "Stopped" in output or "stopped" in output:
            return True

    log(
        "[stabilise] Ctrl-Z did not suspend the local foreground process — "
        "aborting stabilisation."
    )
    return False


def _tmux_capture_pane(session_name: str, history_lines: int = 10) -> str:
    """Grab recent pane contents so we can read back the result of a probe."""
    result = subprocess.run(
        ["tmux", "capture-pane", "-p", "-t", session_name, "-S", f"-{history_lines}"],
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 else ""


# ─── Local terminal size ──────────────────────────────────────────────────────

def _local_terminal_size() -> tuple[int, int]:
    """(rows, cols) of the local controlling terminal, best effort."""
    try:
        size = os.get_terminal_size()
        return size.lines, size.columns
    except OSError:
        pass

    try:
        with open("/dev/tty") as tty:
            out = subprocess.run(
                ["stty", "size"],
                stdin=tty,
                capture_output=True,
                text=True,
                timeout=1,
            )
        rows, cols = out.stdout.strip().split()
        return int(rows), int(cols)
    except Exception:
        return 24, 80


# ─── Binary discovery ─────────────────────────────────────────────────────────────────────

def _python_candidates() -> list[str]:
    """Preference order for the remote python binary, from config."""
    pref = config.get_shell_python_preference()
    return ["python3", "python"] if pref == "python3_first" else ["python", "python3"]


def _parse_which_output(pane_text: str, binary: str) -> str | None:
    """
    Pull the most recent absolute path for `binary` out of captured pane
    text. 
    """
    for line in reversed(pane_text.strip().splitlines()):
        line = line.strip()
        if line.startswith("/") and binary in line and " " not in line:
            return line
    return None


def _probe_remote_python(
    session_name: str,
    log: Callable[[str], None],
    delay: float,
) -> str | None:

    for binary in _python_candidates():
        if not _tmux_send(session_name, f"which {binary}", literal=True, enter=True):
            log(f"[stabilise] failed to send probe for {binary!r}")
            return None

        time.sleep(delay)
        output = _tmux_capture_pane(session_name)
        resolved = _parse_which_output(output, binary)

        if resolved:
            log(f"[stabilise] {binary} -> {resolved}")
            return resolved

        log(f"[stabilise] {binary} not found on remote")

    return None


# ─── Command builders ─────────────────────────────────────────────────────────────────

def _stabilisation_tail(rows: int, cols: int) -> list[str]:
    term = config.get_shell_export_term()

    lines = [
        "__CTRL_Z__",
        "stty raw -echo; fg",
        "", 
        "reset",
        f"export TERM={shlex.quote(term)}",
    ]

    if config.get_shell_sync_stty_size():
        lines.append(f"stty rows {rows} columns {cols}")

    return lines


def _script_method_commands(rows: int, cols: int) -> list[str]:
    """`script` wrapper method — no python required on the remote box."""
    shell = config.get_shell_path()
    return [f"script -qc {shlex.quote(shell)} /dev/null", *_stabilisation_tail(rows, cols)]


def _python_method_commands(rows: int, cols: int, python_path: str) -> list[str]:
    shell = config.get_shell_path()
    return [f'{python_path} -c \'import pty;pty.spawn("{shell}")\'', *_stabilisation_tail(rows, cols)]


def _resolve_method() -> str:
    """'auto' currently resolves to the python-pty technique; 'script' and
    'python' are honoured explicitly."""
    method = config.get_shell_method()
    return "python" if method == "auto" else method


# ─── Public API ───────────────────────────────────────────────────────────────

def build_stabilisation_plan() -> dict:
    method = _resolve_method()
    rows, cols = (
        _local_terminal_size() if config.get_shell_auto_identify_terminal() else (24, 80)
    )

    if method == "script":
        commands = _script_method_commands(rows, cols)
    else:
        placeholder_path = f"/usr/bin/{_python_candidates()[0]}"
        commands = _python_method_commands(rows, cols, placeholder_path)

    return {
        "method": method,
        "rows": rows,
        "cols": cols,
        "shell_path": config.get_shell_path(),
        "export_term": config.get_shell_export_term(),
        "commands": commands,
    }


def stabilise(
    tmux_session_name: str | None,
    log: Callable[[str], None] = print,
    line_delay: float = 0.4,
    probe_delay: float = 0.6,
) -> bool:

    if not tmux_session_name:
        log("[stabilise] no tmux session name provided — nothing to send.")
        return False

    if not _tmux_has_session(tmux_session_name):
        log(f"[stabilise] tmux session {tmux_session_name!r} not running — nothing to send.")
        return False

    method = _resolve_method()
    rows, cols = (
        _local_terminal_size() if config.get_shell_auto_identify_terminal() else (24, 80)
    )

    try:
        if method == "script":
            commands = _script_method_commands(rows, cols)
        else:
            resolved_python = _probe_remote_python(tmux_session_name, log, probe_delay)
            if resolved_python is None:
                log("[stabilise] no python found on remote — falling back to script method")
                commands = _script_method_commands(rows, cols)
            else:
                commands = _python_method_commands(rows, cols, resolved_python)

        log(f"[stabilise] method={method} rows={rows} cols={cols}")

        for line in commands:
            if line == "__CTRL_Z__":
                ok = _tmux_send_ctrl_z(tmux_session_name)
                if ok:
                    ok = _ctrl_z_suspend_confirmed(tmux_session_name, log)
                    if not ok:
                        return False
            else:
                ok = _tmux_send(tmux_session_name, line, literal=True, enter=True)

            if not ok:
                log(f"[stabilise] failed sending line {line!r} to tmux session {tmux_session_name!r}")
                return False

            time.sleep(line_delay)

        log("[stabilise] sequence sent")
        return True
    except Exception:
        log("[stabilise] unexpected error")
        log(traceback.format_exc())
        return False


def maybe_stabilise(tmux_session_name: str | None, log: Callable[[str], None] = print) -> bool:
    """
    Convenience wrapper for listener.py: no-ops (returns False) unless
    shell_stabilisation.auto_stabilise is enabled in config, otherwise
    delegates to stabilise().
    """
    if not config.get_shell_auto_stabilise():
        return False
    return stabilise(tmux_session_name, log=log)