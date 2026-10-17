#!/bin/sh
# Stop gate for Python repos with uncommitted .py changes. A failure blocks the
# stop up to 3 times per prompt. After that the user is told, and the same tree
# is not blocked again until it changes.
input=$(cat)
cd "$CLAUDE_PROJECT_DIR" 2>/dev/null && [ -f pyproject.toml ] || exit 0
git rev-parse --verify -q HEAD >/dev/null || exit 0
files=$({
	git diff --name-only --diff-filter=d HEAD -- '*.py'
	git ls-files -o --exclude-standard -- '*.py'
} | sort -u)
[ -n "$files" ] || exit 0

state=${TMPDIR:-/tmp}/claude-py-gate/$(printf '%s' "$PWD" | shasum | cut -c1-12)
mkdir -p "$state"
tree=$({
	git diff HEAD
	printf '%s\n' "$files" | xargs cat
} | shasum | cut -c1-40)
[ "$(cat "$state/passed" 2>/dev/null)" = "$tree" ] && exit 0
[ "$(cat "$state/reported" 2>/dev/null)" = "$tree" ] && exit 0

report=""
check() {
	name=$1
	shift
	out=$("$@" 2>&1) || report="$report
== $name failed ==
$out"
}
pytest_gate() {
	uv run --no-sync pytest -q -x
	rc=$?
	[ "$rc" -eq 5 ] && return 0
	return "$rc"
}
check pytest pytest_gate
printf '%s\n' "$files" | tr '\n' '\0' | xargs -0 sh -c 'complexipy --failed --plain "$@"' _ >"$state/complexipy.log" 2>&1 ||
	report="$report
== complexipy failed ==
$(cat "$state/complexipy.log")"
printf '%s\n' "$files" | tr '\n' '\0' | xargs -0 sh -c 'npx -y jscpd@4 --min-lines 5 --threshold 3 --reporters console "$@"' _ >"$state/jscpd.log" 2>&1 ||
	report="$report
== jscpd failed ==
$(grep -v '^    at ' "$state/jscpd.log")"

attempts=$state/attempts
[ "$(printf '%s' "$input" | jq -r '.stop_hook_active')" = true ] || echo 0 >"$attempts"
if [ -z "$report" ]; then
	echo "$tree" >"$state/passed"
	exit 0
fi
n=$(($(cat "$attempts" 2>/dev/null || echo 0) + 1))
echo "$n" >"$attempts"
if [ "$n" -le 3 ]; then
	jq -n --arg reason "Quality gate failed. Fix these before you finish:$report" \
		'{decision: "block", reason: $reason}'
	exit 0
fi
echo "$tree" >"$state/reported"
failed=$(printf '%s\n' "$report" | sed -n 's/^== \(.*\) failed ==$/\1/p' | paste -sd ' ' -)
jq -n --arg msg "Quality gate still fails after 3 fix attempts: $failed" '{systemMessage: $msg}'
