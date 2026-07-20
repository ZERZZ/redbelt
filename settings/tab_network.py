"""
settings/tab_network.py — Network tab
"""

import tkinter as tk

from utils.network import list_ifaces  # moved from local implementation
from utils import status as status_probe
from services import httpserver
from services import listener

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


# ── Toggle slider widget ────────────────────────────────────────────────────── (CENTRALISE IN COMPS.PY)

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


# ── Status button (red/green dot, click to start/stop) ─────────────────────── (could also be centralised but less vital as only used here)

class StatusButton(tk.Frame):
    """
    Small clickable indicator: green dot + 'online' when the configured
    host:port answers, red dot + 'offline' when it doesn't. Click toggls the service
    on / off.
    """

    def __init__(self, parent, probe_fn, toggle_fn, **kw):
        super().__init__(parent, bg=parent["bg"], **kw)
        self._probe_fn = probe_fn
        self._toggle_fn = toggle_fn
        self._destroyed = False

        self.dot = tk.Canvas(self, width=12, height=12, bg=parent["bg"],
                              bd=0, highlightthickness=0, cursor="hand2")
        self.dot.pack(side="left", padx=(0, 6))

        self.label = tk.Label(self, font=(MONO, 8, "bold"),
                               bg=parent["bg"], cursor="hand2", width=8,
                               anchor="w")
        self.label.pack(side="left")

        for w in (self.dot, self.label):
            w.bind("<Button-1>", self._on_click)

        self.bind("<Destroy>", self._on_destroy)
        self.refresh()
        self._schedule_tick()

    def _on_destroy(self, _e=None):
        self._destroyed = True

    def _on_click(self, _e=None):
        self._toggle_fn()
        # give the process a moment to bind or die b4 reattempting 
        self.after(400, self.refresh)

    def refresh(self):
        if self._destroyed:
            return False
        up = self._probe_fn()
        color = GREEN if up else ACCENT
        self.dot.delete("all")
        self.dot.create_oval(1, 1, 11, 11, fill=color, outline="")
        self.label.config(text="online" if up else "offline", fg=color)
        return up

    def _schedule_tick(self):
        if self._destroyed:
            return
        self.refresh()
        self.after(3000, self._schedule_tick)


# ── drop down widget  ────────────────────────────────────────────

class Dropdown(tk.Frame):
    """
    A Menubutton-style dropdown that:
      - shows a ▾ / ▴ arrow that flips when open
      - closes again if you click the button while it's already open
        (plain tk.OptionMenu re-opens instead of closing on a second click)
    """

    def __init__(self, parent, values, var: tk.StringVar,
                 width=14, on_change=None, **kw):
        super().__init__(parent, bg=parent["bg"], **kw)
        self._values = list(values)
        self._var = var
        self._on_change = on_change
        self._popup = None
        self._width = width

        self.btn = tk.Frame(self, bg=BG3, highlightthickness=1,
                             highlightbackground=BORDER, cursor="hand2")
        self.btn.pack(fill="x")

        self.text_lbl = tk.Label(self.btn, textvariable=self._var,
                                  font=(MONO, 9), bg=BG3, fg=FG,
                                  anchor="w", width=width, padx=8, pady=5)
        self.text_lbl.pack(side="left", fill="x", expand=True)

        self.arrow_lbl = tk.Label(self.btn, text="▾", font=(MONO, 8),
                                   bg=BG3, fg=MUTED, padx=8)
        self.arrow_lbl.pack(side="right")

        for w in (self.btn, self.text_lbl, self.arrow_lbl):
            w.bind("<Button-1>", self._on_click)

        # Close if focus is lost elsewhere in the app
        self.bind("<Destroy>", lambda _e: self._close())

    def _on_click(self, _=None):
        if self._popup is not None:
            self._close()
        else:
            self._open()

    def _open(self):
        if not self._values:
            return
        self.arrow_lbl.config(text="▴", fg=CYAN)

        self._popup = tk.Toplevel(self)
        self._popup.overrideredirect(True)
        self._popup.configure(bg=BORDER)

        x = self.btn.winfo_rootx()
        y = self.btn.winfo_rooty() + self.btn.winfo_height()
        self._popup.geometry(f"+{x}+{y}")

        inner = tk.Frame(self._popup, bg=BG3)
        inner.pack(padx=1, pady=1, fill="both", expand=True)

        for val in self._values:
            row = tk.Label(inner, text=val, font=(MONO, 9),
                           bg=BG3, fg=FG, anchor="w",
                           padx=8, pady=6, width=self._width,
                           cursor="hand2")
            row.pack(fill="x")

            def _enter(_e, r=row):
                r.config(bg=ACCENT, fg=FG)

            def _leave(_e, r=row):
                r.config(bg=BG3, fg=FG)

            def _select(_e, v=val):
                self._choose(v)

            row.bind("<Enter>", _enter)
            row.bind("<Leave>", _leave)
            row.bind("<Button-1>", _select)

        # Clicking anywhere outside the popup closes it
        self._popup.bind("<FocusOut>", lambda _e: self._close())
        self._popup.focus_set()
        self._popup_outside_id = self.winfo_toplevel().bind(
            "<Button-1>", self._maybe_close_outside, add="+")

    def _maybe_close_outside(self, event):
        if self._popup is None:
            return
        widget = event.widget
        # If the click landed on the button itself, _on_click already handles it
        if widget in (self.btn, self.text_lbl, self.arrow_lbl):
            return
        try:
            if str(widget).startswith(str(self._popup)):
                return
        except Exception:
            pass
        self._close()

    def _choose(self, val):
        self._var.set(val)
        self._close()
        if self._on_change:
            self._on_change(val)

    def _close(self):
        if self._popup is not None:
            try:
                self.winfo_toplevel().unbind("<Button-1>", self._popup_outside_id)
            except Exception:
                pass
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None
            self.arrow_lbl.config(text="▾", fg=MUTED)

    def set_values(self, values):
        self._values = list(values)


# ── Shared helpers ────────────────────────────────────────────────────────────

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


def _entry(parent, var, width=28):
    return tk.Entry(parent, textvariable=var, font=(MONO, 10),
                    bg=BG3, fg=FG, insertbackground=FG,
                    relief="flat", bd=0, width=width,
                    highlightthickness=1,
                    highlightbackground=BORDER,
                    highlightcolor=CYAN)


def _hint(card, text):
    tk.Label(card, text=f"  {text}", font=(MONO, 8),
             bg=BG2, fg=BORDER, anchor="w").pack(
                 fill="x", padx=14, pady=(0, 8))


def _toggle_row(card, label_text, var, pady=(6, 6), note_text=None,
                note_fg=MUTED):
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

    if note_text:
        tk.Label(card, text=note_text, font=(MONO, 7), bg=BG2,
                 fg=note_fg, anchor="w", justify="left",
                 wraplength=320).pack(fill="x", padx=14, pady=(0, 8))


def _iface_row(card, label_text, iface_var, iface_names, ip_preview_var,
               on_change):
    """One 'interface ▾   1.2.3.4' row, used by both HTTP and Listener cards."""
    row = tk.Frame(card, bg=BG2)
    row.pack(fill="x", padx=14, pady=(10, 4))
    _label(row, label_text, width=16).pack(side="left")

    dd = Dropdown(row, iface_names, iface_var, width=12, on_change=on_change)
    dd.pack(side="left", padx=(0, 16))

    tk.Label(row, textvariable=ip_preview_var,
             font=(MONO, 10, "bold"),
             bg=BG2, fg=CYAN).pack(side="left")
    return row, dd


# ── Build ─────────────────────────────────────────────────────────────────────

def build(parent: tk.Frame, data: dict, result: dict) -> None:

    auto_ip    = data.get("auto_ip", "127.0.0.1")
    auto_iface = data.get("auto_iface", "lo")
    cur_port   = str(data.get("port", 9001))
    cur_ovr    = data.get("ip_override") or ""

    ifaces = list_ifaces()
    iface_names = [i[0] for i in ifaces]
    iface_map = dict(ifaces)

    def _resolve_iface(preferred):
        if preferred and preferred in iface_map:
            return preferred
        if auto_iface in iface_map:
            return auto_iface
        return iface_names[0] if iface_names else "lo"

    default_http_iface     = _resolve_iface(data.get("preferred_http_iface"))
    default_listener_iface = _resolve_iface(data.get("preferred_listener_iface"))
    default_proto           = data.get("listener_proto", "nc")


    # ── Scrollable wrapper ──────────────────────────────────────────
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

    # ── HTTP SERVER ───────────────────────────────────────────────────────────
    _section(wrapper, "HTTP SERVER")
    http_card = _card(wrapper)

    http_iface_var = tk.StringVar(value=default_http_iface)
    http_ip_preview_var = tk.StringVar(
        value=iface_map.get(default_http_iface, auto_ip))

    def _on_http_iface_change(selected):
        ip = iface_map.get(selected, "?")
        http_ip_preview_var.set(ip)
        _sync()

    http_row, _http_dd = _iface_row(http_card, "interface", http_iface_var, iface_names,
               http_ip_preview_var, _on_http_iface_change)

    def _toggle_http():
        if status_probe.is_http_up():
            print("HTTP showing as up, stopping..")
            httpserver.stop()
        else:
            print("HTTP showing as down, starting...")
            httpserver.start()

    StatusButton(http_row, status_probe.is_http_up, _toggle_http).pack(
        side="right")

    tk.Frame(http_card, bg=BORDER, height=1).pack(fill="x", padx=14, pady=(8, 0))

    # IP override
    ovr_row = tk.Frame(http_card, bg=BG2)
    ovr_row.pack(fill="x", padx=14, pady=4)

    _label(ovr_row, "ip override", width=16).pack(side="left", pady=8)
    ip_ovr_var = tk.StringVar(value=cur_ovr)
    e_ovr = _entry(ovr_row, ip_ovr_var, width=30)
    e_ovr.pack(side="left", ipady=5, pady=8)

    _PH = "leave blank — use interface IP"

    if not cur_ovr:
        e_ovr.insert(0, _PH)
        e_ovr.config(fg=MUTED)

    def _ovr_in(ev):
        if e_ovr.get() == _PH:
            e_ovr.delete(0, "end")
            e_ovr.config(fg=FG)

    def _ovr_out(ev):
        if not e_ovr.get():
            e_ovr.insert(0, _PH)
            e_ovr.config(fg=MUTED)

    e_ovr.bind("<FocusIn>", _ovr_in)
    e_ovr.bind("<FocusOut>", _ovr_out)

    # Port
    port_row = tk.Frame(http_card, bg=BG2)
    port_row.pack(fill="x", padx=14, pady=4)

    _label(port_row, "server port", width=16).pack(side="left", pady=8)
    port_var = tk.StringVar(value=cur_port)
    _entry(port_row, port_var, width=8).pack(side="left", ipady=5, pady=8)

    _hint(http_card, "Changing port restarts the HTTP server automatically.")

    auto_http_var = tk.BooleanVar(value=data.get("auto_http", True))
    _toggle_row(http_card, "start server on launch", auto_http_var,
                note_text="Creates a persistent network listener and should only be used in trusted environments.",
                note_fg=ACCENT)

    # ── LISTENER  SECTION ────────────────────────────────────────────────────────
    _section(wrapper, "LISTENER")
    lst_card = _card(wrapper)

    lst_iface_var = tk.StringVar(value=default_listener_iface)
    lst_ip_preview_var = tk.StringVar(
        value=iface_map.get(default_listener_iface, auto_ip))
    lst_ip_var = tk.StringVar(value=iface_map.get(default_listener_iface, auto_ip))

    def _on_listener_iface_change(selected):
        ip = iface_map.get(selected, "?")
        lst_ip_preview_var.set(ip)
        if not lst_ovr_var.get().strip():
            lst_ip_var.set(ip)
        _sync()

    lst_row, _lst_dd = _iface_row(lst_card, "interface", lst_iface_var, iface_names,
               lst_ip_preview_var, _on_listener_iface_change)

    def _toggle_listener():
        if status_probe.is_listener_up():
            print("Listener showing as up, stopped.")
            listener.stop()
        else:
            print("Listener showing as down, starting.")
            listener.start()

    StatusButton(lst_row, status_probe.is_listener_up, _toggle_listener).pack(
        side="right")

    tk.Frame(lst_card, bg=BORDER, height=1).pack(fill="x", padx=14, pady=(8, 0))

    # Listen IP override ─────────────────────
    lst_ovr_row = tk.Frame(lst_card, bg=BG2)
    lst_ovr_row.pack(fill="x", padx=14, pady=4)

    _label(lst_ovr_row, "ip override", width=16).pack(side="left", pady=8)
    lst_ovr_var = tk.StringVar(
        value="" if iface_map.get(default_listener_iface) == data.get("listener_ip")
        else data.get("listener_ip", ""))
    e_lst_ovr = _entry(lst_ovr_row, lst_ovr_var, width=30)
    e_lst_ovr.pack(side="left", ipady=5, pady=8)

    if not lst_ovr_var.get():
        e_lst_ovr.insert(0, _PH)
        e_lst_ovr.config(fg=MUTED)

    def _lst_ovr_in(ev):
        if e_lst_ovr.get() == _PH:
            e_lst_ovr.delete(0, "end")
            e_lst_ovr.config(fg=FG)

    def _lst_ovr_out(ev):
        if not e_lst_ovr.get():
            e_lst_ovr.insert(0, _PH)
            e_lst_ovr.config(fg=MUTED)
        lst_ip_var.set(e_lst_ovr.get() if e_lst_ovr.get() != _PH
                       else lst_ip_preview_var.get())

    e_lst_ovr.bind("<FocusIn>", _lst_ovr_in)
    e_lst_ovr.bind("<FocusOut>", _lst_ovr_out)

    # Listen port
    lst_port_row = tk.Frame(lst_card, bg=BG2)
    lst_port_row.pack(fill="x", padx=14, pady=4)
    _label(lst_port_row, "listen port", width=16).pack(side="left", pady=8)
    lst_port_var = tk.StringVar(value=str(data.get("listener_port", 4444)))
    _entry(lst_port_row, lst_port_var, width=8).pack(side="left", ipady=5, pady=8)

    _hint(lst_card, "This IP will also be used in generated commands like shells and payloads.")


    proto_row = tk.Frame(lst_card, bg=BG2)
    proto_row.pack(fill="x", padx=14, pady=4)
    _label(proto_row, "proto", width=16).pack(side="left", pady=8)

    lst_proto_var = tk.StringVar(value=default_proto)
    Dropdown(proto_row, ["nc", "rlwrap nc", "ncat", "pwncat-cs"], lst_proto_var,
             width=12, on_change=lambda _v: _sync()).pack(side="left", pady=8)

    auto_listen_var = tk.BooleanVar(value=data.get("auto_listen", False))
    _toggle_row(lst_card, "start listener on launch", auto_listen_var,
                note_text="Creates a persistent network listener and should only be used in trusted environments.",
                note_fg=ACCENT)

    # ── SYNC ─────────────────────────────────────────────────────────────────
    def _sync(*_):
        raw_ovr = ip_ovr_var.get().strip()
        raw_lst_ovr = lst_ovr_var.get().strip()

        result["iface_override"] = http_iface_var.get()
        result["ip_override"] = None if raw_ovr in ("", _PH) else raw_ovr
        result["port"] = port_var.get().strip()
        result["preferred_http_iface"] = http_iface_var.get()

        result["listener_ip"] = (raw_lst_ovr if raw_lst_ovr not in ("", _PH)
                                  else lst_ip_preview_var.get())
        result["listener_port"] = lst_port_var.get().strip()
        result["listener_proto"] = lst_proto_var.get()
        result["preferred_listener_iface"] = lst_iface_var.get()

        result["auto_http"] = auto_http_var.get()
        result["auto_listen"] = auto_listen_var.get()


    for v in (ip_ovr_var, port_var, lst_ovr_var, lst_port_var,
              lst_proto_var, auto_http_var, auto_listen_var,
              http_iface_var, lst_iface_var):
        v.trace_add("write", _sync)

    _sync()