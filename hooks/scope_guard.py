"""PreToolUse hook (Edit|Write|MultiEdit|NotebookEdit): keep edits inside the active TASK.

It only acts inside a git worktree that has an active home-office task, i.e. a
`home-office-task.json` in that worktree's private git dir (written by
`scripts/ho.py task-start`). Everywhere else it does nothing, so normal sessions
are never affected.

Inside an active task it denies:
  - any path matching a `deny` rule (project hard rules, e.g. migrations outside one repo);
  - any path outside the TASK's closed file list (`files` / `allow`), when the task has one;
  - Bash/PowerShell commands aimed at that worktree that write files (redirections, tee,
    sed -i, rm/mv/cp…) or change git state: file changes must go through Edit/Write.
The checks gate (SubagentStop) remains the backstop for anything this misses.

Fail-open: on any error it allows the call.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (IS_WINDOWS, denied, emit, find_worktree_root, in_scope,  # noqa: E402
                     load_scope, posix_rel, read_stdin_json)


def deny(reason: str) -> None:
    emit({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    })


PATH_TOKEN = re.compile(r"""(?:[A-Za-z]:[\\/]|/)[^\s'"`;|&<>()]+""")
SAFE_REDIRECTS = re.compile(r"\d?>&\d|&>\s*/dev/null|\d?>{1,2}\s*/dev/null|\d?>{1,2}\s*NUL\b|>\s*\$null")
WRITE_PATTERNS = [
    (re.compile(r">"), "output redirection"),
    (re.compile(r"(^|[\s;|&(])tee\s"), "tee"),
    (re.compile(r"(^|[\s;|&(])(sed|perl)\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*i"), "in-place edit"),
    (re.compile(r"(^|[\s;|&(])(rm|mv|cp|touch|truncate|dd|install|ln|mkdir|rmdir|unlink)\s"), "file command"),
    (re.compile(r"(^|[\s;|&(])(Set-Content|Add-Content|Out-File|New-Item|Remove-Item|Move-Item|Copy-Item)\b",
                re.IGNORECASE), "PowerShell file command"),
    (re.compile(r"git\s+(-C\s+\S+\s+)?(add|commit|push|checkout|switch|restore|reset|stash|rebase|merge|"
                r"clean|cherry-pick|revert|apply|am|rm|mv)\b"), "git write command"),
]


def to_local(token: str) -> str:
    """Git Bash style /c/x on Windows -> C:/x."""
    if IS_WINDOWS and re.match(r"^/[A-Za-z]/", token):
        return f"{token[1].upper()}:{token[2:]}"
    return token


def active_task_in_command(command: str, cwd: str):
    """(worktree, scope) of an active task the command points at, if any."""
    candidates = [cwd] + [to_local(t) for t in PATH_TOKEN.findall(command)]
    for cand in candidates:
        if not cand:
            continue
        probe = cand if os.path.isdir(cand) else os.path.dirname(cand)
        if not probe or not os.path.exists(probe):
            continue
        wt = find_worktree_root(probe)
        if wt:
            scope = load_scope(wt)
            if scope and scope.get("gate") not in ("pass", "fail"):
                return wt, scope
    return None, None


def check_bash(data: dict) -> None:
    command = (data.get("tool_input") or {}).get("command") or ""
    if not command:
        return
    wt, scope = active_task_in_command(command, data.get("cwd") or "")
    if not wt:
        return
    stripped = SAFE_REDIRECTS.sub(" ", command)
    for pattern, label in WRITE_PATTERNS:
        if pattern.search(stripped):
            deny(f"home-office: during {scope.get('task') or 'a TASK'} Bash may only read and run "
                 f"commands/checks ({label} detected). Make file changes with the Edit or Write tools, "
                 f"which are scope-checked. Never commit, stage or switch branches.")
            return


def main() -> None:
    if os.environ.get("HOME_OFFICE_GUARD") == "0":
        return
    data = read_stdin_json()
    if data.get("tool_name") in ("Bash", "PowerShell"):
        check_bash(data)
        return
    tool_input = data.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path")
    if not path:
        return
    cwd = data.get("cwd") or os.getcwd()
    abs_path = path if os.path.isabs(path) else os.path.join(cwd, path)

    worktree = find_worktree_root(os.path.dirname(os.path.abspath(abs_path)))
    if not worktree:
        return
    scope = load_scope(worktree)
    if not scope:
        return

    rel = posix_rel(abs_path, worktree)
    task = scope.get("task") or "the active TASK"

    reason = denied(rel, scope)
    if reason:
        deny(f"home-office hard rule: `{rel}` cannot be written here ({reason}). "
             f"Do not work around it. Stop and report `needs-plan-change` for {task}.")
        return

    if not in_scope(rel, scope):
        listed = ", ".join(scope.get("files") or []) or "(see TASK)"
        deny(f"home-office scope: `{rel}` is not in the file list of {task} ({listed}). "
             f"Do not edit it by other means. If the TASK really needs it, stop and report "
             f"`needs-plan-change` with the reason.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # fail-open
        sys.stderr.write(f"home-office scope_guard: {exc}\n")
