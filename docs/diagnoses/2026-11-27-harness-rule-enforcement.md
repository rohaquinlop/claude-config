# Diagnosis: most harness rules are advisory text, not enforced

<!-- Written by /shepherd:diagnose. A fresh session fixes from this file with `/shepherd:run <this path>`.
     Every claim says what it covers and what it did not check. Facts only from evidence; no guessed people, teams, or owners. -->

- **Status:** root cause confirmed
- **Started:** 2026-11-27
- **Source:** reported in chat

## Symptom

The user must still review agent output by hand, because rules in `CLAUDE.md`, `rules/*.md` and skills can be skipped by the model. Impact: every agentic session needs manual review; a skipped rule (commit on main, `pip install`, Claude trailer, a new branch) reaches a commit or PR.

## Evidence

| # | Evidence | Where it came from | What it shows |
|---|---|---|---|
| E1 | `claude/settings.json` hooks block | repo file; `diff <(jq -S . claude/settings.json) <(jq -S . ~/.claude/settings.json)` → identical | Live config = repo config (one uncommitted change: `rust-analyzer-lsp` off, not touched). |
| E2 | Inline PreToolUse Bash guard: `grep -Eq 'git (reset --hard\|checkout -b)'` | `claude/settings.json` | Only 2 git ops guarded, by substring regex on the whole command text. |
| E3 | Probe output (see Reproduction) | `scratch/harness-rule-enforcement/probe.sh` | Guard misses `git switch -c`, `checkout -B`, `git branch x`, `git  reset --hard` (2 spaces), `git -C . reset --hard`. It blocks `echo 'git reset --hard is bad'` (false positive). |
| E4 | This session's own probe commands were blocked twice | PreToolUse errors in this session | Both the inline guard and `git-push-alone.sh` match text inside heredocs/strings, not real commands. |
| E5 | `git-push-alone.sh` | `claude/hooks/` | Blocks chained push/merge only. Plain `git push`, `--force`, `gh pr merge 1` pass (probe rc=0). |
| E6 | `py-post-edit.sh` | `claude/hooks/` | ruff + ty + complexipy per edited `.py`; feedback only, never blocks. Runs only if repo has `pyproject.toml`. |
| E7 | `py-stop-gate.sh` | `claude/hooks/` | pytest + complexipy + jscpd (5 lines, 3%) on changed `.py`; blocks Stop up to 3 times. Good pattern. |
| E8 | Stop hook `docker ps … && echo WARNING` with exit 0 | `claude/settings.json` | Warns on any running container, including ones not started by the session. Plain stdout + exit 0 from a Stop hook is not fed back to the model (see Assumptions A1). |
| E9 | shepherd plugin `hooks.json`, `pre-push.sh` header | `~/.claude/plugins/cache/shepherd/shepherd/0.7.0/hooks/` | Push gate, merge deny, force-push deny, `--no-verify` deny, diagnose guard — but only on branches with shepherd state. Outside shepherd, none apply. |
| E10 | `git-chain.sh` header | same dir | shepherd chains to global `core.hooksPath` → a global git hooks dir works alongside shepherd. |
| E11 | `git config --global core.hooksPath` → unset; no `.pre-commit-config.yaml`; `gitleaks`/`pre-commit` not installed | local commands | No git-level enforcement exists (commit-msg, pre-commit). |
| E12 | `permissions` has only `defaultMode: auto`; `settings.local.json` has only `allow` rules | both settings files | `permissions.deny` / `ask` unused. |
| E13 | `attribution: {commit: "", pr: ""}` | `claude/settings.json` | Default Claude trailer is already off (enforced). A hand-written trailer is not checked. |
| E14 | `pyright-lsp` disabled | `enabledPlugins` | "Ignore pyright" is already enforced. |
| E15 | Tools on PATH: ruff, ty, complexipy, jscpd, uv | `command -v` | Everything needed for the Python tier exists. |
| E16 | `be-terse` plugin `UserPromptSubmit` hook | plugin `hooks.json` | Terse style is injected each prompt (soft, already in place). |

## Environment checked

- Repo `claude-config`, branch `main`, HEAD `d9c6a0f`. `~/.claude/{CLAUDE.md,settings.json,hooks/*}` are symlinks or identical copies of the repo (E1).
- `~/.claude/rules/work.md` and `org.md` exist only locally (not in repo, by design: "local only").
- Plugins active: shepherd 0.7.0, be-terse.

## Hypotheses

| # | Hypothesis | Status | Settled by |
|---|---|---|---|
| H1 | Most rules have no deterministic check; they rely on the model reading markdown. | confirmed | Inventory below: 6 rules enforced (E2, E5–E7, E13, E14), ~45 rules advisory. |
| H2 | The existing Bash guards are reliable. | refuted | E3, E4: false negatives and false positives from substring regex. |
| H3 | shepherd already covers git safety everywhere. | refuted | E9: only on branches with shepherd state. |
| H4 | Git-level hooks would conflict with shepherd. | refuted | E10: shepherd chains to global `core.hooksPath`. |

## Root cause

Rules are written as prose in `~/.claude/CLAUDE.md`, `~/.claude/rules/*.md` and skill files. Only a few have a hook, setting or tool behind them, and the git guards that exist match raw text (`claude/settings.json` PreToolUse inline command; `claude/hooks/git-push-alone.sh:9`), so they both miss variants and fire on harmless strings. Nothing runs at the git layer, so a commit made by any path is unchecked.

### Rule inventory, by how it can be enforced

Mechanisms, strongest first:
- **D — deny**: `permissions.deny` or PreToolUse exit 2 / `permissionDecision: "deny"`. Hard stop.
- **A — ask**: PreToolUse `permissionDecision: "ask"`. Forces a user prompt; fits "do X only when I ask".
- **G — git hook**: global `core.hooksPath` (`pre-commit`, `commit-msg`, `pre-push`). Catches every commit, from any tool.
- **L — linter config**: ruff/ty/complexipy/jscpd rules, surfaced by the existing post-edit and stop gates.
- **C — check script**: PostToolUse/Stop script that inspects a file or diff and feeds back or blocks.
- **J — LLM judge**: Stop/SubagentStop hook of `type: "prompt"` or `"agent"` (model-evaluated). Probabilistic; costs latency.
- **S — soft**: cannot be checked; stays prose.

| Rule (source) | Today | Best mechanism | How |
|---|---|---|---|
| No commit on a default branch without asking (CLAUDE.md) | none | **A** + **G** | PreToolUse: `git commit` while branch is in the default-branch list (config, default `main` plus the repo's base branch) → ask. Git `pre-commit`: refuse on those branches unless `ALLOW_MAIN_COMMIT=1`. |
| No new branches unless asked (CLAUDE.md) | partial, buggy (E3) | **A** | Parse each simple command: `checkout -b/-B`, `switch -c/-C`, `branch <name>`, `worktree add -b` → ask. Skip when shepherd state exists (run authorizes branches). |
| Never commit/push unless asked (CLAUDE.md) | partial (E5, E9) | **A** | `git push` outside shepherd state → ask. `git commit` → ask only on a default branch (user decision, 2026-11-27); other branches pass. |
| Never merge (CLAUDE.md) | shepherd only | **D** | `permissions.deny: ["Bash(gh pr merge:*)"]` + parser rule for `gh api …/merge`. |
| No `reset --hard`, force push, `--no-verify` | partial (E2, E9) | **D** | Same parser; covers `-C`, extra spaces, `--force-with-lease`. |
| `git fetch` before merge/compare (CLAUDE.md) | none | **D** | `git merge`/`rebase`/`diff`/`log` naming `origin/…` when `.git/FETCH_HEAD` older than N min → block with "run git fetch". |
| Stage only touched files; no `git add .`/`-A`/`commit -a` (CLAUDE.md, git-commit skill) | none | **D** | Parser rule. |
| No Co-Authored-By / "Generated with Claude" (CLAUDE.md) | default only (E13) | **G** | `commit-msg` hook rejects those trailers. |
| Conventional, scoped commits (CLAUDE.md, git-commit skill) | none | **G** | `commit-msg` regex `^(feat\|fix\|refactor\|docs\|chore\|test\|perf\|ci\|build)\([a-z0-9-]+\)!?: `. |
| `pyproject.toml` + `uv.lock` together (git-commit skill) | none | **G** | `pre-commit`: one staged without the other → fail. |
| Never stage `.env`, secrets, backups, `.claude/shepherd/`, scratchpad (CLAUDE.md) | none | **G** | `pre-commit` path deny list (`.env*` except `.env.example`, `*.bak`, `*.orig`, `*~`, `.claude/shepherd/`, `/tmp/claude-*`). Add `gitleaks protect --staged` if installed (not installed today, E11). |
| No hard-wrap in PR bodies / Slack / Jira (CLAUDE.md, create-pr) | none | **C** | PreToolUse on `gh pr create/edit` (read `--body-file`) and Slack/Jira MCP tools: flag prose paragraphs broken by single newlines → block with reason. Heuristic; needs tests. |
| Slack: never send, draft only (draft-slack-message skill) | none | **D** | `permissions.deny` on `mcp__*__slack_send_message`, `mcp__*__slack_schedule_message`. |
| `uv`, never `python3`/`pip` (CLAUDE.md) | none | **D** | Parser rule: first word `python`, `python3`, `pip`, `pip3` → block with the `uv` equivalent. Allow inside `docker exec`/`ssh` args. |
| Do not leave containers/background processes (CLAUDE.md) | warn, invisible (E8) | **C** | SessionStart: save `docker ps -q`. Stop: diff; new containers → `decision: block` with names. Same for background shells if listable. |
| Imports at top; no `TYPE_CHECKING`, no conditional import (CLAUDE.md) | partial via ruff defaults | **L** | ruff `PLC0415`, `E402`; `TID251` banned-api for `typing.TYPE_CHECKING`. `try/except ImportError` → small ast check (C). |
| Keep `Optional[X]` (CLAUDE.md) | none | **L** | ruff ignore `UP007`/`UP045`. |
| pathlib, annotations, complexity (CLAUDE.md) | complexity only | **L** | ruff `PTH`, `ANN`; complexipy already (E6, E7). |
| `__init__.py` empty (CLAUDE.md) | none | **C** | PostToolUse: non-empty `__init__.py` → feedback; Stop gate → block. |
| No `getattr`/dict lookup on payloads (CLAUDE.md) | none | **L/C** | ruff `B009/B010` (constant getattr). Dict lookups on models: ast-grep rule, partial. |
| Duplicated blocks in new code (CLAUDE.md "no duplicated test helpers") | jscpd at Stop (E7) | **L** | Already there. Optional: run jscpd on test files at post-edit for earlier feedback. |
| Never remove config/infra entries the task does not name (CLAUDE.md) | none | **C** | PostToolUse on `docker-compose*.y*ml` / `.env*`: compare service names and env keys with `HEAD`; removed keys → ask. Generic; the job layer adds its named keys on top. |
| Subagent: always pass `model` (CLAUDE.md) | none | **D** | PreToolUse matcher `Agent`: no `model` and `subagent_type` not in a list of plugin agents that set one → block. |
| No implementation in subagents (CLAUDE.md) | none | **D** | PreToolUse `Edit\|Write\|MultiEdit\|NotebookEdit` with `agent_id` in input → block (see A2). |
| Skill/agent files: no `tools:` allowlist (CLAUDE.md) | none | **C** | PostToolUse on `**/SKILL.md`, `**/agents/*.md`: frontmatter has `tools:` → feedback. |
| Docs into repo, not scratchpad (CLAUDE.md) | none | **S/C** | Weak: PreToolUse Write of `*.md` under the scratchpad path → feedback. |
| Review own diff before "done" (CLAUDE.md) | shepherd only | **J** | Stop hook: uncommitted diff and no review marker this turn → block "review the diff". Or `type: "agent"` Stop hook that reviews. |
| No explanatory comments; minimal diff; no unasked scope; don't reword UI text; adjacent bugs as one line (CLAUDE.md) | none | **J** | One `type: "prompt"` Stop hook over the turn's diff with a short checklist. Probabilistic. |
| Exploration cap ~5 reads (CLAUDE.md) | none | **C (soft)** | Count Read calls before first Edit per prompt; inject a reminder at 6. Feedback only. |
| Response style, AskUserQuestion, one decision at a time, facts backed by query, no invented roles (CLAUDE.md) | be-terse (E16) | **S** | Stay prose. |
| Use shepherd for feature/bug work (CLAUDE.md) | none | **S/A** | Optional: first `Edit` in a repo with no shepherd state and no diagnosis → inject reminder. Mostly S. |

### Job layer (work.md, org.md): out of the core harness

These rules matter only at the job. They depend on job env vars, hosts, data stores and internal SDKs. They stay out of `claude-config`, which stays portable (CLAUDE.md "Skill & doc design"). They go in a separate, private layer that is enabled only on the work machine (see Fix direction, slice 9). The core harness does not wait on them.

| Rule (source) | Best mechanism | How |
|---|---|---|
| `os.getenv` banned; use `environment_variables.py` (work.md) | **L** | ruff `TID251` banned-api in each job repo's `pyproject.toml`. |
| Sonar duplication gate, parametrize (work.md) | **L** | Covered by core jscpd; thresholds per job repo. |
| Keep `VAR=${VAR}` compose style; keep SDK env vars (`URL_WORKER_ROTATION_API`, `WORKER_NUMBER`, `PROCESS_NAME`, `WORKER_ROTATION_API_*_TIMEOUT`, `SENTRY_DSN`, `WATCHDOG_HEARTBEAT_PATH`), watchdog and `autoheal` (work.md, org.md) | **C** | Extends the core compose/env diff check with a named-key list. |
| Snowflake: no correlated EXISTS, no named WINDOW (work.md) | **C** | Regex on Snowflake MCP calls, `snow sql`, `*.sql` edits → block with reason. |
| ScyllaDB DELETE keyed correctly (work.md) | **A** | `cqlsh … DELETE` → ask. |
| Never target prod; never install on EC2 (org.md) | **A/D** | `prod`/`production` segment in aws/ssh/ssm/kubectl/snow args → ask; installs over ssh/ssm → deny. |
| VPN + enigma env vars before live runs (org.md) | **D** | Cluster commands with a missing env var or VPN down → block with the exact command. |
| `enigma-main` is a default branch (org.md) | **A** | Job layer adds `enigma-main` to the core guard's default-branch list (core reads the list from config, default `main`). |

Count: about 30 of ~50 rules move to D/A/G/L/C in the core; ~7 to J; ~8 to the job layer; the rest stay S.

## Reproduction

`/Users/rhafid/claude-config/.git/shepherd/_diagnose/scratch/harness-rule-enforcement/probe.sh`, output in `probe.out` next to it:

```
BLOCK | git reset --hard
BLOCK | git checkout -b x
allow | git switch -c x
allow | git checkout -B x
allow | git branch x
allow | git commit -m x
allow | git add -A
allow | pip install requests
allow | git push --force
allow | gh pr merge 1
BLOCK | echo 'git reset --hard is bad'
allow | git  reset --hard
allow | git -C . reset --hard
rc=2 | git commit -m x && git push
rc=0 | git push
rc=0 | echo 'never do x && git push'
```

The fix session turns each line into a guard test case.

## Ruled out

- Live config drift: repo and live `settings.json` match (E1).
- Conflict between a global git hooks dir and shepherd (E10).
- Missing tools for the Python tier (E15).

## Assumptions to confirm

- **A1**: Stop hook plain stdout with exit 0 is not shown to the model (only a JSON `decision`/`reason` or exit 2 is). Confirm in current Claude Code hook docs before rewriting E8.
- **A2**: PreToolUse input carries `agent_id` for calls made inside a subagent (herdr hook reads it for SessionStart). Confirm with a one-line logging hook before relying on it.
- **A3**: `type: "prompt"` / `type: "agent"` hooks are supported on Stop in the installed Claude Code version. Confirm in docs.
- **A4**: `permissionDecision: "ask"` still prompts in `defaultMode: auto`. Confirm with one test call.
- **A5**: `permissions.deny` Bash prefix rules apply to each part of a compound command. If not, keep the parser hook as the real guard and use deny for MCP tools only.
- **A6** (job layer only): user-level `~/.claude/settings.local.json` is loaded and can register hooks. Not needed if the job layer is a plugin.

## Open checks

| Check | Owner | Exact command or steps |
|---|---|---|
| A1–A5 | Claude (fix session) | Read hook docs; one throwaway logging hook per assumption in a scratch project. |
| Job layer only, not blocking the core: cluster command list, enigma env var names, VPN check | user | Answer when slice 9 starts. |

## Fix direction

Build the portable core in `claude-config`, tested, in this order. Each slice is one PR. No job names, hosts, env vars or SDKs in the core. Lists that differ per machine (default branches, protected keys) are config with generic defaults, so the job layer can extend them.

1. **Bash guard rewrite.** Replace the inline regex and `git-push-alone.sh` with one script `claude/hooks/guard-bash` that splits the call into simple commands (handles `&&`, `;`, `|`, `-C <dir>`, extra spaces, quoted strings, heredocs) and applies a rule table: deny / ask / pass, with the reason text. Rules: branch creation, commit on default branch, push outside shepherd, merge, reset --hard, force, `--no-verify`, `add .`/`-A`/`commit -a`, `python`/`pip`, fetch freshness. Keep the chained-push rule (shepherd needs it). Read shepherd state presence only, never its internals. The rule table accepts extra rules from an optional file, for the job layer.
2. **Test harness for hooks.** `tests/` with JSON fixtures per rule, run by a single script (bats or `uv run pytest`). Every probe line in Reproduction becomes a case. Add a pre-commit or CI run of it in this repo, so a hook change can't regress silently.
3. **Global git hooks.** `claude/githooks/{pre-commit,commit-msg}` linked by `install.sh`, `core.hooksPath` set globally. Trailer ban, conventional scoped subject, path deny list, pyproject/uv.lock pairing, default-branch refusal.
4. **permissions.deny.** Slack send/schedule MCP tools, `gh pr merge`.
5. **Python lint profile.** A shared ruff snippet (PLC0415, E402, TID251 for `TYPE_CHECKING`, PTH, ANN, B009/B010, ignore UP007/UP045) that repos extend. `py-post-edit.sh` keeps running it. Add the `__init__.py` and `try/except ImportError` checks.
6. **Config/file checks.** Generic compose/env removed-key guard, skill `tools:` frontmatter check, container diff at Stop (replace E8).
7. **Subagent guards.** `model` required on Agent; no edits with `agent_id` (after A2).
8. **LLM judge (optional, last).** One Stop `prompt` hook with the scope/comment/reword checklist; measure its false-block rate before keeping it.
9. **Job layer (separate, later).** Not in `claude-config`. A private plugin with its own `hooks.json`, enabled only on the work machine, holding the job-layer rules above and extending the core's lists (`enigma-main`, SDK keys). Answer the job open check first. The shepherd/be-terse plugin pattern already used here shows this works; a hooks entry in `~/.claude/settings.local.json` is the other option only if that file is confirmed to load hooks (A6).

Out of scope:
- `git-commit` skill says "Never push changes"; CLAUDE.md says `/shepherd:run` authorizes pushes. Wording conflict, file separately.
- `rules/work.md` and `rules/org.md` are not versioned in this repo; decide separately whether to track them in a private repo.

## Acceptance criteria

| # | Criterion | Test |
|---|---|---|
| 1 | Every "allow" line in Reproduction that a rule targets is denied or asked; `echo '…'` strings pass. | Guard fixture suite; fails on today's hooks. |
| 2 | `git commit` with a Claude trailer, or a non-conventional subject, is rejected at the git layer. | `commit-msg` test in a temp repo. |
| 3 | Staging `.env` or `.claude/shepherd/x` fails `pre-commit`. | Temp-repo test. |
| 4 | Slack send tools cannot run. | Settings test: deny list contains them. |
| 5 | Containers started during a session block Stop with their names; pre-existing ones do not. | Stop-hook fixture with fake `docker ps` output. |
| 6 | Hook tests run on every commit in `claude-config`. | Pre-commit/CI config present and green. |

## Deadlines

- none

## Next session

`/shepherd:run docs/diagnoses/2026-11-27-harness-rule-enforcement.md` — start with slices 1 and 2 together (guard + its tests). Confirm A1–A5 first. Slices 1–8 only; slice 9 (job layer) is separate work in a private repo, not in this one. Commit rule: ask only on default branches (user decided). Note: the current guards block command text inside strings and heredocs; write probe fixtures with the file tool, not shell heredocs.
