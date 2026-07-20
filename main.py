#!/usr/bin/env python3
"""
main.py — pentest tray launcher entry point
Requires: pip install pystray pyperclip Pillow pynput
"""
import sys
import threading
import tkinter as tk

import config.config as config
from services import httpserver, listener
from utils import autostart
from services import tray
from services import hotkeys
from utils.network import detect_ip_and_iface


def main() -> None:
    # Keep the OS autostart entry (~/.config/autostart/pentest-tray.desktop)
    # in sync with the config flag. This is what actually makes "start on
    # login" work — the toggle controls whether that file exists, not
    # whether this script bails out early.
    autostart.sync(config.get_start_on_login())

    # HTTP server
    if config.get_auto_http():
        httpserver.start()

    # Listener
    if config.get_auto_listen():
        listener.start()

    ip, iface = detect_ip_and_iface()
    config.runtime["iface"] = iface
    print(f"[*] {iface} → {ip}:{config.get_port()}  ({config.get_tools_base()})")

    root = tk.Tk()
    root.withdraw()

    hotkeys.start(root)

    def shutdown() -> None:
        try:
            listener.stop() # THIS MAY NOT ACTUALLY KILL TMUX SESSION AS WELL WHICH BREAKS IT VERIFY
        except Exception as e:
            print(f"[!] listener stop failed: {e}")
        root.after(0, root.quit)

    tray.set_quit_callback(shutdown)

    icon = tray.build_icon()
    threading.Thread(target=icon.run, daemon=True).start()

    root.mainloop()

    root.destroy()
    sys.exit(0)


if __name__ == "__main__":
    main()