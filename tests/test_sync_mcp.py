"""Tests for MCP server config merging across claude, codex, and copilot.

Split out of the former tests/test_sync.py (2969 lines, agent-dotfiles#331).
Pure reorganisation -- no behaviour change.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import sync  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sync_helpers import APM_MARKER, SyncTestCase, make_repo  # noqa: E402


class McpMergeTests(SyncTestCase):
    def write_fragment(self, servers: dict) -> None:
        (self.repo / "settings" / "mcp" / "servers.json").write_text(
            json.dumps({"mcpServers": servers}) + "\n"
        )

    def test_merge_writes_declared_servers_preserving_unmanaged(self) -> None:
        self.write_fragment(
            {"context7": {"type": "http", "url": "https://c7.example/mcp"}}
        )
        live = self.home / ".claude.json"
        live.write_text(
            json.dumps(
                {
                    "mcpServers": {"personal": {"command": "foo"}},
                    "projects": {"/x": {}},
                }
            )
        )

        self.syncer.merge_mcp()

        merged = json.loads(live.read_text())
        self.assertEqual(
            merged["mcpServers"]["context7"]["url"], "https://c7.example/mcp"
        )
        self.assertEqual(merged["mcpServers"]["personal"], {"command": "foo"})
        self.assertEqual(merged["projects"], {"/x": {}})  # untouched
        prev = self.syncer.state["mcp"][str(live)]
        self.assertEqual(prev["context7"], sync.ABSENT)

    def test_merge_records_previous_value_of_overridden_server(self) -> None:
        self.write_fragment({"context7": {"type": "http", "url": "https://new"}})
        live = self.home / ".claude.json"
        live.write_text(
            json.dumps({"mcpServers": {"context7": {"command": "old"}}})
        )
        self.syncer.merge_mcp()
        prev = self.syncer.state["mcp"][str(live)]
        self.assertEqual(prev["context7"], {"command": "old"})

    def test_merge_creates_live_file_when_absent(self) -> None:
        self.write_fragment({"deepwiki": {"type": "http", "url": "https://dw"}})
        self.syncer.merge_mcp()
        merged = json.loads((self.home / ".claude.json").read_text())
        self.assertEqual(merged["mcpServers"]["deepwiki"]["url"], "https://dw")

    def test_empty_or_missing_fragment_is_noop(self) -> None:
        self.syncer.merge_mcp()
        self.assertFalse((self.home / ".claude.json").exists())
        (self.repo / "settings" / "mcp" / "servers.json").unlink()
        self.syncer.merge_mcp()
        self.assertFalse((self.home / ".claude.json").exists())

    def test_apply_runs_mcp_merge(self) -> None:
        self.write_fragment({"deepwiki": {"type": "http", "url": "https://dw"}})
        self.syncer.apply(no_apm=True)
        merged = json.loads((self.home / ".claude.json").read_text())
        self.assertIn("deepwiki", merged["mcpServers"])

    def test_remove_restores_previous_mcp_state(self) -> None:
        self.write_fragment(
            {
                "context7": {"type": "http", "url": "https://new"},
                "deepwiki": {"type": "http", "url": "https://dw"},
            }
        )
        live = self.home / ".claude.json"
        live.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "context7": {"command": "old"},
                        "personal": {"command": "foo"},
                    }
                }
            )
        )
        self.syncer.apply(no_apm=True)
        self.syncer.remove(no_apm=True)
        restored = json.loads(live.read_text())
        self.assertEqual(
            restored["mcpServers"],
            {"context7": {"command": "old"}, "personal": {"command": "foo"}},
        )

    def test_apply_twice_then_remove_restores_original(self) -> None:
        self.write_fragment({"deepwiki": {"type": "http", "url": "https://dw"}})
        live = self.home / ".claude.json"
        live.write_text(json.dumps({"mcpServers": {}}))
        self.syncer.apply(no_apm=True)
        self.syncer.apply(no_apm=True)
        self.syncer.remove(no_apm=True)
        self.assertEqual(json.loads(live.read_text()), {"mcpServers": {}})

    def test_doctor_warns_on_unset_mcp_env_var(self) -> None:
        self.write_fragment(
            {
                "context7": {
                    "type": "http",
                    "url": "https://c7",
                    "headers": {"Authorization": "Bearer ${CONTEXT7_API_KEY}"},
                }
            }
        )
        checks = dict(self.syncer.doctor_checks(env={}))
        ok, detail = checks["mcp-env-CONTEXT7_API_KEY"]
        self.assertIsNone(ok)  # warning, not failure
        self.assertIn("CONTEXT7_API_KEY", detail)
        checks = dict(
            self.syncer.doctor_checks(env={"CONTEXT7_API_KEY": "abc"})
        )
        self.assertTrue(checks["mcp-env-CONTEXT7_API_KEY"][0])

    def test_status_flags_declared_server_missing_from_live(self) -> None:
        self.write_fragment({"deepwiki": {"type": "http", "url": "https://dw"}})
        self.syncer.apply(no_apm=True)
        live = self.home / ".claude.json"
        live.write_text(json.dumps({"mcpServers": {}}))
        self.assertEqual(self.syncer.status(), 1)

class CodexMcpTests(SyncTestCase):
    def write_fragment(self, servers: dict) -> None:
        (self.repo / "settings" / "mcp" / "servers.json").write_text(
            json.dumps({"mcpServers": servers}) + "\n"
        )

    def setUp(self) -> None:
        super().setUp()
        self.config = self.home / ".codex" / "config.toml"
        self.config.parent.mkdir()
        self.config.write_text(
            'model = "gpt"\n\n[mcp_servers.node_repl]\ncommand = "node"\n'
        )
        self.write_fragment(
            {
                "context7": {
                    "type": "http",
                    "url": "https://c7.example/mcp",
                    "headers": {"Authorization": "Bearer ${CONTEXT7_API_KEY}"},
                },
                "deepwiki": {"type": "http", "url": "https://dw.example/mcp"},
            }
        )

    def test_writes_marker_block_preserving_existing_config(self) -> None:
        self.syncer.merge_codex_mcp()
        text = self.config.read_text()
        self.assertIn('model = "gpt"', text)
        self.assertIn("[mcp_servers.node_repl]", text)
        self.assertIn(sync.CODEX_MCP_BEGIN, text)
        self.assertIn("[mcp_servers.context7]", text)
        self.assertIn('url = "https://c7.example/mcp"', text)
        self.assertIn('bearer_token_env_var = "CONTEXT7_API_KEY"', text)
        self.assertIn("[mcp_servers.deepwiki]", text)
        self.assertIn(sync.CODEX_MCP_END, text)

    def test_idempotent_reapply_keeps_single_block(self) -> None:
        self.syncer.merge_codex_mcp()
        first = self.config.read_text()
        self.syncer.merge_codex_mcp()
        self.assertEqual(self.config.read_text(), first)

    def test_skips_server_already_defined_outside_block(self) -> None:
        self.config.write_text(
            'model = "gpt"\n\n[mcp_servers.context7]\ncommand = "mine"\n'
        )
        self.syncer.merge_codex_mcp()
        text = self.config.read_text()
        self.assertEqual(text.count("[mcp_servers.context7]"), 1)
        self.assertIn('command = "mine"', text)
        self.assertIn("[mcp_servers.deepwiki]", text)  # others still land

    def test_stdio_server_renders_command_and_args(self) -> None:
        """agent-dotfiles#198. Before this, a `command`/`args` server rendered
        as a bare `[mcp_servers.<name>]` table with nothing under it -- valid
        TOML declaring a server Codex could not launch. The expected shape is
        what `codex mcp add` itself writes."""
        self.write_fragment(
            {"supervisor": {"type": "stdio", "command": "python3", "args": ["/x/mcp_server.py"]}}
        )
        self.syncer.merge_codex_mcp()
        text = self.config.read_text()
        self.assertIn("[mcp_servers.supervisor]", text)
        self.assertIn('command = "python3"', text)
        self.assertIn('args = ["/x/mcp_server.py"]', text)
        self.assertEqual(tomllib.loads(text)["mcp_servers"]["supervisor"],
                         {"command": "python3", "args": ["/x/mcp_server.py"]})

    def test_stdio_server_without_args_still_renders_its_command(self) -> None:
        self.write_fragment({"bare": {"command": "supervisor-mcp"}})
        self.syncer.merge_codex_mcp()
        self.assertEqual(tomllib.loads(self.config.read_text())["mcp_servers"]["bare"],
                         {"command": "supervisor-mcp"})

    def test_skipped_when_codex_absent(self) -> None:
        self.config.unlink()
        self.config.parent.rmdir()
        self.syncer.merge_codex_mcp()
        self.assertFalse(self.config.exists())

    def test_remove_strips_block_only(self) -> None:
        self.syncer.merge_codex_mcp()
        self.syncer.save_state()
        self.syncer.remove(no_apm=True)
        text = self.config.read_text()
        self.assertIn('model = "gpt"', text)
        self.assertIn("[mcp_servers.node_repl]", text)
        self.assertNotIn(sync.CODEX_MCP_BEGIN, text)
        self.assertNotIn("context7", text)

class CopilotMcpTests(SyncTestCase):
    def write_fragment(self, servers: dict) -> None:
        (self.repo / "settings" / "mcp" / "servers.json").write_text(
            json.dumps({"mcpServers": servers}) + "\n"
        )

    def setUp(self) -> None:
        super().setUp()
        (self.home / ".copilot").mkdir()
        self.mcp_config = self.home / ".copilot" / "mcp-config.json"
        self.write_fragment(
            {"deepwiki": {"type": "http", "url": "https://dw.example/mcp"}}
        )

    def test_merge_creates_mcp_config_preserving_unmanaged(self) -> None:
        self.mcp_config.write_text(
            json.dumps({"mcpServers": {"personal": {"command": "foo"}}})
        )
        self.syncer.merge_copilot_mcp()
        merged = json.loads(self.mcp_config.read_text())
        self.assertEqual(
            merged["mcpServers"]["deepwiki"]["url"], "https://dw.example/mcp"
        )
        self.assertEqual(merged["mcpServers"]["personal"], {"command": "foo"})

    def test_skipped_when_copilot_absent(self) -> None:
        (self.home / ".copilot").rmdir()
        self.syncer.merge_copilot_mcp()
        self.assertFalse(self.mcp_config.exists())

    def test_remove_restores_previous(self) -> None:
        self.syncer.apply(no_apm=True)
        self.assertTrue(self.mcp_config.is_file())
        self.syncer.remove(no_apm=True)
        merged = json.loads(self.mcp_config.read_text())
        self.assertNotIn("deepwiki", merged["mcpServers"])

    def test_status_flags_missing_copilot_server(self) -> None:
        self.syncer.apply(no_apm=True)
        self.mcp_config.write_text(json.dumps({"mcpServers": {}}))
        self.assertEqual(self.syncer.status(), 1)
