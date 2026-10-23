"""Agent integrations use installed CLI commands with argument arrays, never a shell."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from .common import default_home


def connection(client, home=None, cad=False):
    if cad and os.name != "nt":
        raise ValueError("native SolidWorks server must run on its Windows host; omit --cad for portable design tools")
    home = str(Path(home).expanduser().resolve() if home else default_home())
    name = "solidworks" if cad else "solidworks-design"
    if cad:
        command = [sys.executable, "-m", "solidworks_mcp.server"]
    else:
        command = [sys.executable, "-m", "solidworks_mcp.design.mcp", "--home", home]
    entry = {"command": command[0], "args": command[1:]}
    if client == "codex":
        cli = ["codex", "mcp", "add", name, "--", *command]
        config = f'[mcp_servers.{name}]\ncommand = {json.dumps(command[0])}\nargs = {json.dumps(command[1:])}\n'
    elif client == "claude-code":
        cli = ["claude", "mcp", "add", "--scope", "local", name, "--", *command]
        config = {"mcpServers": {name: entry}}
    elif client == "claude-desktop":
        cli = None
        config = {"mcpServers": {name: entry}}
    else:
        raise ValueError("client must be codex, claude-code or claude-desktop")
    return {"client": client, "name": name, "command": command, "registration_argv": cli, "config": config,
            "home": home, "cad": cad}


def apply_connection(config):
    argv = config["registration_argv"]
    if not argv:
        raise ValueError("Claude Desktop: merge the generated mcpServers entry into its existing configuration, preserving other entries")
    executable = shutil.which(argv[0])
    if not executable:
        raise ValueError(f"{argv[0]} is not installed or not on PATH")
    # Refuse to replace a registration pointing at another executable/installation.
    check = subprocess.run([executable, "mcp", "get", config["name"]], text=True, capture_output=True, timeout=30)
    if check.returncode == 0:
        raise ValueError(f"{config['name']} is already registered; inspect it and remove/update explicitly to preserve existing configuration")
    missing = (check.stdout + check.stderr).lower()
    if not ("no mcp server named" in missing or "no mcp server found with name" in missing):
        raise ValueError("could not establish that the registration is absent; inspect the client's MCP configuration before applying")
    result = subprocess.run([executable, *argv[1:]], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError(f"registration failed: {result.stderr.strip()}")
    return {"registered": True, "client": config["client"], "name": config["name"], "output": result.stdout.strip(),
            "restart_required": "Start a new agent session to load tools. Validate with sw-design doctor --mcp."}


def start_agent(client, project, home=None):
    if client not in {"codex", "claude-code"}:
        raise ValueError("start --agent must be codex or claude-code")
    from .store import Store
    with Store(home) as store:
        store.project(project)
        resolved = str(store.home)
    binary = "codex" if client == "codex" else "claude"
    executable = shutil.which(binary)
    if not executable:
        raise ValueError(f"{binary} is not installed or not on PATH")
    prompt = (f"Work on the local Design Studio project {project!r}. SW_DESIGN_HOME={resolved!r}. "
              "Use design_status and design_context quality first. Preserve baseline and protected interfaces. "
              "Investigate actual artifacts, substantiate numerical and aesthetic criteria, compare three alternatives, "
              "submit an immutable revision and export a review packet. Never record human approval yourself. "
              f"CLI fallback argv: {json.dumps([sys.executable, '-m', 'solidworks_mcp', '--home', resolved])}. "
              "Report unknowns and wait for the user's review before implementation handoff.")
    env = {**os.environ, "SW_DESIGN_HOME": resolved}
    # Interactive inherited stdio; no API keys or paid model are selected by this project.
    return subprocess.call([executable, prompt], env=env)
