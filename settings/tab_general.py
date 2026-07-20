"""
settings/tab_general.py — General tab
Start-on-login + notification toggles, and a reset-to-defaults button.

Writes into result: start_on_login, notify_clipboard, notify_listener, notify_http
"""

import tkinter as tk
from config import config

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
SCRIM  = "#010409"


# ── Toggle slider widget ( SHOULD BE IN COMPONENTS COMING SOON ) ───────────────────────────────────────────────────

class ToggleSlider(tk.Canvas):
    """A simple iOS-style toggle drawn on a Canvas."""

    W, H, R = 44, 22, 10

    def __init__(self, parent, var: tk.BooleanVar, **kw):
        super().__init__(parent, width=self.W, height=self.H,
                         bg=parent["bg"], bd=0, highlightthickness=0,
                         cursor="hand2", **kw)
        self._var = var
        self._draw()
        self.bind("<Button-1>", self._toggle)
        var.trace_add("write", lambda *_: self._draw())

    def _toggle(self, _=None):
        self._var.set(not self._var.get())

    def _draw(self):
        self.delete("all")
        on    = self._var.get()
        track = GREEN if on else BG3
        knob  = FG    if on else MUTED

        self.create_oval(1, 1, self.H-1, self.H-1, fill=track, outline=BORDER)
        self.create_oval(self.W-self.H+1, 1, self.W-1, self.H-1,
                         fill=track, outline=BORDER)
        self.create_rectangle(self.H//2, 1, self.W-self.H//2, self.H-1,
                               fill=track, outline=track)

        x = self.W - self.H//2 - 1 if on else self.H//2 + 1

        self.create_oval(x - self.R, self.H//2 - self.R,
                         x + self.R, self.H//2 + self.R,
                         fill=knob, outline="")


# ── Shared helpers ───────────────── (COMPONENTS . PY COMPONENTS DOT PY)

def _section(parent, title, pady=(20, 8)):
    hdr = tk.Frame(parent, bg=BG)
    hdr.pack(fill="x", padx=24, pady=pady)
    tk.Label(hdr, text=title, font=(MONO, 8, "bold"),
             bg=BG, fg=ACCENT, anchor="w").pack(side="left")
    tk.Frame(hdr, bg=BORDER, height=1).pack(
        side="left", fill="x", expand=True, padx=(10, 0))


def _card(parent):
    f = tk.Frame(parent, bg=BG2)
    f.pack(fill="x", padx=24)
    return f


def _label(parent, text, width=None, color=MUTED):
    kw = {"width": width} if width else {}
    return tk.Label(parent, text=text, font=(MONO, 9),
                    bg=parent["bg"], fg=color, anchor="w", **kw)


def _hint(card, text):
    tk.Label(card, text=f"  {text}", font=(MONO, 8),
             bg=BG2, fg=BORDER, anchor="w").pack(
                 fill="x", padx=14, pady=(0, 8))


def _toggle_row(card, label_text, var, pady=(6, 6)):
    row = tk.Frame(card, bg=BG2)
    row.pack(fill="x", padx=14, pady=pady)
    _label(row, label_text).pack(side="left", pady=4)

    lbl = tk.Label(row, font=(MONO, 8), bg=BG2,
                   fg=GREEN if var.get() else MUTED)
    lbl.pack(side="right", padx=(0, 6))

    slider = ToggleSlider(row, var)
    slider.pack(side="right", padx=(0, 8))

    def _update_label(*_):
        lbl.config(text="on " if var.get() else "off",
                   fg=GREEN if var.get() else MUTED)

    var.trace_add("write", _update_label)
    _update_label()


# ── Build ───────────────────────────────────────────────────────────────────── ─────────────────

def build(parent: tk.Frame, data: dict, result: dict, reload_other_tabs=None) -> None:

    outer = tk.Frame(parent, bg=BG)
    outer.pack(fill="both", expand=True)

    canvas = tk.Canvas(outer, bg=BG, bd=0, highlightthickness=0)
    canvas.pack(side="left", fill="both", expand=True)

    scrollbar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview,
                             bg=BG2, troughcolor=BG, bd=0,
                             activebackground=BORDER)
    scrollbar.pack(side="right", fill="y")
    canvas.configure(yscrollcommand=scrollbar.set)

    wrapper = tk.Frame(canvas, bg=BG)
    wrapper_id = canvas.create_window((0, 0), window=wrapper, anchor="nw")

    def _on_wrapper_configure(_e=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas_configure(e):
        canvas.itemconfig(wrapper_id, width=e.width)

    wrapper.bind("<Configure>", _on_wrapper_configure)
    canvas.bind("<Configure>", _on_canvas_configure)

    def _on_mousewheel(event):
        if getattr(event, "num", None) == 5 or getattr(event, "delta", 0) < 0:
            canvas.yview_scroll(1, "units")
        elif getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0:
            canvas.yview_scroll(-1, "units")

    def _bind_mousewheel(_=None):
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel)
        canvas.bind_all("<Button-5>", _on_mousewheel)

    def _unbind_mousewheel(_=None):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    canvas.bind("<Enter>", _bind_mousewheel)
    canvas.bind("<Leave>", _unbind_mousewheel)

    # ── STARTUP ─────────────────────────────────────────────────────────────── ─────────────────
    _section(wrapper, "STARTUP")
    startup_card = _card(wrapper)

    start_on_login_var = tk.BooleanVar(value=data.get("start_on_login", False))
    _toggle_row(startup_card, "start on login", start_on_login_var)
    _hint(startup_card, "Launches the tray automatically when you log in.")


    # ── NOTIFICATIONS ──────────────────────────────────────────────────────────────────────────
    _section(wrapper, "NOTIFICATIONS")
    notif_card = _card(wrapper)

    notify_clipboard_var = tk.BooleanVar(value=data.get("notify_clipboard", True))
    _toggle_row(notif_card, "notify on copy", notify_clipboard_var)
    _hint(notif_card, "Shows a 'Copied ✓' popup whenever a command is copied.")

    notify_listener_var = tk.BooleanVar(value=data.get("notify_listener", True))
    _toggle_row(notif_card, "notify on listener connection", notify_listener_var)
    _hint(notif_card, "Shows a popup when the listener gets a new connection.")

    notify_http_var = tk.BooleanVar(value=data.get("notify_http", True))
    _toggle_row(notif_card, "notify on http request", notify_http_var)
    _hint(notif_card, "Shows a popup whenever the HTTP server serves a request.")


    # ── OTHER ───────────────────────────────────────────────────────────────────────────d────
    _section(wrapper, "OTHER")
    other_card = _card(wrapper)

    open_terminal_on_listener_var = tk.BooleanVar(
        value=data.get("open_terminal_on_listener_connection", False)
    )
    _toggle_row(other_card, "auto open terminal on listener connection", open_terminal_on_listener_var)
    _hint(other_card, "Opens a terminal whenever the listener reports a new connection.")

    # ── RESET ─────────────────────────────────────────────────────────────────
    _section(wrapper, "RESET")
    reset_card = _card(wrapper)

    reset_row = tk.Frame(reset_card, bg=BG2)
    reset_row.pack(fill="x", padx=14, pady=(10, 4))

    status = tk.Label(reset_row, text="", font=(MONO, 8), bg=BG2, fg=GREEN, anchor="w")

    # ── Reset confirmation modal ─────────────────────────────────────────────

    modal_scrim = tk.Frame(outer, bg=SCRIM)
    modal_card = tk.Frame(modal_scrim, bg=BG2, highlightthickness=1,
                           highlightbackground=BORDER)
    modal_card.place(relx=0.5, rely=0.5, anchor="center")

    def _hide_confirm():
        modal_scrim.place_forget()

    def _do_reset():
        modal_scrim.place_forget()

        config.reset_to_defaults()

        # Refresh this tab's widgets (need to update others too )
        start_on_login_var.set(config.get_start_on_login())
        notify_clipboard_var.set(config.get_notify_clipboard())
        notify_listener_var.set(config.get_notify_listener())
        notify_http_var.set(config.get_notify_http())
        open_terminal_on_listener_var.set(config.get_open_terminal_on_listener_connection())

        status.config(text="✓ reset to defaults")
        reset_card.after(1800, lambda: status.config(text=""))

        # now reload all other tabs so they update after reset to defaults is triggered
        if reload_other_tabs:
            reload_other_tabs()

    def _show_confirm():
        for w in modal_card.winfo_children():
            w.destroy()

        pad = tk.Frame(modal_card, bg=BG2)
        pad.pack(padx=22, pady=18)

        tk.Label(pad, text="⚠  reset all settings?",
                 font=(MONO, 10, "bold"), bg=BG2, fg=ACCENT,
                 anchor="w", justify="left").pack(fill="x", pady=(0, 10))
        tk.Label(pad,
                 text="are you sure you'd like to reset all\nsettings (except tools) to defaults?",
                 font=(MONO, 9), bg=BG2, fg=MUTED,
                 anchor="w", justify="left").pack(fill="x", pady=(0, 16))

        yn_row = tk.Frame(pad, bg=BG2)
        yn_row.pack(fill="x")
        tk.Button(yn_row, text="no", font=(MONO, 9), bg=BG3, fg=MUTED,
                  activebackground=BORDER, activeforeground=FG,
                  relief="flat", bd=0, padx=14, pady=7, cursor="hand2",
                  command=_hide_confirm).pack(side="right", padx=(8, 0))
        tk.Button(yn_row, text="yes, reset", font=(MONO, 9, "bold"),
                  bg=BG3, fg=ACCENT,
                  activebackground=BORDER, activeforeground=FG,
                  relief="flat", bd=0, padx=14, pady=7, cursor="hand2",
                  command=_do_reset).pack(side="right")

        modal_scrim.place(relx=0, rely=0, relwidth=1, relheight=1)
        modal_scrim.tkraise()

    #  clicking anywhere else dismiss 
    modal_scrim.bind("<Button-1>", lambda _e: _hide_confirm())

    reset_btn = tk.Button(reset_row, text="⚠  reset to defaults",
                           font=(MONO, 9, "bold"),
                           bg=BG3, fg=ACCENT,
                           activebackground=BORDER, activeforeground=FG,
                           relief="flat", bd=0, padx=12, pady=8,
                           cursor="hand2", command=_show_confirm,
                           highlightthickness=1, highlightbackground=BORDER)
    reset_btn.pack(side="left")
    status.pack(side="left", padx=(10, 0))

    _hint(reset_card, "Resets all settings (except tools) to defaults.")

    # ── SYNC ─────────────────────────────────────────────────────────────────
    def _sync(*_):
        result["start_on_login"] = start_on_login_var.get()
        result["notify_clipboard"] = notify_clipboard_var.get()
        result["notify_listener"] = notify_listener_var.get()
        result["notify_http"] = notify_http_var.get()
        result["open_terminal_on_listener_connection"] = open_terminal_on_listener_var.get()

    for v in (start_on_login_var, notify_clipboard_var,
              notify_listener_var, notify_http_var, open_terminal_on_listener_var):
        v.trace_add("write", _sync)

    _sync()