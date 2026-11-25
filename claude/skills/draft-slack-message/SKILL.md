---
name: draft-slack-message
description: Draft a Slack message or thread reply for the team, or rewrite one I wrote ("say it better"). Reads the thread first, writes in a gentle and direct tone, shows the draft for approval, then saves it as a Slack draft. Never sends.
---
Draft a Slack message about: $ARGUMENTS

## 1. Read before you write

- If there is a thread or channel link, read the whole thread first.
- List for yourself: what is already settled (who said it), what is still open, and the main question the message must answer.
- Never re-ask or restate a settled point. For each question in the draft, you must be able to cite the message that leaves it open.
- If a reply looks like a conflict only under one reading, take the reading that makes it consistent, or ask me. Do not put the doubt in the draft.
- Do not paraphrase colleagues or contradict them in the message.

## 2. Content

- Answer the main question first. Leave out facts that do not help answer it (processing times, side notes, internal steps).
- Give enough context that anyone who reads it cold understands what we did and why. A bare status line is too plain.
- State only facts verified in this session. Frame data facts as "based on what we checked in the tables". Mark anything unverified.
- Do not name who will do a task unless I said so. Use neutral actions ("close that connection").
- Do not name other teams' internals (jobs, DAGs, people who ran statements). Point "how it works inside" questions to the owning team.
- Do not imply work is pending or unvalidated unless I confirmed it.
- No date promises later than needed. If it can be done today, say today or give no date. Soft deadlines are near and concrete ("by end of day tomorrow", "by Thursday noon").

## 3. Tone

- Gentle, friendly and professional. Direct, never rude or blunt.
- Never use the word "but".
- Frame facts positively: lead with what improved or what works. Never make data loss, drops or failures sound normal or acceptable.
- Ask open points as direct questions, not as "please confirm X" items.
- No preamble. No closing pleasantries ("Happy to go through it anytime!", "Let me know if you have questions"). End on the last fact or question.
- No emoji unless I ask.

## 4. Shape

Pick the shape that fits. Do not force a line limit on a message that needs context.

- Short reply: 2-6 lines, plain sentences.
- Investigation result: `**TLDR, root cause + fix:**` with the PR link, then 3 bullets: what the symptom really was (correcting the thread's earlier guess, with numbers), any other contributing cause, the fix and its impact.
- Proposal or multi-topic ask: one context sentence with the link to the earlier thread, then `**1. Topic**` sections. Each section: current state, `Proposal:`, and the direct question if one is open.
- Update or announcement: what we did, why it matters, where to find it (link).

## 5. Formatting

- Drafts are saved with `slack_send_message_draft`, which takes standard Markdown: `**bold**`, `- ` lists (indent for nesting), `[text](url)` links. A single `*text*` renders as italic.
- Never hard-wrap lines.
- Use bold only for the header and section titles.

## 6. Review and save

1. Show the draft in chat in one fenced block. If the thread has settled points, show the settled/open list above it in 2-4 lines.
2. Wait for my approval. Apply my edits without changing anything else.
3. Save it with `slack_send_message_draft`, in the thread if there is one. Never send.
4. Check the response has a `draft_id`. If not, the save failed: tell me.
5. The API cannot update or delete a draft, and a second draft in the same thread silently fails. To change a saved draft, ask me to delete the old one in Slack first, then save again.

If I only want text to paste, or there is no Slack connector, stop after step 2.

## "Say it better"

When I give my own message to improve: keep its meaning and facts, apply the tone and shape rules above, and return one version. If you used a soft-deadline or polite-request phrase, keep it visible so I can learn it.
