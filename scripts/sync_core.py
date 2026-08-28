"""Sync's constructor and on-disk state (agent-dotfiles#335).

Split out of the former scripts/sync.py (2141 lines). Pure move -- no
behaviour change from the original module.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


class SyncCoreMixin:
    def __init__(self, repo_root: Path, home: Path | None = None) -> None:
        self.repo = Path(repo_root)
        self.home = Path(home) if home else Path.home()
        # `apm`/`apm compile` are subprocesses -- they resolve their own
        # $HOME independently of self.home, which is otherwise the single
        # seam this class uses for every other write. Without this, a
        # caller that constructs Sync(home=<a test directory>) still
        # silently drives real `apm` against the *real* $HOME's
        # ~/.apm/apm.yml, ~/.claude/skills, and root instruction files --
        # exactly the incident this comment now prevents a repeat of: an
        # "isolated" test run in this repo's own history mutated the real
        # deployed configuration because this wrapper did not exist (#9
        # review). A bound method, not a lambda, so it stays introspectable
        # and every existing `self.syncer.runner = <fake>` test override
        # keeps working unchanged -- those replace this attribute entirely.
        self.runner = self._run_apm
        self.state_file = self.home / ".agent-dotfiles" / "state.json"
        self.state = self._load_state()

    def _run_apm(self, cmd: list[str], check: bool = False):
        env = {**os.environ, "HOME": str(self.home)}
        return subprocess.run(cmd, check=check, env=env)

    # -- state ------------------------------------------------------------

    def _load_state(self) -> dict:
        if self.state_file.is_file():
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        return {
            "version": 1,
            "settings": {},
            "mcp": {},
            "pi_agents_md": None,
            "removed": [],
        }

    def save_state(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(self.state, indent=2) + "\n", encoding="utf-8"
        )
