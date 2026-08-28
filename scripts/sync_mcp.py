"""MCP server projection into Claude Code, Copilot, and Codex
(agent-dotfiles#335).

Split out of the former scripts/sync.py (2141 lines). Pure move -- no
behaviour change from the original module.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from sync_constants import ABSENT, CODEX_MCP_BEGIN, CODEX_MCP_END, CODEX_SKILLS_BEGIN, CODEX_SKILLS_END
from sync_skills import codex_disabled_skills
from sync_util import deep_merge


class McpMixin:
    def mcp_fragment_file(self) -> Path:
        return self.repo / "settings" / "mcp" / "servers.json"

    def declared_mcp_servers(self) -> dict:
        fragment_file = self.mcp_fragment_file()
        if not fragment_file.is_file():
            # Left as "nothing to check" rather than fixed closed, unlike
            # #29 and #35 (#38): this input is git-tracked, checked out in
            # the same clone sync.py runs from, so its absence is already
            # visible via `git status` rather than silently disappearing.
            return {}
        return json.loads(fragment_file.read_text(encoding="utf-8")).get(
            "mcpServers", {}
        )

    def _merge_mcp_json(self, live_path: Path) -> None:
        """Merge the declared servers into a JSON file with a top-level
        mcpServers key, recording previous values for reversal."""
        servers = self.declared_mcp_servers()
        if not servers:
            return
        live = {}
        if live_path.is_file():
            live = json.loads(live_path.read_text(encoding="utf-8"))

        previous = self.state.setdefault("mcp", {}).setdefault(str(live_path), {})
        live_servers = live.get("mcpServers", {})
        for name in servers:
            if name not in previous:
                previous[name] = live_servers.get(name, ABSENT)

        live["mcpServers"] = deep_merge(live_servers, servers)
        live_path.write_text(
            json.dumps(live, indent=2) + "\n", encoding="utf-8"
        )

    def merge_mcp(self) -> None:
        """Project the declared MCP set into Claude Code user scope
        (~/.claude.json). Pi gets none by design (SPEC §3.4)."""
        self._merge_mcp_json(self.home / ".claude.json")

    def merge_copilot_mcp(self) -> None:
        """Copilot CLI reads ~/.copilot/mcp-config.json (same mcpServers
        schema). Only projected when the harness directory exists."""
        if not (self.home / ".copilot").is_dir():
            return
        self._merge_mcp_json(self.home / ".copilot" / "mcp-config.json")

    @staticmethod
    def _strip_codex_block(text: str) -> str:
        pattern = re.compile(
            r"\n*" + re.escape(CODEX_MCP_BEGIN) + r".*?" + re.escape(CODEX_MCP_END) + r"\n?",
            re.S,
        )
        return pattern.sub("", text)

    def merge_codex_mcp(self) -> None:
        """Codex has no user-scope JSON MCP surface; render the declared
        servers as a marker-delimited block in ~/.codex/config.toml.
        Servers the user already defines outside the block are skipped."""
        config = self.home / ".codex" / "config.toml"
        if not config.parent.is_dir():
            return
        servers = self.declared_mcp_servers()
        text = config.read_text(encoding="utf-8") if config.is_file() else ""
        base = self._strip_codex_block(text)

        lines: list[str] = []
        for name, spec in servers.items():
            if f"[mcp_servers.{name}]" in base:
                print(f"[skip] codex mcp: {name} defined outside managed block")
                continue
            lines.append(f"[mcp_servers.{name}]")
            if "url" in spec:
                lines.append(f'url = "{spec["url"]}"')
            # A stdio server (agent-dotfiles#198's supervisor server is the
            # first one declared here) is `command` plus `args`, not a url.
            # Without this branch the loop emitted a bare
            # `[mcp_servers.<name>]` table with nothing in it -- a
            # syntactically valid config declaring a server Codex cannot
            # launch, which is worse than not projecting it at all. The
            # rendered shape is what `codex mcp add` itself writes, checked
            # against a real `codex mcp add -- python3 <path>` run into a
            # throwaway CODEX_HOME, not inferred from the docs. `json.dumps`
            # does the quoting: TOML basic strings and arrays accept JSON's
            # escaping, and hand-rolled f-string quotes are how a path with a
            # quote or a backslash in it would silently corrupt the file.
            if "command" in spec:
                lines.append(f"command = {json.dumps(spec['command'])}")
                if spec.get("args"):
                    lines.append(f"args = {json.dumps(list(spec['args']))}")
            auth = spec.get("headers", {}).get("Authorization", "")
            match = re.fullmatch(r"Bearer \$\{(\w+)\}", auth)
            if match:
                lines.append(f'bearer_token_env_var = "{match.group(1)}"')
            lines.append("")

        if lines:
            block = "\n".join([CODEX_MCP_BEGIN, *lines[:-1], CODEX_MCP_END])
            new = (base.rstrip("\n") + "\n\n" + block + "\n").lstrip("\n")
            self.state["codex_mcp"] = str(config)
        else:
            new = base
        if new != text:
            config.write_text(new, encoding="utf-8")

    @staticmethod
    def _strip_codex_skills_block(text: str) -> str:
        pattern = re.compile(
            r"\n*" + re.escape(CODEX_SKILLS_BEGIN) + r".*?"
            + re.escape(CODEX_SKILLS_END) + r"\n?",
            re.S,
        )
        return pattern.sub("", text)

    def merge_codex_skills(self) -> None:
        """Enforce Codex's resolved roster as a managed `[[skills.config]]`
        block in ~/.codex/config.toml (SPEC §4.1 Tier B).

        Marker-delimited because the same table holds the user's own plugin
        disables; stripping and rewriting only the managed span leaves those
        untouched and makes the block reversible on teardown.
        """
        config = self.home / ".codex" / "config.toml"
        if not config.parent.is_dir():
            return
        text = config.read_text(encoding="utf-8") if config.is_file() else ""
        base = self._strip_codex_skills_block(text)

        lines: list[str] = []
        for name in codex_disabled_skills(self.repo):
            lines.extend(["[[skills.config]]", f'name = "{name}"',
                          "enabled = false", ""])
        if lines:
            block = "\n".join([CODEX_SKILLS_BEGIN, *lines[:-1], CODEX_SKILLS_END])
            new = (base.rstrip("\n") + "\n\n" + block + "\n").lstrip("\n")
            self.state["codex_skills"] = str(config)
        else:
            new = base
            self.state["codex_skills"] = None

        if new != text:
            config.write_text(new, encoding="utf-8")
