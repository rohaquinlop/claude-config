---
name: pr-review
description: Review a pull request someone else wrote, with the shepherd review steps - a review bundle, fresh read-only reviewers, triage of every finding with evidence, and a new round each time the author pushes. Drafts standalone comments, posts only the ones I approve, and checks the posted count. Use when I ask to review, check, or comment on another person's PR. Not for my own changes (use shepherd:run).
---
Review pull request: $ARGUMENTS

You review. You do not push to the author's branch unless I ask.

## 1. Gather

1. `git fetch`. Then `gh pr view <pr> --json number,title,body,baseRefName,headRefOid,author,files,closingIssuesReferences`.
2. Task contract: the linked issue, else the PR description. Write down what the PR must do and what it must not change.
3. Read the whole PR discussion: top-level comments, review bodies and review threads. Note what is settled (a maintainer reply settles it). Do not reopen it.
4. Make two temporary worktrees outside the repo:
   - `POLICY_BASE`: the base branch tip. Its `CLAUDE.md` / `AGENTS.md` files are the rules.
   - `HEAD`: the PR head SHA. Use it to run checks and reproduce claims.
5. Run the repo's own checks on `HEAD` (tests, lint, type check) when they are cheap. Record each command and its result.

## 2. Bundle

Write one markdown file in a temp folder outside the repo:

- Task contract and settled decisions (quote them).
- Base SHA, head SHA.
- The exact diff: `git diff <base-sha>...<head-sha>`.
- The PR discussion.
- Checks run and results.
- From round 2: the prior findings, so each one is checked.

## 3. Review calls

Dispatch the `shepherd:reviewer` agent. The prompt holds only `BUNDLE: <path>`, `POLICY_BASE: <path>`, `call N of M`. Never add hints, your opinion or what to look for.

- Round 1: two calls in parallel with the agent's default model. If the diff is large or risky, a third call with `model: "opus"`.
- Later rounds: one call with the default model.
- At most 3 calls per round.

## 4. Triage

Merge the candidates and remove duplicates. Check every one yourself against the code at `HEAD`. Reproduce it when you can: a failing test, a script, a command.

- **Valid**: you confirmed it. Keep it, with the evidence.
- **Invalid**: dismiss it, with the evidence (file:line, the test that passes, the rule that allows it).
- **Cannot test** (needs credentials, VPN, a cluster): keep it as a question, not as a bug.
- **DECISION** (design choice, API trade-off, default): ask me. Do not pick for the author.

If more than 3 findings are left, run one verify call: a `general-purpose` agent with `model: "opus"`, given the bundle path and the kept findings. Its job is to refute each one with evidence. Drop the ones it refutes and you cannot defend.

## 5. Draft

Show me a table: number, file:line, severity (blocking / suggestion / nit), one line on the problem, the evidence. Then the dismissed findings in one line each.

I pick which ones to post. For each picked finding, draft the comment:

- It must stand alone. No internal finding numbers, agent names, rounds or session references.
- Say the problem, why it matters, and a concrete fix or a direct question.
- Gentle and direct. Thank outside contributors once, in the review body, not in each comment.
- Do not hard-wrap.

Then the review body (2-4 lines) and the event: `COMMENT`, `REQUEST_CHANGES` or `APPROVE`. I choose the event.

## 6. Post

Only after I approve the exact drafts.

1. Count the approved comments. Post them in one review with `gh api repos/{owner}/{repo}/pulls/<pr>/reviews` (`commit_id` = the reviewed head SHA, `event`, `body`, `comments[]` with `path`, `line`, `side`). Write the JSON to a file and pass it with `--input`.
2. Read the review back. Check that the number of inline comments equals the approved count. If not, tell me.

## 7. Next round

When the author pushes new commits, start again at step 1 with the new head. Pass the prior findings in the bundle. Report for each prior finding: fixed, not fixed, or changed. Review only the new delta for new findings. Do not re-raise a point the author answered with a valid reason.

## 8. Clean up

Remove both worktrees and the temp folder. Tell me what you removed.
