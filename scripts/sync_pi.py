"""Pi root-file projection and neutral-skills mirroring (agent-dotfiles#335).

Split out of the former scripts/sync.py (2141 lines). Pure move -- no
behaviour change from the original module.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from sync_constants import SYNC_MARKER
from sync_skills import neutral_union
from sync_util import strip_frontmatter


class PiMixin:
    def pi_available(self) -> bool:
        return shutil.which("pi") is not None

    def project_pi(self) -> Path | None:
        pi_dir = self.home / ".pi" / "agent"
        if not pi_dir.is_dir():
            # pi installed but never launched (fresh machine): initialize
            if self.pi_available():
                pi_dir.mkdir(parents=True, exist_ok=True)
            else:
                return None
        target = pi_dir / "AGENTS.md"
        if target.exists() and SYNC_MARKER not in target.read_text(encoding="utf-8"):
            print(f"[skip] hand-authored, not overwriting: {target}")
            return None

        core = strip_frontmatter(
            (self.repo / "instructions" / "global.instructions.md").read_text(
                encoding="utf-8"
            )
        )
        overlay = (self.repo / "instructions" / "overlays" / "pi.md").read_text(
            encoding="utf-8"
        )
        target.write_text(
            f"{SYNC_MARKER}\n\n{core.strip()}\n\n{overlay.strip()}\n",
            encoding="utf-8",
        )
        self.state["pi_agents_md"] = str(target)
        return target

    def ensure_neutral_skills(self) -> None:
        """APM's neutral-path (~/.agents/skills) targeting is unreliable on
        fresh machines; mirror into it so Pi/Codex/Copilot always see their
        set.

        Tier A scoping (SPEC §4.1): only the neutral trio's resolved roster
        is mirrored, so a Claude-scoped skill never reaches the shared path.
        Links this wrapper created and that have since left the union are
        removed; links it did not create are never touched.
        """
        neutral = self.home / ".agents" / "skills"
        claude_skills = self.home / ".claude" / "skills"
        if not claude_skills.is_dir():
            return
        wanted = set(neutral_union(self.repo))
        managed = set(self.state.get("neutral_skills", []))
        neutral.mkdir(parents=True, exist_ok=True)
        for skill in sorted(claude_skills.iterdir()):
            if not skill.is_dir() or skill.name not in wanted:
                continue
            target = neutral / skill.name
            if not target.exists():
                target.symlink_to(skill)
                managed.add(skill.name)
        for name in sorted(managed - wanted):
            target = neutral / name
            if target.is_symlink():
                target.unlink()
            managed.discard(name)
        self.state["neutral_skills"] = sorted(managed)
