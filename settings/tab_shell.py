"""
settings/tab_shell.py — Shell Stabilisation tab
Auto-stabilisation, terminal identification, method (auto/script/python),
python preference, TERM export, stty row/col sync, and the auto open terminal 
option.


Writes into result:
    shell_stabilisation: {
        auto_stabilise, auto_identify_terminal, method,
        python_preference, export_term, sync_stty_size, shell_path
    }
    open_terminal_on_listener_connection   (kept top-level/unchanged key)
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


# ── Toggle slider widget ───────────────── (comps.py lol )

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


# ── Shared helpers ────────────────────────────────────────── comps DOT PY

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
             bg=BG2, fg=BORDER, anchor="w", justify="left").pack(
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


def _choice_row(card, label_text, var: tk.StringVar, options, pady=(6, 6)):
    """options: list of (value, display_label) tuples. Renders a small row
    of pill buttons; the one matching var's current value is highlighted."""
    row = tk.Frame(card, bg=BG2)
    row.pack(fill="x", padx=14, pady=pady)
    _label(row, label_text).pack(side="left", pady=4)

    btn_row = tk.Frame(row, bg=BG2)
    btn_row.pack(side="right")

    buttons = {}

    def _select(value):
        var.set(value)

    def _refresh(*_):
        current = var.get()
        for val, btn in buttons.items():
            if val == current:
                btn.config(bg=CYAN, fg=SCRIM, activebackground=CYAN, activeforeground=SCRIM)
            else:
                btn.config(bg=BG3, fg=MUTED, activebackground=BORDER, activeforeground=FG)

    for value, display in options:
        b = tk.Button(btn_row, text=display, font=(MONO, 8, "bold"),
                      bg=BG3, fg=MUTED, activebackground=BORDER, activeforeground=FG,
                      relief="flat", bd=0, padx=10, pady=5, cursor="hand2",
                      command=lambda v=value: _select(v))
        b.pack(side="left", padx=(4, 0))
        buttons[value] = b

    var.trace_add("write", _refresh)
    _refresh()


def _entry_row(card, label_text, var: tk.StringVar, width=14, pady=(6, 6)):
    row = tk.Frame(card, bg=BG2)
    row.pack(fill="x", padx=14, pady=pady)
    _label(row, label_text).pack(side="left", pady=4)

    entry = tk.Entry(row, textvariable=var, width=width, font=(MONO, 9),
                     bg=BG3, fg=FG, insertbackground=FG, relief="flat", bd=0,
                     highlightthickness=1, highlightbackground=BORDER,
                     highlightcolor=CYAN)
    entry.pack(side="right", ipady=4, padx=(0, 8))


# ── Build ─────────────────────────────────────────────────────────────────────

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

    shell_cfg = data.get("shell_stabilisation", {}) or {}

    # ── STABILISATION ─────────────────────────────────────────────────────────
    _section(wrapper, "STABILISATION")
    stab_card = _card(wrapper)

    auto_stabilise_var = tk.BooleanVar(value=shell_cfg.get("auto_stabilise", False))
    _toggle_row(stab_card, "auto stabilise shells", auto_stabilise_var)
    _hint(stab_card, "Runs the stabilisation sequence automatically as soon as a\n"
                     "listener connection comes in, instead of waiting for you to\n"
                     "trigger it manually.")

    method_var = tk.StringVar(value=shell_cfg.get("method", "auto"))
    _choice_row(stab_card, "method", method_var, [
        ("auto", "auto"),
        ("python", "python"),
        ("script", "script"),
    ])
    _hint(stab_card, "auto: checks for python3, then python, then falls back to the\n"
                     "script wrapper.  python: always uses\n"
                     "python3/python -c 'import pty; pty.spawn(\"/bin/bash\")'.\n"
                     "script: always uses 'script /dev/null -c bash' followed by\n"
                     "Ctrl+Z, stty raw -echo; fg, export TERM=...")

    auto_identify_var = tk.BooleanVar(value=shell_cfg.get("auto_identify_terminal", True))
    _toggle_row(stab_card, "auto identify terminal type", auto_identify_var)
    _hint(stab_card, "Attempts to detect whether the shell is Linux or Windows before\n"
                     "picking a stabilisation sequence, rather than assuming Linux.")

    # ── PYTHON ────────────────────────────────────────────────────────────────
    _section(wrapper, "PYTHON")
    python_card = _card(wrapper)

    python_pref_var = tk.StringVar(value=shell_cfg.get("python_preference", "python3_first"))
    _choice_row(python_card, "check order", python_pref_var, [
        ("python3_first", "python3 → python"),
        ("python_first", "python → python3"),
    ])
    _hint(python_card, "Which binary to probe for first when method is 'auto' or\n"
                       "'python'. Falls through to the other if the first isn't found.")

    # ── TERMINAL ──────────────────────────────────────────────────────────────
    _section(wrapper, "TERMINAL")
    term_card = _card(wrapper)

    export_term_var = tk.StringVar(value=shell_cfg.get("export_term", "xterm"))
    _entry_row(term_card, "export TERM=", export_term_var)
    _hint(term_card, "Value exported after stabilising (export TERM=...). 'xterm' is\n"
                     "the safe default; use 'xterm-256color' if you want colour.")

    sync_stty_var = tk.BooleanVar(value=shell_cfg.get("sync_stty_size", True))
    _toggle_row(term_card, "sync rows/cols (stty)", sync_stty_var)
    _hint(term_card, "After stabilising, runs 'stty rows R columns C' matched to your\n"
                     "local terminal size, so full-screen tools (vim, nano, less) render\n"
                     "correctly instead of wrapping/garbling.")

    shell_path_var = tk.StringVar(value=shell_cfg.get("shell_path", "bash"))
    _entry_row(term_card, "shell binary", shell_path_var)
    _hint(term_card, "Shell spawned by the script/python wrapper, e.g. 'bash' or 'sh'.")

    open_terminal_var = tk.BooleanVar(
        value=data.get("open_terminal_on_listener_connection", False)
    )
    _toggle_row(term_card, "auto open terminal on listener connection", open_terminal_var)
    _hint(term_card, "Opens a terminal window whenever the listener reports a new\n"
                     "connection, so a stabilisation sequence can be run straight away.")

    # ── SYNC ─────────────────────────────────────────────────────────────────
    def _sync(*_):
        result["shell_stabilisation"] = {
            "auto_stabilise": auto_stabilise_var.get(),
            "auto_identify_terminal": auto_identify_var.get(),
            "method": method_var.get(),
            "python_preference": python_pref_var.get(),
            "export_term": export_term_var.get(),
            "sync_stty_size": sync_stty_var.get(),
            "shell_path": shell_path_var.get(),
        }
        result["open_terminal_on_listener_connection"] = open_terminal_var.get()

    for v in (auto_stabilise_var, auto_identify_var, method_var, python_pref_var,
              export_term_var, sync_stty_var, shell_path_var, open_terminal_var):
        v.trace_add("write", _sync)

    _sync()