#!/usr/bin/env bash
# Claude Code status line — inspired by oh-my-zsh refined (Pure) theme

input=$(cat)

# Single jq pass (was three). Split on US (0x1f), not tab: bash collapses runs of
# IFS *whitespace*, which would shift fields when a value is absent.
IFS=$'\037' read -r cwd used win five <<<"$(printf '%s' "$input" | jq -r '
  [ (.workspace.current_dir // .cwd // ""),
    (.context_window.used_percentage // "" | tostring),
    (.context_window.context_window_size // "" | tostring),
    (.rate_limits.five_hour.used_percentage // "" | tostring)
  ] | join("")')"

# Short path: replace $HOME with ~
short_path="${cwd/#$HOME/\~}"

# Git branch and dirty marker (skip locks to avoid conflicts).
# symbolic-ref already fails outside a work tree, so no rev-parse guard needed.
branch=$(git -C "$cwd" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null)
dirty=""
if [ -n "$branch" ]; then
    git -C "$cwd" --no-optional-locks diff --quiet --ignore-submodules HEAD 2>/dev/null || dirty="*"
fi

parts=()

# git branch
if [ -n "$branch" ]; then
    parts+=("${branch}${dirty}")
fi

# context usage, with the window size so 200k vs 1M is unambiguous
if [ -n "$used" ]; then
    if [ -n "$win" ] && [ "$win" -ge 1000000 ] 2>/dev/null; then
        wlabel="1M"
    elif [ -n "$win" ]; then
        wlabel="$((win / 1000))k"
    else
        wlabel="?"
    fi
    parts+=("ctx: $(printf '%.0f' "$used")% of ${wlabel}")
fi

# 5-hour rate limit (absent on non-subscription plans — omitted when empty)
if [ -n "$five" ]; then
    parts+=("5h: $(printf '%.0f' "$five")%")
fi

# Join with separator
result=""
for part in "${parts[@]}"; do
    if [ -z "$result" ]; then
        result="$part"
    else
        result="$result  |  $part"
    fi
done

printf '%s' "$result"
