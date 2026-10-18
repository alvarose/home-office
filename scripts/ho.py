"""home-office helper for the conductor. Deterministic steps, so the model does not improvise them.

  worktree    create (or reuse) a feature worktree and prepare it
  task-start  open a TASK in a worktree: closed file list, deny rules, checks, baseline
  task-status show the active TASK of a worktree
  task-end    close the TASK: print the gate result and the touched files, remove the scope file
  context     print the context size of a session transcript (debugging)

Usage examples (paths are absolute):

  python3 ho.py worktree --repo C:/src/app --dest C:/src/.worktrees/app/07-x \\
      --branch feature/07-x --base dev --copy .env --setup "composer install"
  python3 ho.py task-start --worktree C:/src/.worktrees/app/07-x --task "07-x / TASK 2" \\
      --file app/Models/Pet.php --file tests/Unit/PetTest.php \\
      --deny "database/migrations/**=Migrations only in the core repo" \\
      --check "composer test" --attempts 2
  python3 ho.py task-end --worktree C:/src/.worktrees/app/07-x

All commands print one JSON object on stdout.
"""

import argparse
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "hooks"))
from _common import (git, last_context_tokens, load_scope, run_check,  # noqa: E402
                     save_scope, scope_path, snapshot)


def out(obj: dict, code: int = 0) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(code)


def cmd_worktree(a) -> None:
    repo, dest = os.path.abspath(a.repo), os.path.abspath(a.dest)
    created = False
    if not os.path.exists(os.path.join(dest, ".git")):
        exists = git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{a.branch}").returncode == 0
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        args = ["worktree", "add", dest, a.branch] if exists else \
            ["worktree", "add", "-b", a.branch, dest, a.base]
        res = git(repo, *args)
        if res.returncode != 0:
            out({"ok": False, "error": (res.stderr or res.stdout).strip()}, 1)
        created = True

    copied, setup = [], []
    if created:
        for rel in a.copy or []:
            src, dst = os.path.join(repo, rel), os.path.join(dest, rel)
            if os.path.isfile(src) and not os.path.exists(dst):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                copied.append(rel)
        for cmd in a.setup or []:
            ok, tail = run_check(cmd, dest, timeout=1800, tail=15)
            setup.append({"command": cmd, "ok": ok, **({} if ok else {"output": tail})})
    branch = git(dest, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    out({"ok": all(s["ok"] for s in setup), "worktree": dest, "branch": branch,
         "created": created, "copied": copied, "setup": setup})


def parse_deny(items):
    rules = []
    for item in items or []:
        glob, _, reason = item.partition("=")
        rules.append({"glob": glob.strip(), "reason": reason.strip() or None})
    return rules


def cmd_task_start(a) -> None:
    wt = os.path.abspath(a.worktree)
    if not scope_path(wt):
        out({"ok": False, "error": f"not a git worktree: {wt}"}, 1)
    current = load_scope(wt)
    if current and current.get("gate") not in ("pass", "fail") and not a.force:
        out({"ok": False, "error": f"another task is active here: {current.get('task')}. "
                                   f"Run task-end first, or pass --force."}, 1)
    scope = {
        "task": a.task,
        "worktree": wt,
        "files": [f.replace("\\", "/") for f in a.file or []],
        "allow": [g.replace("\\", "/") for g in a.allow or []],
        "deny": parse_deny(a.deny),
        "checks": a.check or [],
        "ignore": [g.replace("\\", "/") for g in a.ignore or []],
        "attempts": a.attempts,
        "check_timeout": a.check_timeout,
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "baseline": snapshot(wt),
        "gate": None,
        "gate_blocks": 0,
    }
    save_scope(wt, scope)
    out({"ok": True, "task": a.task, "worktree": wt, "files": scope["files"],
         "deny": scope["deny"], "checks": scope["checks"],
         "prompt_marker": f"HOME-OFFICE-WORKTREE: {wt}"})


def summary(scope: dict) -> dict:
    return {k: scope.get(k) for k in ("task", "worktree", "gate", "gate_blocks", "touched",
                                      "results", "problems", "started", "last_run")}


def cmd_task_status(a) -> None:
    scope = load_scope(os.path.abspath(a.worktree))
    out({"ok": True, "active": bool(scope), **(summary(scope) if scope else {})})


def cmd_task_end(a) -> None:
    wt = os.path.abspath(a.worktree)
    scope = load_scope(wt)
    if not scope:
        out({"ok": True, "active": False})
    result = summary(scope)
    if not a.keep:
        try:
            os.remove(scope_path(wt))
        except OSError:
            pass
    out({"ok": True, **result})


def cmd_context(a) -> None:
    out({"ok": True, "tokens": last_context_tokens(a.transcript)})


def main() -> None:
    p = argparse.ArgumentParser(prog="ho.py", description="home-office conductor helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("worktree")
    w.add_argument("--repo", required=True)
    w.add_argument("--dest", required=True)
    w.add_argument("--branch", required=True)
    w.add_argument("--base", required=True)
    w.add_argument("--copy", action="append", help="untracked file to copy from the repo, e.g. .env")
    w.add_argument("--setup", action="append", help="command to run once in a new worktree")
    w.set_defaults(fn=cmd_worktree)

    s = sub.add_parser("task-start")
    s.add_argument("--worktree", required=True)
    s.add_argument("--task", required=True)
    s.add_argument("--file", action="append", help="file the TASK may change (repeat)")
    s.add_argument("--allow", action="append", help="glob the TASK may change (repeat)")
    s.add_argument("--deny", action="append", help="'glob=reason' that must never change (repeat)")
    s.add_argument("--check", action="append", help="command that must pass (repeat)")
    s.add_argument("--ignore", action="append",
                   help="glob of generated files that never count as changed (repeat; common "
                        "build and test artifacts are ignored already)")
    s.add_argument("--attempts", type=int, default=2)
    s.add_argument("--check-timeout", type=int, default=1200)
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_task_start)

    t = sub.add_parser("task-status")
    t.add_argument("--worktree", required=True)
    t.set_defaults(fn=cmd_task_status)

    e = sub.add_parser("task-end")
    e.add_argument("--worktree", required=True)
    e.add_argument("--keep", action="store_true", help="print the result but keep the scope file")
    e.set_defaults(fn=cmd_task_end)

    c = sub.add_parser("context")
    c.add_argument("--transcript", required=True)
    c.set_defaults(fn=cmd_context)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
