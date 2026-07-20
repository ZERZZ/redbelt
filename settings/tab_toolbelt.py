"""
settings/tab_toolbelt.py — Toolbelt tab

IMPORT TOOL

IMPORT COMMAND

EDIT TOOL
"""

import tkinter as tk
from pathlib import Path

from config.config import _coerce_tools_base_path
from utils import tool_import

BG     = "#0d1117"
BG2    = "#161b22"
BG3    = "#21262d"
BG4    = "#2d333b"
BORDER = "#30363d"
ACCENT = "#d73a49"
GREEN  = "#3fb950"
CYAN   = "#58a6ff"
MUTED  = "#8b949e"
FG     = "#e6edf3"
MONO   = "Monospace"

PREVIEW_LEN = 52


def _default_hotkey(label: str) -> str:
    """First alnum character of *label*, lowercased. Empty string if none."""
    for ch in label or "":
        if ch.isalnum():
            return ch.lower()
    return ""


def _normalize(raw: dict) -> dict:

    norm: dict = {}
    for section, tools in (raw or {}).items():
        norm[section] = {}
        for name, val in tools.items():
            if isinstance(val, dict):
                nickname = val.get("nickname", name)
                norm[section][name] = {
                    "command": val.get("command", ""),
                    "nickname": nickname,
                    "hotkey": val.get("hotkey") or _default_hotkey(nickname),
                    "path": val.get("path"),
                }
            else:
                norm[section][name] = {
                    "command": str(val),
                    "nickname": name,
                    "hotkey": _default_hotkey(name),
                    "path": None,
                }
    return norm


def build(parent: tk.Frame, data: dict, result: dict) -> None:

    norm = _normalize(result.get("tools") or data.get("tools", {}))

    # ── ordered in-memory model ─────────────────────────────────────────────
    sections: list = list(norm.keys())
    tool_order: dict = {s: list(norm[s].keys()) for s in sections}
    tool_info: dict = {
        (s, n): dict(info) for s, tools in norm.items() for n, info in tools.items()
    }
    collapsed: dict = {s: True for s in sections} 

    row_meta: dict = {}        
    row_order: list = []       

    # drag state: what's being dragged
    drag = {"active": False, "kind": None, "section": None, "name": None}
    # pending: where it would land if released right now
    pending = {"valid": False, "kind": None, "section": None, "index": None}
    # floating "ghost" label that follows the cursor
    ghost = {"win": None}

    def _rebuild_nested() -> dict:
        nested: dict = {}
        for s in sections:
            nested[s] = {}
            for n in tool_order.get(s, []):
                nested[s][n] = tool_info[(s, n)]
        return nested

    def _persist():
        result["tools"] = _rebuild_nested()

    _persist()

    wrapper = tk.Frame(parent, bg=BG)
    wrapper.pack(fill="both", expand=True)

    hdr = tk.Frame(wrapper, bg=BG)
    hdr.pack(fill="x", padx=24, pady=(20, 8))
    tk.Label(hdr, text="TOOLBELT", font=(MONO, 8, "bold"),
              bg=BG, fg=ACCENT, anchor="w").pack(side="left")

    import_btn = tk.Button(
        hdr, text="＋ import tool", font=(MONO, 8, "bold"),
        bg=BG3, fg=GREEN, activebackground=BORDER, activeforeground=FG,
        relief="flat", bd=0, padx=10, pady=4, cursor="hand2",
        highlightthickness=1, highlightbackground=BORDER,
    )
    import_btn.pack(side="right")


    import_cmd_btn = tk.Button(
        hdr, text="＋ import command", font=(MONO, 8, "bold"),
        bg=BG3, fg=CYAN, activebackground=BORDER, activeforeground=FG,
        relief="flat", bd=0, padx=10, pady=4, cursor="hand2",
        highlightthickness=1, highlightbackground=BORDER,
    )
    import_cmd_btn.pack(side="right", padx=(0, 8))

    tk.Frame(hdr, bg=BORDER, height=1).pack(
        side="left", fill="x", expand=True, padx=(10, 10))

    body = tk.Frame(wrapper, bg=BG)
    body.pack(fill="both", expand=True, padx=24, pady=(0, 16))

    # ── list ────────────────────────────────────────────────────────
    list_card = tk.Frame(body, bg=BG2)
    list_card.pack(fill="both", expand=True)

    hint = tk.Label(list_card,
                     text="drag ≡ to reorder · click ✎ to edit a tool · click a section header to collapse  [build v3]",
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

    indicator_id = canvas.create_line(0, 0, 0, 0, fill=CYAN, width=4,
                                       state="hidden", capstyle="round")

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

    # ── import tool ─────────────────────────────────────────────────

    def _unique_name(section: str, name: str) -> str:
        if name not in tool_order.get(section, []):
            return name
        i = 2
        while f"{name} ({i})" in tool_order.get(section, []):
            i += 1
        return f"{name} ({i})"

    def _on_tool_imported(section: str, name: str, entry: dict):
        name = _unique_name(section, name)
        if section not in sections:
            sections.append(section)
        tool_order.setdefault(section, []).append(name)
        tool_info[(section, name)] = entry
        collapsed[section] = False
        _persist()
        _rerender_preserve_scroll()

    def _open_import_dialog(path_str: str):
        path = Path(path_str).expanduser()
        base = _coerce_tools_base_path(data.get("tools_base") or str(path.parent))
        kind = tool_import.detect_platform(path)
        default_section = kind if kind in sections else (sections[0] if sections else "Misc")
        tool_import.ImportDialog(
            parent, path=path, tools_base=base,
            sections=list(sections), default_section=default_section,
            detected_kind=kind,
            example_ip=data.get("listener_ip", "0.0.0.0"),
            example_port=data.get("port", 9001),
            on_save=_on_tool_imported,
        )

    def _open_import_browser():
        start = data.get("tools_base") or ""
        tool_import.FilePicker(parent, start, on_select=_open_import_dialog)

    import_btn.config(command=_open_import_browser)

    # ── import command ─────────────────────────────────────────────────

    def _open_command_dialog():
        default_section = sections[0] if sections else "Misc"
        tool_import.CommandImportDialog(
            parent,
            sections=list(sections),
            default_section=default_section,
            on_save=_on_tool_imported,
        )

    import_cmd_btn.config(command=_open_command_dialog)

    # ── edit popup ───────────────────────────────────────────────────────────

    def _open_editor_popup(section, name):
        info = tool_info[(section, name)]
        root = parent.winfo_toplevel()

        pop = tk.Toplevel(root)
        pop.title(f"{section} / {name}")
        pop.configure(bg=BG2)
        pop.transient(root)
        pop.resizable(False, False)
        try:
            pop.attributes("-topmost", True)
        except tk.TclError:
            pass

        inner = tk.Frame(pop, bg=BG2, padx=18, pady=16)
        inner.pack(fill="both", expand=True)

        tk.Label(inner, text=f"{section} / {name}", font=(MONO, 9, "bold"),
                  bg=BG2, fg=CYAN, anchor="w").pack(fill="x", pady=(0, 12))

        tk.Label(inner, text="tray / hotkey nickname", font=(MONO, 8),
                  bg=BG2, fg=MUTED, anchor="w").pack(fill="x")
        nickname_var = tk.StringVar(value=info["nickname"])
        nickname_entry = tk.Entry(inner, textvariable=nickname_var,
                                    font=(MONO, 10), bg=BG3, fg=FG,
                                    insertbackground=FG, relief="flat", bd=0,
                                    highlightthickness=1, highlightbackground=BORDER,
                                    highlightcolor=CYAN)
        nickname_entry.pack(fill="x", ipady=5, pady=(4, 14))

        tk.Label(inner, text="clipboard command", font=(MONO, 8),
                  bg=BG2, fg=MUTED, anchor="w").pack(fill="x")

        cmd_frame = tk.Frame(inner, bg=BG3, highlightthickness=1,
                              highlightbackground=BORDER)
        cmd_frame.pack(fill="both", expand=True, pady=(4, 10))

        cmd_text = tk.Text(cmd_frame, font=(MONO, 9), bg=BG3, fg=FG,
                             insertbackground=FG, relief="flat", bd=0,
                             wrap="char", height=8, width=48, padx=8, pady=6,
                             highlightthickness=0)
        cmd_scroll = tk.Scrollbar(cmd_frame, orient="vertical",
                                    command=cmd_text.yview,
                                    bg=BG3, troughcolor=BG2,
                                    activebackground=BORDER)
        cmd_text.configure(yscrollcommand=cmd_scroll.set)
        cmd_text.pack(side="left", fill="both", expand=True)
        cmd_scroll.pack(side="right", fill="y")
        cmd_text.insert("1.0", info["command"])

        tk.Label(inner, text="{IP} and {PORT} are filled in automatically at copy time.",
                  font=(MONO, 8), bg=BG2, fg=BORDER, anchor="w",
                  justify="left", wraplength=340).pack(fill="x", pady=(0, 14))

        status = tk.Label(inner, text="", font=(MONO, 8), bg=BG2, fg=GREEN, anchor="w")

        btn_row = tk.Frame(inner, bg=BG2)
        btn_row.pack(fill="x")


        confirm_frame = tk.Frame(inner, bg=BG2)

        def _do_cancel():
            pop.destroy()

        def _do_save():
            info["nickname"] = nickname_var.get().strip() or name
            info["command"] = cmd_text.get("1.0", "end").rstrip("\n")
            _persist()
            status.config(text="✓ saved")
            pop.after(350, pop.destroy)
            _rerender_preserve_scroll()

        def _hide_confirm():
            confirm_frame.pack_forget()
            btn_row.pack(fill="x")

        def _do_remove():
            path_str = info.get("path")
            if path_str:
                try:
                    p = Path(path_str).expanduser()
                    if p.is_file():
                        p.unlink()
                except OSError:
                    pass  
            if name in tool_order.get(section, []):
                tool_order[section].remove(name)
            tool_info.pop((section, name), None)
            _persist()
            pop.destroy()
            _rerender_preserve_scroll()

        def _show_confirm():
            btn_row.pack_forget()
            for w in confirm_frame.winfo_children():
                w.destroy()
            tk.Label(confirm_frame,
                      text="are you sure you'd like to remove this item?",
                      font=(MONO, 8, "bold"), bg=BG2, fg=ACCENT, anchor="w",
                      justify="left", wraplength=340).pack(fill="x", pady=(0, 8))
            yn_row = tk.Frame(confirm_frame, bg=BG2)
            yn_row.pack(fill="x")
            tk.Button(yn_row, text="no", font=(MONO, 9), bg=BG3, fg=MUTED,
                       activebackground=BORDER, activeforeground=FG,
                       relief="flat", bd=0, padx=12, pady=6, cursor="hand2",
                       command=_hide_confirm).pack(side="right", padx=(8, 0))
            tk.Button(yn_row, text="yes, remove", font=(MONO, 9, "bold"),
                       bg=BG3, fg=ACCENT,
                       activebackground=BORDER, activeforeground=FG,
                       relief="flat", bd=0, padx=12, pady=6, cursor="hand2",
                       command=_do_remove).pack(side="right")
            confirm_frame.pack(fill="x", pady=(4, 0))

        tk.Button(btn_row, text="cancel", font=(MONO, 9), bg=BG3, fg=MUTED,
                   activebackground=BORDER, activeforeground=FG,
                   relief="flat", bd=0, padx=12, pady=6, cursor="hand2",
                   command=_do_cancel).pack(side="right", padx=(8, 0))
        tk.Button(btn_row, text="💾 save", font=(MONO, 9, "bold"), bg=BG3, fg=GREEN,
                   activebackground=BORDER, activeforeground=FG,
                   relief="flat", bd=0, padx=12, pady=6, cursor="hand2",
                   command=_do_save).pack(side="right")
        tk.Button(btn_row, text="🗑 remove", font=(MONO, 9), bg=BG3, fg=ACCENT,
                   activebackground=BORDER, activeforeground=FG,
                   relief="flat", bd=0, padx=12, pady=6, cursor="hand2",
                   command=_show_confirm).pack(side="left")
        status.pack(side="left", padx=(10, 0))

        pop.bind("<Escape>", lambda e: _do_cancel())
        nickname_entry.focus_set()
        nickname_entry.select_range(0, "end")

        pop.update_idletasks()
        root.update_idletasks()
        x = root.winfo_rootx() + max((root.winfo_width() - pop.winfo_width()) // 2, 0)
        y = root.winfo_rooty() + max((root.winfo_height() - pop.winfo_height()) // 3, 0)
        pop.geometry(f"+{x}+{y}")
        pop.grab_set()



    # ── drag and drop wirign ───────────────────────────────────────────────

    def _row_widget_at(x_root, y_root):
        canvas_left = canvas.winfo_rootx()
        canvas_right = canvas_left + canvas.winfo_width()
        if not (canvas_left <= x_root <= canvas_right):
            return None
        for widget, meta in row_order:
            try:
                if not widget.winfo_viewable():
                    continue
                top = widget.winfo_rooty()
                bottom = top + widget.winfo_height()
            except tk.TclError:
                continue
            if top <= y_root < bottom:
                return widget
        return None

    def _half_hover(widget, y_root):
        top = widget.winfo_rooty()
        height = widget.winfo_height() or 1
        return "top" if (y_root - top) < height / 2 else "bottom"

    def _make_ghost(text):
        root = parent.winfo_toplevel()
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        try:
            win.attributes("-topmost", True)
        except tk.TclError:
            pass
        tk.Label(win, text=text, font=(MONO, 9, "bold"),
                 bg=CYAN, fg=BG, padx=8, pady=4).pack()
        return win

    def _hide_indicator():
        canvas.itemconfigure(indicator_id, state="hidden")

    def _show_indicator_at(widget, half):
        top_screen = widget.winfo_rooty() - canvas.winfo_rooty()
        y = top_screen if half == "top" else top_screen + widget.winfo_height()
        cy = canvas.canvasy(y)
        x1 = canvas.canvasx(0)
        x2 = canvas.canvasx(max(canvas.winfo_width(), 10))
        canvas.coords(indicator_id, x1, cy, x2, cy)
        canvas.itemconfigure(indicator_id, state="normal")
        canvas.tag_raise(indicator_id)

    def _apply_tool_drop(section_to, insert_idx):
        s_from, name = drag["section"], drag["name"]
        if s_from == section_to:
            orig_idx = tool_order[s_from].index(name)
            tool_order[s_from].remove(name)
            if orig_idx < insert_idx:
                insert_idx -= 1
        else:
            tool_order[s_from].remove(name)
            tool_info[(section_to, name)] = tool_info.pop((s_from, name))
        tool_order.setdefault(section_to, [])
        insert_idx = max(0, min(insert_idx, len(tool_order[section_to])))
        tool_order[section_to].insert(insert_idx, name)

    def _apply_section_drop(insert_idx):
        sec = drag["section"]
        orig_idx = sections.index(sec)
        sections.remove(sec)
        if orig_idx < insert_idx:
            insert_idx -= 1
        insert_idx = max(0, min(insert_idx, len(sections)))
        sections.insert(insert_idx, sec)

    def _drag_motion(event):
        if ghost["win"] is not None:
            try:
                ghost["win"].geometry(f"+{event.x_root + 14}+{event.y_root + 8}")
            except tk.TclError:
                pass

        pending["valid"] = False
        target = _row_widget_at(event.x_root, event.y_root)

        if target is not None and target in row_meta:
            meta = row_meta[target]
            half = _half_hover(target, event.y_root)

            if drag["kind"] == "tool":
                if meta["kind"] == "tool":
                    sec = meta["section"]
                    names = tool_order.get(sec, [])
                    idx = names.index(meta["name"]) if meta["name"] in names else len(names)
                    insert_idx = idx if half == "top" else idx + 1
                    pending.update(valid=True, kind="tool", section=sec, index=insert_idx)
                    _show_indicator_at(target, half)
                elif meta["kind"] == "section":
                    sec = meta["section"]
                    pending.update(valid=True, kind="tool", section=sec, index=0)
                    _show_indicator_at(target, "bottom")

            elif drag["kind"] == "section":
                sec = meta["section"]
                idx = sections.index(sec) if sec in sections else len(sections)
                insert_idx = idx if half == "top" else idx + 1
                pending.update(valid=True, kind="section", section=sec, index=insert_idx)
                _show_indicator_at(target, half)

        if not pending["valid"]:
            _hide_indicator()

    def _drag_release(event):
        try:
            if ghost["win"] is not None:
                ghost["win"].destroy()
        except tk.TclError:
            pass
        ghost["win"] = None
        _hide_indicator()
        canvas.unbind_all("<B1-Motion>")
        canvas.unbind_all("<ButtonRelease-1>")
        canvas.config(cursor="")

        if drag["active"] and pending["valid"]:
            if drag["kind"] == "tool" and pending["kind"] == "tool":
                _apply_tool_drop(pending["section"], pending["index"])
                _persist()
            elif drag["kind"] == "section" and pending["kind"] == "section":
                _apply_section_drop(pending["index"])
                _persist()

        drag["active"] = False
        pending["valid"] = False
        _rerender_preserve_scroll()

    def _drag_start(event, kind, section, name):
        try:
            event.widget.grab_release()
        except tk.TclError:
            pass
        drag.update(active=True, kind=kind, section=section, name=name)
        canvas.config(cursor="fleur")
        if kind == "tool":
            label_text = "≡ " + tool_info[(section, name)]["nickname"]
        else:
            label_text = "≡ " + section.upper()
        ghost["win"] = _make_ghost(label_text)
        canvas.bind_all("<B1-Motion>", _drag_motion)
        canvas.bind_all("<ButtonRelease-1>", _drag_release)

    # ── collapse / expand ────────────────────────────────────────────────────

    def _toggle_section(section):
        collapsed[section] = not collapsed.get(section, False)
        _rerender_preserve_scroll()

    # ── rendering ────────────────────────────────────────────────────────────

    def _render():
        row_meta.clear()
        row_order.clear()
        for w in scroll_frame.winfo_children():
            w.destroy()
        list_inner = tk.Frame(scroll_frame, bg=BG2, padx=4, pady=6)
        list_inner.pack(fill="both", expand=True)

        for section in sections:
            names = tool_order.get(section, [])
            is_collapsed = collapsed.get(section, False)

            sec_row = tk.Frame(list_inner, bg=BG3, cursor="hand2")
            sec_row.pack(fill="x", pady=(8, 2))
            row_meta[sec_row] = {"kind": "section", "section": section, "name": None}
            row_order.append((sec_row, row_meta[sec_row]))
            sec_row.bind("<Button-1>", lambda e, s=section: _toggle_section(s))

            sec_handle = tk.Label(sec_row, text="≡", font=(MONO, 16, "bold"),
                                    bg=BG3, fg=MUTED, cursor="fleur", padx=12, pady=8)
            sec_handle.pack(side="left")
            sec_handle.bind("<ButtonPress-1>",
                             lambda e, s=section: _drag_start(e, "section", s, None))

            sec_label = tk.Label(sec_row, text=section.upper(),
                                   font=(MONO, 9, "bold"), bg=BG3, fg=ACCENT,
                                   anchor="w", cursor="hand2")
            sec_label.pack(side="left", padx=(4, 0))
            sec_label.bind("<Button-1>", lambda e, s=section: _toggle_section(s))

            sec_count = tk.Label(sec_row, text=f"({len(names)})",
                                   font=(MONO, 8), bg=BG3, fg=MUTED, cursor="hand2")
            sec_count.pack(side="left", padx=(6, 0))
            sec_count.bind("<Button-1>", lambda e, s=section: _toggle_section(s))

            arrow_txt = "▸" if is_collapsed else "▾"
            sec_arrow = tk.Label(sec_row, text=arrow_txt, font=(MONO, 11, "bold"),
                                   bg=BG3, fg=ACCENT, cursor="hand2", padx=14)
            sec_arrow.pack(side="right")
            sec_arrow.bind("<Button-1>", lambda e, s=section: _toggle_section(s))

            sec_fill = tk.Frame(sec_row, bg=BG3, cursor="hand2")
            sec_fill.pack(side="left", fill="x", expand=True)
            sec_fill.bind("<Button-1>", lambda e, s=section: _toggle_section(s))

            for widget in (sec_row, sec_label, sec_count, sec_fill, sec_arrow):
                row_meta[widget] = row_meta[sec_row]

            if is_collapsed:
                continue

            if not names:
                empty_row = tk.Frame(list_inner, bg=BG2)
                empty_row.pack(fill="x")
                row_meta[empty_row] = {"kind": "section", "section": section, "name": None}
                row_order.append((empty_row, row_meta[empty_row]))
                tk.Label(empty_row, text="  (no tools in this section — drop one here, or ＋ import tool)",
                          font=(MONO, 8), bg=BG2, fg=BORDER, anchor="w").pack(
                    fill="x", padx=(20, 0), pady=4)

            for name in names:
                info = tool_info[(section, name)]

                row = tk.Frame(list_inner, bg=BG2)
                row.pack(fill="x")
                row_meta[row] = {"kind": "tool", "section": section, "name": name}
                row_order.append((row, row_meta[row]))

                handle = tk.Label(row, text="≡", font=(MONO, 14, "bold"), bg=BG2,
                                    fg=MUTED, cursor="fleur", padx=12, pady=8)
                handle.pack(side="left")
                handle.bind("<ButtonPress-1>",
                            lambda e, s=section, n=name: _drag_start(e, "tool", s, n))

                pencil = tk.Label(row, text="✎", font=(MONO, 10), bg=BG2,
                                    fg=CYAN, cursor="hand2", padx=10, pady=5)
                pencil.pack(side="right")
                pencil.bind("<Button-1>",
                             lambda e, s=section, n=name: _open_editor_popup(s, n))

                text_col = tk.Frame(row, bg=BG2)
                text_col.pack(side="left", fill="x", expand=True, pady=3)

                nick = info["nickname"]
                title_txt = nick if nick == name else f"{nick}  ({name})"
                tk.Label(text_col, text=title_txt, font=(MONO, 9, "bold"),
                          bg=BG2, fg=FG, anchor="w").pack(fill="x")

                preview = info["command"].replace("\n", " ")
                if len(preview) > PREVIEW_LEN:
                    preview = preview[:PREVIEW_LEN] + "…"
                tk.Label(text_col, text=preview, font=(MONO, 8),
                          bg=BG2, fg=MUTED, anchor="w").pack(fill="x")

                for widget in (row, text_col, *text_col.winfo_children()):
                    row_meta[widget] = row_meta[row]

        canvas.tag_raise(indicator_id)

    def _rerender_preserve_scroll():
        frac = canvas.yview()[0]
        _render()
        canvas.yview_moveto(frac)

    _render()