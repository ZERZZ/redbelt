"""
services/httpserver.py — manages the background Python HTTP server.
"""

import sys
import threading
import subprocess
from pathlib import Path
from utils.network import get_ip
import config.config as config

_proc: subprocess.Popen | None = None
_lock = threading.Lock()


def start() -> None:
    """Start the HTTP server if it isn't already running."""
    global _proc
    with _lock:
        if _proc and _proc.poll() is None:
            return

        tools_base: Path = config.get_tools_base()
        tools_base.mkdir(parents=True, exist_ok=True)

        _proc = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(config.get_port())],
            cwd=str(tools_base),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    override_ip = config.get_ip_override()

    ip = override_ip if override_ip else get_ip()

    print(f"[*] HTTP server → http://{ip}:{config.get_port()}  ({config.get_tools_base()})")


# STOP ─────────────────────────────────────────────────────────────


def stop() -> None:
    """Terminate the HTTP server if it is running."""
    global _proc

    print("[DEBUG] HTTP stop() called")

    with _lock:
        print("[DEBUG] Acquired lock (http stop)")

        port = config.get_port()
        print(f"[DEBUG] Target port → {port}")

        # kill by port first (fuser appears to be more reliable)
        try:
            print(f"[DEBUG] Running fuser -k {port}/tcp")
            subprocess.run(
                ["fuser", "-k", f"{port}/tcp"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("[DEBUG] fuser executed")
        except Exception as e:
            print(f"[DEBUG] fuser failed: {e}")

        # fallback process cleanup
        if _proc and _proc.poll() is None:
            print(f"[DEBUG] Terminating proc PID={_proc.pid}")
            _proc.terminate()

            try:
                _proc.wait(timeout=3)
                print("[DEBUG] Proc exited cleanly")
            except subprocess.TimeoutExpired:
                print("[DEBUG] Proc kill() fallback")
                _proc.kill()

        _proc = None
        print("[DEBUG] _proc cleared")


def restart() -> None:
    """Stop then start — call after a port or tools_base change."""
    stop()
    start()