"""
notify.py — desktop notification helpers
"""

import subprocess
import config.config as config


def _send(title: str, body: str, timeout_ms: int = 2000) -> None:
    try:
        subprocess.Popen(
            ["notify-send", "-t", str(timeout_ms), title, body],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass


def notify_clipboard(cmd: str) -> None:
    if not config.get_notify_clipboard():
        return
    _send("Copied ✓", cmd[:80])

def notify_listener(ip: str) -> None:
    if not config.get_notify_listener():
        return
    _send("Listener", f"New connection from {ip}")

def notify_http(path: str = "") -> None:
    if not config.get_notify_http():
        return
    _send("HTTP", f"Request: {path}" if path else "HTTP request served")