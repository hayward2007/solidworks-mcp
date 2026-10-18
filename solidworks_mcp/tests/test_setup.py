"""Installer tests:  python -m unittest solidworks_mcp.tests.test_setup"""
import importlib.util
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("setup_mcp", ROOT / "setup_mcp.py")
setup_mcp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(setup_mcp)

ENTRY = {"command": "C:\\x\\python.exe", "args": ["C:\\x\\solidworks_mcp_server.py"]}


def front_matter(text: str) -> dict:
    assert text.startswith("---\n"), "front matter must open on the first line"
    fields = {}
    for line in text[4:text.index("\n---\n", 4)].splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip('"')
    return fields


class SkillTests(unittest.TestCase):
    def test_front_matter(self):
        text = (setup_mcp.SKILL_DIR / "SKILL.md").read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
        fields = front_matter(text)
        self.assertEqual(fields["name"], setup_mcp.SKILL_NAME)
        self.assertEqual(setup_mcp.SKILL_DIR.name, fields["name"])
        self.assertLessEqual(len(fields["name"]), 64)
        self.assertLessEqual(len(fields["description"]), 200)  # claude.ai skill upload limit

    def test_install_remove_and_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / "skills"
            target = setup_mcp.install_skill(skills)
            data = (target / "SKILL.md").read_bytes()
            self.assertTrue(data.startswith(b"---\n"))
            self.assertNotIn(b"\r\n", data)
            self.assertEqual(setup_mcp.install_skill(skills), target)  # running again overwrites
            self.assertEqual(setup_mcp.remove_skill(skills), "removed")
            self.assertEqual(setup_mcp.remove_skill(skills), "not installed")
            old = setup_mcp.DIST_DIR
            setup_mcp.DIST_DIR = Path(tmp) / "dist"
            try:
                archive = setup_mcp.build_skill_zip()
            finally:
                setup_mcp.DIST_DIR = old
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(bundle.namelist(), ["solidworks-design/SKILL.md"])
                self.assertEqual(bundle.read("solidworks-design/SKILL.md"), data)


class DesktopConfigTests(unittest.TestCase):
    def test_register_and_unregister_keep_everything_else(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "Claude" / "claude_desktop_config.json"
            self.assertEqual(setup_mcp.register(config, ENTRY), "created")
            self.assertEqual(setup_mcp.register(config, ENTRY), "already up to date")
            data = json.loads(config.read_text(encoding="utf-8"))
            data["mcpServers"]["other"] = {"command": "node", "args": ["한글.js"]}
            data["preferences"] = {"x": 1}
            config.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            moved = dict(ENTRY, args=["D:\\elsewhere\\solidworks_mcp_server.py"])
            self.assertTrue(setup_mcp.register(config, moved).startswith("updated (backup: "))
            self.assertTrue(setup_mcp.unregister(config).startswith("removed (backup: "))
            self.assertEqual(setup_mcp.unregister(config), "not registered")
            self.assertEqual(json.loads(config.read_text(encoding="utf-8")),
                             {"mcpServers": {"other": {"command": "node", "args": ["한글.js"]}},
                              "preferences": {"x": 1}})
            self.assertTrue(list(config.parent.glob("claude_desktop_config.json.bak-*")))
            self.assertEqual(setup_mcp.unregister(Path(tmp) / "missing.json"), "no config file")

    def test_invalid_json_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "claude_desktop_config.json"
            config.write_text("{ not json", encoding="utf-8")
            with self.assertRaises(ValueError):
                setup_mcp.register(config, ENTRY)
            with self.assertRaises(ValueError):
                setup_mcp.unregister(config)
            self.assertEqual(config.read_text(encoding="utf-8"), "{ not json")


class ClaudeCodeTests(unittest.TestCase):
    """A stand-in for the claude CLI records its arguments; 'add' creates a marker, 'remove' needs it."""

    def fake_cli(self, folder: Path, fail_add: bool = False) -> tuple:
        log, mark = folder / "calls.txt", folder / "present"
        if os.name == "nt":
            cli = folder / "claude.cmd"
            add = "(echo boom 1>&2 & exit /b 1)" if fail_add else f'(type nul > "{mark}" & exit /b 0)'
            cli.write_text("@echo off\r\n"
                           f'echo %*>>"{log}"\r\n'
                           f'if "%2"=="add" {add}\r\n'
                           f'if "%2"=="remove" if exist "{mark}" (del "{mark}" & exit /b 0)\r\n'
                           'if "%2"=="remove" (echo No MCP server found 1>&2 & exit /b 1)\r\n'
                           "exit /b 2\r\n", encoding="ascii")
        else:
            cli = folder / "claude"
            add = "echo boom >&2; exit 1" if fail_add else f'touch "{mark}"; exit 0'
            cli.write_text("#!/bin/sh\n"
                           f'echo "$@" >> "{log}"\n'
                           'case "$2" in\n'
                           f"  add) {add} ;;\n"
                           f'  remove) if [ -f "{mark}" ]; then rm "{mark}"; exit 0; fi; '
                           'echo "No MCP server found" >&2; exit 1 ;;\n'
                           "esac\nexit 2\n", encoding="ascii")
            cli.chmod(0o755)
        return str(cli), log

    def test_register_replaces_and_unregister_removes(self):
        with tempfile.TemporaryDirectory() as tmp:
            cli, log = self.fake_cli(Path(tmp))
            self.assertEqual(setup_mcp.register_claude_code(cli, ENTRY), "registered for all projects (user scope)")
            calls = [line.strip() for line in log.read_text().splitlines()]
            self.assertEqual(calls, ["mcp remove solidworks --scope user",
                                     "mcp add --scope user solidworks -- C:\\x\\python.exe "
                                     "C:\\x\\solidworks_mcp_server.py"])
            self.assertEqual(setup_mcp.unregister_claude_code(cli), "removed")
            self.assertEqual(setup_mcp.unregister_claude_code(cli), "not registered")

    def test_failed_add_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            cli, _ = self.fake_cli(Path(tmp), fail_add=True)
            with self.assertRaisesRegex(RuntimeError, "boom"):
                setup_mcp.register_claude_code(cli, ENTRY)


class ArgumentTests(unittest.TestCase):
    def test_defaults_and_repeats(self):
        args = setup_mcp.parse_args([])
        self.assertFalse(args.yes or args.uninstall or args.no_desktop or args.no_claude_code or args.no_skill)
        self.assertIsNone(args.desktop_config)
        args = setup_mcp.parse_args(["-y", "--desktop-config", "a.json", "--desktop-config", "b.json",
                                     "--skills-dir", "s", "--uninstall"])
        self.assertTrue(args.yes and args.uninstall)
        self.assertEqual(args.desktop_config, [Path("a.json"), Path("b.json")])
        self.assertEqual(args.skills_dir, Path("s"))

    @unittest.skipIf(os.name == "nt", "on Windows main() really installs")
    def test_main_refuses_other_systems(self):
        self.assertEqual(setup_mcp.main(["--yes"]), 1)


if __name__ == "__main__":
    unittest.main()
