#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import tomllib
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "filmcraft_agent.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("filmcraft_agent_under_test", SCRIPT)
agent = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(agent)


class ConfiguratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.old = agent.ROOT, agent.RUNTIME, agent.PROBE_PATH, agent.MANIFEST_PATH
        agent.ROOT = self.root
        agent.RUNTIME = self.root / "workspace" / "runtime"
        agent.PROBE_PATH = agent.RUNTIME / "probe.json"
        agent.MANIFEST_PATH = self.root / "references" / "upstream-manifest.json"

    def tearDown(self) -> None:
        agent.ROOT, agent.RUNTIME, agent.PROBE_PATH, agent.MANIFEST_PATH = self.old
        self.temporary.cleanup()

    def configure(self, clients: list[str], address: str = "127.0.0.1:9876"):
        args = SimpleNamespace(cli=None, app=None, address=address, project=None, clients=clients)
        with patch.object(agent, "load_probe", return_value={"filmcraft": {"cli": "/bin/true"}}):
            return agent.configure(args)

    def test_merge_preserve_and_managed_update(self) -> None:
        (self.root / ".kimi-code").mkdir(parents=True)
        (self.root / ".kimi-code" / "mcp.json").write_text(
            '{"mcpServers":{"other":{"command":"/bin/other"}},"custom":42}')
        (self.root / ".codex").mkdir()
        (self.root / ".codex" / "config.toml").write_text(
            'model = "preserved"\n[mcp_servers.other]\ncommand = "/bin/other"\n')
        (self.root / "opencode.json").write_text(
            '{"theme":"preserved","mcp":{"servers":{"other":{"type":"local","command":["/bin/other"]}}}}')
        clients = ["kimi", "copilot", "opencode", "codex"]
        self.configure(clients)
        self.configure(clients, "127.0.0.1:9888")
        kimi = json.loads((self.root / ".kimi-code" / "mcp.json").read_text())
        self.assertEqual(kimi["custom"], 42)
        self.assertEqual(kimi["mcpServers"]["other"]["command"], "/bin/other")
        self.assertEqual(kimi["mcpServers"]["filmcraft"]["args"][-1], "127.0.0.1:9888")
        codex = tomllib.loads((self.root / ".codex" / "config.toml").read_text())
        self.assertEqual(codex["model"], "preserved")
        self.assertEqual(codex["mcp_servers"]["other"]["command"], "/bin/other")
        self.assertEqual(codex["mcp_servers"]["filmcraft"]["args"][-1], "127.0.0.1:9888")
        opencode = json.loads((self.root / "opencode.json").read_text())
        self.assertEqual(opencode["theme"], "preserved")
        self.assertEqual(opencode["mcp"]["servers"]["filmcraft"]["type"], "local")
        self.assertNotIn("enabled", opencode["mcp"]["servers"]["filmcraft"])
        copilot = json.loads((self.root / ".mcp.json").read_text())
        self.assertEqual(copilot["mcpServers"]["filmcraft"]["type"], "stdio")
        self.assertTrue(list(agent.RUNTIME.glob("config-backup/*")))

    def test_conflict_rejected_before_any_write(self) -> None:
        clients = ["kimi", "copilot", "opencode", "codex"]
        (self.root / ".codex").mkdir(parents=True)
        (self.root / ".codex" / "config.toml").write_text(
            '[mcp_servers.filmcraft]\ncommand = "/bin/do-not-use"\n')
        sentinel = self.root / ".kimi-code" / "mcp.json"
        sentinel.parent.mkdir()
        sentinel.write_text('{"mcpServers":{},"unchanged":true}')
        before = sentinel.read_bytes()
        with self.assertRaises(ValueError):
            self.configure(clients)
        self.assertEqual(sentinel.read_bytes(), before)
        self.assertFalse((self.root / ".mcp.json").exists())
        self.assertFalse((self.root / "opencode.json").exists())

    def test_opencode_legacy_is_explicit_and_replaces_v2_filmcraft_only(self) -> None:
        (self.root / "opencode.json").write_text(json.dumps({
            "mcp": {"servers": {
                "filmcraft": {"type": "local", "command": ["old"]},
                "other": {"type": "local", "command": ["preserved"]},
            }}}))
        self.configure(["opencode-legacy"])
        data = json.loads((self.root / "opencode.json").read_text())
        self.assertNotIn("filmcraft", data["mcp"]["servers"])
        self.assertEqual(data["mcp"]["servers"]["other"]["command"], ["preserved"])
        self.assertTrue(data["mcp"]["filmcraft"]["enabled"])

    def test_invalid_address_and_project_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.configure(["generic"], "0.0.0.0:9876")
        args = SimpleNamespace(cli=None, app=None, address="127.0.0.1:9876",
                               project=self.root / "missing.fcproj", clients=["generic"])
        with patch.object(agent, "load_probe", return_value={"filmcraft": {"cli": "/bin/true"}}):
            with self.assertRaises(ValueError):
                agent.configure(args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
