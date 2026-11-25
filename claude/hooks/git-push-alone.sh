#!/usr/bin/env bash
# Blocks `git push` / `gh pr merge` chained after another command. PreToolUse hooks
# (shepherd's push gate) check the repo before the chain runs, so `git commit && git push`
# fails on a tree the commit has not written yet. A leading `cd <dir> &&` is allowed.
cmd=$(jq -r '.tool_input.command // empty')
cd_prefix='^[[:space:]]*cd[[:space:]]+("[^"]*"|'"'"'[^'"'"']*'"'"'|[^[:space:];&|]+)[[:space:]]*&&'
[[ "$cmd" =~ $cd_prefix ]] && cmd=${cmd:${#BASH_REMATCH[0]}}
git_opts='([[:space:]]+-[Cc][[:space:]]+[^[:space:]]+|[[:space:]]+--[^[:space:]]+)*'
chained='[;&|][[:space:]]*(git'"$git_opts"'[[:space:]]+push|gh[[:space:]]+pr[[:space:]]+merge)([[:space:]]|$)'
if [[ "$cmd" =~ $chained ]]; then
	echo 'Blocked: run `git push` / `gh pr merge` as its own command, after the commit has run.' >&2
	exit 2
fi
exit 0
