"""
settings/tab_files.py — Files tab

Browse or update the tools root directory, auto updates on path change.
Also offers "＋ import tool": pick any file on disk


Writes: result["tools_base"], result["tools"] (only the latter if something is imported from this tab)
"""

import os
import tkinter as tk
from pathlib import Path

from config.config import _coerce_tools_base_path, _display_path
from utils import tool_import

# CENTRALISE THIS ALREADY-USED STUFF SO IT'S EASY TO TWEAK THEME/BEHAVIOUR IN ONE PLACE
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

DEBOUNCE_MS = 350
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TOOLS_ROOT = PROJECT_ROOT / "tools"


def _check_path(base: Path | str):
    """Return (ok: bool, message: str) describing the root path's validity."""
    base = _coerce_tools_base_path(base)
    if not str(base):
        return False, "no path entered"
    if not base.exists():
        return False, "path does not exist"
    if not base.is_dir():
        return False, "path exists but is not a directory"
    if not os.access(base, os.R_OK):
        return False, "path exists but is not readable (permission denied)"
    return True, "path is valid"


# Custom themed directory browser bc the default one was ugly  ─────────────────

class DirBrowser(tk.Toplevel):
    def __init__(self, parent, start_path: str, on_select):
        super().__init__(parent)
        self.on_select = on_select
        self.title("Select tools root")
        self.configure(bg=BG)
        self.geometry("560x460")
        self.minsize(420, 340)
        self.transient(parent.winfo_toplevel())
        self.grab_set()

        start = _coerce_tools_base_path(start_path) if start_path else Path.home()
        if not start.exists() or not start.is_dir():
            start = Path.home()
        self.current = start.resolve()

        # ── path bar ──────────────────────────────────────────────────────
        top = tk.Frame(self, bg=BG2)
        top.pack(fill="x")

        inner_top = tk.Frame(top, bg=BG2, padx=12, pady=10)
        inner_top.pack(fill="x")

        tk.Button(inner_top, text="↑", font=(MONO, 10, "bold"),
                  bg=BG3, fg=CYAN, activebackground=BORDER,
                  activeforeground=FG, relief="flat", bd=0,
                  padx=8, pady=2, cursor="hand2",
                  command=self._go_up,
                  highlightthickness=1,
                  highlightbackground=BORDER).pack(side="left", padx=(0, 8))

        self.path_var = tk.StringVar()
        entry = tk.Entry(inner_top, textvariable=self.path_var,
                          font=(MONO, 10), bg=BG3, fg=FG,
                          insertbackground=FG, relief="flat", bd=0,
                          highlightthickness=1, highlightbackground=BORDER,
                          highlightcolor=CYAN)
        entry.pack(side="left", fill="x", expand=True, ipady=5)
        entry.bind("<Return>", self._go_to_typed)

        # ── listing ──────────────────────────────────────────────────────
        list_outer = tk.Frame(self, bg=BG2)
        list_outer.pack(fill="both", expand=True, padx=0, pady=(1, 0))

        self.canvas = tk.Canvas(list_outer, bg=BG2, bd=0,
                                 highlightthickness=0, relief="flat")
        sb = tk.Scrollbar(list_outer, orient="vertical",
                           command=self.canvas.yview,
                           bg=BG3, troughcolor=BG2,
                           activebackground=BORDER)
        self.list_frame = tk.Frame(self.canvas, bg=BG2)

        self.list_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.canvas.bind("<Enter>", lambda e: self._bind_wheel())
        self.canvas.bind("<Leave>", lambda e: self._unbind_wheel())

        # ── footer ───────────────────────────────────────────────────────
        foot = tk.Frame(self, bg=BG2)
        foot.pack(fill="x")
        foot_inner = tk.Frame(foot, bg=BG2, padx=12, pady=10)
        foot_inner.pack(fill="x")

        self.err_label = tk.Label(foot_inner, text="", font=(MONO, 8),
                                   bg=BG2, fg=ACCENT, anchor="w")
        self.err_label.pack(side="left")

        tk.Button(foot_inner, text="cancel", font=(MONO, 9),
                  bg=BG3, fg=MUTED, activebackground=BORDER,
                  activeforeground=FG, relief="flat", bd=0,
                  padx=10, pady=5, cursor="hand2",
                  command=self.destroy,
                  highlightthickness=1,
                  highlightbackground=BORDER).pack(side="right", padx=(6, 0))

        tk.Button(foot_inner, text="✓  select this folder", font=(MONO, 9, "bold"),
                  bg=BG3, fg=GREEN, activebackground=BORDER,
                  activeforeground=FG, relief="flat", bd=0,
                  padx=10, pady=5, cursor="hand2",
                  command=self._select_current,
                  highlightthickness=1,
                  highlightbackground=BORDER).pack(side="right")

        self._populate()

    def _bind_wheel(self):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        self.canvas.bind_all("<Button-4>", self._on_wheel)
        self.canvas.bind_all("<Button-5>", self._on_wheel)

    def _unbind_wheel(self):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_wheel(self, event):
        if getattr(event, "num", None) == 5 or getattr(event, "delta", 0) < 0:
            self.canvas.yview_scroll(1, "units")
        elif getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0:
            self.canvas.yview_scroll(-1, "units")

    def _go_up(self):
        parent = self.current.parent
        if parent != self.current:
            self.current = parent
            self._populate()

    def _go_to_typed(self, *_):
        typed = Path(self.path_var.get()).expanduser()
        if typed.exists() and typed.is_dir() and os.access(typed, os.R_OK):
            self.current = typed.resolve()
            self._populate()
        else:
            self.err_label.config(text="that path isn't a readable directory")

    def _enter(self, d: Path):
        self.current = d
        self._populate()

    def _select_current(self):
        self.on_select(_display_path(self.current))
        self.destroy()

    def _populate(self):
        self.err_label.config(text="")
        self.path_var.set(str(self.current))
        for w in self.list_frame.winfo_children():
            w.destroy()

        try:
            entries = sorted(
                (d for d in self.current.iterdir() if d.is_dir()),
                key=lambda p: p.name.lower()
            )
        except PermissionError:
            entries = []
            self.err_label.config(text="permission denied reading this folder")

        if not entries:
            tk.Label(self.list_frame, text="(no subfolders here)",
                     font=(MONO, 9), bg=BG2, fg=MUTED).pack(
                anchor="w", padx=14, pady=10)

        for d in entries:
            row = tk.Frame(self.list_frame, bg=BG2)
            row.pack(fill="x")

            def on_enter(e, r=row):
                r.configure(bg=BG4)
                for c in r.winfo_children():
                    c.configure(bg=BG4)

            def on_leave(e, r=row):
                r.configure(bg=BG2)
                for c in r.winfo_children():
                    c.configure(bg=BG2)

            lbl = tk.Label(row, text=f"📁  {d.name}", font=(MONO, 10),
                            bg=BG2, fg=FG, anchor="w", padx=14, pady=6)
            lbl.pack(fill="x")

            for widget in (row, lbl):
                widget.bind("<Enter>", on_enter)
                widget.bind("<Leave>", on_leave)
                widget.bind("<Button-1>", lambda e, dd=d: self._enter(dd))
                widget.bind("<Double-Button-1>", lambda e, dd=d: self._enter(dd))
                widget.configure(cursor="hand2")


def build(parent: tk.Frame, data: dict, result: dict) -> None:

    cur_path = _display_path(data.get("tools_base") or DEFAULT_TOOLS_ROOT)
    path_var = tk.StringVar(value=cur_path)
    edited   = {"flag": False}
    refresh_job = {"id": None}
    import_status_var = tk.StringVar(value="")

    def _sync(*_):
        result["tools_base"] = path_var.get().strip()

    path_var.trace_add("write", _sync)
    _sync()

    # ── import plumbing shared by the header button ─────────────────────────

    def _existing_sections() -> list:
        tools = result.get("tools") or data.get("tools", {})
        return list(tools.keys())

    def _merge_tool(section: str, name: str, entry: dict):
        tools = {s: dict(t) for s, t in (result.get("tools") or data.get("tools", {})).items()}
        section_tools = dict(tools.get(section, {}))
        final_name = name
        if final_name in section_tools:
            i = 2
            while f"{name} ({i})" in section_tools:
                i += 1
            final_name = f"{name} ({i})"
        section_tools[final_name] = entry
        tools[section] = section_tools
        result["tools"] = tools
        import_status_var.set(f"✓ imported '{entry['nickname']}' into {section} — see it on the Toolbelt tab")

    def _open_import_dialog_for(path: Path):
        base = _coerce_tools_base_path(path_var.get() or str(path.parent))
        kind = tool_import.detect_platform(path)
        sections = _existing_sections()
        default_section = kind if kind in sections else (sections[0] if sections else "Misc")
        tool_import.ImportDialog(
            parent, path=path, tools_base=base,
            sections=sections, default_section=default_section,
            detected_kind=kind,
            example_ip=data.get("listener_ip", "0.0.0.0"),
            example_port=data.get("port", 9001),
            on_save=_merge_tool,
        )

    def _browse_and_import():
        tool_import.FilePicker(
            parent, path_var.get(),
            on_select=lambda p: _open_import_dialog_for(Path(p)),
        )

    wrapper = tk.Frame(parent, bg=BG)
    wrapper.pack(fill="both", expand=True)

    # ── Section: tool root path ─────────────────────────────────────────────────────────────────────

    hdr = tk.Frame(wrapper, bg=BG)
    hdr.pack(fill="x", padx=24, pady=(20, 8))
    tk.Label(hdr, text="TOOLS DIRECTORY", font=(MONO, 8, "bold"),
             bg=BG, fg=ACCENT, anchor="w").pack(side="left")
    tk.Button(hdr, text="＋ import tool", font=(MONO, 8, "bold"),
              bg=BG3, fg=GREEN, activebackground=BORDER, activeforeground=FG,
              relief="flat", bd=0, padx=10, pady=4, cursor="hand2",
              highlightthickness=1, highlightbackground=BORDER,
              command=_browse_and_import).pack(side="right")
    tk.Frame(hdr, bg=BORDER, height=1).pack(
        side="left", fill="x", expand=True, padx=(10, 10))

    dir_card = tk.Frame(wrapper, bg=BG2)
    dir_card.pack(fill="x", padx=24)

    dir_inner = tk.Frame(dir_card, bg=BG2, padx=14, pady=12)
    dir_inner.pack(fill="x")

    tk.Label(dir_inner, text="root path", font=(MONO, 9),
             bg=BG2, fg=MUTED, width=10, anchor="w").pack(side="left")

    path_entry = tk.Entry(dir_inner, textvariable=path_var,
                          font=(MONO, 10),
                          bg=BG3, fg=FG, insertbackground=FG,
                          relief="flat", bd=0, width=28,
                          highlightthickness=1,
                          highlightbackground=BORDER,
                          highlightcolor=CYAN)
    path_entry.pack(side="left", ipady=5, padx=(0, 8))

    def _on_browser_select(chosen: str):
        edited["flag"] = True
        path_var.set(chosen)

    def _browse():
        DirBrowser(parent, path_var.get(), _on_browser_select)

    tk.Button(dir_inner, text="📂  browse",
              font=(MONO, 9),
              bg=BG3, fg=CYAN,
              activebackground=BORDER, activeforeground=FG,
              relief="flat", bd=0, padx=10, pady=5,
              cursor="hand2", command=_browse,
              highlightthickness=1,
              highlightbackground=BORDER).pack(side="left")

    # ── Path validity indicator ────────────────────────────────────────────
    # this is ugly if its not triggered it should say path is valid by default if it is not only when u update it 
    status_row = tk.Frame(dir_card, bg=BG2)
    status_row.pack(fill="x", padx=14, pady=(0, 12))

    status_dot = tk.Label(status_row, text="●", font=(MONO, 9),
                           bg=BG2, fg=MUTED)
    status_dot.pack(side="left", padx=(0, 6))

    status_label = tk.Label(status_row, text="", font=(MONO, 9),
                             bg=BG2, fg=MUTED, anchor="w")
    status_label.pack(side="left")

    def _update_status():
        ok, msg = _check_path(path_var.get())
        status_dot.config(fg=GREEN if ok else ACCENT)
        status_label.config(text=msg, fg=GREEN if ok else ACCENT)
        return ok

    # ── import feedback line  ──────────────────────────────────
    import_status_label = tk.Label(dir_card, textvariable=import_status_var,
                                    font=(MONO, 8), bg=BG2, fg=GREEN, anchor="w")
    import_status_label.pack(fill="x", padx=14, pady=(0, 10))


    # ── Section: files on disk ────────────────────────────────────────────────

    hdr2 = tk.Frame(wrapper, bg=BG)
    hdr2.pack(fill="x", padx=24, pady=(16, 8))
    tk.Label(hdr2, text="FILES ON DISK", font=(MONO, 8, "bold"),
             bg=BG, fg=ACCENT, anchor="w").pack(side="left")
    tk.Frame(hdr2, bg=BORDER, height=1).pack(
        side="left", fill="x", expand=True, padx=(10, 0))

    files_outer = tk.Frame(wrapper, bg=BG2)
    files_outer.pack(fill="both", expand=True, padx=24, pady=(0, 16))

    # Scrollable canvas
    canvas = tk.Canvas(files_outer, bg=BG2, bd=0,
                       highlightthickness=0, relief="flat")
    scrollbar = tk.Scrollbar(files_outer, orient="vertical",
                             command=canvas.yview,
                             bg=BG3, troughcolor=BG2,
                             activebackground=BORDER)
    scroll_frame = tk.Frame(canvas, bg=BG2)

    scroll_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    files_inner = tk.Frame(scroll_frame, bg=BG2, padx=14, pady=10)
    files_inner.pack(fill="x")

    # scroll wheel support ───────────────────────────────────────────────────
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

    def _refresh():
        for w in files_inner.winfo_children():
            w.destroy()

        ok = _update_status()

        if not ok:
            tk.Label(files_inner,
                     text="Root path is invalid — nothing to scan.",
                     font=(MONO, 9), bg=BG2, fg=MUTED).pack(anchor="w", pady=8)
            tk.Label(files_inner,
                     text="Fix the root path above.",
                     font=(MONO, 8), bg=BG2, fg=BORDER).pack(anchor="w")
            return

        base  = _coerce_tools_base_path(path_var.get())
        found = False

        try:
            subdirs = sorted(
                d for d in base.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            )
        except PermissionError:
            subdirs = []

        for d in subdirs:
            try:
                files = sorted(f for f in d.iterdir() if f.is_file())
            except PermissionError:
                continue
            if files:
                found = True
                # Sub-dir header
                sh = tk.Frame(files_inner, bg=BG2)
                sh.pack(fill="x", pady=(6, 2))
                tk.Label(sh, text=f"/{d.name}/",
                         font=(MONO, 9, "bold"),
                         bg=BG2, fg=CYAN).pack(side="left")
                tk.Label(sh, text=f"({len(files)})",
                         font=(MONO, 8),
                         bg=BG2, fg=MUTED).pack(side="left", padx=(6, 0))
                tk.Frame(sh, bg=BORDER, height=1).pack(
                    side="left", fill="x", expand=True, padx=(8, 0))

                for f in files:
                    size_kb = f.stat().st_size // 1024
                    size_str = f"{size_kb} KB" if size_kb else "< 1 KB"
                    row = tk.Frame(files_inner, bg=BG2)
                    row.pack(fill="x", pady=1)

                    tk.Label(row, text="▸", font=(MONO, 9),
                             bg=BG2, fg=BORDER).pack(side="left", padx=(6, 4))
                    tk.Label(row, text=f.name, font=(MONO, 9),
                             bg=BG2, fg=FG).pack(side="left")
                    tk.Label(row, text=size_str, font=(MONO, 8),
                             bg=BG2, fg=MUTED).pack(side="right", padx=(0, 12))

        if not found:
            tk.Label(files_inner,
                     text="No files found in any subdirectory under this path.",
                     font=(MONO, 9), bg=BG2, fg=MUTED).pack(anchor="w", pady=8)
            tk.Label(files_inner,
                     text="Check the root path above.",
                     font=(MONO, 8), bg=BG2, fg=BORDER).pack(anchor="w")

    def _debounced_refresh(*_):
        if refresh_job["id"] is not None:
            parent.after_cancel(refresh_job["id"])
        refresh_job["id"] = parent.after(DEBOUNCE_MS, _refresh)

    def _on_path_edit(*_):
        edited["flag"] = True
        _debounced_refresh()

    path_var.trace_add("write", _on_path_edit)

    _refresh()