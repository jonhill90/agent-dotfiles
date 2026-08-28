"""Machine-global git commit-msg hook install (agent-dotfiles#335).

Split out of the former scripts/sync.py (2141 lines). Pure move -- no
behaviour change from the original module.
"""

from __future__ import annotations

import shutil
from pathlib import Path


class GitHooksMixin:
    def git_hooks_dir(self) -> Path:
        return self.home / ".git-hooks"

    def configured_hooks_path(self) -> str:
        """The global `core.hooksPath` value, read directly from
        ~/.gitconfig rather than shelling out to `git config --get` --
        every subprocess.run() call this module makes must go through
        self.runner() (or match its (cmd, check, env) signature) so tests
        can intercept it uniformly (ApmSubprocessIsolationTests); a raw
        capturing subprocess call would be a second, incompatible shape."""
        gitconfig = self.home / ".gitconfig"
        if not gitconfig.is_file():
            return ""
        section = None
        for line in gitconfig.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                section = stripped[1:-1].strip()
                continue
            if section == "core" and "=" in stripped:
                key, _, value = stripped.partition("=")
                if key.strip() == "hooksPath":
                    return value.strip()
        return ""

    def install_git_hooks(self) -> tuple[bool, str]:
        """Install hooks/no-coauthor-trailer as the *machine-global* git
        commit-msg hook via `core.hooksPath` (#275), so the Co-Authored-By
        guard fires for every repo on the machine -- not just the checkout
        it was authored in. A per-repo .git/hooks entry would cover one
        checkout out of however many exist; a global hooksPath covers all
        of them, including ones cloned after this ran.

        Never clobbers an operator's own hooksPath customization: if
        core.hooksPath is already set to something other than our target
        directory, this is a no-op that reports the conflict instead of
        overwriting it.
        """
        source = self.repo / "hooks" / "no-coauthor-trailer"
        if not source.is_file():
            return False, "hooks/no-coauthor-trailer missing from repo"
        target_dir = self.git_hooks_dir()
        target = target_dir / "commit-msg"
        existing = self.configured_hooks_path()
        if existing and existing != str(target_dir):
            return (
                False,
                f"core.hooksPath already set to {existing}, not overwriting",
            )
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(0o755)
        if existing != str(target_dir):
            self.runner(
                ["git", "config", "--global", "core.hooksPath", str(target_dir)],
                check=True,
            )
        return True, str(target_dir)
