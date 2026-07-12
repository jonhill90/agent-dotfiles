# Phase 0: Pi Harness Survey (initial)

- **Date:** 2026-07-11
- **Status:** partial — evidence from superpowers' shipped Pi projection.
  Full pass over Pi docs pending (Pi is not installed on this machine yet;
  installing + hands-on survey is a spec-phase prerequisite).

## What is known (from `superpowers/.pi/extensions/superpowers.ts`)

- Package: `@earendil-works/pi-coding-agent` (Mario Zechner / badlogic's
  Pi). Extensions are TypeScript modules receiving an `ExtensionAPI`.
- **Skill discovery:** `resources_discover` event returns `skillPaths` —
  Pi natively consumes Agent Skills directories. The PRD's portable-format
  bet holds for Pi.
- **Hook-equivalents:** events observed — `session_start`,
  `session_compact`, `agent_end`, and `context` (which can inject messages
  into the model context). That's enough to implement the
  bootstrap-injection pattern (superpowers proves it: it re-injects its
  using-superpowers contract after start/compaction, exactly like its
  Claude Code SessionStart hook).
- **Instructions:** not evidenced in this file; expected AGENTS.md-family
  support — verify in docs.
- **MCP:** not evidenced here — verify. (APM has no Pi target either, so
  MCP config for Pi is wrapper-owned regardless.)

## Consequences for the spec

1. The dotfiles' Pi projection = one small extension (skillPaths +
   context-injection bootstrap) + whatever instructions/MCP mechanism the
   docs reveal. Superpowers' extension is a working reference
   implementation to pattern-match, not copy.
2. "New-machine test" for Pi must include installing Pi itself (not
   present on the current machine), so the sync wrapper needs an
   install-or-skip stance per harness: configure what exists, optionally
   install what doesn't.
3. Open verifications for the docs pass: instructions file support, MCP
   config surface, settings/permissions model, skill scan behavior
   (recursive? one-level?), extension install path (~/.pi/?).
