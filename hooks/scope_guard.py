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
    The one exception is deleting files or folders in the TASK's delete list (`delete`) by
    exact path with `rm`, `unlink`, `git rm` or `Remove-Item`.
The checks gate (SubagentStop) remains the backstop for anything this misses.

Fail-open: on any error it allows the call.
"""

import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (IS_WINDOWS, denied, emit, find_worktree_root,  # noqa: E402
                     in_delete_list, in_scope, load_scope, posix_rel, read_stdin_json)


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


SEGMENT_SPLIT = re.compile(r"&&|\|\||[;|&\n]")
CD_COMMANDS = {"cd", "chdir", "pushd", "set-location", "sl"}
DELETE_COMMANDS = {"rm", "unlink", "del", "erase", "remove-item", "ri"}
PS_PATH_PARAMS = {"-path", "-literalpath", "-lp"}
PS_VALUE_PARAMS = {"-erroraction", "-ea", "-warningaction", "-wa", "-informationaction", "-infa"}
UNSAFE_TARGET = re.compile(r"[*?\[\]{}$`~]")  # globs, variables, substitutions, home


def tokens_of(segment: str):
    """Whitespace-split words with quotes removed; backslashes kept (Windows paths)."""
    try:
        words = shlex.split(segment, posix=False)
    except ValueError:
        return None
    return [w[1:-1] if len(w) >= 2 and w[0] == w[-1] and w[0] in "'\"" else w for w in words]


def resolve(token: str, base: str) -> str:
    path = to_local(token)
    return path if os.path.isabs(path) else os.path.join(base, path)


def cd_target(words, base: str):
    """New working directory if the segment is a plain `cd <dir>`, else None."""
    if not words or words[0].lower() not in CD_COMMANDS:
        return None
    args = [w for w in words[1:] if w.lower() not in PS_PATH_PARAMS]
    return resolve(args[0], base) if len(args) == 1 else None


def delete_targets(words, base: str):
    """(base, targets) if the segment is rm / unlink / git rm / Remove-Item, else None."""
    if not words:
        return None
    head = words[0].lower()
    if head == "git":
        i = 1
        while i < len(words) and words[i].startswith("-"):
            if words[i] == "-C" and i + 1 < len(words):
                base = resolve(words[i + 1], base)
                i += 2
            elif words[i] == "-c":
                i += 2
            else:
                i += 1
        if i >= len(words) or words[i] != "rm":
            return None
        args = words[i + 1:]
    elif head in DELETE_COMMANDS:
        args = words[1:]
    else:
        return None
    targets, i, only_paths = [], 0, False
    while i < len(args):
        word, low = args[i], args[i].lower()
        if not only_paths and word == "--":
            only_paths = True
        elif not only_paths and low in PS_PATH_PARAMS and i + 1 < len(args):
            targets.append(args[i + 1])
            i += 1
        elif not only_paths and low in PS_VALUE_PARAMS:
            i += 1
        elif not only_paths and word.startswith("-"):
            pass  # a switch: -f, -r, --cached, -Force, -Recurse…
        else:
            targets.append(word)
        i += 1
    # PowerShell takes comma-separated lists; splitting is only ever stricter for rm
    return base, [t.strip("'\"") for word in targets for t in word.split(",") if t.strip("'\"")]


def denied_inside(path: str, wt: str, scope: dict):
    """For a folder to delete: the deny reason of the first forbidden file inside it."""
    if not os.path.isdir(path) or not scope.get("deny"):
        return None
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            reason = denied(posix_rel(os.path.join(root, name), wt), scope)
            if reason:
                return reason
    return None


def planned_delete(words, base: str, wt: str, scope: dict):
    """None: not a delete. True: every target is in the TASK's delete list. str: why not."""
    found = delete_targets(words, base)
    if found is None or not scope.get("delete"):
        return None
    base, targets = found
    task = scope.get("task") or "the active TASK"
    if not targets:
        return f"home-office: name the files to delete explicitly ({task})."
    for target in targets:
        if UNSAFE_TARGET.search(target):
            return (f"home-office: delete `{target}` by its exact path; globs, variables and "
                    f"substitutions are not allowed in deletions during {task}.")
        path = resolve(target, base)
        try:
            rel = posix_rel(path, wt)
        except ValueError:  # another drive
            rel = "../" + target
        reason = denied(rel, scope) or denied_inside(path, wt, scope)
        if reason:
            return (f"home-office hard rule: `{rel}` cannot be deleted here ({reason}). "
                    f"Stop and report `needs-plan-change` for {task}.")
        if rel.startswith("../") or rel == ".." or not in_delete_list(rel, scope):
            listed = ", ".join(scope.get("delete") or [])
            return (f"home-office scope: `{rel}` is not in the delete list of {task} ({listed}). "
                    f"Do not delete it by other means. If the TASK really needs it, stop and "
                    f"report `needs-plan-change` with the reason.")
    return True


def check_bash(data: dict) -> None:
    command = (data.get("tool_input") or {}).get("command") or ""
    if not command:
        return
    wt, scope = active_task_in_command(command, data.get("cwd") or "")
    if not wt:
        return
    task = scope.get("task") or "a TASK"
    base = data.get("cwd") or wt
    stripped = SAFE_REDIRECTS.sub(" ", command)
    for segment in SEGMENT_SPLIT.split(stripped):
        segment = segment.strip()
        if not segment:
            continue
        words = tokens_of(segment)
        new_base = cd_target(words, base)
        if new_base:
            base = new_base
            continue
        verdict = planned_delete(words, base, wt, scope)
        if verdict is True:
            continue
        if verdict:
            deny(verdict)
            return
        for pattern, label in WRITE_PATTERNS:
            if pattern.search(segment):
                deny(f"home-office: during {task} Bash may only read and run commands/checks "
                     f"({label} detected). Make file changes with the Edit or Write tools, which "
                     f"are scope-checked. Files in the TASK's delete list may be removed with "
                     f"`rm <path>` or `git rm <path>`. Never commit, stage or switch branches.")
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
