#!/bin/sh
# Per-edit Python checks. Reports to Claude as context; never blocks or rewrites the file.
path=$(jq -r '.tool_input.file_path // empty')
case $path in *.py | *.pyi) ;; *) exit 0 ;; esac
cd "$CLAUDE_PROJECT_DIR" 2>/dev/null && [ -f pyproject.toml ] || exit 0
report=""
check() {
	name=$1
	shift
	out=$("$@" 2>&1) || report="$report
== $name failed ==
$out"
}
check ruff ruff check --force-exclude -q "$path"
check ty ty check --force-exclude "$path"
check complexipy complexipy --failed --plain "$path"
[ -n "$report" ] || exit 0
jq -n --arg ctx "Checks on $path:$report" \
	'{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}'
