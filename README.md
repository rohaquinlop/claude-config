# claude-config

Personal Claude Code configuration: global instructions, skills, agents, hooks,
and status line. Sanitized for public sharing — no org names, private repo
paths, credentials, or machine-specific data.

## Install

```
git clone <this-repo-url>
cd claude-config
./install.sh
```

This symlinks each file into `~/.claude/`, merging per-file into `hooks/`,
`skills/`, and `agents/` (stow-style) so any local-only files there are left
untouched. Anything it replaces is moved to
`~/.claude-config-backup-<timestamp>/` first, nothing is deleted. Safe to
re-run any time to pick up repo updates.

## What's here

- `claude/CLAUDE.md` — global instructions (all projects)
- `claude/settings.json` — model, hooks, status line, plugin marketplaces
- `claude/statusline.sh` — git branch, context usage, rate limit status line
- `claude/hooks/` — session hooks (`herdr-agent-state.sh` is a no-op unless
  the [herdr](https://herdr.app) terminal integration env vars are set;
  safe to keep even without herdr installed)
- `claude/skills/` — reusable skills (git commit conventions, PR creation,
  codebase system-mapping, handoff docs, etc.)
- `claude/agents/` — subagent definitions (code review, codebase recon,
  web research)

## What's intentionally excluded

Anything project-, org-, or machine-specific never leaves your local
`~/.claude/`: session history, `projects/`, `plans/`, caches, telemetry,
usage data, and `settings.local.json` (per-machine permission allowlist).
The `autoMode.environment` block that Claude Code auto-populates with your
org/repo details is also excluded — regenerate it locally if you use
Auto Mode.

## Before you push changes back here

Re-run a quick sanity check for anything sensitive before committing:

```
grep -rniE "api[_-]?key|token|secret|password|AKIA|-----BEGIN" claude/
```
