import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "claude" / "hooks" / "guard-bash.py"
CASES_FILE = Path(__file__).parent / "guard_bash_cases.json"


@dataclass(frozen=True)
class Case:
    id: str
    command: str
    expect: str
    branch: str = "feature"
    base: str | None = None
    shepherd: bool = False
    fetched_minutes_ago: int | None = None
    config: dict | None = None


CASES = [Case(**raw) for raw in json.loads(CASES_FILE.read_text())]


def make_repo(root: Path, case: Case) -> Path:
    repo = root / "repo"
    subprocess.run(["git", "init", "-q", "-b", case.branch, str(repo)], check=True)
    git_dir = repo / ".git"
    if case.base:
        subprocess.run(["git", "-C", str(repo), "symbolic-ref", "refs/remotes/origin/HEAD",
                        f"refs/remotes/origin/{case.base}"], check=True)
    if case.shepherd:
        state = git_dir / "shepherd" / case.branch.replace("/", "__") / "state.json"
        state.parent.mkdir(parents=True)
        state.write_text("{}")
    if case.fetched_minutes_ago is not None:
        fetch_head = git_dir / "FETCH_HEAD"
        fetch_head.write_text("")
        stamp = time.time() - case.fetched_minutes_ago * 60
        os.utime(fetch_head, (stamp, stamp))
    return repo


def run_guard(command: str, cwd: Path, config: Path) -> str:
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
               "tool_input": {"command": command}, "cwd": str(cwd)}
    result = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload),
                            capture_output=True, text=True, check=True,
                            env={**os.environ, "CLAUDE_GUARD_BASH_CONFIG": str(config)})
    if not result.stdout.strip():
        return "allow"
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_guard_bash(case: Case, tmp_path: Path) -> None:
    repo = make_repo(tmp_path, case)
    config = tmp_path / "guard-bash.json"
    if case.config is not None:
        config.write_text(json.dumps(case.config))
    assert run_guard(case.command, repo, config) == case.expect
