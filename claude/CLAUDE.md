# Global instructions (all projects)

## Git & Commits

- NEVER commit, push, or create branches unless explicitly asked. If I ask
  for a merge, do only the merge.
- Commit on the branch I am currently on. Do not create a new branch unless
  I say so.
- Never include `.sdd/` or session scratchpad artifacts in commits or PRs.
- Group changes into conventional commits (feat/fix/refactor/docs, scoped).
- Never include `Co-Authored-By` or "Generated with Claude" trailers.
- Before committing, run `git status` and stage only the files you touched —
  never sweep pre-staged `git mv`/`rm` changes into your commit.
- Never hard-wrap PR bodies or markdown at 80 columns; GitHub renders literal
  line breaks.

## Scope Discipline

- When I ask for options or a comparison, list them and STOP. Do not
  implement.
- Prefer the minimal diff. No extra inline comments, no duplicated test
  helpers — factor shared setup.
- Do not leave background processes or verification containers running;
  clean up and tell me what you started.
- After every implementation, before telling me it's done: review the diff
  yourself, report what you found, then fix it — the same loop I'd ask for
  manually. Do this by default; don't wait for me to say "review this."
- Only change what was asked. Do not add helpers, PR notes, doc blocks or
  "while I'm here" fixes without asking first.
- Do not reword existing user-facing text (help strings, labels, messages)
  unless the task is about that text.
- If you spot an adjacent bug, report it in one line and wait for a
  go-ahead.

## Workflow: SDD & shipping

- Feature and bug work follows explore → propose → apply → review → archive
  → commit → PR. Don't skip steps or merge them unless asked.
- Commits: small, logical, and scoped. Never stage backup files, .env files,
  or anything containing secrets.
- Before merging or comparing branches, always `git fetch` first. Never
  trust local remote-tracking refs.
- Live runs against remote environments may need VPN and project env vars. Check
  first. If either is missing, say so and give me the exact command to run
  instead of retrying.
- Facts and claims to stakeholders must be backed by a query result. Label
  anything unverified as a hypothesis.

## Subagent discipline

- Do NOT delegate implementation work to subagents — write code directly in
  the main thread. Subagents are for read-only exploration or independent
  validation only.
- Default to direct tools (Read/Grep/Bash) for anything answerable in a
  handful of calls. Don't dispatch a subagent just to "be thorough" — the
  subagent's full output lands back in this context anyway, so it never
  saves tokens for small lookups; it only adds latency and cost.
- If a task looks large enough that a subagent seems warranted, ask before
  spawning one rather than dispatching by default. Exception: if a skill
  or plugin I invoked tells you to dispatch a subagent (e.g. shepherd's
  reviewer), dispatch it without asking.
- When a subagent is genuinely warranted, prompt it to return a **concise
  synthesized finding** (short bulleted summary), not verbatim file dumps or
  quoted code blocks. Raw dumps land directly in the parent's context
  regardless of fork vs. fresh — asking for a summary is what actually saves
  tokens.
- If a skill, plugin or agent definition sets the model for a subagent
  (e.g. shepherd), follow it. The order below applies only when nothing
  else sets the model.
- Pick the subagent model in this order. Always pass `model` explicitly:
    1. `haiku` (first choice): recon, lookups, searches, mechanical or
       boilerplate work.
    2. `sonnet` (the default): use it when the task is too complex for
       haiku, for example research synthesis, multi-step investigation or
       a normal review.
    3. `opus` (last resort): use it only when sonnet is not enough, for
       example adversarial verification, ambiguous design tradeoffs,
       architecture, or a complex `Plan` task.
- Don't run a second validation pass on something already verified directly
  unless there's a concrete reason to doubt it.
- When writing or editing a subagent/skill definition file, omit its
  `tools:` allowlist so it inherits the full toolset. A hand-picked list
  goes stale and silently drops tools (e.g. Grep/Glob).

## Implementation discipline

- Cap exploration at ~5 file reads before writing code. If more context is
  genuinely needed, state what's missing and start with the smallest working
  change rather than continuing to read.
- Follow the given plan exactly. Don't add unplanned scope — no extra
  refactor, no caching layer, no "while I'm here" cleanup. Propose
  deviations first and wait.

## Debugging

- When you have the repo, execute the code path or run the command yourself
  instead of asking me to grep or check a DB.
- State root-cause hypotheses as hypotheses and verify them before
  implementing a fix.
- For UI/terminal/visual issues, ask for a screenshot or `:ls!`/`ps` output
  before theorizing.

## Response style

Verbosity and scope creep are the most common failure modes. When in doubt,
cut, don't add.

- Short sentences, one idea each. Plain, simplified technical English.
  Bullets over paragraphs.
- Lead with the 1-2 things that matter. No walls of text, no restated code,
  no summary tables, no "notes for reviewers" — unless asked.
- Report only what changed, what was verified, what failed.
- If I give a numbered list of fixes ("do #1, #3, #5"), act on them
  directly. Don't re-confirm the plan first.
- When you need me to decide, choose, or approve, use the structured
  question tool (AskUserQuestion). Never bury the ask in a paragraph.
- One decision at a time. If a second issue comes up, raise it as its own
  ask after the first is settled, not as a "by the way".
- Restate the state you rely on. Never write "as we decided above" or
  "keep in mind X": say X again.

## Writing (Slack / Jira / release notes)

- Default to terse: 3-6 lines for Slack, no preamble, no hedging.
- Do NOT hard-wrap text destined for Slack, Jira, or GitHub release bodies —
  those render literal line breaks.
- State only verified facts; never invent rationale or context. If a claim
  is unverified, say so or ask.
- Save generated docs into the repo (e.g. `docs/`), never to a session
  scratchpad.

## Skill & doc design

- Keep skills/docs portable: no hardcoded company- or team-specific names,
  stacks, or example paths, unless the skill is explicitly scoped to this
  org.
- Prefer one consolidated skill over several overlapping ones — merge
  related skills instead of creating near-duplicates.

## Python tooling: prefer `uv`

- Never invoke `python3`/`python`, `pip`, or `pip3` directly. Use `uv`
  equivalents instead:
    - Running a script or module → `uv run <script.py>` /
      `uv run -m <module>` (not `python3 script.py`).
    - Installing/adding a dependency → `uv add <pkg>` (not `pip install`).
    - One-off/ephemeral dependency for a single run → `uv run --with <pkg> ...`.
    - Creating a venv → `uv venv` (not `python3 -m venv`).
    - Running a standalone tool (e.g. black, ruff, httpie) → `uvx <tool>`
      (not `pip install <tool> && <tool>`).
    - Pinning/checking Python version → `uv python pin` / `uv python list`
      (not managing interpreters manually).
- This applies whenever the project already has a `uv.lock`,
  `pyproject.toml` managed by uv, or a `.venv` created by uv — and by
  default on any new Python work, since `uv` is available.
- If a project has no uv setup and clearly uses a different toolchain
  (e.g. poetry, conda, an existing non-uv venv with its own lock file),
  follow that project's existing convention instead of forcing `uv` in.
- If `uv` is not installed or a command genuinely requires bare
  `python3` (e.g. inside a Docker image without uv, or a shebang line),
  it's fine to fall back — just don't default to `python3`/`pip` when
  `uv` is a viable option.
- Respect existing typing conventions (e.g. `Optional[X]`) — don't let
  ruff/pyupgrade autofixes silently rewrite them.
- The type checker is `ty`, not pyright or mypy. Ignore pyright diagnostics.
- Prefer explicit type annotations and low cyclomatic complexity.
- Tests must pass on Windows CI too: use pathlib and avoid POSIX-only
  assumptions.
- No explanatory code comments. Never write a comment that restates what
  the code does — only comment when the WHY is non-obvious (a hidden
  constraint, a subtle invariant, a workaround for a specific bug). Use
  docstrings for that, not inline comments.
