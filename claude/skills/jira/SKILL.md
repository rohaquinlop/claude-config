---
name: jira
description: Draft a Jira story or incident writeup
---
Write a Jira story/writeup about: $ARGUMENTS

Rules:
- State only facts verified in this session (root cause, fix, evidence). Never invent rationale, context, or pipeline/system names not confirmed.
- If a claim is unverified, put it under a separate "Assumptions to confirm" list — do not fold it into the main body.
- Do NOT hard-wrap lines; Jira renders literal breaks.
- Terse: short sections (Summary, Root Cause, Fix, Impact), no filler prose.
- One unified scope — don't split into a "follow-up" section unless I asked for a follow-up.
- Save the draft to the repo (e.g. `docs/` or `.sdd/`) if a repo is in scope; otherwise output in a single fenced block.
