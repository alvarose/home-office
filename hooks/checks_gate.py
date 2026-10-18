"""SubagentStop hook: an executor cannot finish its TASK with checks failing or files out of scope.

Acts only when the stopping subagent is a home-office executor (backend, frontend,
implementer) and its worktree has an active task (`home-office-task.json`, written by
`scripts/ho.py task-start`). The worktree is found from:
  1. a `worktree: <path>` line in the subagent's final report (`last_assistant_message`), or
  2. the `HOME-OFFICE-WORKTREE: <path>` line the conductor puts in the subagent's prompt.

Checks, in order:
  - the TASK's prepare commands (e.g. code generators), run inside the worktree; the files
    they write never count as changed by the TASK;
  - files changed since task start that are outside the TASK's file list or hit a deny rule
    (files in the TASK's delete list may be gone);
  - the TASK's checks (the repo's commands), run inside the worktree.

On failure it blocks the stop and sends the problems back, so the executor fixes them.
After `attempts` blocks (default 2) it lets the subagent stop and records `gate: fail`,
so the conductor escalates to the user instead of looping. On success: `gate: pass`.

Fail-open: on any error it lets the subagent stop.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (emit, evaluate_task, load_scope, read_stdin_json,  # noqa: E402
                     save_scope)

EXECUTORS = {"backend", "frontend", "implementer"}
REPORT_RE = re.compile(r"^\s*worktree:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
PROMPT_RE = re.compile(r"HOME-OFFICE-WORKTREE:\s*(.+?)\s*$", re.MULTILINE)


def role_of(agent_type: str) -> str:
    return (agent_type or "").split(":")[-1].strip().lower()


def worktree_from_transcript(path: str):
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i > 50:
                    break
                if "HOME-OFFICE-WORKTREE" not in line:
                    continue
                entry = json.loads(line)
                content = (entry.get("message") or {}).get("content")
                texts = [content] if isinstance(content, str) else [
                    c.get("text", "") for c in (content or []) if isinstance(c, dict)]
                for text in texts:
                    m = PROMPT_RE.search(text or "")
                    if m:
                        return m.group(1).strip().strip("`'\"")
    except Exception:
        return None
    return None


def agent_transcript(data: dict):
    path = data.get("agent_transcript_path")
    if path:
        return path
    # Fallback: <session transcript dir>/<session id>/subagents/agent-<id>.jsonl
    main = data.get("transcript_path") or ""
    agent_id = data.get("agent_id") or ""
    if main and agent_id:
        base = os.path.splitext(main)[0]
        candidate = os.path.join(base, "subagents", f"agent-{agent_id}.jsonl")
        if os.path.isfile(candidate):
            return candidate
    return None


def find_worktree(data: dict):
    m = REPORT_RE.search(data.get("last_assistant_message") or "")
    if m:
        path = m.group(1).strip().strip("`'\"")
        if os.path.isdir(path):
            return path
    path = worktree_from_transcript(agent_transcript(data))
    if path and os.path.isdir(path):
        return path
    return None


def main() -> None:
    if os.environ.get("HOME_OFFICE_GATE") == "0":
        return
    data = read_stdin_json()
    if role_of(data.get("agent_type")) not in EXECUTORS:
        return
    worktree = find_worktree(data)
    if not worktree:
        return
    scope = load_scope(worktree)
    if not scope or scope.get("gate") in ("pass", "fail"):
        return

    task = scope.get("task") or "this TASK"
    problems = evaluate_task(worktree, scope)

    if not problems:
        scope["gate"] = "pass"
        save_scope(worktree, scope)
        return

    blocks = int(scope.get("gate_blocks") or 0) + 1
    scope["gate_blocks"] = blocks
    scope["problems"] = problems
    limit = int(scope.get("attempts") or 2)
    if blocks > limit:
        scope["gate"] = "fail"
        save_scope(worktree, scope)
        emit({"systemMessage": f"home-office: {task} still fails after {limit} attempts. "
                               f"The conductor will escalate it to you."})
        return

    save_scope(worktree, scope)
    emit({
        "decision": "block",
        "reason": (f"home-office checks gate for {task} (attempt {blocks} of {limit}). "
                   f"You cannot finish yet:\n\n" + "\n\n".join(problems)
                   + "\n\nFix this within the TASK's files and report again. Do not weaken tests "
                     "or checks. If it is not fixable within the TASK, report `blocked` or "
                     "`needs-plan-change` and explain why."),
    })


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # fail-open
        sys.stderr.write(f"home-office checks_gate: {exc}\n")
