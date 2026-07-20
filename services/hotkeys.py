"""
hotkeys.py — leader -> section -> tool chord launcher.

feel like up down nav could be improved

also visually could be improved.
"""

import tkinter as tk

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    from pynput import keyboard
except ImportError:
    keyboard = None

from config import config

# ── theme (should centralise this in comps.py in /utils or theme eventually) ──────────────────────────────────

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

POPUP_WIDTH = 280

# ── module state ──────────────────────────────────────────────────────────────

_root = None
_listener = None
_popup = None
_chord_after_id = None
_current_section = None

_chord_listener = None   # pynput.keyboard.Listener
_key_to_cb = {}          # str -> callback, for the open popup


_options = []            # list of dicts: {hk, label, cb, row, key_lbl, text_lbl} for open popup
_selected_index = None   # int index into _options, or None if nothing selected yet


# ── public API ───────────────────────────────────────────────────────────────────────────

def start(root: tk.Tk) -> None:
    """Register the global leader hotkey. Call once, after config is loaded."""
    global _root
    _root = root
    _register_leader()


def stop() -> None:
    """Tear down the global listener(s)."""
    global _listener
    if _listener is not None:
        try:
            _listener.stop()
        except Exception:
            pass
        _listener = None
    _stop_chord_listener()  


def restart() -> None:
    """Re-read config (leader/timeout/enabled) and re-arm. Call after settings save."""
    stop()
    _close_popup()
    _register_leader()


# ── leader registration ──────────────────────────────────────────────────────

def _register_leader() -> None:
    global _listener
    if keyboard is None:
        print("[hotkeys] pynput not installed — global leader hotkey disabled")
        return
    if not config.get_hotkey_launch_enabled():
        return

    leader = config.get_hotkey_launch_leader()
    try:
        _listener = keyboard.GlobalHotKeys({leader: _on_leader_fired})
        _listener.start()
    except Exception as e:
        print(f"[hotkeys] failed to register leader '{leader}': {e}")
        _listener = None


def _on_leader_fired() -> None:
    if _root is not None:
        _root.after(0, _open_section_popup)



# ── chord popups ─────────────────────────────────────────────────────────────────────────

def _close_popup() -> None:
    global _popup, _chord_after_id, _current_section, _options, _selected_index
    _stop_chord_listener()
    if _chord_after_id is not None and _root is not None:
        try:
            _root.after_cancel(_chord_after_id)
        except Exception:
            pass
        _chord_after_id = None
    if _popup is not None:
        try:
            _popup.grab_release()
        except Exception:
            pass
        try:
            _popup.destroy()
        except Exception:
            pass
        _popup = None
    _current_section = None
    _key_to_cb.clear()
    _options = []         
    _selected_index = None


def _start_chord_listener() -> None:
    global _chord_listener
    _stop_chord_listener()
    if keyboard is None:
        return
    try:
        _chord_listener = keyboard.Listener(on_press=_on_chord_key)
        _chord_listener.start()
    except Exception as e:
        print(f"[hotkeys] failed to start chord listener: {e}")
        _chord_listener = None


def _stop_chord_listener() -> None:
    global _chord_listener
    if _chord_listener is not None:
        try:
            _chord_listener.stop()
        except Exception:
            pass
        _chord_listener = None


def _on_chord_key(key) -> None:
    if key == keyboard.Key.esc:
        if _root is not None:
            _root.after(0, _close_popup)
        return
    

    if key == keyboard.Key.up:
        if _root is not None:
            _root.after(0, lambda: _move_selection(-1))
        return
    if key == keyboard.Key.down:
        if _root is not None:
            _root.after(0, lambda: _move_selection(1))
        return
    if key in (keyboard.Key.space, keyboard.Key.enter):
        if _root is not None:
            _root.after(0, _activate_selection)
        return

    char = getattr(key, "char", None)
    if not char:
        return
    char = char.lower()

    if _root is not None:
        _root.after(0, lambda c=char: _handle_chord_key(c))


def _handle_chord_key(char: str) -> None:
    if _popup is None:
        return
    cb = _key_to_cb.get(char)
    if cb is not None:
        cb()


def _move_selection(delta: int) -> None:
    global _selected_index
    if _popup is None or not _options:
        return
    if _selected_index is None:
        # First arrow press: land top or bottom (more intuitive but maybe need refine)
        _selected_index = 0 if delta > 0 else len(_options) - 1
    else:
        _selected_index = (_selected_index + delta) % len(_options)
    _refresh_selection_highlight()
    _arm_timeout()


def _activate_selection() -> None:
    if _popup is None or _selected_index is None:
        return
    if 0 <= _selected_index < len(_options):
        _options[_selected_index]["cb"]()


def _refresh_selection_highlight() -> None:
    for i, opt in enumerate(_options):
        bg = BG3 if i == _selected_index else BG2
        try:
            opt["row"].configure(bg=bg)
            opt["text_lbl"].configure(bg=bg)
        except Exception:
            pass  # widget may already be gone if popup is closing


def _arm_timeout() -> None:
    global _chord_after_id
    if _root is None:
        return
    if _chord_after_id is not None:
        _root.after_cancel(_chord_after_id)
    timeout = config.get_hotkey_launch_timeout_ms()
    _chord_after_id = _root.after(timeout, _close_popup)


def _open_section_popup() -> None:
    global _current_section
    _close_popup()
    _current_section = None

    sections = list(config.get_tools().keys())
    if not sections:
        return

    options = [
        (config.get_section_hotkey(s), s.upper(), (lambda s=s: _open_tool_popup(s)))
        for s in sections
    ]
    _show_popup("SELECT SECTION", options)
    _arm_timeout()


def _open_tool_popup(section: str) -> None:
    global _current_section
    _close_popup()
    _current_section = section

    tools = config.get_tools().get(section, {})
    if not tools:
        return

    options = [
        (
            info.get("hotkey", ""),
            info.get("nickname", name),
            (lambda section=section, name=name: _launch_tool(section, name)),
        )
        for name, info in tools.items()
    ]
    _show_popup(section.upper(), options)
    _arm_timeout()


def _launch_tool(section: str, name: str) -> None:
    template = config.get_tool_command(section, name)
    command = config.resolve_command(template)

    copied = False
    if pyperclip is not None:
        try:
            pyperclip.copy(command)
            copied = True
        except Exception as e:
            print(f"[hotkeys] clipboard copy failed: {e}")
    else:
        print("[hotkeys] pyperclip not installed — cannot copy to clipboard")

    if config.get_log_launches():
        print(f"[hotkeys] {section}/{name} -> {command}")

    _close_popup()

    if copied and config.get_notify_clipboard():
        _flash_notification(f"{config.get_tool_nickname(section, name)} copied")


# ── popup rendering ─────────────────────────────────────────────────────────────────

def _center_on_screen(win: tk.Toplevel, width: int, height: int | None = None) -> None:
    win.update_idletasks()
    h = height or win.winfo_reqheight()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = (sw - width) // 2
    y = (sh - h) // 3
    win.geometry(f"{width}x{h}+{x}+{y}")


def _show_popup(title: str, options: list) -> None:
    """options: list of (hotkey_char, label, callback)."""
    global _popup, _options, _selected_index

    win = tk.Toplevel(_root)
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    win.configure(bg=ACCENT)  # 1px border effect via padding below (it could look better)

    border = tk.Frame(win, bg=ACCENT)
    border.pack(fill="both", expand=True)

    outer = tk.Frame(border, bg=BG, padx=14, pady=12)
    outer.pack(fill="both", expand=True, padx=1, pady=1)

    tk.Label(outer, text=title, font=(MONO, 9, "bold"),
             bg=BG, fg=ACCENT, anchor="w").pack(fill="x", pady=(0, 8))


    _key_to_cb.clear()
    _options = []          
    _selected_index = None

    if not options:
        tk.Label(outer, text="(nothing here)", font=(MONO, 9),
                  bg=BG, fg=MUTED, anchor="w").pack(fill="x", pady=4)

    for hk, label, cb in options:
        row = tk.Frame(outer, bg=BG2, cursor="hand2")
        row.pack(fill="x", pady=2)

        key_lbl = tk.Label(row, text=(hk or "?").upper(), font=(MONO, 10, "bold"),
                            bg=BG3, fg=CYAN, width=3, anchor="center")
        key_lbl.pack(side="left", ipady=5, padx=(0, 10))

        text_lbl = tk.Label(row, text=label, font=(MONO, 10),
                             bg=BG2, fg=FG, anchor="w")
        text_lbl.pack(side="left", fill="x", expand=True, pady=7, padx=(0, 10))

        for widget in (row, key_lbl, text_lbl):
            widget.bind("<Button-1>", lambda _e, cb=cb: cb())
            widget.bind("<Enter>", lambda _e, r=row, t=text_lbl: (r.configure(bg=BG3), t.configure(bg=BG3)))
            widget.bind("<Leave>", lambda _e, r=row, t=text_lbl: (r.configure(bg=BG2), t.configure(bg=BG2)))

        if hk:
            _key_to_cb[hk.lower()] = cb


        _options.append({"hk": hk, "label": label, "cb": cb, "row": row, "key_lbl": key_lbl, "text_lbl": text_lbl})

    tk.Label(outer, text="esc to cancel  \u2022  \u2191\u2193 + space/enter to select", font=(MONO, 7),
              bg=BG, fg=BORDER, anchor="w").pack(fill="x", pady=(8, 0))

    def _on_key(event):
        if event.keysym == "Escape":
            _close_popup()
            return
        if event.keysym == "Up":
            _move_selection(-1)
            return
        if event.keysym == "Down":
            _move_selection(1)
            return
        if event.keysym in ("space", "Return"):
            _activate_selection()
            return
        sym = (event.char or "").lower()
        cb = _key_to_cb.get(sym)
        if cb is not None:
            cb()

    win.bind_all("<Key>", _on_key)
    win.bind("<FocusOut>", lambda _e: _close_popup())

    _start_chord_listener()

    _center_on_screen(win, POPUP_WIDTH)
    win.lift()

    def _claim_focus():
        try:
            win.focus_force()
            win.focus_set()
            win.grab_set()
        except Exception as e:
            print(f"[hotkeys] failed to grab focus: {e}")

    win.after(30, _claim_focus)

    _popup = win


def _flash_notification(text: str, ms: int = 1100) -> None:
    if _root is None:
        return
    note = tk.Toplevel(_root)
    note.overrideredirect(True)
    note.attributes("-topmost", True)
    note.configure(bg=GREEN)

    inner = tk.Frame(note, bg=BG2)
    inner.pack(padx=1, pady=1)
    tk.Label(inner, text=f"\u2713 {text}", font=(MONO, 10, "bold"),
              bg=BG2, fg=GREEN, padx=16, pady=10).pack()

    _center_on_screen(note, 220)
    note.after(ms, note.destroy)