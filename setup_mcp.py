#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SolidWorks MCP Server - Windows setup
-------------------------------------
Automates README steps 2 and 3 ("Install Dependencies" and "Configure Claude Desktop"):

  1. creates a virtual environment in .venv next to this file
  2. installs requirements.txt into it
  3. self-tests the server over MCP stdio (initialize + tools/list)
  4. registers it as "solidworks" in Claude Desktop's claude_desktop_config.json
     (other servers and settings are kept; a timestamped backup is written first)

Usage:  double-click setup_windows.bat      (or run:  py setup_mcp.py)
Then:   open SolidWorks, fully quit Claude Desktop (tray icon > Quit) and start it again.
"""

import json
import os
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
SERVER_SCRIPT = ROOT / "solidworks_mcp_server.py"
REQUIREMENTS = ROOT / "requirements.txt"
SERVER_NAME = "solidworks"
MIN_PYTHON = (3, 10)
LOG_FILE = ROOT / "setup_mcp.log"  # copy of everything this script prints (git-ignored by *.log)


def venv_python() -> Path:
    """Path of the interpreter inside the virtual environment."""
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def step(title: str) -> None:
    print(f"\n==> {title}", flush=True)


class _Tee:
    """Send print() output to the console and to setup_mcp.log."""

    def __init__(self, stream, path: Path):
        self._stream = stream
        self._file = open(path, "a", encoding="utf-8")

    def write(self, text: str) -> int:
        self._stream.write(text)
        self._file.write(text)
        self.flush()
        return len(text)

    def flush(self) -> None:
        self._stream.flush()
        self._file.flush()


def claude_desktop_running() -> bool:
    """True if the Claude desktop app (not the Claude Code CLI) is running."""
    if os.name != "nt":
        return False
    query = ("@(Get-Process -Name claude -ErrorAction SilentlyContinue | Where-Object { "
             "$_.Path -like '*\\WindowsApps\\*' -or $_.Path -like '*\\AnthropicClaude\\*' }).Count")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", query],
                             capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False
    return out.isdigit() and int(out) > 0


# ---------------------------------------------------------------------------
# 1-2. Virtual environment + requirements
# ---------------------------------------------------------------------------

def create_venv() -> Path:
    """Create .venv (or reuse a working one) and return its interpreter."""
    python = venv_python()
    if python.exists():
        probe = subprocess.run([str(python), "-c", "import sys"], capture_output=True)
        if probe.returncode == 0:
            print(f"    reusing {VENV_DIR}")
            return python
        print("    the existing .venv is broken - recreating it")
    subprocess.check_call([sys.executable, "-m", "venv", "--clear", str(VENV_DIR)])
    ignore = VENV_DIR / ".gitignore"  # keep the venv out of git (Python 3.13+ writes this itself)
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")
    print(f"    created {VENV_DIR}")
    return python


def install_requirements(python: Path) -> None:
    subprocess.check_call([str(python), "-m", "pip", "install",
                           "--disable-pip-version-check", "-r", str(REQUIREMENTS)])


# ---------------------------------------------------------------------------
# 3. Self-test over MCP stdio, the same way Claude Desktop launches the server
# ---------------------------------------------------------------------------

def _shutdown(proc: subprocess.Popen) -> None:
    try:
        proc.stdin.close()  # EOF on stdin makes an MCP stdio server exit cleanly
    except OSError:
        pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def self_test(python: Path, timeout: float = 120.0) -> list:
    """Start the server, run the MCP handshake and return the names of its tools."""
    proc = subprocess.Popen([str(python), str(SERVER_SCRIPT)],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout_lines = queue.Queue()
    stderr_chunks = []
    threading.Thread(target=lambda: [stdout_lines.put(line) for line in iter(proc.stdout.readline, b"")],
                     daemon=True).start()
    stderr_reader = threading.Thread(
        target=lambda: [stderr_chunks.append(line) for line in iter(proc.stderr.readline, b"")],
        daemon=True)
    stderr_reader.start()

    def send(message: dict) -> None:
        proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        proc.stdin.flush()

    def result_of(request_id: int) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = stdout_lines.get(timeout=0.5).strip()
            except queue.Empty:
                if proc.poll() is not None and stdout_lines.empty():
                    raise RuntimeError(f"the server exited early (exit code {proc.returncode})")
                continue
            if not line:
                continue
            message = json.loads(line)
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(f"the server returned an error: {message['error']}")
                return message["result"]
        raise TimeoutError(f"no answer from the server within {timeout:.0f} s")

    failure = None
    tools = []
    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                         "clientInfo": {"name": "setup_mcp-selftest", "version": "1.0"}}})
        result_of(1)
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools = [tool["name"] for tool in result_of(2)["tools"]]
    except Exception as exc:  # reported below together with the server's own error output
        failure = exc
    finally:
        _shutdown(proc)
    if failure is not None:
        stderr_reader.join(timeout=5)
        details = b"".join(stderr_chunks).decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"{failure}\n--- server error output ---\n{details[-4000:] or '(none)'}")
    return tools


# ---------------------------------------------------------------------------
# 4. Claude Desktop registration
# ---------------------------------------------------------------------------

def claude_config_paths() -> list:
    """claude_desktop_config.json locations Claude Desktop may read on this PC."""
    paths = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        paths.append(Path(appdata) / "Claude" / "claude_desktop_config.json")
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        # The Microsoft Store / MSIX build of Claude keeps its own copy of AppData\Roaming here
        for package in sorted((Path(local_appdata) / "Packages").glob("Claude_*")):
            config_dir = package / "LocalCache" / "Roaming" / "Claude"
            if config_dir.is_dir():
                paths.append(config_dir / "claude_desktop_config.json")
    return paths


def register(config_path: Path, entry: dict) -> str:
    """Add or replace mcpServers.solidworks in one config file; returns what happened.

    Raises ValueError (and leaves the file untouched) if the existing file isn't valid JSON.
    """
    data = {}
    if config_path.exists():
        text = config_path.read_text(encoding="utf-8-sig")
        if text.strip():
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"it is not valid JSON ({exc}), so it was left unchanged") from None
            if not isinstance(data, dict):
                raise ValueError("it is not a JSON object, so it was left unchanged")
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError('its "mcpServers" value is not a JSON object, so it was left unchanged')
    if servers.get(SERVER_NAME) == entry:
        return "already up to date"

    if config_path.exists():
        backup = config_path.with_name(f"{config_path.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
        backup.write_bytes(config_path.read_bytes())
        status = f"updated (backup: {backup.name})"
    else:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        status = "created"
    servers[SERVER_NAME] = entry
    temp = config_path.with_name(config_path.name + ".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, config_path)
    return status


# ---------------------------------------------------------------------------

def main() -> int:
    print(f"SolidWorks MCP setup - {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  project folder : {ROOT}")
    print(f"  base Python    : {sys.executable} ({sys.version.split()[0]})")
    if os.name != "nt":
        print("\nThis setup is for Windows - SolidWorks and pywin32 only run there.")
        return 1
    if sys.version_info < MIN_PYTHON:
        print(f"\nPython {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer is required.")
        return 1
    if claude_desktop_running():
        print("\nClaude Desktop is running. Quit it first so it reloads its settings afterwards:")
        print("right-click the Claude icon in the taskbar tray (bottom-right, maybe under ^) > Quit.")
        input("Press Enter once Claude is closed... ")
        print("  Claude Desktop " + ("is STILL running - continuing anyway."
                                     if claude_desktop_running() else "is closed."))

    step("1/4  Creating the virtual environment (.venv)")
    python = create_venv()

    step("2/4  Installing requirements.txt")
    install_requirements(python)

    step("3/4  Self-test: starting the server and asking for its tools")
    tools = self_test(python)
    print(f"    OK - the server answered with {len(tools)} tools")

    step('4/4  Registering "solidworks" in Claude Desktop')
    entry = {"command": str(python), "args": [str(SERVER_SCRIPT)]}
    updated = 0
    for path in claude_config_paths():
        try:
            print(f"    {register(path, entry)}: {path}")
            updated += 1
        except (OSError, ValueError) as exc:
            print(f"    could not update {path}: {exc}")
    if not updated:
        print("\nClaude Desktop could not be configured automatically. In Claude, open")
        print("Settings > Developer > Edit Config and add this to claude_desktop_config.json:")
        print(json.dumps({"mcpServers": {SERVER_NAME: entry}}, indent=2))
        return 1

    print("\nAll set. Next:")
    print("  1. Open SolidWorks.")
    print("  2. Start Claude Desktop (if it is open, quit it from its tray icon first).")
    print('  3. Ask Claude: "Connect to SolidWorks".')
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(line_buffering=True)  # keep our lines in order with pip's output
    except AttributeError:
        pass
    sys.stdout = _Tee(sys.stdout, LOG_FILE)
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        print(f"\nSetup failed: {' '.join(map(str, exc.cmd))} exited with code {exc.returncode}.")
        sys.exit(1)
    except Exception as exc:
        print(f"\nSetup failed: {exc}")
        sys.exit(1)
