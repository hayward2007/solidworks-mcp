#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SolidWorks MCP Server - Windows setup
-------------------------------------
Installs the server for Claude Desktop and Claude Code:

  1. creates a virtual environment in .venv next to this file
  2. installs requirements.txt into it
  3. self-tests the server over MCP stdio (initialize + tools/list)
  4. registers it as "solidworks" in Claude Desktop's claude_desktop_config.json
     (other servers and settings are kept; a timestamped backup is written first)
  5. registers it in Claude Code (claude mcp add --scope user) when the claude CLI is found,
     copies the solidworks-design skill to ~/.claude/skills and writes
     dist/solidworks-design.zip for uploading the skill to Claude Desktop / claude.ai

Usage:  install.ps1 or setup_windows.bat    (or run:  py setup_mcp.py [options])
        py setup_mcp.py --help               lists the options (--yes, --uninstall, ...)
Then:   open SolidWorks, fully quit Claude Desktop (tray icon > Quit) and start it again.
"""

import argparse
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
SERVER_SCRIPT = ROOT / "solidworks_mcp_server.py"
REQUIREMENTS = ROOT / "requirements.txt"
SERVER_NAME = "solidworks"
MIN_PYTHON = (3, 10)
LOG_FILE = ROOT / "setup_mcp.log"  # copy of everything this script prints (git-ignored by *.log)
SKILL_NAME = "solidworks-design"
SKILL_DIR = ROOT / "skills" / SKILL_NAME  # working rules for Claude (Cowork does not pass server instructions on)
DIST_DIR = ROOT / "dist"  # git-ignored


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
    print("    (the first run downloads about 60 MB and can take a few minutes)")
    subprocess.check_call([str(python), "-m", "pip", "install", "--quiet",
                           "--disable-pip-version-check", "-r", str(REQUIREMENTS)])
    print("    done")


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
        status = f"updated (backup: {_backup(config_path)})"
    else:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        status = "created"
    servers[SERVER_NAME] = entry
    _write_json(config_path, data)
    return status


def unregister(config_path: Path) -> str:
    """Remove mcpServers.solidworks from one config file; returns what happened."""
    if not config_path.exists():
        return "no config file"
    text = config_path.read_text(encoding="utf-8-sig")
    data = json.loads(text) if text.strip() else {}
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(servers, dict) or SERVER_NAME not in servers:
        return "not registered"
    backup = _backup(config_path)
    del servers[SERVER_NAME]
    _write_json(config_path, data)
    return f"removed (backup: {backup})"


def _backup(config_path: Path) -> str:
    backup = config_path.with_name(f"{config_path.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
    backup.write_bytes(config_path.read_bytes())
    return backup.name


def _write_json(config_path: Path, data: dict) -> None:
    temp = config_path.with_name(config_path.name + ".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, config_path)


# ---------------------------------------------------------------------------
# 5. Claude Code and the solidworks-design skill
# ---------------------------------------------------------------------------

def find_claude_cli():
    """Path of the Claude Code CLI, or None if it is not installed."""
    found = shutil.which("claude")
    if found:
        return found
    candidates = [Path.home() / ".local" / "bin" / ("claude.exe" if os.name == "nt" else "claude")]
    if os.environ.get("APPDATA"):
        candidates.append(Path(os.environ["APPDATA"]) / "npm" / "claude.cmd")
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def _claude(cli: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([cli, *args], capture_output=True, text=True, errors="replace",
                          stdin=subprocess.DEVNULL, timeout=120)


def register_claude_code(cli: str, entry: dict) -> str:
    """Add (or replace) the user-scope "solidworks" server in Claude Code."""
    _claude(cli, "mcp", "remove", SERVER_NAME, "--scope", "user")  # fails harmlessly if absent
    done = _claude(cli, "mcp", "add", "--scope", "user", SERVER_NAME, "--",
                   entry["command"], *entry["args"])
    if done.returncode != 0:
        raise RuntimeError((done.stderr or done.stdout).strip()[-800:] or f"exit code {done.returncode}")
    return "registered for all projects (user scope)"


def unregister_claude_code(cli: str) -> str:
    done = _claude(cli, "mcp", "remove", SERVER_NAME, "--scope", "user")
    return "removed" if done.returncode == 0 else "not registered"


def _skill_files():
    """(relative path, bytes) of the skill; Markdown with LF endings so the front matter parses."""
    for path in sorted(SKILL_DIR.rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            if path.suffix.lower() == ".md":
                data = data.replace(b"\r\n", b"\n")
            yield path.relative_to(SKILL_DIR), data


def install_skill(skills_dir: Path) -> Path:
    """Copy the skill into a Claude Code skills folder (overwrites older copies of its files)."""
    target = skills_dir / SKILL_NAME
    for relative, data in _skill_files():
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    return target


def remove_skill(skills_dir: Path) -> str:
    target = skills_dir / SKILL_NAME
    if not (target / "SKILL.md").is_file():
        return "not installed"
    shutil.rmtree(target)
    return "removed"


def build_skill_zip() -> Path:
    """dist/solidworks-design.zip with the skill folder at its root (Claude's skill upload format)."""
    DIST_DIR.mkdir(exist_ok=True)
    archive = DIST_DIR / f"{SKILL_NAME}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for relative, data in _skill_files():
            bundle.writestr(f"{SKILL_NAME}/{relative.as_posix()}", data)
    return archive


# ---------------------------------------------------------------------------

def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="setup_mcp.py",
        description="Install (or remove) the SolidWorks MCP server for Claude Desktop and Claude Code.")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="never wait for input (for scripts and AI agents)")
    parser.add_argument("--no-desktop", action="store_true", help="leave Claude Desktop alone")
    parser.add_argument("--desktop-config", action="append", type=Path, metavar="PATH",
                        help="update this claude_desktop_config.json instead of the detected ones (repeatable)")
    parser.add_argument("--no-claude-code", action="store_true", help="leave Claude Code alone")
    parser.add_argument("--no-skill", action="store_true", help="skip the solidworks-design skill")
    parser.add_argument("--skills-dir", type=Path, metavar="PATH",
                        help="Claude Code skills folder (default: ~/.claude/skills)")
    parser.add_argument("--uninstall", action="store_true",
                        help="remove the registrations and the skill (keeps this folder)")
    return parser.parse_args(argv)


def uninstall(args, desktop_paths: list, skills_dir: Path, cli) -> int:
    step('Removing "solidworks" from Claude Desktop')
    if args.no_desktop:
        print("    skipped (--no-desktop)")
    for path in [] if args.no_desktop else desktop_paths:
        try:
            print(f"    {unregister(path)}: {path}")
        except (OSError, ValueError) as exc:
            print(f"    could not update {path}: {exc}")
    step("Removing it from Claude Code")
    print(f"    {unregister_claude_code(cli)}" if cli else "    Claude Code not found or skipped")
    step("Removing the solidworks-design skill")
    print("    skipped (--no-skill)" if args.no_skill
          else f"    {remove_skill(skills_dir)}: {skills_dir / SKILL_NAME}")
    print(f"\nDone. You can delete {ROOT} now (server, .venv and knowledge notes).")
    print("Restart Claude Desktop so it stops starting the server. A skill saved in your Claude")
    print("account (Cowork, claude.ai) stays until you delete it there.")
    return 0


def main(argv=None) -> int:
    args = parse_args(argv)
    interactive = not args.yes and sys.stdin is not None and sys.stdin.isatty()
    print(f"SolidWorks MCP {'removal' if args.uninstall else 'setup'} - {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  project folder : {ROOT}")
    print(f"  base Python    : {sys.executable} ({sys.version.split()[0]})")
    if os.name != "nt":
        print("\nThis setup is for Windows - SolidWorks and pywin32 only run there.")
        return 1
    if sys.version_info < MIN_PYTHON:
        print(f"\nPython {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer is required.")
        return 1
    desktop_paths = args.desktop_config or claude_config_paths()
    skills_dir = args.skills_dir or Path.home() / ".claude" / "skills"
    cli = None if args.no_claude_code else find_claude_cli()
    if args.uninstall:
        return uninstall(args, desktop_paths, skills_dir, cli)

    if not args.no_desktop and claude_desktop_running():
        if interactive:
            print("\nClaude Desktop is running. Quit it first so it reloads its settings afterwards:")
            print("right-click the Claude icon in the taskbar tray (bottom-right, maybe under ^) > Quit.")
            input("Press Enter once Claude is closed... ")
            print("  Claude Desktop " + ("is STILL running - continuing anyway."
                                         if claude_desktop_running() else "is closed."))
        else:
            print("\nClaude Desktop is running: after setup, quit it from its tray icon and start it again.")

    step("1/5  Creating the virtual environment (.venv)")
    python = create_venv()

    step("2/5  Installing requirements.txt")
    install_requirements(python)

    step("3/5  Self-test: starting the server and asking for its tools")
    tools = self_test(python)
    print(f"    OK - the server answered with {len(tools)} tools")

    entry = {"command": str(python), "args": [str(SERVER_SCRIPT)]}
    registered = 0
    step('4/5  Registering "solidworks" in Claude Desktop')
    if args.no_desktop:
        print("    skipped (--no-desktop)")
    else:
        for path in desktop_paths:
            try:
                print(f"    {register(path, entry)}: {path}")
                registered += 1
            except (OSError, ValueError) as exc:
                print(f"    could not update {path}: {exc}")
        if not registered:
            print("    Claude Desktop could not be configured automatically. In Claude, open")
            print("    Settings > Developer > Edit Config and add this to claude_desktop_config.json:")
            print(json.dumps({"mcpServers": {SERVER_NAME: entry}}, indent=2))

    step("5/5  Claude Code and the solidworks-design skill")
    if cli:
        try:
            print(f"    Claude Code: {register_claude_code(cli, entry)}")
            registered += 1
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            print(f"    Claude Code: could not register it ({exc})")
    elif args.no_claude_code:
        print("    Claude Code: skipped (--no-claude-code)")
    else:
        print("    Claude Code: not found, skipped. To add it later:")
        print(f'      claude mcp add --scope user {SERVER_NAME} -- "{python}" "{SERVER_SCRIPT}"')
    if args.no_skill:
        print("    skill: skipped (--no-skill)")
    elif not (SKILL_DIR / "SKILL.md").is_file():
        print(f"    skill: {SKILL_DIR} is missing, skipped")
    else:
        if args.skills_dir or cli or (Path.home() / ".claude").is_dir():
            print(f"    skill for Claude Code: {install_skill(skills_dir)}")
        print(f"    skill for Claude Desktop / claude.ai: {build_skill_zip()}")
        print("      (upload it under Settings > Capabilities > Skills, or ask Claude in Cowork to save the")
        print(f"      skill from {SKILL_DIR / 'SKILL.md'})")

    if not registered:
        print("\nThe server works but nothing was registered - see the messages above.")
        return 1
    print("\nAll set. Next:")
    print("  1. Open SolidWorks.")
    print("  2. Fully quit Claude Desktop (tray icon > Quit) and start it again;")
    print("     in Claude Code, start a new session.")
    print('  3. Ask Claude: "Connect to SolidWorks".')
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(line_buffering=True)  # keep our lines in order with pip's output
    except AttributeError:
        pass
    sys.stdout = _Tee(sys.stdout, LOG_FILE)
    try:
        sys.exit(main(sys.argv[1:]))
    except subprocess.CalledProcessError as exc:
        print(f"\nSetup failed: {' '.join(map(str, exc.cmd))} exited with code {exc.returncode}.")
        sys.exit(1)
    except Exception as exc:
        print(f"\nSetup failed: {exc}")
        sys.exit(1)
