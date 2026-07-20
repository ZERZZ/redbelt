#!/usr/bin/env python3
"""
settings/window.py — pentest_tray settings window
Launched as a subprocess by pentest_tray.py
Args: <json_config> <result_file>
"""

import sys
import json
from pathlib import Path
import tkinter as tk

sys.path.insert(0, str(Path(__file__).parent.parent))

from settings.tab_general       import build as build_general
from settings.tab_network       import build as build_network
from settings.tab_files         import build as build_files
from settings.tab_toolbelt      import build as build_toolbelt
from settings.tab_hotkeys       import build as build_hotkeys
from settings.tab_shell         import build as build_shell

from config import config as cfgmod

BG     = "#0d1117"
BG2    = "#161b22"
BG3    = "#21262d"
BORDER = "#30363d"
ACCENT = "#d73a49"
GREEN  = "#3fb950"
CYAN   = "#58a6ff"
MUTED  = "#8b949e"
FG     = "#e6edf3"
MONO   = "Monospace"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ICON_PNG = PROJECT_ROOT / "assets" / "settings.png"


CONFIG_JSON_PATH = Path(cfgmod.__file__).parent / "config.json"

data    = json.loads(sys.argv[1])
outfile = sys.argv[2]

# ── Root window ──────────────────────────────────────────────────────────────────────
win = tk.Tk()
win.title("RedBelt — settings")
win.configure(bg=BG)
win.resizable(False, False)


if ICON_PNG.exists():
    try:
        win._icon_img = tk.PhotoImage(file=str(ICON_PNG))
        win.iconphoto(True, win._icon_img)
    except Exception as e:
        print(f"[!] failed to set settings window icon {ICON_PNG}: {e}")
else:
    print(f"[!] settings window icon not found at {ICON_PNG}")

W, H = 580, 640
win.update_idletasks()
sw = win.winfo_screenwidth()
sh = win.winfo_screenheight()
win.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

# bring to foreground ( still not full proof idk why)
def _bring_to_front() -> None:
    try:
        win.attributes("-topmost", True)
    except Exception:
        pass
    try:
        win.update_idletasks()
        win.deiconify()
        win.lift()
        win.focus_force()
    except Exception as e:
        print(f"[!] failed to bring settings window to front: {e}")

win.after(100, _bring_to_front)

# ── Header strip ─────────────────────────────────────────────────────────────────────
tk.Frame(win, bg=ACCENT, height=3).pack(fill="x")

hdr = tk.Frame(win, bg=BG, padx=24, pady=14)
hdr.pack(fill="x")

left = tk.Frame(hdr, bg=BG)
left.pack(side="left")
tk.Label(left, text="RedBelt", font=(MONO, 14, "bold"),
         bg=BG, fg=FG).pack(anchor="w")
tk.Label(left, text="settings", font=(MONO, 10),
         bg=BG, fg=MUTED).pack(anchor="w")

right = tk.Frame(hdr, bg=BG)
right.pack(side="right", anchor="ne")

# Header icon —──────────────────────────────────────────────────────────────────────
if ICON_PNG.exists():
    try:
        header_img = tk.PhotoImage(file=str(ICON_PNG))
        target_h = 36
        src_h = header_img.height()
        if src_h > 0:
            factor = target_h / src_h
            if factor > 1:
                header_img = header_img.zoom(max(1, round(factor)))
            elif factor < 1:
                header_img = header_img.subsample(max(1, round(1 / factor)))
        win._header_icon_img = header_img
        tk.Label(right, image=header_img, bg=BG).pack(anchor="e")
    except Exception as e:
        print(f"[!] failed to load header icon {ICON_PNG}: {e}")

tk.Frame(win, bg=BORDER, height=1).pack(fill="x")

# ── Tab bar ───────────────────────────────────────────────────────────────────
TABS = ["General", "Network", "Files", "Toolbelt", "Hotkeys", "Shell"]

tab_bar = tk.Frame(win, bg=BG2, height=38)
tab_bar.pack(fill="x")
tab_bar.pack_propagate(False)

tab_btns   = {}
tab_frames = {}

_current_tab = ["General"]

def switch_tab(name):
    _current_tab[0] = name
    for n, btn in tab_btns.items():
        active = (n == name)
        btn.config(fg=FG if active else MUTED,
                   bg=BG if active else BG2)
    for n, frame in tab_frames.items():
        if n == name:
            frame.tkraise()

for tab_name in TABS:
    btn = tk.Button(
        tab_bar, text=tab_name,
        font=(MONO, 9, "bold"),
        fg=MUTED, bg=BG2,
        activeforeground=FG, activebackground=BG,
        relief="flat", bd=0,
        padx=18, pady=10,
        cursor="hand2",
        highlightthickness=0,
        command=lambda n=tab_name: switch_tab(n),
    )
    btn.pack(side="left")
    tab_btns[tab_name] = btn

tk.Frame(win, bg=BORDER, height=1).pack(fill="x")


# ── Tab content area ──────────────────────────────────────────────────────────
content = tk.Frame(win, bg=BG)
content.pack(fill="both", expand=True)

result: dict = {}

tab_builders = {
    "General":  build_general,
    "Network":  build_network,
    "Files":    build_files,
    "Toolbelt": build_toolbelt,
    "Hotkeys":  build_hotkeys,
    "Shell":    build_shell,
}

def _load_fresh_data() -> dict:
    with open(CONFIG_JSON_PATH) as f:
        return json.load(f)

def reload_other_tabs() -> None: # for reset to defaults 
    """Tear down and rebuild every tab except General using fresh data."""
    fresh = _load_fresh_data()
    for tab_name, builder in tab_builders.items():
        if tab_name == "General":
            continue
        old_frame = tab_frames[tab_name]
        old_frame.destroy()
        f = tk.Frame(content, bg=BG)
        f.place(relx=0, rely=0, relwidth=1, relheight=1)
        tab_frames[tab_name] = f
        builder(f, fresh, result)
    switch_tab(_current_tab[0])

for tab_name in TABS:
    f = tk.Frame(content, bg=BG)
    f.place(relx=0, rely=0, relwidth=1, relheight=1)
    tab_frames[tab_name] = f
    if tab_name == "General":
        tab_builders[tab_name](f, data, result, reload_other_tabs)
    else:
        tab_builders[tab_name](f, data, result)


# ── Footer ────────────────────────────────────────────────────────────────────
tk.Frame(win, bg=BORDER, height=1).pack(fill="x", side="bottom")

footer = tk.Frame(win, bg=BG2, padx=24, pady=12)
footer.pack(fill="x", side="bottom")

feedback_var = tk.StringVar()
fb_label = tk.Label(footer, textvariable=feedback_var,
                    font=(MONO, 9), bg=BG2, fg=GREEN, anchor="w")
fb_label.pack(side="left")

def flash(msg, color=GREEN):
    feedback_var.set(msg)
    fb_label.config(fg=color)
    win.after(3000, lambda: feedback_var.set(""))

_last_written: dict = {}

def _build_out() -> dict | None: # again why is this not centralised in config.py and just called here?
    """Validate and return the output dict, or None on error."""
    out = {
        # NETWORK TAB
        "ip_override":    result.get("ip_override") or None,
        "port":           result.get("port",        data.get("port", 9001)),
        "tools_base":     result.get("tools_base",  data.get("tools_base", "")),
        "auto_http":      result.get("auto_http",   True),
        "auto_listen":    result.get("auto_listen", False),
        "listener_ip":    result.get("listener_ip", ""),
        "listener_port":  result.get("listener_port", "4444"),
        "listener_proto": result.get("listener_proto", "nc"),
        "preferred_http_iface":     result.get("preferred_http_iface",
                                                 data.get("preferred_http_iface")),
        "preferred_listener_iface": result.get("preferred_listener_iface",
                                                 data.get("preferred_listener_iface")),
        # FILES / TOOLBELT TAB
        "tools":          result.get("tools", data.get("tools", {})),
        # HOTKEYS TAB
        "hotkey_launch":   result.get("hotkey_launch",   data.get("hotkey_launch", {})),
        "section_hotkeys": result.get("section_hotkeys", data.get("section_hotkeys", {})),
        # START ON LOGIN
        "start_on_login": result.get("start_on_login", False),
        # NOTIFICATIONS
        "notify_clipboard": result.get("notify_clipboard", True),
        "notify_listener":  result.get("notify_listener", True),
        "notify_http":      result.get("notify_http", True),
        # SHELL TAB (open-terminal toggle lives here now; shell_stabilisation
        # is the new block written by tab_shell.py)
        "open_terminal_on_listener_connection": result.get(
            "open_terminal_on_listener_connection",
            data.get("open_terminal_on_listener_connection", False),
        ),
        "shell_stabilisation": result.get(
            "shell_stabilisation",
            data.get("shell_stabilisation", {}),
        ),
    }
    try:
        int(out["port"])
    except (ValueError, TypeError):
        return None
    try:
        int(out["listener_port"])
    except (ValueError, TypeError):
        return None
    return out

def do_apply():
    out = _build_out()
    if out is None:
        flash("✗  invalid port number", ACCENT)
        return
    with open(outfile, "w") as f:
        json.dump(out, f)
    _last_written.update(out)
    flash("✓  applied")

def do_close():
    # Flush on close too so parent always gets latest state
    out = _build_out()
    if out and out != _last_written:
        with open(outfile, "w") as f:
            json.dump(out, f)
    win.destroy()

tk.Button(footer, text="Apply",
          font=(MONO, 10, "bold"),
          bg=ACCENT, fg=FG,
          activebackground="#b02030", activeforeground=FG,
          relief="flat", bd=0, padx=24, pady=8,
          cursor="hand2", command=do_apply).pack(side="right")

tk.Button(footer, text="Close",
          font=(MONO, 10),
          bg=BG3, fg=MUTED,
          activebackground=BORDER, activeforeground=FG,
          relief="flat", bd=0, padx=16, pady=8,
          cursor="hand2", command=do_close).pack(side="right", padx=(0, 8))

win.protocol("WM_DELETE_WINDOW", do_close)

switch_tab("General")
win.mainloop()