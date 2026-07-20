"""
utils/autostart.py — XDG autostart integration (Linux)

auto start on launch (linux only feature)
"""

import sys
from pathlib import Path

AUTOSTART_DIR = Path.home() / ".config" / "autostart"
DESKTOP_FILE  = AUTOSTART_DIR / "pentest-tray.desktop"

# Path to the actual launcher script
_SCRIPT = Path(__file__).parent.parent / "main.py"


def _desktop_entry() -> str:
    python = sys.executable
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Pentest Tray\n"
        f"Exec={python} {_SCRIPT}\n"
        "X-GNOME-Autostart-enabled=true\n"
        "NoDisplay=false\n"
        "Terminal=false\n"
    )


def enable() -> None:
    AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
    DESKTOP_FILE.write_text(_desktop_entry())


def disable() -> None:
    try:
        DESKTOP_FILE.unlink()
    except FileNotFoundError:
        pass


def is_enabled() -> bool:
    return DESKTOP_FILE.exists()


def sync(want_enabled: bool) -> None:
    """Make the on-disk autostart entry match the config toggle."""
    if want_enabled and not is_enabled():
        enable()
    elif not want_enabled and is_enabled():
        disable()