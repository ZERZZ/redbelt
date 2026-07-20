#!/usr/bin/env python3
"""
services/tray.py — pystray icon, menu, settings dialog, clipboard helpers

Requires: pip install pystray pyperclip Pillow
"""

import sys
import os
import json
import tempfile
import threading
import subprocess
from pathlib import Path

import config.config as config
from services import httpserver
from services import hotkeys
from services import listener
from utils import status
from utils import autostart
from utils.notify import notify_clipboard

try:
    import pyperclip
except ImportError:
    sys.exit("[!] pip install pyperclip")

try:
    import pystray
    from pystray import MenuItem as Item, Menu
except ImportError:
    sys.exit("[!] pip install pystray")

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("[!] pip install Pillow")


# ─── Clipboard ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

SHELLS_CATEGORY = "shells" 


def copy_command(template: str, category: str | None = None) -> None:
    if category and category.lower() == SHELLS_CATEGORY:
        ip   = config.get_ip_override() or config.get_listener_ip()
        port = config.get_listener_port()
    else:
        from utils.network import get_ip
        ip   = get_ip()
        port = config.get_port()

    cmd = config.resolve_command(template, ip=ip, port=port)
    pyperclip.copy(cmd)
    notify_clipboard(cmd)


# Tray icon ───────────────────────────────────────────────────────────────────────

def make_icon(size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    p   = 3
    d.rounded_rectangle([p, p, size-p, size-p], radius=12, fill=(13, 17, 23, 255))
    d.rectangle([p+2, p+2, size-p-2, p+8], fill=(215, 58, 73, 255))
    cx, cy = size//2 - 2, size//2 + 5
    d.polygon([(cx-9, cy-9), (cx+7, cy), (cx-9, cy+9), (cx-4, cy)], fill=(215, 58, 73, 255))
    d.rectangle([cx+9, cy+2, cx+16, cy+7], fill=(139, 233, 253, 220))
    return img


# ─── Settings dialog ──────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PY = PROJECT_ROOT / "settings" / "window.py"
TRAY_ICON_PNG = PROJECT_ROOT / "assets" / "tray.png"

_settings_proc: subprocess.Popen | None = None


def open_settings(icon=None, item=None) -> None:
    global _settings_proc

    if _settings_proc and _settings_proc.poll() is None:
        return  # shit already open

    if not SETTINGS_PY.exists():
        print(f"[!] settings window not found at {SETTINGS_PY}")
        return

    from utils.network import detect_ip_and_iface
    auto_ip, auto_iface = detect_ip_and_iface()

    result_f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, prefix="pt_cfg_"
    )
    result_f.close()

    # why is this not done in config and called here ? saves me updating window.py, config.py & tray.py each time.
    payload = json.dumps({
        "auto_ip":                  auto_ip,
        "auto_iface":               auto_iface,
        "port":                     config.get_port(),
        "ip_override":              config.get_ip_override(),
        "tools_base":               str(config.get_tools_base()),
        "serving":                  status.is_http_up(),
        "auto_http":                config.AUTO_HTTP,
        "auto_listen":              config.AUTO_LISTEN,
        "listener_port":            config.LISTENER_PORT,
        "listener_ip":              config.get_listener_ip(),
        "listener_proto":           config.get_listener_proto(),
        "preferred_http_iface":     config.get_preferred_http_iface(),
        "preferred_listener_iface": config.get_preferred_listener_iface(),
        "start_on_login":           config.get_start_on_login(),
        "notify_clipboard":         config.get_notify_clipboard(),
        "notify_listener":          config.get_notify_listener(),
        "notify_http":              config.get_notify_http(),
        "open_terminal_on_listener_connection": config.get_open_terminal_on_listener_connection(),
        "tools":                    config.get_tools(),

        # HOTKEYS
        "hotkey_launch": {
            "enabled":                  config.get_hotkey_launch_enabled(),
            "leader":                   config.get_hotkey_launch_leader(),
            "timeout_ms":               config.get_hotkey_launch_timeout_ms(),
            "log_launches":             config.get_log_launches(),
        },
        "section_hotkeys":          config.get_section_hotkeys(),
        "shell_stabilisation": {
            "auto_stabilise":          config.get_shell_auto_stabilise(),
        "auto_identify_terminal":  config.get_shell_auto_identify_terminal(),
        "method":                  config.get_shell_method(),
        "python_preference":       config.get_shell_python_preference(),
        "export_term":             config.get_shell_export_term(),
        "sync_stty_size":          config.get_shell_sync_stty_size(),
        "shell_path":              config.get_shell_path(),
        },
    })

    def _run() -> None:
        global _settings_proc
        _settings_proc = subprocess.Popen(
            [sys.executable, str(SETTINGS_PY), payload, result_f.name],
            env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")},
        )
        _settings_proc.wait()

        try:
            txt = Path(result_f.name).read_text().strip()
            if txt:
                parsed = json.loads(txt)
                port_changed = config.apply_settings(parsed)
                autostart.sync(config.get_start_on_login())
                want_http = parsed.get("auto_http", config.AUTO_HTTP)
                if port_changed:
                    httpserver.restart()
                elif want_http and not status.is_http_up():
                    httpserver.start()
                elif not want_http and status.is_http_up():
                    httpserver.stop()


                try:
                    hotkeys.restart()
                except Exception as e:
                    print(f"[!] hotkeys restart failed: {e}")

                if icon is not None:
                    icon.menu = build_menu()
                    icon.update_menu()
        except Exception as e:
            print(f"[!] settings apply failed: {e}")

        try:
            os.unlink(result_f.name)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


# ─── Tray menu ────────────────────────────────────────────────────────────────

def _make_copy(template: str, category: str | None = None):
    def action(icon, item):
        copy_command(template, category)
    return action

_quit_callback = None


def set_quit_callback(callback) -> None:
    """Called by main.py to register how the rest of the app should shut down."""
    global _quit_callback
    _quit_callback = callback


def quit_tray(icon, item) -> None:
    httpserver.stop()

    if _quit_callback is not None:
        try:
            _quit_callback()
        except Exception as e:
            print(f"[!] quit callback failed: {e}")

    icon.stop()


def _format_session_label(session: dict) -> str:
    ip = session.get("remote_ip", "unknown")
    port = session.get("remote_port") or "?"
    suffix = " [terminal]" if session.get("terminal_opened") else ""
    return f"{ip}:{port}{suffix}"


def build_menu() -> Menu:
    def section(cat: str) -> Menu:
        tools = config.get_tools().get(cat, {})
        if not tools:
            return Menu(Item("(empty)", None, enabled=False))
        items = []
        for name, val in tools.items():
            if isinstance(val, dict):
                cmd = val.get("command", "")
                label = val.get("nickname") or name
            else:
                cmd = val
                label = name
            items.append(Item(label, _make_copy(cmd, cat)))
        return Menu(*items)

    categories = list(config.get_tools().keys())
    items = [Item(cat, section(cat)) for cat in categories]

    sessions = listener.get_sessions()
    if sessions:
        session_items = []
        for session in reversed(sessions):
            session_id = session.get("id")
            session_label = _format_session_label(session)
            session_items.append(
                Item(
                    session_label,
                    Menu(
                        Item("Open terminal", lambda icon, item, session_id=session_id: listener.open_terminal_for_session_id(session_id)),
                        Item("Remove", lambda icon, item, session_id=session_id: listener.close_session(session_id)),
                    ),
                )
            )
        items += [
            Menu.SEPARATOR,
            Item("Sessions", Menu(*session_items)),
        ]

    items += [
        Menu.SEPARATOR,
        Item("Settings", open_settings),
        Menu.SEPARATOR,
        Item("Quit", quit_tray),
    ]
    return Menu(*items)


def _load_tray_image() -> Image.Image:
    """Custom tray artwork if present at assets/tray.png, otherwise the
    drawn fallback icon (make_icon) so a missing/renamed file can't crash
    tray startup."""
    print(f"[*] tray icon path: {TRAY_ICON_PNG}  (exists={TRAY_ICON_PNG.exists()})")
    if TRAY_ICON_PNG.exists():
        try:
            img = Image.open(TRAY_ICON_PNG)
            img.load()  # force read so corrupt file dont get stuck 
            if img.mode != "RGBA":
                img = img.convert("RGBA") 
            print(f"[*] tray icon loaded: {img.size} {img.mode}")
            return img
        except Exception as e:
            print(f"[!] failed to load tray icon {TRAY_ICON_PNG}: {e}")
    else:
        print(f"[!] tray icon not found at {TRAY_ICON_PNG} — using drawn fallback")
    return make_icon(64)


def build_icon():
    """Construct (but don't run) the tray icon, ready for icon.run()."""
    icon = pystray.Icon("pentest_tray", _load_tray_image(), "Pentest Tray", build_menu())

    def _refresh_menu() -> None:
        try:
            icon.menu = build_menu()
            icon.update_menu()
        except Exception as exc:
            print(f"[!] tray menu refresh failed: {exc}")

    listener.register_session_change_callback(_refresh_menu)
    return icon