"""
settings/tab_hotkeys.py — Hotkeys tab
"""

import tkinter as tk

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

_DEFAULT_LEADER = "<ctrl>+<alt>+<space>"
_DEFAULT_TIMEOUT_MS = 2500

# ── shared key column sizing —────────────────────────────────────
KEY_COL_PADX    = (0, 12)
KEY_ENTRY_FONT  = (MONO, 10, "bold")
KEY_ENTRY_W     = 3
KEY_ENTRY_IPADY = 3
KEY_RESET_FONT  = (MONO, 12, "bold")
KEY_WARN_FONT   = (MONO, 14, "bold")
KEY_WARN_W      = 2   # fixed width


def _default_hotkey(label: str) -> str:
    """First alnum character of *label*, lowercased. Empty string if none."""
    for ch in label or "":
        if ch.isalnum():
            return ch.lower()
    return ""


def _safe_int(val, default: int) -> int:
    try:
        return max(250, int(val))
    except (TypeError, ValueError):
        return default


def _format_leader(raw: str) -> str:
    """Normalize free-typed leader text into pynput's GlobalHotKeys format."""
    raw = (raw or "").strip()
    if not raw:
        return _DEFAULT_LEADER

    parts = [p.strip().strip("<>").lower() for p in raw.split("+")]
    parts = [p for p in parts if p]
    if not parts:
        return _DEFAULT_LEADER

    formatted = []
    for p in parts:
        if len(p) == 1 and p.isalnum():
            formatted.append(p)
        else:
            formatted.append(f"<{p}>")
    return "+".join(formatted)


def build(parent: tk.Frame, data: dict, result: dict) -> None:

    base_tools = result.get("tools") or data.get("tools", {})
    base_launch = result.get("hotkey_launch") or data.get("hotkey_launch", {}) or {}
    base_section_hotkeys = result.get("section_hotkeys") or data.get("section_hotkeys", {}) or {}

    # ── tool model ────────────────────────────────────────────────────────────
    sections: list = list(base_tools.keys())
    tool_order: dict = {s: list(base_tools[s].keys()) for s in sections}
    tool_info: dict = {}
    for s, tools in base_tools.items():
        for n, val in tools.items():
            if isinstance(val, dict):
                nickname = val.get("nickname", n)
                tool_info[(s, n)] = {
                    "command": val.get("command", ""),
                    "nickname": nickname,
                    "hotkey": val.get("hotkey") or _default_hotkey(nickname),
                }
            else:
                tool_info[(s, n)] = {
                    "command": str(val),
                    "nickname": n,
                    "hotkey": _default_hotkey(n),
                }

    # ── section model ───────────────────────────────────────────────────────────────────
    section_hotkeys: dict = {
        s: (base_section_hotkeys.get(s) or _default_hotkey(s)) for s in sections
    }

    collapsed: dict = {s: False for s in sections}   # start expanded — this tab's whole job is the keys

    hotkey_vars: dict = {}             # (section, name) -> tk.StringVar          (tool keys)
    hotkey_widgets: dict = {}          # (section, name) -> (entry, warn_label)   (tool keys)
    section_hotkey_vars: dict = {}     # section -> tk.StringVar
    section_hotkey_widgets: dict = {}  # section -> (entry, warn_label)

    # ── persist ─────────────────────────────────────────────────────────

    def _rebuild_nested() -> dict:
        nested: dict = {}
        for s in sections:
            nested[s] = {}
            for n in tool_order.get(s, []):
                nested[s][n] = tool_info[(s, n)]
        return nested

    def _persist_tools():
        result["tools"] = _rebuild_nested()

    def _persist_section_hotkeys():
        result["section_hotkeys"] = dict(section_hotkeys)

    def _persist_launch():
        result["hotkey_launch"] = {
            "enabled": bool(launch_enabled_var.get()),
            "leader": _format_leader(leader_var.get()),
            "timeout_ms": _safe_int(timeout_var.get(), _DEFAULT_TIMEOUT_MS),
        }

    _persist_tools()
    _persist_section_hotkeys()

    # ── layout shell ──────────────────────────────────────────────────────────────────────────

    wrapper = tk.Frame(parent, bg=BG)
    wrapper.pack(fill="both", expand=True)

    hdr = tk.Frame(wrapper, bg=BG)
    hdr.pack(fill="x", padx=24, pady=(20, 8))
    tk.Label(hdr, text="HOTKEYS", font=(MONO, 8, "bold"),
              bg=BG, fg=ACCENT, anchor="w").pack(side="left")
    tk.Frame(hdr, bg=BORDER, height=1).pack(
        side="left", fill="x", expand=True, padx=(10, 0))

    body = tk.Frame(wrapper, bg=BG)
    body.pack(fill="both", expand=True, padx=24, pady=(0, 8))

    # ── LAUNCH card ────────────────────────────────────────────────────────────────

    launch_card = tk.Frame(body, bg=BG2)
    launch_card.pack(fill="x", pady=(0, 12))

    launch_inner = tk.Frame(launch_card, bg=BG2, padx=14, pady=12)
    launch_inner.pack(fill="x")

    launch_top = tk.Frame(launch_inner, bg=BG2)
    launch_top.pack(fill="x")

    launch_enabled_var = tk.BooleanVar(value=bool(base_launch.get("enabled", True)))

    def _on_launch_toggle():
        _persist_launch()

    tk.Checkbutton(launch_top, text="enable hotkey launch",
                    variable=launch_enabled_var, font=(MONO, 9, "bold"),
                    bg=BG2, fg=FG, selectcolor=BG3, activebackground=BG2,
                    activeforeground=FG, relief="flat", bd=0,
                    highlightthickness=0, cursor="hand2",
                    command=_on_launch_toggle).pack(side="left")

    launch_row = tk.Frame(launch_inner, bg=BG2)
    launch_row.pack(fill="x", pady=(10, 0))

    tk.Label(launch_row, text="leader", font=(MONO, 9),
              bg=BG2, fg=MUTED, width=8, anchor="w").pack(side="left")

    leader_var = tk.StringVar(value=str(base_launch.get("leader") or _DEFAULT_LEADER))

    def _on_leader_write(*_):
        _persist_launch()

    leader_var.trace_add("write", _on_leader_write)

    def _on_leader_focus_out(_e=None):
        leader_var.set(_format_leader(leader_var.get()))

    leader_entry = tk.Entry(launch_row, textvariable=leader_var,
                              font=(MONO, 10), bg=BG3, fg=CYAN,
                              insertbackground=FG, relief="flat", bd=0,
                              width=22,
                              highlightthickness=1, highlightbackground=BORDER,
                              highlightcolor=CYAN)
    leader_entry.pack(side="left", ipady=5, padx=(0, 16))
    leader_entry.bind("<FocusOut>", _on_leader_focus_out)

    tk.Label(launch_row, text="timeout", font=(MONO, 9),
              bg=BG2, fg=MUTED, anchor="w").pack(side="left")

    timeout_var = tk.StringVar(value=str(_safe_int(base_launch.get("timeout_ms"), _DEFAULT_TIMEOUT_MS)))

    def _on_timeout_write(*_):
        _persist_launch()

    timeout_var.trace_add("write", _on_timeout_write)

    timeout_spin = tk.Spinbox(launch_row, textvariable=timeout_var,
                                from_=250, to=10000, increment=250,
                                font=(MONO, 10), bg=BG3, fg=CYAN,
                                insertbackground=FG, relief="flat", bd=0,
                                width=6, justify="center",
                                highlightthickness=1, highlightbackground=BORDER,
                                highlightcolor=CYAN, buttonbackground=BG3)
    timeout_spin.pack(side="left", padx=(8, 4))

    tk.Label(launch_row, text="ms", font=(MONO, 8),
              bg=BG2, fg=BORDER).pack(side="left")

    tk.Label(launch_inner,
              text="leader is formatted automatically from what you type, e.g. ctrl+alt+space · timeout is how long the chord waits between keypresses before cancelling",
              font=(MONO, 8), bg=BG2, fg=BORDER, anchor="w",
              wraplength=500, justify="left").pack(fill="x", pady=(10, 0))

    _persist_launch()

    # ── tool/section list ────────────────────────────────────────────────────

    list_card = tk.Frame(body, bg=BG2)
    list_card.pack(fill="both", expand=True)

    hint = tk.Label(list_card,
                     text="section key (in the header) must be unique across all sections · tool key must be unique within its section · click ↺ to restore default",
                     font=(MONO, 8), bg=BG2, fg=BORDER, anchor="w")
    hint.pack(fill="x", padx=14, pady=(10, 4))

    list_outer = tk.Frame(list_card, bg=BG2)
    list_outer.pack(fill="both", expand=True, padx=(10, 0), pady=(0, 10))

    canvas = tk.Canvas(list_outer, bg=BG2, bd=0,
                        highlightthickness=0, relief="flat")
    scrollbar = tk.Scrollbar(list_outer, orient="vertical",
                               command=canvas.yview,
                               bg=BG3, troughcolor=BG2,
                               activebackground=BORDER)
    scroll_frame = tk.Frame(canvas, bg=BG2)

    scroll_win = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

    def _on_scroll_frame_configure(_event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas_configure(event):
        canvas.itemconfigure(scroll_win, width=event.width)

    scroll_frame.bind("<Configure>", _on_scroll_frame_configure)
    canvas.bind("<Configure>", _on_canvas_configure)

    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

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

    # ── conflict detection ────────────────────────────────────────────────────────

    def _recalc_tool_conflicts():
        for section in sections:
            counts: dict = {}
            for name in tool_order.get(section, []):
                hk = tool_info[(section, name)]["hotkey"]
                if hk:
                    counts[hk] = counts.get(hk, 0) + 1
            for name in tool_order.get(section, []):
                pair = hotkey_widgets.get((section, name))
                if pair is None:
                    continue
                entry, warn = pair
                hk = tool_info[(section, name)]["hotkey"]
                conflict = bool(hk) and counts.get(hk, 0) > 1
                entry.configure(
                    highlightbackground=ACCENT if conflict else BORDER,
                    highlightcolor=ACCENT if conflict else CYAN,
                )
                warn.configure(text="⚠" if conflict else "")

    def _recalc_section_conflicts():
        counts: dict = {}
        for section in sections:
            hk = section_hotkeys[section]
            if hk:
                counts[hk] = counts.get(hk, 0) + 1
        for section in sections:
            pair = section_hotkey_widgets.get(section)
            if pair is None:
                continue
            entry, warn = pair
            hk = section_hotkeys[section]
            conflict = bool(hk) and counts.get(hk, 0) > 1
            entry.configure(
                highlightbackground=ACCENT if conflict else BORDER,
                highlightcolor=ACCENT if conflict else CYAN,
            )
            warn.configure(text="⚠" if conflict else "")

    # ── collapse / expand ──────────────────────────────────────────────────────────────

    def _toggle_section(section):
        collapsed[section] = not collapsed.get(section, False)
        _rerender_preserve_scroll()

    # ── hotkey var wiring — tools ─────────────────────────────────────────────────

    def _make_hotkey_var(section, name):
        var = tk.StringVar(value=tool_info[(section, name)]["hotkey"])

        def _on_write(*_):
            val = var.get()
            if len(val) > 1:
                val = val[-1]
            val = val.lower()
            if val and not val.isalnum():
                val = tool_info[(section, name)]["hotkey"]  # reject, revert
            if var.get() != val:
                var.set(val) 
                return
            tool_info[(section, name)]["hotkey"] = val
            _persist_tools()
            _recalc_tool_conflicts()

        var.trace_add("write", _on_write)
        return var

    def _reset_hotkey(section, name):
        hotkey_vars[(section, name)].set(
            _default_hotkey(tool_info[(section, name)]["nickname"])
        )

    # ── hotkey var wiring ───── ──────────────────────────────────────────────

    def _make_section_hotkey_var(section):
        var = tk.StringVar(value=section_hotkeys[section])

        def _on_write(*_):
            val = var.get()
            if len(val) > 1:
                val = val[-1]
            val = val.lower()
            if val and not val.isalnum():
                val = section_hotkeys[section]  # reject, revert
            if var.get() != val:
                var.set(val)
                return
            section_hotkeys[section] = val
            _persist_section_hotkeys()
            _recalc_section_conflicts()

        var.trace_add("write", _on_write)
        return var

    def _reset_section_hotkey(section):
        section_hotkey_vars[section].set(_default_hotkey(section))

    # ── rendering ────────────────────────────────────────────────────────────

    def _render():
        hotkey_vars.clear()
        hotkey_widgets.clear()
        section_hotkey_vars.clear()
        section_hotkey_widgets.clear()
        for w in scroll_frame.winfo_children():
            w.destroy()
        list_inner = tk.Frame(scroll_frame, bg=BG2, padx=4, pady=6)
        list_inner.pack(fill="both", expand=True)

        for section in sections:
            names = tool_order.get(section, [])
            is_collapsed = collapsed.get(section, False)

            sec_row = tk.Frame(list_inner, bg=BG3, cursor="hand2")
            sec_row.pack(fill="x", pady=(8, 2))
            sec_row.bind("<Button-1>", lambda e, s=section: _toggle_section(s))

            # ── left side───── collapse arrow ──────────
            arrow_txt = "▸" if is_collapsed else "▾"
            sec_arrow = tk.Label(sec_row, text=arrow_txt, font=(MONO, 11, "bold"),
                                   bg=BG3, fg=ACCENT, cursor="hand2", padx=14)
            sec_arrow.pack(side="left")
            sec_arrow.bind("<Button-1>", lambda e, s=section: _toggle_section(s))

            sec_label = tk.Label(sec_row, text=section.upper(),
                                   font=(MONO, 9, "bold"), bg=BG3, fg=ACCENT,
                                   anchor="w", cursor="hand2", pady=8)
            sec_label.pack(side="left")
            sec_label.bind("<Button-1>", lambda e, s=section: _toggle_section(s))

            sec_count = tk.Label(sec_row, text=f"({len(names)})",
                                   font=(MONO, 8), bg=BG3, fg=MUTED, cursor="hand2")
            sec_count.pack(side="left", padx=(6, 0))
            sec_count.bind("<Button-1>", lambda e, s=section: _toggle_section(s))

            sec_fill = tk.Frame(sec_row, bg=BG3, cursor="hand2")
            sec_fill.pack(side="left", fill="x", expand=True)
            sec_fill.bind("<Button-1>", lambda e, s=section: _toggle_section(s))


            # ── right side: key column ────────────────────
            sec_key_col = tk.Frame(sec_row, bg=BG3)
            sec_key_col.pack(side="right", padx=KEY_COL_PADX)

            sec_var = _make_section_hotkey_var(section)
            section_hotkey_vars[section] = sec_var

            sec_entry = tk.Entry(sec_key_col, textvariable=sec_var,
                                   font=KEY_ENTRY_FONT, bg=BG,
                                   fg=CYAN, insertbackground=FG, relief="flat", bd=0,
                                   width=KEY_ENTRY_W, justify="center",
                                   highlightthickness=1, highlightbackground=BORDER,
                                   highlightcolor=CYAN)
            sec_entry.pack(side="right", ipady=KEY_ENTRY_IPADY)

            sec_reset = tk.Label(sec_key_col, text="↺", font=KEY_RESET_FONT,
                                   bg=BG3, fg=CYAN, cursor="hand2", padx=4)
            sec_reset.pack(side="right")
            sec_reset.bind("<Button-1>", lambda e, s=section: _reset_section_hotkey(s))

            sec_warn = tk.Label(sec_key_col, text="", font=KEY_WARN_FONT,
                                  bg=BG3, fg=ACCENT, width=KEY_WARN_W)
            sec_warn.pack(side="right", padx=(0, 4))

            section_hotkey_widgets[section] = (sec_entry, sec_warn)

            if is_collapsed:
                continue

            if not names:
                tk.Label(list_inner, text="  (no tools in this section)",
                          font=(MONO, 8), bg=BG2, fg=BORDER, anchor="w").pack(
                    fill="x", padx=(20, 0), pady=4)
                continue

            for name in names:
                info = tool_info[(section, name)]

                row = tk.Frame(list_inner, bg=BG2)
                row.pack(fill="x")

                key_col = tk.Frame(row, bg=BG2)
                key_col.pack(side="right", padx=KEY_COL_PADX, pady=3)

                var = _make_hotkey_var(section, name)
                hotkey_vars[(section, name)] = var

                entry = tk.Entry(key_col, textvariable=var, font=KEY_ENTRY_FONT,
                                   bg=BG3, fg=CYAN, insertbackground=FG,
                                   relief="flat", bd=0, width=KEY_ENTRY_W, justify="center",
                                   highlightthickness=1, highlightbackground=BORDER,
                                   highlightcolor=CYAN)
                entry.pack(side="right", ipady=KEY_ENTRY_IPADY)

                reset_btn = tk.Label(key_col, text="↺", font=KEY_RESET_FONT,
                                       bg=BG2, fg=CYAN, cursor="hand2", padx=6)
                reset_btn.pack(side="right")
                reset_btn.bind("<Button-1>",
                                 lambda e, s=section, n=name: _reset_hotkey(s, n))

                warn = tk.Label(key_col, text="", font=KEY_WARN_FONT,
                                  bg=BG2, fg=ACCENT, width=KEY_WARN_W)
                warn.pack(side="right", padx=(0, 4))

                hotkey_widgets[(section, name)] = (entry, warn)

                text_col = tk.Frame(row, bg=BG2)
                text_col.pack(side="left", fill="x", expand=True, pady=3, padx=(14, 0))

                nick = info["nickname"]
                title_txt = nick if nick == name else f"{nick}  ({name})"
                tk.Label(text_col, text=title_txt, font=(MONO, 9, "bold"),
                          bg=BG2, fg=FG, anchor="w").pack(fill="x")

        _recalc_tool_conflicts()
        _recalc_section_conflicts()

    def _rerender_preserve_scroll():
        frac = canvas.yview()[0]
        _render()
        canvas.yview_moveto(frac)

    _render()