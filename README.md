# claude-config

Personal Claude Code configuration: global instructions, skills, hooks,
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

## Requirements

The Python hooks need these tools on `PATH`. Without them, the stop gate blocks with `command not found`.

- [complexipy](https://github.com/rohaquinlop/complexipy), used by `py-post-edit.sh` and `py-stop-gate.sh`: `uv tool install complexipy`
- [jscpd](https://github.com/kucherenko/jscpd) v4, used by `py-stop-gate.sh`: `bun add -g jscpd@4` (v5 adds color codes to its output)

## What's here

- `claude/CLAUDE.md` — global instructions (all projects)
- `claude/settings.json` — model, hooks, status line, plugin marketplaces
- `claude/statusline.sh` — git branch, context usage, rate limit status line
- `claude/hooks/` — session hooks (`herdr-agent-state.sh` is a no-op unless
  the [herdr](https://herdr.app) terminal integration env vars are set;
  safe to keep even without herdr installed). `py-post-edit.sh` and
  `py-stop-gate.sh` run ruff, ty, complexipy, pytest and jscpd in Python
  projects (`pyproject.toml`) only
- `claude/skills/` — reusable skills (git commit conventions, PR creation,
  codebase system-mapping, handoff docs, etc.)

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
