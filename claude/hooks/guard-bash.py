#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# ///
"""PreToolUse guard for Bash calls.

Splits the call into simple commands the way the shell does (quotes, operators,
newlines, heredocs, redirects, substitutions, `sh -c`), so text inside strings
never matches and spacing or `git -C` never hides a command. Each command is
checked against a rule table; the strictest decision wins.

Optional config, `$CLAUDE_GUARD_BASH_CONFIG` or `~/.claude/guard-bash.json`:
`{"default_branches": [...], "rules": [{"match": regex, "decision": "ask"|"deny", "reason": text}]}`.
`default_branches` extends `main` and the repo's `origin/HEAD` branch. Each rule
regex is searched in the command's words joined by single spaces.
"""

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import IntEnum
from functools import cached_property
from pathlib import Path


class Decision(IntEnum):
    ALLOW = 0
    ASK = 1
    DENY = 2


@dataclass(frozen=True)
class Finding:
    decision: Decision
    reason: str


@dataclass(frozen=True)
class ExtraRule:
    pattern: re.Pattern[str]
    decision: Decision
    reason: str


@dataclass(frozen=True)
class Config:
    default_branches: frozenset[str]
    rules: tuple[ExtraRule, ...]


@dataclass(frozen=True)
class HookInput:
    command: str
    cwd: Path

    @classmethod
    def from_json(cls, raw: str) -> "HookInput":
        data = json.loads(raw)
        return cls(command=data["tool_input"]["command"], cwd=Path(data["cwd"]))


@dataclass(frozen=True)
class GitCall:
    sub: str
    args: list[str]
    cwd: Path
    configs: list[str]


FETCH_MAX_AGE_SECONDS = 600
SHELLS = {"sh", "bash", "zsh"}
PREFIX_WORDS = {"command", "builtin", "exec", "nohup", "time", "env", "sudo", "nice",
                "{", "}", "!", "if", "then", "do", "else", "elif", "while", "until"}
WRAPPER_VALUE_OPTIONS = {"sudo": {"-u", "-g", "-U", "-C", "-D", "-h", "-p"},
                         "env": {"-u", "-C"}, "nice": {"-n"}}
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
PYTHON = re.compile(r"(python|pip)(3(\.\d+)?)?")
ORIGIN_REF = re.compile(r"(^|[^\w-])origin/")
GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}
BRANCH_NON_CREATE = {"-d", "-D", "--delete", "-m", "-M", "--move", "-l", "--list", "--contains",
                     "--no-contains", "--merged", "--no-merged", "--points-at", "--show-current",
                     "-u", "--set-upstream-to", "--unset-upstream", "--edit-description",
                     "-a", "--all", "-r", "--remotes", "-v", "-vv", "--verbose", "--sort", "--format"}
GH_WRITE_FLAGS = {"-f", "-F", "--field", "--raw-field", "--input"}

R_BRANCH = "ask the user before creating a branch (CLAUDE.md: no new branches unless asked)."
R_COMMIT_DEFAULT = "committing on a default branch ({}): ask the user first."
R_PUSH = "pushing outside a shepherd run: ask the user first."
R_CHAIN = "run `git push` / `gh pr merge` as its own command, after the commit has run."
R_MERGE = "never merge a PR; hand it back to the user."
R_RESET = "`git reset --hard` discards work; ask the user to run it."
R_FORCE = "never force-push; push follow-up commits instead."
R_NO_VERIFY = "never skip git hooks (--no-verify, -n, core.hooksPath)."
R_ADD_ALL = "stage only the files you touched (no `git add .`/`-A`/`--all`, no `commit -a`)."
R_PYTHON = ("use uv, not python/pip: `uv run <script>`, `uv run -m <module>`, `uv add <pkg>`, "
            "`uv run --with <pkg> ...`, `uv venv`, `uvx <tool>`.")
R_FETCH = "run `git fetch` first; remote-tracking refs are older than 10 minutes."


class Tokenizer:
    """Splits shell text into simple commands (word lists) and nested scripts."""

    def __init__(self, text: str) -> None:
        self.text = text.replace("\\\n", "")
        self.pos = 0
        self.commands: list[tuple[tuple[int, ...], list[str]]] = []
        self.nested: list[str] = []
        self.words: list[str] = []
        self.word: list[str] | None = None
        self.role = ""
        self.heredocs: list[tuple[str, bool]] = []
        self.groups: list[int] = []
        self.group_count = 0

    def run(self) -> tuple[list[tuple[tuple[int, ...], list[str]]], list[str]]:
        while self.pos < len(self.text):
            self._step(self.text[self.pos])
        self._end_command()
        return self.commands, self.nested

    def _peek(self, offset: int = 1) -> str:
        return self.text[self.pos + offset: self.pos + offset + 1]

    def _step(self, ch: str) -> None:
        if ch in " \t":
            self._end_word()
            self.pos += 1
        elif ch == "\n":
            self._end_command()
            self.pos += 1
            self._skip_heredoc_bodies()
        elif ch == "#" and self.word is None:
            end = self.text.find("\n", self.pos)
            self.pos = len(self.text) if end == -1 else end
        elif ch in "<>" or (ch == "&" and self._peek() == ">"):
            self._redirect()
        elif ch in ";&|()":
            self._end_command()
            self._group(ch)
            self.pos += 1
        else:
            self._word_char(ch)

    def _word_char(self, ch: str) -> None:
        if self.word is None:
            self.word = []
        if ch == "\\":
            self.word.append(self._peek())
            self.pos += 2
        elif ch == "'":
            end = self.text.find("'", self.pos + 1)
            end = len(self.text) if end == -1 else end
            self.word.append(self.text[self.pos + 1:end])
            self.pos = end + 1
        elif ch == '"':
            self._double_quoted()
        elif not self._substitution(ch):
            self.word.append(ch)
            self.pos += 1

    def _substitution(self, ch: str) -> bool:
        if ch == "`":
            end = self.text.find("`", self.pos + 1)
            end = len(self.text) if end == -1 else end
            self.nested.append(self.text[self.pos + 1:end])
            self.pos = end + 1
            return True
        if ch == "$" and self._peek() == "(":
            self.pos = self._capture_parens(self.pos + 2)
            return True
        return False

    def _double_quoted(self) -> None:
        assert self.word is not None
        self.pos += 1
        while self.pos < len(self.text) and self.text[self.pos] != '"':
            ch = self.text[self.pos]
            if ch == "\\" and self._peek() in '"\\$`':
                self.word.append(self._peek())
                self.pos += 2
            elif not self._substitution(ch):
                self.word.append(ch)
                self.pos += 1
        self.pos += 1

    def _capture_parens(self, start: int) -> int:
        depth, quote, i = 1, "", start
        while i < len(self.text) and depth:
            ch = self.text[i]
            if quote:
                quote = "" if ch == quote else quote
            elif ch in "'\"":
                quote = ch
            else:
                depth += {"(": 1, ")": -1}.get(ch, 0)
            i += 1
        self.nested.append(self.text[start:i - 1 if depth == 0 else i])
        return i

    def _redirect(self) -> None:
        if self.word is not None and "".join(self.word).isdigit():
            self.word = None
        self._end_word()
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] in "<>&|-":
            self.pos += 1
        op = self.text[start:self.pos]
        heredoc = op.startswith("<<") and not op.startswith("<<<")
        self.role = ("heredoc-strip" if op.endswith("-") else "heredoc") if heredoc else "redirect"

    def _end_word(self) -> None:
        if self.word is None:
            return
        word = "".join(self.word)
        self.word = None
        role, self.role = self.role, ""
        if role.startswith("heredoc"):
            self.heredocs.append((word, role == "heredoc-strip"))
        elif not role:
            self.words.append(word)

    def _end_command(self) -> None:
        self._end_word()
        self.role = ""
        if self.words:
            self.commands.append((tuple(self.groups), self.words))
        self.words = []

    def _group(self, ch: str) -> None:
        if ch == "(":
            self.group_count += 1
            self.groups.append(self.group_count)
        elif ch == ")" and self.groups:
            self.groups.pop()

    def _skip_heredoc_bodies(self) -> None:
        for delimiter, strip_tabs in self.heredocs:
            while self.pos < len(self.text):
                end = self.text.find("\n", self.pos)
                end = len(self.text) if end == -1 else end
                line = self.text[self.pos:end]
                self.pos = end + 1
                if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                    break
        self.heredocs = []


class Repo:
    """Git facts for one directory, read on first use."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd

    def _git(self, *args: str) -> str | None:
        result = subprocess.run(["git", "-C", str(self.cwd), *args],
                                capture_output=True, text=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    @cached_property
    def branch(self) -> str | None:
        return self._git("symbolic-ref", "--short", "-q", "HEAD")

    @cached_property
    def base_branch(self) -> str | None:
        ref = self._git("symbolic-ref", "--short", "-q", "refs/remotes/origin/HEAD")
        return ref.removeprefix("origin/") if ref else None

    @cached_property
    def shepherd_active(self) -> bool:
        git_dir = self._git("rev-parse", "--absolute-git-dir")
        if not git_dir or not self.branch:
            return False
        return (Path(git_dir) / "shepherd" / self.branch.replace("/", "__") / "state.json").is_file()

    def fetch_age(self) -> float | None:
        path = self._git("rev-parse", "--path-format=absolute", "--git-path", "FETCH_HEAD")
        if not path or not Path(path).is_file():
            return None
        return time.time() - Path(path).stat().st_mtime


class Guard:
    """Applies the rule table to every simple command of one Bash call."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.repos: dict[Path, Repo] = {}

    def repo(self, cwd: Path) -> Repo:
        return self.repos.setdefault(cwd, Repo(cwd))

    def evaluate(self, script: str, cwd: Path) -> list[Finding]:
        commands, nested = Tokenizer(script).run()
        findings: list[Finding] = []
        cwds: dict[tuple[int, ...], Path] = {(): cwd}
        chained = False
        for group, words in commands:
            argv = self._strip_prefix(words)
            here = self._group_cwd(cwds, group)
            if not argv:
                continue
            if argv[0] == "cd":
                cwds[group] = self._change_dir(here, argv[1:])
                continue
            nested.extend(self._shell_script(argv))
            findings.extend(self._check(argv, here, chained))
            chained = True
        for sub_script in nested:
            findings.extend(self.evaluate(sub_script, cwd))
        return findings

    def _group_cwd(self, cwds: dict[tuple[int, ...], Path], group: tuple[int, ...]) -> Path:
        if group not in cwds:
            cwds[group] = self._group_cwd(cwds, group[:-1])
        return cwds[group]

    def _strip_prefix(self, argv: list[str]) -> list[str]:
        i = 0
        while i < len(argv) and (argv[i] in PREFIX_WORDS or ASSIGNMENT.match(argv[i])):
            word = argv[i]
            i += 1
            if word in PREFIX_WORDS:
                i = self._skip_options(argv, i, WRAPPER_VALUE_OPTIONS.get(word, set()))
        return argv[i:]

    def _skip_options(self, argv: list[str], i: int, value_options: set[str]) -> int:
        while i < len(argv) and argv[i].startswith("-"):
            i += 2 if argv[i] in value_options else 1
        return i

    def _change_dir(self, cwd: Path, args: list[str]) -> Path:
        target = next((a for a in args if not a.startswith("-")), "~")
        return (cwd / Path(target).expanduser()).resolve()

    def _shell_script(self, argv: list[str]) -> list[str]:
        if Path(argv[0]).name not in SHELLS:
            return []
        for i, arg in enumerate(argv[1:-1], start=1):
            if re.fullmatch(r"-[a-z]*c[a-z]*", arg):
                return [argv[i + 1]]
        return []

    def _check(self, argv: list[str], cwd: Path, chained: bool) -> list[Finding]:
        line = " ".join(argv)
        findings = [Finding(rule.decision, rule.reason)
                    for rule in self.config.rules if rule.pattern.search(line)]
        name = Path(argv[0]).name
        if PYTHON.fullmatch(name):
            findings.append(Finding(Decision.DENY, R_PYTHON))
        if name == "gh":
            findings.extend(self._check_gh(argv[1:], chained))
        git = self._parse_git(argv, cwd)
        if git:
            findings.extend(self._check_git(git, chained))
        return findings

    def _check_gh(self, args: list[str], chained: bool) -> list[Finding]:
        words = [a for a in args if not a.startswith("-")]
        if any(words[k:k + 2] == ["pr", "merge"] for k in range(len(words))):
            return [Finding(Decision.DENY, R_MERGE)] + ([Finding(Decision.DENY, R_CHAIN)] if chained else [])
        if "api" in words[:2] and self._is_api_merge(args):
            return [Finding(Decision.DENY, R_MERGE)]
        return []

    def _is_api_merge(self, args: list[str]) -> bool:
        if any("mergePullRequest" in a for a in args):
            return True
        merge_path = any(re.search(r"(^|/)pulls/[^/]+/merge/?$", a.split("?")[0]) for a in args)
        method = next((args[i + 1] for i, a in enumerate(args[:-1]) if a in ("-X", "--method")), "")
        writes = method.upper() == "PUT" or any(a.split("=")[0] in GH_WRITE_FLAGS for a in args)
        return merge_path and writes

    def _check_git(self, git: GitCall, chained: bool) -> list[Finding]:
        repo = self.repo(git.cwd)
        findings = [f for rule in GIT_RULES if (f := rule(self, git, repo))]
        if git.sub == "push" and chained:
            findings.append(Finding(Decision.DENY, R_CHAIN))
        return findings

    def default_branches(self, repo: Repo) -> set[str]:
        return {"main", *self.config.default_branches, *filter(None, [repo.base_branch])}

    def _parse_git(self, argv: list[str], cwd: Path) -> GitCall | None:
        if Path(argv[0]).name != "git":
            return None
        i, configs = 1, []
        while i < len(argv) and argv[i].startswith("-"):
            if argv[i] in GIT_VALUE_OPTIONS and i + 1 < len(argv):
                if argv[i] == "-C":
                    cwd = (cwd / Path(argv[i + 1]).expanduser()).resolve()
                elif argv[i] == "-c":
                    configs.append(argv[i + 1])
                i += 1
            i += 1
        return GitCall(argv[i], argv[i + 1:], cwd, configs) if i < len(argv) else None


def has_flag(args: list[str], short: str, *long: str) -> bool:
    for arg in args:
        if arg == "--":
            return False
        if arg in long or any(arg.startswith(f"{opt}=") for opt in long):
            return True
        if short and re.fullmatch(r"-[A-Za-z]+", arg) and short in arg[1:]:
            return True
    return False


def branch_rule(guard: Guard, git: GitCall, repo: Repo) -> Finding | None:
    args = git.args
    creates = {
        "checkout": has_flag(args, "", "-b", "-B", "--orphan"),
        "switch": has_flag(args, "", "-c", "-C", "--create", "--force-create", "--orphan"),
        "branch": has_flag(args, "", "-c", "-C", "--copy") or (
            any(not a.startswith("-") for a in args) and not set(args) & BRANCH_NON_CREATE),
        "worktree": args[:1] == ["add"] and has_flag(args, "", "-b", "-B"),
    }.get(git.sub, False)
    if creates and not repo.shepherd_active:
        return Finding(Decision.ASK, R_BRANCH)
    return None


def commit_rule(guard: Guard, git: GitCall, repo: Repo) -> Finding | None:
    if git.sub != "commit":
        return None
    if has_flag(git.args, "a", "--all"):
        return Finding(Decision.DENY, R_ADD_ALL)
    if has_flag(git.args, "n", "--no-verify"):
        return Finding(Decision.DENY, R_NO_VERIFY)
    if repo.branch in guard.default_branches(repo):
        return Finding(Decision.ASK, R_COMMIT_DEFAULT.format(repo.branch))
    return None


def add_rule(guard: Guard, git: GitCall, repo: Repo) -> Finding | None:
    sweeping = {".", "./", ":/", "*"} & set(git.args) or has_flag(git.args, "A", "--all")
    return Finding(Decision.DENY, R_ADD_ALL) if git.sub == "add" and sweeping else None


def push_rule(guard: Guard, git: GitCall, repo: Repo) -> Finding | None:
    if git.sub != "push":
        return None
    forced = has_flag(git.args, "f", "--force", "--force-with-lease", "--force-if-includes", "--mirror")
    if forced or any(a.startswith("+") for a in git.args):
        return Finding(Decision.DENY, R_FORCE)
    if has_flag(git.args, "", "--no-verify"):
        return Finding(Decision.DENY, R_NO_VERIFY)
    return None if repo.shepherd_active else Finding(Decision.ASK, R_PUSH)


def reset_rule(guard: Guard, git: GitCall, repo: Repo) -> Finding | None:
    return Finding(Decision.DENY, R_RESET) if git.sub == "reset" and "--hard" in git.args else None


def hooks_path_rule(guard: Guard, git: GitCall, repo: Repo) -> Finding | None:
    keys = [c.split("=")[0].lower() for c in git.configs]
    return Finding(Decision.DENY, R_NO_VERIFY) if "core.hookspath" in keys else None


def fetch_rule(guard: Guard, git: GitCall, repo: Repo) -> Finding | None:
    if git.sub not in {"merge", "rebase", "diff", "log"}:
        return None
    if not any(ORIGIN_REF.search(a) for a in git.args):
        return None
    age = repo.fetch_age()
    return Finding(Decision.DENY, R_FETCH) if age is None or age > FETCH_MAX_AGE_SECONDS else None


GIT_RULES = (branch_rule, commit_rule, add_rule, push_rule, reset_rule, hooks_path_rule, fetch_rule)


def load_config() -> Config:
    default = Path.home() / ".claude" / "guard-bash.json"
    path = Path(os.environ.get("CLAUDE_GUARD_BASH_CONFIG", default))
    data = json.loads(path.read_text()) if path.is_file() else {}
    rules = tuple(ExtraRule(re.compile(r["match"]), Decision[r["decision"].upper()], r["reason"])
                  for r in data.get("rules", []))
    return Config(frozenset(data.get("default_branches", [])), rules)


def decide(raw: str) -> tuple[Decision, str]:
    hook = HookInput.from_json(raw)
    findings = Guard(load_config()).evaluate(hook.command, hook.cwd)
    decision = max((f.decision for f in findings), default=Decision.ALLOW)
    reasons = dict.fromkeys(f.reason for f in findings if f.decision is decision)
    return decision, " ".join(reasons)


def main() -> None:
    """Fails closed: an error in the guard or its config denies the call, so a bug never lets it through."""
    try:
        decision, reason = decide(sys.stdin.read())
    except (OSError, ValueError, LookupError, RuntimeError, TypeError, re.error) as error:
        decision, reason = Decision.DENY, f"the guard failed ({error!r}); fix it or its config file."
    if decision is Decision.ALLOW:
        return
    output = {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision.name.lower(),
        "permissionDecisionReason": f"guard-bash: {reason}",
    }}
    print(json.dumps(output))


if __name__ == "__main__":
    main()
