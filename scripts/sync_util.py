"""General-purpose helpers used across the sync.py split (agent-dotfiles#335).

Split out of the former scripts/sync.py (2141 lines). Pure move -- no
behaviour change from the original module.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from sync_constants import OVERLAY_FILES

CORPORATE_MOUNT_HINTS = ("OneDrive-SharedLibraries",)


def is_corporate_mount(path: str) -> bool:
    if any(hint in path for hint in CORPORATE_MOUNT_HINTS):
        return True
    for part in Path(path).parts:
        if part.startswith("OneDrive-") and part != "OneDrive-Personal":
            return True
    return False


def strip_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0] == "---":
        try:
            closing = lines.index("---", 1)
            return "\n".join(lines[closing + 1 :]).lstrip("\n")
        except ValueError:
            pass
    return text


def resolve_hook_commands(hooks_block: dict, repo: Path) -> dict:
    """Rewrite `"command": "hooks/<script>"` entries in a Claude Code hooks
    block to this repo's absolute path (agent-dotfiles#276). The fragment
    checked into settings/claude/settings.json stays repo-relative and
    portable; only the live ~/.claude/settings.json this writes needs an
    absolute path, because Claude Code invokes hook commands from whatever
    cwd the session is in, not from the repo root.

    A command that does not start with "hooks/" is left untouched -- this
    only owns paths into this repo's own hooks/ directory, never a hook a
    user or another package declared.
    """
    resolved = json.loads(json.dumps(hooks_block))  # deep copy, JSON-safe
    for entries in resolved.values():
        if not isinstance(entries, list):
            continue
        for matcher_entry in entries:
            for hook in matcher_entry.get("hooks", []):
                command = hook.get("command", "")
                if command.startswith("hooks/"):
                    hook["command"] = str(repo / command)
    return resolved


def deep_merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _description_of(skill_md: Path) -> str:
    """A skill's `description`, whitespace-normalised, or "" if unreadable."""
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return ""
    match = re.search(r"^description:\s*(.*?)(?=^\w+:|^---)", text, re.M | re.S)
    return " ".join(match.group(1).split()) if match else ""


def overlay_body(repo: Path, harness: str) -> str:
    """An overlay's content, or "" when it is a placeholder.

    A file that only documents why it is empty must not produce a block --
    `claude-code.md` is deliberately empty and says so at length.
    """
    name = OVERLAY_FILES.get(harness)
    if not name:
        return ""
    path = repo / "instructions" / "overlays" / name
    if not path.is_file():
        return ""
    raw = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S)
    lines = [
        line for line in raw.splitlines()
        if line.strip() and not line.startswith("#")
    ]
    body = "\n".join(lines).strip()
    if not body or "intentionally empty" in body.lower():
        return ""
    return body
