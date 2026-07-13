#!/bin/bash
# agent-dotfiles bootstrap (SPEC §8). macOS v1. Idempotent.
# Usage: ./install.sh [--non-interactive]
#   Non-interactive mode requires AGENT_MEMORY_VAULT to be exported (or
#   already present in the shell profile) and skips all prompts.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PROFILE="${AGENT_DOTFILES_PROFILE:-$HOME/.zshrc}"
MARKER_BEGIN="# >>> agent-dotfiles >>>"
MARKER_END="# <<< agent-dotfiles <<<"
NONINTERACTIVE=0
[ "${1:-}" = "--non-interactive" ] && NONINTERACTIVE=1

step() { printf '\n[%s] %s\n' "$1" "$2"; }

step 1 "uv + apm"
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
command -v apm >/dev/null || uv tool install apm
echo "  apm: $(apm --version 2>/dev/null | head -1)"

step 2 "Obsidian CLI (optional — memory uses direct file ops)"
OB_BUNDLE="/Applications/Obsidian.app/Contents/MacOS/obsidian-cli"
if [ -x "$OB_BUNDLE" ]; then
  mkdir -p "$HOME/bin"
  ln -sf "$OB_BUNDLE" "$HOME/bin/obsidian"
  echo "  official CLI linked at ~/bin/obsidian"
elif [ -d "/Applications/Obsidian.app" ]; then
  echo "  WARNING: Obsidian installer predates the CLI (in-app updates do"
  echo "  not deliver it). Download a fresh installer from obsidian.md."
else
  echo "  Obsidian not installed — skipping (memory still works)"
fi

step 3 "machine-local environment"
if [ -z "${AGENT_MEMORY_VAULT:-}" ] && ! grep -q "AGENT_MEMORY_VAULT" "$PROFILE" 2>/dev/null; then
  if [ "$NONINTERACTIVE" = 1 ]; then
    echo "  WARNING: AGENT_MEMORY_VAULT not set; memory disabled until it is"
  else
    printf '  Path to your PERSONAL memory vault (never employer storage): '
    read -r AGENT_MEMORY_VAULT
    export AGENT_MEMORY_VAULT
  fi
fi
if ! grep -q "$MARKER_BEGIN" "$PROFILE" 2>/dev/null; then
  {
    echo "$MARKER_BEGIN"
    echo 'export PATH="$HOME/bin:$HOME/.local/bin:$PATH"'
    [ -n "${AGENT_MEMORY_VAULT:-}" ] && printf 'export AGENT_MEMORY_VAULT="%s"\n' "$AGENT_MEMORY_VAULT"
    echo 'export APM_COPILOT_COWORK_SKILLS_DIR="$HOME/Library/CloudStorage/OneDrive-Personal/Cowork/skills"'
    echo '[ -f ~/.zshrc.local ] && source ~/.zshrc.local  # secrets live here, untracked'
    echo "$MARKER_END"
  } >> "$PROFILE"
  echo "  profile block written to $PROFILE"
else
  echo "  profile block already present"
fi
export APM_COPILOT_COWORK_SKILLS_DIR="${APM_COPILOT_COWORK_SKILLS_DIR:-$HOME/Library/CloudStorage/OneDrive-Personal/Cowork/skills}"

step "3.5" "memory vault skeleton"
if [ -n "${AGENT_MEMORY_VAULT:-}" ] && [ ! -f "$AGENT_MEMORY_VAULT/agent/index.md" ]; then
  mkdir -p "$AGENT_MEMORY_VAULT/agent/facts"
  printf -- '---\nokf_version: "0.1"\n---\n\n# Facts\n' > "$AGENT_MEMORY_VAULT/agent/index.md"
  printf '# Agent Memory Log\n\nAppend-only. `## YYYY-MM-DD` headings, newest first.\n' > "$AGENT_MEMORY_VAULT/agent/log.md"
  echo "  vault skeleton created at $AGENT_MEMORY_VAULT/agent/"
else
  echo "  vault present or AGENT_MEMORY_VAULT unset — skipped"
fi

step 4 "sync apply"
python3 "$REPO_DIR/scripts/sync.py" apply

step 5 "doctor"
python3 "$REPO_DIR/scripts/sync.py" doctor || true

echo
echo "Done. Open a NEW terminal (or 'source $PROFILE') and start your harness."
