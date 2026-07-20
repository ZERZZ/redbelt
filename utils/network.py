"""
utils/network.py — network helper utilities
Interface enumeration + IPv4 lookup helpers, plus IP detection helpers.
"""

import socket
import struct
import fcntl

import config.config as config


def iface_ip(ifname: str) -> str | None:
    """Return the IPv4 address bound to *ifname*, or None if unavailable."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        r = fcntl.ioctl(
            s.fileno(),
            0x8915,
            struct.pack("256s", ifname[:15].encode())
        )
        return socket.inet_ntoa(r[20:24])
    except OSError:
        return None


def _default_iface() -> str | None:
    """Parse /proc/net/route to find the interface carrying the default route."""
    try:
        with open("/proc/net/route") as f:
            for line in f.readlines()[1:]:
                parts = line.strip().split()
                if parts[1] == "00000000":
                    return parts[0]
    except Exception:
        pass
    return None


def detect_ip_and_iface() -> tuple[str, str]:
    """
    Walk PREFERRED_IFACES first, then fall back to the default-route interface,
    then to loopback.
    """
    for iface in config.PREFERRED_IFACES:
        ip = iface_ip(iface)
        if ip:
            return ip, iface

    iface = _default_iface()
    if iface:
        ip = iface_ip(iface)
        if ip:
            return ip, iface

    return "127.0.0.1", "lo"


def get_ip() -> str:
    """Return the IP to embed in generated commands."""
    override = config.get_ip_override()
    if override:
        return override

    ip, iface = detect_ip_and_iface()
    config.runtime["iface"] = iface
    return ip


def list_ifaces() -> list[tuple[str, str]]:
    """
    Return [(iface, ip), ...] for every interface that has an IPv4 address.
    Falls back to loopback if nothing is found.
    """
    pairs = []

    try:
        with open("/proc/net/dev") as f:
            for line in f.readlines()[2:]:
                iface = line.split(":")[0].strip()
                ip = iface_ip(iface)
                if ip and ip != "0.0.0.0":
                    pairs.append((iface, ip))
    except Exception:
        pass

    if not pairs:
        pairs = [("lo", "127.0.0.1")]

    return pairs