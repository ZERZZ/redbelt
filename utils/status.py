"""
utils/status.py — quick TCP reachability probes.

Doesn't care who is listening or how — just opens a socket to the
configured host:port and sees if anything answers. Used by the
settings UI.
"""

import socket
import subprocess

import config.config as config


def _probe(host: str | None, port: int | None, timeout: float = 0.4) -> bool:
    """Return True if a TCP connection to host:port succeeds."""
    if not host or not port:
        return False
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def is_http_up() -> bool:
    """True if something is accepting connections on the configured HTTP port."""
    return _probe("127.0.0.1", config.get_port())


def is_listener_up() -> bool:
    port = str(config.get_listener_port())

    try:
        result = subprocess.run(
            ["ss", "-tulnp"],
            capture_output=True,
            text=True,
            timeout=0.5
        )

        # look for the port in output
        return f":{port} " in result.stdout

    except Exception as e:
        print(f"[DEBUG] ss probe failed: {e}")
        return False