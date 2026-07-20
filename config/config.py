"""
config.py — loads config.json and exposes typed config + mutable runtime state.
Import this everywhere instead of touching config.json directly.
"""

import json
from pathlib import Path

# ─── Locate config.json ──────────────────────────────────────────────────────

_CONFIG_PATH = Path(__file__).parent / "config.json"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TOOLS_ROOT = PROJECT_ROOT / "tools"

# ─── Default config ───────────────────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "preferred_http_iface": "tun0",
    "ip_override": None,
    "port": 9001,
    "auto_http": False,
    "auto_listen": False,
    "preferred_listener_iface": "tun0",
    "listener_ip": None,  # Will use preferred interface or default fallback
    "listener_port": 4444,
    "listener_proto": "rlwrap nc",
    "preferred_ifaces": ["tun0", "wg0", "tap0"],
    "tools_base": "~/redbelt/tools",
    "start_on_login": True,
    "notify_clipboard": True,
    "notify_listener": True,
    "notify_http": True,
    "open_terminal_on_listener_connection": False,
    "hotkey_launch": {
        "enabled": True,
        "leader": "<ctrl>+<alt>+<space>",
        "timeout_ms": 3000,
        "log_launches": True,
    },
    "shell_stabilisation": {
        "auto_stabilise": False,
        "auto_identify_terminal": True,
        "method": "auto",              # "auto" | "script" | "python"
        "python_preference": "python3_first",  # "python3_first" | "python_first"
        "export_term": "xterm",
        "sync_stty_size": True,
        "shell_path": "bash",
    },
}


def _display_path(path: str | Path | None) -> str:
    """Return a user-friendly path string, using ~ for the current home dir."""
    if path is None:
        return ""

    path_obj = Path(str(path)).expanduser()
    if not path_obj.is_absolute():
        return str(path_obj)

    home = Path.home().resolve()
    try:
        relative = path_obj.resolve().relative_to(home)
    except ValueError:
        return str(path_obj)

    if relative == Path("."):
        return "~"
    return f"~/{relative.as_posix()}"


def _coerce_tools_base_path(value: str | Path | None) -> Path:
    """Expand ~ and return an absolute Path for the tools root."""
    raw = str(value or "").strip()
    if not raw:
        return DEFAULT_TOOLS_ROOT
    return Path(raw).expanduser().resolve()


def _load() -> dict:
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"config.json not found at {_CONFIG_PATH}")
    with _CONFIG_PATH.open() as f:
        return json.load(f)


def _save(data: dict) -> None:
    with _CONFIG_PATH.open("w") as f:
        json.dump(data, f, indent=2)



# ─── Tools helpers ─────────────────────────────────────────────────────

def _default_hotkey(label: str) -> str:
    """First alnum character of *label*, lowercased. Empty string if none."""
    for ch in label or "":
        if ch.isalnum():
            return ch.lower()
    return ""


def _normalize_tools(raw: dict) -> dict:
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
                }
            else:
                norm[section][name] = {
                    "command": str(val),
                    "nickname": name,
                    "hotkey": _default_hotkey(name),
                }
    return norm


# ─── Hotkey-launch helpers ─────────────────────────────────────────────

_HOTKEY_LAUNCH_DEFAULTS = {
    "enabled": True,
    "leader": "<ctrl>+<alt>+space",
    "timeout_ms": 2500,
    "log_launches": True,
}


def _normalize_hotkey_launch(raw: dict) -> dict:
    merged = {**_HOTKEY_LAUNCH_DEFAULTS, **(raw or {})}
    merged["enabled"] = bool(merged.get("enabled", True))
    merged["log_launches"] = bool(merged.get("log_launches", True))
    merged["leader"] = str(merged.get("leader") or _HOTKEY_LAUNCH_DEFAULTS["leader"])
    try:
        merged["timeout_ms"] = max(250, int(merged.get("timeout_ms", 2500)))
    except (TypeError, ValueError):
        merged["timeout_ms"] = _HOTKEY_LAUNCH_DEFAULTS["timeout_ms"]
    return merged


def _normalize_section_hotkeys(raw: dict, sections) -> dict:
    """One key per section, always. Fills in a first-letter default for any
    section missing from *raw* (new sections, or a fresh config)."""
    raw = raw or {}
    return {s: (raw.get(s) or _default_hotkey(s)) for s in sections}


# ─── Shell-stabilisation helpers ───────────────────────────────────────

_SHELL_STABILISATION_DEFAULTS = {
    "auto_stabilise": False,
    "auto_identify_terminal": True,
    "method": "auto",
    "python_preference": "python3_first",
    "export_term": "xterm",
    "sync_stty_size": True,
    "shell_path": "bash",
}

_VALID_SHELL_METHODS = {"auto", "script", "python"}
_VALID_PYTHON_PREFERENCES = {"python3_first", "python_first"}


def _normalize_shell_stabilisation(raw: dict) -> dict:
    merged = {**_SHELL_STABILISATION_DEFAULTS, **(raw or {})}

    merged["auto_stabilise"] = bool(merged.get("auto_stabilise", False))
    merged["auto_identify_terminal"] = bool(merged.get("auto_identify_terminal", True))
    merged["sync_stty_size"] = bool(merged.get("sync_stty_size", True))

    method = str(merged.get("method") or "auto").strip().lower()
    merged["method"] = method if method in _VALID_SHELL_METHODS else "auto"

    pref = str(merged.get("python_preference") or "python3_first").strip().lower()
    merged["python_preference"] = pref if pref in _VALID_PYTHON_PREFERENCES else "python3_first"

    merged["export_term"] = str(merged.get("export_term") or "xterm").strip() or "xterm"
    merged["shell_path"] = str(merged.get("shell_path") or "bash").strip() or "bash"

    return merged


# ─── Load config ──────────────────────────────────────────────────────────────────────────────

_data = _load()

# ─── Static config (file ) ─────────────────────────────────────────────────────────────────────────────

TOOLS_BASE: Path = _coerce_tools_base_path(_data.get("tools_base", DEFAULT_TOOLS_ROOT))
PREFERRED_IFACES: list[str] = _data["preferred_ifaces"]
TOOLS: dict = _normalize_tools(_data.get("tools", {}))

HOTKEY_LAUNCH: dict = _normalize_hotkey_launch(_data.get("hotkey_launch", {}))
SECTION_HOTKEYS: dict = _normalize_section_hotkeys(_data.get("section_hotkeys", {}), TOOLS.keys())

SHELL_STABILISATION: dict = _normalize_shell_stabilisation(_data.get("shell_stabilisation", {}))

AUTO_HTTP: bool = _data.get("auto_http", True)
AUTO_LISTEN: bool = _data.get("auto_listen", False)

LISTENER_PORT: int = int(_data.get("listener_port", 4444))
LISTENER_PROTO: str = _data.get("listener_proto", "nc")

PREFERRED_HTTP_IFACE: str | None = _data.get("preferred_http_iface")
PREFERRED_LISTENER_IFACE: str | None = _data.get("preferred_listener_iface")

# General tab
START_ON_LOGIN: bool = _data.get("start_on_login", False)
NOTIFY_CLIPBOARD: bool = _data.get("notify_clipboard", True)
NOTIFY_LISTENER: bool = _data.get("notify_listener", True)
NOTIFY_HTTP: bool = _data.get("notify_http", True)

# Shell tab (this toggle lives on the Shell Stabilisation tab now, but keeps
# its original top-level config key/getter so nothing else has to change)
OPEN_TERMINAL_ON_LISTENER_CONNECTION: bool = _data.get("open_terminal_on_listener_connection", False)

# ─── Runtime state ────────────────────────────────────────────────────────────────

runtime: dict = {
    "port": int(_data["port"]),
    "ip_override": _data.get("ip_override"),
    "iface": "unknown",

    "listener_ip": _data.get("listener_ip"),
    "listener_port": int(_data.get("listener_port", 4444)),
    "listener_proto": _data.get("listener_proto", "nc"),
}

# ─── get configers  ────────────────────────────────────────────────────────────────────────

# HTTP

def get_auto_http() -> bool:
    return AUTO_HTTP

def get_port() -> int:
    return runtime["port"]

def get_ip_override() -> str | None:
    return runtime["ip_override"]


# LISTENER 

def get_listener_ip() -> str:
    return (
        runtime.get("listener_ip")
        or _data.get("listener_ip")
        or "127.0.0.1"
    )

def get_listener_port() -> int:
    return runtime.get("listener_port", LISTENER_PORT)

def get_listener_proto() -> str:
    return runtime.get("listener_proto") or LISTENER_PROTO


def get_auto_listen() -> bool:
    return AUTO_LISTEN


# PREFERENCES

def get_preferred_http_iface() -> str | None:
    return PREFERRED_HTTP_IFACE

def get_preferred_listener_iface() -> str | None:
    return PREFERRED_LISTENER_IFACE


# GENERAL

def get_start_on_login() -> bool:
    return START_ON_LOGIN

def get_notify_clipboard() -> bool:
    return NOTIFY_CLIPBOARD

def get_notify_listener() -> bool:
    return NOTIFY_LISTENER

def get_notify_http() -> bool:
    return NOTIFY_HTTP


def get_open_terminal_on_listener_connection() -> bool:
    return OPEN_TERMINAL_ON_LISTENER_CONNECTION


# SHELL STABILISATION

def get_shell_auto_stabilise() -> bool:
    return SHELL_STABILISATION["auto_stabilise"]

def get_shell_auto_identify_terminal() -> bool:
    return SHELL_STABILISATION["auto_identify_terminal"]

def get_shell_method() -> str:
    """'auto' | 'script' | 'python'"""
    return SHELL_STABILISATION["method"]

def get_shell_python_preference() -> str:
    """'python3_first' | 'python_first'"""
    return SHELL_STABILISATION["python_preference"]

def get_shell_export_term() -> str:
    return SHELL_STABILISATION["export_term"]

def get_shell_sync_stty_size() -> bool:
    return SHELL_STABILISATION["sync_stty_size"]

def get_shell_path() -> str:
    return SHELL_STABILISATION["shell_path"]

def get_shell_stabilisation() -> dict:
    """Full {'auto_stabilise', 'auto_identify_terminal', 'method',
    'python_preference', 'export_term', 'sync_stty_size', 'shell_path'} dict."""
    return SHELL_STABILISATION


# TOOLS

def get_tools_base() -> Path:
    return TOOLS_BASE

def get_tools() -> dict:
    """Full nested {section: {name: {'command', 'nickname', 'hotkey'}}} structure, in order."""
    return TOOLS

def get_tool(section: str, name: str) -> dict | None:
    """Return {'command', 'nickname', 'hotkey'} for a single tool, or None if it doesn't exist."""
    return TOOLS.get(section, {}).get(name)

def get_tool_command(section: str, name: str) -> str:
    """Raw clipboard command template for a tool, with {IP}/{PORT} placeholders
    left unresolved. This is what the toolbelt editor reads/writes."""
    tool = get_tool(section, name)
    return tool["command"] if tool else ""

def get_tool_nickname(section: str, name: str) -> str:
    """Tray/hotkey display nickname for a tool (falls back to its internal name)."""
    tool = get_tool(section, name)
    return tool["nickname"] if tool else name

def get_tool_hotkey(section: str, name: str) -> str:
    """Single-key tray/hotkey binding for a tool (falls back to first letter of its nickname)."""
    tool = get_tool(section, name)
    if tool is None:
        return ""
    return tool.get("hotkey") or _default_hotkey(tool.get("nickname", name))

def iter_tool_hotkeys():
    """Yield (section, name, hotkey) for every tool that has a non-empty hotkey.
    Handy for main.py/tray code registering global bindings."""
    for section, tools in TOOLS.items():
        for name, info in tools.items():
            hk = info.get("hotkey")
            if hk:
                yield section, name, hk


# HOTKEY LAUNCH

def get_hotkey_launch_enabled() -> bool:
    return HOTKEY_LAUNCH["enabled"]

def get_hotkey_launch_leader() -> str:
    return HOTKEY_LAUNCH["leader"]

def get_hotkey_launch_timeout_ms() -> int:
    return HOTKEY_LAUNCH["timeout_ms"]

def get_log_launches() -> bool:
    return HOTKEY_LAUNCH["log_launches"]

def get_section_hotkeys() -> dict:
    """{section: single_key} for every section currently in TOOLS."""
    return SECTION_HOTKEYS

def get_section_hotkey(section: str) -> str:
    return SECTION_HOTKEYS.get(section) or _default_hotkey(section)

def iter_section_hotkeys():
    """Yield section / hotkey for every section that has a key."""
    for section, hk in SECTION_HOTKEYS.items():
        if hk:
            yield section, hk

def resolve_command(template: str, ip: str | None = None, port: int | None = None) -> str:
    """Fill in {IP}/{PORT} placeholders in a command template."""
    resolved_ip = ip or get_ip_override() or get_listener_ip()
    resolved_port = port if port is not None else get_port()
    return template.replace("{IP}", str(resolved_ip)).replace("{PORT}", str(resolved_port))


# ─── Settings apply ─────────────────────────────────────────────────────────────────

def apply_settings(new: dict) -> bool:
    global TOOLS_BASE, AUTO_HTTP, AUTO_LISTEN
    global PREFERRED_HTTP_IFACE, PREFERRED_LISTENER_IFACE, LISTENER_PROTO
    global TOOLS
    global HOTKEY_LAUNCH, SECTION_HOTKEYS
    global SHELL_STABILISATION
    global START_ON_LOGIN, NOTIFY_CLIPBOARD, NOTIFY_LISTENER, NOTIFY_HTTP
    global OPEN_TERMINAL_ON_LISTENER_CONNECTION

    old_port = runtime["port"]
    new_port = int(new.get("port", old_port))

    # ── runtime sync ──────────────────────────────────────────────────────────
    runtime["port"] = new_port
    runtime["ip_override"] = new.get("ip_override", runtime.get("ip_override"))

    runtime["listener_ip"] = new.get("listener_ip", runtime.get("listener_ip"))
    runtime["listener_port"] = int(new.get("listener_port", runtime.get("listener_port")))
    runtime["listener_proto"] = new.get("listener_proto", runtime.get("listener_proto"))

    # ── module sync ─────────────────────────────────────────────────────
    TOOLS_BASE = _coerce_tools_base_path(new.get("tools_base", str(TOOLS_BASE)))

    AUTO_HTTP = bool(new.get("auto_http", AUTO_HTTP))
    AUTO_LISTEN = bool(new.get("auto_listen", AUTO_LISTEN))

    LISTENER_PROTO = runtime["listener_proto"]

    PREFERRED_HTTP_IFACE = new.get("preferred_http_iface", PREFERRED_HTTP_IFACE)
    PREFERRED_LISTENER_IFACE = new.get("preferred_listener_iface", PREFERRED_LISTENER_IFACE)

    START_ON_LOGIN = bool(new.get("start_on_login", START_ON_LOGIN))
    NOTIFY_CLIPBOARD = bool(new.get("notify_clipboard", NOTIFY_CLIPBOARD))
    NOTIFY_LISTENER = bool(new.get("notify_listener", NOTIFY_LISTENER))
    NOTIFY_HTTP = bool(new.get("notify_http", NOTIFY_HTTP))
    OPEN_TERMINAL_ON_LISTENER_CONNECTION = bool(
        new.get("open_terminal_on_listener_connection", OPEN_TERMINAL_ON_LISTENER_CONNECTION)
    )

    if "tools" in new:
        TOOLS = _normalize_tools(new["tools"])



    HOTKEY_LAUNCH = _normalize_hotkey_launch(new.get("hotkey_launch", HOTKEY_LAUNCH))
    SECTION_HOTKEYS = _normalize_section_hotkeys(
        new.get("section_hotkeys", SECTION_HOTKEYS), TOOLS.keys()
    )

    SHELL_STABILISATION = _normalize_shell_stabilisation(
        new.get("shell_stabilisation", SHELL_STABILISATION)
    )

    # ── persist to disk ───────────────────────────────────────────────────────
    _data.update({
        "port": runtime["port"],
        "ip_override": runtime["ip_override"],

        "listener_ip": runtime["listener_ip"],
        "listener_port": runtime["listener_port"],
        "listener_proto": runtime["listener_proto"],

        "tools_base": _display_path(TOOLS_BASE),
        "auto_http": AUTO_HTTP,
        "auto_listen": AUTO_LISTEN,

        "hotkey_launch": HOTKEY_LAUNCH,
        "section_hotkeys": SECTION_HOTKEYS,

        "preferred_http_iface": PREFERRED_HTTP_IFACE,
        "preferred_listener_iface": PREFERRED_LISTENER_IFACE,

        "start_on_login": START_ON_LOGIN,
        "notify_clipboard": NOTIFY_CLIPBOARD,
        "notify_listener": NOTIFY_LISTENER,
        "notify_http": NOTIFY_HTTP,
        "open_terminal_on_listener_connection": OPEN_TERMINAL_ON_LISTENER_CONNECTION,

        "shell_stabilisation": SHELL_STABILISATION,

        "tools": TOOLS,
    })

    _save(_data)

    return new_port != old_port


# ─── reset to defaults ──────────────────────────────────────────────────────────────

def reset_to_defaults() -> None:
    """Reset all settings (except tools) to DEFAULT_CONFIG values."""
    # Preserve existing tools and section_hotkeys structure
    reset_config = dict(DEFAULT_CONFIG)
    reset_config["tools"] = _data.get("tools", {})
    reset_config["section_hotkeys"] = _normalize_section_hotkeys({}, list(_data.get("tools", {}).keys()))

    apply_settings(reset_config)