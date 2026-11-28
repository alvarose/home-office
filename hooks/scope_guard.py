"""PreToolUse hook (Edit|Write|MultiEdit|NotebookEdit): keep edits inside the active TASK.

It only acts inside a git worktree that has an active home-office task, i.e. a
`home-office-task.json` in that worktree's private git dir (written by
`scripts/ho.py task-start`). Everywhere else it does nothing, so normal sessions
are never affected.

Inside an active task it denies:
  - any path matching a `deny` rule (project hard rules, e.g. migrations outside one repo);
  - any path outside the TASK's closed file list (`files` / `allow`), when the task has one.
    Both are matched by exact path or glob, so a folder only works written as `<folder>/**`;
  - Bash/PowerShell commands aimed at that worktree that write files (redirections into the
    worktree — output redirected to $TEMP, /tmp or any path outside it is fine —, inline
    scripts that write files, tee,
    sed -i, rm/mv/cp…) or change git state: file changes must go through Edit/Write.
    The one exception is deleting files or folders in the TASK's delete list (`delete`) by
    exact path with `rm`, `unlink`, `git rm` or `Remove-Item`.
The checks gate (SubagentStop) remains the backstop for anything this misses.

Only the session that opened the TASK (`session` in the scope, from task-start's
CLAUDE_CODE_SESSION_ID) and its executors are held to it. Another session working in the same
checkout (a `task` in a repo's main checkout, a parallel job) gets a warning instead of a block.

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
    (re.compile(r"(^|[\s;|&(])tee\s"), "tee"),
    (re.compile(r"(^|[\s;|&(])(sed|perl)\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*i"), "in-place edit"),
    (re.compile(r"(^|[\s;|&(])(rm|mv|cp|touch|truncate|dd|install|ln|mkdir|rmdir|unlink)\s"), "file command"),
    (re.compile(r"(^|[\s;|&(])(Set-Content|Add-Content|Out-File|New-Item|Remove-Item|Move-Item|Copy-Item)\b",
                re.IGNORECASE), "PowerShell file command"),
    (re.compile(r"git\s+(-C\s+\S+\s+)?(add|commit|push|checkout|switch|restore|reset|stash|rebase|merge|"
                r"clean|cherry-pick|revert|apply|am|rm|mv)\b"), "git write command"),
]


# Inline scripts (heredocs, -c / -r / -e) that write files: they bypass Edit/Write.
SCRIPT_WRITE = re.compile(
    r"""open\([^)]*['"][wax]b?\+?['"]|\.write_(text|bytes)\(|shutil\.(copy|move)|os\.(remove|rename|replace)\("""
    r"""|file_put_contents\s*\(|fopen\([^)]*['"][wax]|fs\.(writeFile|appendFile|rm|unlink)(Sync)?\("""
    r"""|\bSet-Content\b|\bOut-File\b""")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\s*(\n|$)", re.DOTALL)
QUOTED = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
REDIRECT = re.compile(r"(?<![-=<>])(\d?&?>{1,2})(?![=&])\s*([^\s;|&<>()]+)?")
TEMP_VARS = re.compile(r"^(\$\{?(TEMP|TMP|TMPDIR)\}?|%(TEMP|TMP)%|\$env:(TEMP|TMP))(?=[\\/]|$)", re.IGNORECASE)


def redirect_target_inside(target: str, base: str, wt: str):
    """True if a redirection target is in the worktree (or cannot be resolved), else False."""
    if not target:
        return True
    target = target.strip("'\"")
    if TEMP_VARS.match(target):
        return False  # $TEMP, $TMP, %TEMP%…: never inside a worktree
    if target.startswith("~"):
        target = os.path.expanduser(target)
    if "$" in target or "%" in target or "`" in target:
        return True  # an unknown variable: be safe
    if target in ("/tmp",) or target.startswith("/tmp/"):
        return False
    path = os.path.normcase(os.path.abspath(resolve(target, base)))
    root = os.path.normcase(os.path.abspath(wt))
    return path == root or path.startswith(root.rstrip("\\/") + os.sep)


def redirect_problem(segment: str, base: str, wt: str) -> bool:
    """True if the segment redirects output into the worktree (or somewhere unknown)."""
    # Mask quoted text (same length) so a `>` inside quotes is not a redirection, but read the
    # target from the original, so a quoted target path is kept whole.
    masked = QUOTED.sub(lambda q: "Q" * len(q.group()), segment)
    for m in REDIRECT.finditer(masked):
        target = segment[m.start(2):m.end(2)] if m.group(2) else ""
        if redirect_target_inside(target, base, wt):
            return True
    return False


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


def other_session(scope: dict, data: dict) -> bool:
    """The TASK was opened by another session (its executors share the opener's session id)."""
    mine, owner = data.get("session_id"), scope.get("session")
    return bool(mine and owner and mine != owner)


def warn_other(scope: dict, what: str) -> None:
    """Another session's TASK is open where this session works: warn, do not block."""
    task = scope.get("task") or "a TASK"
    emit({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": (
            f"[home-office] Another session has {task} open in this checkout ({what}). This call is "
            f"not blocked, but files you change here count as out of scope in that TASK's gate. Do "
            f"not touch its files ({', '.join((scope.get('files') or [])[:8]) or 'see its TASK'}); "
            f"prefer a worktree of your own, or wait until that session runs task-end."),
    }})


def check_bash(data: dict) -> None:
    command = (data.get("tool_input") or {}).get("command") or ""
    if not command:
        return
    wt, scope = active_task_in_command(command, data.get("cwd") or "")
    if not wt:
        return
    if other_session(scope, data):
        if any(p.search(command) for p, _ in WRITE_PATTERNS) or SCRIPT_WRITE.search(command):
            warn_other(scope, "Bash")
        return
    task = scope.get("task") or "a TASK"
    base = data.get("cwd") or wt
    if SCRIPT_WRITE.search(command):
        deny(f"home-office: during {task} Bash may only read and run commands/checks (a script "
             f"that writes files detected). Make file changes with the Edit or Write tools, which "
             f"are scope-checked. Never commit, stage or switch branches.")
        return
    stripped = SAFE_REDIRECTS.sub(" ", HEREDOC.sub("\n", command))
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
        hits = [label for pattern, label in WRITE_PATTERNS if pattern.search(segment)]
        if redirect_problem(segment, base, wt):
            hits.insert(0, "output redirection into the worktree")
        if hits:
            deny(f"home-office: during {task} Bash may only read and run commands/checks "
                 f"({hits[0]} detected). Make file changes with the Edit or Write tools, which "
                 f"are scope-checked. To keep command output, redirect it to a file outside the "
                 f"worktree (e.g. `> \"$TEMP/out.log\"`). Files in the TASK's delete list may be "
                 f"removed with `rm <path>` or `git rm <path>`. Never commit, stage or switch "
                 f"branches.")
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
    if other_session(scope, data):
        warn_other(scope, f"edit of {posix_rel(abs_path, worktree)}")
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
