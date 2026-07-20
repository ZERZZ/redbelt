"""
services/listener.py — manages background listener process (rlwrap, nc / pwncat etc).

Runs the listener inside a detached tmux session instead of a raw Popen pipe.

There are some issues with the connection not closing properly on relaunch, we should explore using a different approach. 

Also banner may be different for pwncat that needs checking.
"""

import subprocess
import threading
import traceback
import time
import os
import re
import shlex
from datetime import datetime
from typing import Callable

import config.config as config
from utils.notify import notify_listener
from utils.stabilise import maybe_stabilise

try:
    from gi.repository import GLib
    _HAS_GLIB = True
except Exception:
    _HAS_GLIB = False


_lock = threading.Lock()
_sessions: list[dict] = []
_session_callbacks: list[Callable[[], None]] = []

_tmux_session_name: str | None = None   # name of tmux session (that seems to stay open even post quit)
_logfile_path: str | None = None        # output log file maybe use in future 
_reader_stop_flag = threading.Event()


# tmux helpers ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _session_name_for(port: int) -> str:
    return f"redbelt_listener_{port}"


def _logfile_for(port: int) -> str:
    return f"/tmp/redbelt_listener_{port}.log"


def _tmux_has_session(name: str) -> bool:
    result = subprocess.run(
        ["tmux", "has-session", "-t", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _tmux_kill_session(name: str) -> None:
    subprocess.run(
        ["tmux", "kill-session", "-t", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _tmux_send_keys(name: str, text: str, enter: bool = True) -> bool:
    """Send raw input into the listener's tmux pane (for stabilisation)"""
    if not _tmux_has_session(name):
        print(f"[DEBUG] _tmux_send_keys: session {name} not running, can't send")
        return False
    cmd = ["tmux", "send-keys", "-t", name, text]
    if enter:
        cmd.append("Enter")
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print(f"[!] tmux send-keys failed: {result.stderr.decode(errors='replace')}")
        return False
    return True


# session bookkeeping  ────────────────────────────────────────────────────────────


def _run_callback_safe(callback: Callable[[], None]) -> bool:
    try:
        callback()
    except Exception as exc:
        print(f"[!] session callback failed: {exc}")
    return False 


def _emit_session_change() -> None:
    callbacks = list(_session_callbacks)
    for callback in callbacks:
        if _HAS_GLIB:
            GLib.idle_add(_run_callback_safe, callback)
        else:
            _run_callback_safe(callback)


def register_session_change_callback(callback: Callable[[], None]) -> None:
    with _lock:
        _session_callbacks.append(callback)


def clear_sessions() -> None:
    with _lock:
        _sessions.clear()
    _emit_session_change()


def get_sessions() -> list[dict]:
    with _lock:
        return [dict(session) for session in _sessions]


def _format_session_label(session: dict) -> str:
    ip = session.get("remote_ip", "unknown")
    port = session.get("remote_port") or "?"
    suffix = " [terminal]" if session.get("terminal_opened") else ""
    return f"{ip}:{port}{suffix}"


def _extract_remote_ip(line: str) -> str | None:
    match = re.search(r"from\s+([0-9A-Fa-f:\.\-]+)", line)
    if match:
        return match.group(1).rstrip(".,;:")
    match = re.search(r"([0-9A-Fa-f:\.\-]+)\s*:\s*\d+", line)
    if match:
        return match.group(1).rstrip(".,;:")
    # nc banner: "connect to [ip] from (UNKNOWN) [10.10.10.5] 54321" (will need to test for pwncat too)
    match = re.search(r"\[([0-9A-Fa-f:\.]+)\]\s+\d+\s*$", line.strip())
    if match:
        return match.group(1)
    return None


def _extract_remote_port(line: str) -> str | None:
    match = re.search(r"port\s+(\d+)", line, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"\s(\d{2,5})\s*$", line.strip())
    if match:
        return match.group(1)
    return None


def record_connection(remote_ip: str | None = None, remote_port: str | None = None, source_line: str | None = None) -> dict:
    with _lock:
        session = {
            "id": f"session-{time.time_ns()}",
            "remote_ip": remote_ip or "unknown",
            "remote_port": remote_port or str(config.get_listener_port()),
            "created_at": datetime.now().strftime("%H:%M:%S"),
            "source": (source_line or "").strip(),
            "terminal_opened": False,
            "label": "",
        }
        session["label"] = _format_session_label(session)
        _sessions.append(session)

        print(f"[DEBUG] record_connection: session created → {session}")

        notify_listener(session["remote_ip"])

        auto_open = config.get_open_terminal_on_listener_connection()
        print(f"[DEBUG] record_connection: auto-open-terminal config = {auto_open}")

        if auto_open:
            opened = open_terminal_for_session(session)
            print(f"[DEBUG] record_connection: open_terminal_for_session returned {opened}")
        else:
            print("[DEBUG] record_connection: NOT opening terminal — config flag is False/disabled")

        _emit_session_change()
        return dict(session)


def open_terminal_for_session(session: dict) -> bool:
    """
    Opens a real terminal attached to the listener's tmux session.
    """
    global _tmux_session_name

    if not _tmux_session_name or not _tmux_has_session(_tmux_session_name):
        print("[WARN] open_terminal_for_session: no live tmux session to attach to")
        return False

    if not config.get_open_terminal_on_listener_connection():
        print("[DEBUG] open_terminal_for_session: config flag is off, refusing to open")
        return False

    attach_cmd_str = f"tmux attach-session -t {shlex.quote(_tmux_session_name)}"

    candidates = (
        ["x-terminal-emulator", "-e", attach_cmd_str],
        ["gnome-terminal", "--", "tmux", "attach-session", "-t", _tmux_session_name],
        ["konsole", "-e", "tmux", "attach-session", "-t", _tmux_session_name],
        ["xterm", "-e", "tmux", "attach-session", "-t", _tmux_session_name],
    )

    for cmd in candidates:
        print(f"[DEBUG] open_terminal_for_session: trying {cmd}")
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            time.sleep(0.3)
            if proc.poll() is not None:
                err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
                print(f"[DEBUG] open_terminal_for_session: {cmd[0]} exited immediately "
                      f"(code={proc.poll()}) stderr={err.strip()!r} — trying next candidate")
                continue

            print(f"[DEBUG] open_terminal_for_session: {cmd[0]} launched OK, PID={proc.pid}, "
                  f"attached to tmux session {_tmux_session_name!r}")
            session["terminal_opened"] = True
            session["label"] = _format_session_label(session)
            return True
        except FileNotFoundError:
            print(f"[DEBUG] open_terminal_for_session: {cmd[0]} not found on PATH")
            continue
        except Exception as exc:
            print(f"[!] failed to launch terminal {cmd}: {exc}")
            continue

    print("[WARN] open_terminal_for_session: ALL terminal candidates failed")
    return False


def open_terminal_for_session_id(session_id: str) -> bool:
    with _lock:
        session = next((item for item in _sessions if item.get("id") == session_id), None)
        if session is None:
            return False
        return open_terminal_for_session(session)


def close_session(session_id: str) -> bool:
    with _lock:
        for idx, session in enumerate(_sessions):
            if session.get("id") == session_id:
                _sessions.pop(idx)
                _emit_session_change()
                return True
    return False


def _maybe_record_connection(line: str) -> None:
    lower = line.lower()
    if "connection" not in lower and "connect" not in lower and "accept" not in lower:
        return

    print(f"[DEBUG] _maybe_record_connection: matched trigger line → {line.strip()!r}")

    remote_ip = _extract_remote_ip(line)
    remote_port = _extract_remote_port(line)

    print(f"[DEBUG] _maybe_record_connection: parsed remote_ip={remote_ip}, remote_port={remote_port}")

    session = record_connection(remote_ip, remote_port, line)

    if config.get_shell_auto_stabilise():
        print(f"[DEBUG] Stabilising session {session['id']}")
        try:
            maybe_stabilise(_tmux_session_name)
        except Exception as exc:
            print(f"[!] maybe_stabilise failed (likely needs updating for tmux): {exc}")


# log tailing (replaces the old stdout/stderr pipe reader) ─────────────────────────────────────────────────────────────


def _tail_logfile(logfile: str, session_name: str) -> None:
    print(f"[DEBUG] Reader started, tailing {logfile} for session {session_name}")

    # wait for the logfile to exist 
    for _ in range(50): 
        if os.path.exists(logfile):
            break
        time.sleep(0.1)

    try:
        with open(logfile, "r", errors="replace") as f:
            f.seek(0, os.SEEK_END)  # only read new output from here on
            while not _reader_stop_flag.is_set():
                line = f.readline()
                if not line:
                    if not _tmux_has_session(session_name):
                        print(f"[DEBUG] _tail_logfile: session {session_name} gone, stopping reader")
                        break
                    time.sleep(0.2)
                    continue
                print(f"[NC-LOG] {line.strip()}")
                _maybe_record_connection(line)
    except Exception:
        print("[DEBUG] Reader crashed")
        print(traceback.format_exc())


# START ─────────────────────────────────────────────────────────────


def start() -> None:
    global _tmux_session_name, _logfile_path

    print("[DEBUG] start() called")

    try:
        with _lock:
            print("[DEBUG] Acquired lock (start)")

            ip = config.get_listener_ip()
            port = config.get_listener_port()
            proto = config.get_listener_proto()

            session_name = _session_name_for(port)
            logfile = _logfile_for(port)

            if _tmux_has_session(session_name):
                print(f"[DEBUG] Listener already running in tmux session {session_name}")
                return

            print(f"[DEBUG] Config → ip={ip}, port={port}, proto={proto}")

            if proto == "nc":
                cmd_list = ["nc", "-lvnp", str(port), "-s", ip]
            elif proto == "rlwrap nc":
                cmd_list = ["rlwrap", "nc", "-lvnp", str(port), "-s", ip]
            elif proto == "pwncat":
                cmd_list = ["pwncat-cs", "-lp", str(port)]
            else:
                raise ValueError(f"Unknown proto: {proto}")

            cmd_str = " ".join(shlex.quote(part) for part in cmd_list)
            print(f"[DEBUG] Command → {cmd_str}")

            # fresh logfile each start
            open(logfile, "w").close()

            create = subprocess.run(
                ["tmux", "new-session", "-d", "-s", session_name, cmd_str],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if create.returncode != 0:
                print(f"[ERROR] tmux new-session failed: {create.stderr.decode(errors='replace')}")
                return

            pipe = subprocess.run(
                ["tmux", "pipe-pane", "-o", "-t", session_name, f"cat >> {shlex.quote(logfile)}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if pipe.returncode != 0:
                print(f"[ERROR] tmux pipe-pane failed: {pipe.stderr.decode(errors='replace')}")
                # not fatal to the listener itself, but detection won't work
            else:
                print(f"[DEBUG] tmux pipe-pane streaming pane output → {logfile}")

            _tmux_session_name = session_name
            _logfile_path = logfile
            _reader_stop_flag.clear()

            print(f"[DEBUG] tmux session {session_name!r} created OK")

        threading.Thread(target=_tail_logfile, args=(logfile, session_name), daemon=True).start()

        time.sleep(0.2)

        print(f"[DEBUG] tmux session alive? → {_tmux_has_session(session_name)}")
        print(f"[*] Listener → {ip}:{port} ({proto}) [tmux session: {session_name}]")

    except Exception as e:
        print("[ERROR] start() failed")
        print(e)
        print(traceback.format_exc())


# STOP ─────────────────────────────────────────────────────────────


def stop() -> None:
    global _tmux_session_name, _logfile_path

    print("[DEBUG] stop() called")

    try:
        with _lock:
            print("[DEBUG] Acquired lock (stop)")

            port = config.get_listener_port()
            session_name = _tmux_session_name or _session_name_for(port)

            print(f"[DEBUG] Killing port via fuser → {port}/tcp")
            subprocess.run(
                ["fuser", "-k", f"{port}/tcp"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("[DEBUG] fuser executed")

            _reader_stop_flag.set()

            if _tmux_has_session(session_name):
                print(f"[DEBUG] Killing tmux session {session_name}")
                _tmux_kill_session(session_name)
                for _ in range(20):
                    if not _tmux_has_session(session_name):
                        break
                    time.sleep(0.1)
            else:
                print("[DEBUG] no tmux session to kill (already gone)")

            _tmux_session_name = None
            _logfile_path = None
            print("[DEBUG] listener state cleared")

    except Exception as e:
        print("[ERROR] stop() failed")
        print(e)
        print(traceback.format_exc())



# STATUS (for settings) ─────────────────────────────────────────────────────────────


def is_running() -> bool:
    if not _tmux_session_name:
        return False
    return _tmux_has_session(_tmux_session_name)


def restart() -> None:
    stop()
    start()