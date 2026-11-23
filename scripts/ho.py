"""home-office helper for the conductor. Deterministic steps, so the model does not improvise them.

  worktree    create (or reuse) a feature worktree and prepare it (--link clones vendor/
              node_modules from the main checkout with hard links when the lock files match)
  worktree-remove  remove a feature worktree after the merge (refuses with an open TASK or
              uncommitted changes) and, with --delete-branch, its branch if merged into --base
  task-start  open a TASK in a worktree: closed file list, delete list, deny rules,
              prepare commands, checks, advisories (never blocking), baseline
  task-status show the active TASK of a worktree
  task-end    close the TASK: always print the gate (pass / fail; it runs the checks here when no
              checks gate ran, e.g. delegated tools) and the touched files, remove the scope file,
              and count rework (gate fail, or --report blocked / needs-plan-change) in the
              feature's STATE.md. Called again, it repeats the last TASK's result.
  check       run one check command in a worktree through the result cache: the same command on
              the same tree state (any edit changes it) is answered from the cache, never rerun
  claims      list the file claims of the open TASKs of a repo (all its worktrees), as JSON;
              task-start records them and reports overlaps with other features (`conflicts`),
              and refuses a hotspot another feature holds (`--hotspot`, unless --force)
  sync        merge the base branch into a feature worktree, early, only when it is clean and
              no TASK is open: up_to_date | merged | conflict (aborted, nothing changed)
  waiting     the waiting inbox <work>/waiting.md: add | answer | acted | list | stats (ids and
              timestamps are deterministic; answered rows are kept, they are the measurement)
  weight      measure what every session loads (config, board, waiting inbox, indexes, project /
              stream / batch pages, open STATE.md files, the repos' CLAUDE.md / AGENTS.md) against
              limits; --rotate moves old log rows and old acted waiting rows to <work>/archive/
  maturity    per repo: commits, age, test files, checks and `mature` (or the repo's `mature:`);
              the classifier sends more work to the short lane in a mature repo
  context     print the context size of a session transcript (debugging)

Usage examples (paths are absolute):

  python3 ho.py worktree --repo C:/src/app --dest C:/src/.worktrees/app/07-x \\
      --branch feature/07-x --base dev --copy .env --setup "composer install"
  python3 ho.py task-start --worktree C:/src/.worktrees/app/07-x --task "07-x / TASK 2" \\
      --file app/Models/Pet.php --file tests/Unit/PetTest.php \\
      --delete app/Models/OldPet.php \\
      --deny "database/migrations/**=Migrations only in the core repo" \\
      --prepare "php artisan routes:generate" --check "composer test" --attempts 2
  python3 ho.py task-end --worktree C:/src/.worktrees/app/07-x

All commands print one JSON object on stdout.
"""

import argparse
import json
import math
import os
import re
import shutil
import stat
import sys
import statistics
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "hooks"))
from _common import (bump_rework, changed_files, evaluate_task, feature_state,  # noqa: E402
                     find_up, git, git_dir, last_context_tokens, load_scope, matches,
                     run_cached_check, run_check, save_scope, scope_path, snapshot, work_dir)


def out(obj: dict, code: int = 0) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(code)


# --link: dependency folders cloned from the repo's main checkout with hard links instead of
# installing them, when the worktree's lock files are identical to the main checkout's.
LOCKS = {"vendor": ["composer.lock"],
         "node_modules": ["package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb"]}
MANIFESTS = {"vendor": ["composer.json", "composer.lock"],
             "node_modules": ["package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
                              "bun.lockb"]}
INSTALLERS = {"vendor": ("composer install",),
              "node_modules": ("npm ci", "npm install", "pnpm install", "yarn install", "yarn",
                               "bun install")}
# Copied for real, never linked: files rewritten in place (autoload with __DIR__ paths) or caches.
REAL_COPY = {"vendor": ["composer"], "node_modules": []}
SKIP = {".git", ".cache", ".vite", ".vite-temp"}
LINKS_FILE = "home-office-links.json"


def links_path(wt: str):
    gd = git_dir(wt)
    return os.path.join(gd, LINKS_FILE) if gd else None


def load_links(wt: str) -> list:
    try:
        with open(links_path(wt), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return []


def save_links(wt: str, links: list) -> None:
    path = links_path(wt)
    if not path:
        return
    if links:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(links, fh)
    elif os.path.exists(path):
        os.remove(path)


def same_locks(repo: str, dest: str, folder: str) -> bool:
    """True if every lock file of `folder` that exists in the repo is identical in the worktree."""
    found = False
    for name in LOCKS.get(folder, []):
        src, dst = os.path.join(repo, name), os.path.join(dest, name)
        if os.path.isfile(src):
            found = True
            if not os.path.isfile(dst):
                return False
            with open(src, "rb") as f1, open(dst, "rb") as f2:
                if f1.read() != f2.read():
                    return False
    return found


def link_or_copy(src: str, dst: str) -> None:
    try:
        os.link(src, dst)
    except OSError:  # another volume, or links not supported
        shutil.copy2(src, dst)


def clone_folder(repo: str, dest: str, folder: str) -> None:
    src, dst = os.path.join(repo, folder), os.path.join(dest, folder)
    real = set(REAL_COPY.get(folder, []))

    def is_reparse(p: str) -> bool:
        return os.path.islink(p) or (hasattr(os.path, "isjunction") and os.path.isjunction(p))

    shutil.copytree(src, dst, copy_function=link_or_copy,
                    ignore=lambda d, names: [n for n in names if n in SKIP or is_reparse(os.path.join(d, n)) or
                                             (os.path.normpath(d) == os.path.normpath(src) and n in real)])
    for name in real:
        if os.path.isdir(os.path.join(src, name)):
            shutil.copytree(os.path.join(src, name), os.path.join(dst, name))


def remove_tree(path: str) -> None:
    def onexc(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=onexc)
    else:
        shutil.rmtree(path, onerror=lambda f, p, e: onexc(f, p, e))


def installs(cmd: str, folder: str) -> bool:
    c = " ".join(cmd.split())
    return any(c == i or c.startswith(i + " ") for i in INSTALLERS.get(folder, ()))


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
            if os.path.exists(dst):
                continue
            if os.path.isfile(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                copied.append(rel)
            elif os.path.isdir(src):  # e.g. built assets git ignores
                shutil.copytree(src, dst)
                copied.append(rel + "/")
        linked = []
        for folder in a.link or []:
            folder = folder.strip("/\\")
            if (folder in LOCKS and os.path.isdir(os.path.join(repo, folder))
                    and not os.path.exists(os.path.join(dest, folder)) and same_locks(repo, dest, folder)):
                clone_folder(repo, dest, folder)
                linked.append(folder)
        save_links(dest, linked)
        for cmd in a.setup or []:
            skipped = [f for f in linked if installs(cmd, f)]
            if skipped:
                setup.append({"command": cmd, "ok": True, "skipped": f"{skipped[0]} cloned from the main checkout"})
                continue
            ok, tail = run_check(cmd, dest, timeout=1800, tail=15)
            setup.append({"command": cmd, "ok": ok, **({} if ok else {"output": tail})})
    branch = git(dest, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    out({"ok": all(s["ok"] for s in setup), "worktree": dest, "branch": branch,
         "created": created, "copied": copied, "linked": load_links(dest), "setup": setup})


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
    feature = feature_of(wt, a.task)
    claimed = [f.replace("\\", "/") for f in (a.file or []) + (a.allow or []) + (a.delete or [])]
    conflicts = find_conflicts(wt, feature, claimed, a.hotspot or [], a.base) if claimed else []
    held = [c for c in conflicts if c.get("hotspot")]
    if held and not a.force:
        out({"ok": False, "error": "hotspot held by another feature: " + "; ".join(
                 f"{c['file']} ({c['feature']}" + (f", {c['task']}" if c.get("task") else ", unmerged branch") + ")"
                 for c in held),
             "hotspots_held": held, "conflicts": conflicts,
             "hint": "do other independent TASKs first, or file a wait; --force overrides"}, 1)
    links, reinstalled = load_links(wt), []
    listed = [f.replace("\\", "/") for f in (a.file or []) + (a.delete or [])]
    for folder in list(links):
        if any(os.path.basename(f) in MANIFESTS.get(folder, []) and "/" not in f.strip("/") for f in listed):
            # The TASK changes this folder's dependencies: give the worktree its own real install.
            remove_tree(os.path.join(wt, folder))
            links.remove(folder)
            for cmd in a.setup or []:
                if installs(cmd, folder):
                    ok, tail = run_check(cmd, wt, timeout=1800, tail=15)
                    reinstalled.append({"command": cmd, "ok": ok, **({} if ok else {"output": tail})})
    save_links(wt, links)
    deny_links = [{"glob": f"{f}/**", "reason": f"{f}/ is shared with the main checkout (hard links): never edit it"}
                  for f in links]
    state = os.path.abspath(a.state) if a.state else feature_state(a.task, os.getcwd())
    scope = {
        "task": a.task,
        "worktree": wt,
        "state": state,
        "files": [f.replace("\\", "/") for f in a.file or []],
        "allow": [g.replace("\\", "/") for g in a.allow or []],
        "delete": [f.replace("\\", "/") for f in a.delete or []],
        "deny": parse_deny(a.deny) + deny_links,
        "prepare": a.prepare or [],
        "checks": a.check or [],
        "advisory": a.advisory or [],
        "gate_seconds": a.gate_seconds,
        "ignore": [g.replace("\\", "/") for g in a.ignore or []],
        "attempts": a.attempts,
        "check_timeout": a.check_timeout,
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "baseline": snapshot(wt),
        "gate": None,
        "gate_blocks": 0,
    }
    save_scope(wt, scope)
    if claimed:
        try:
            add_claim(wt, {"feature": feature, "task": a.task, "worktree": wt,
                           "files": scope["files"] + scope["allow"], "delete": scope["delete"],
                           "since": time.strftime("%Y-%m-%d %H:%M")})
        except Exception:  # claims are advice: never lose the TASK over them
            pass
    out({"ok": True, "task": a.task, "worktree": wt, "feature": feature, "conflicts": conflicts,
         "files": scope["files"],
         "delete": scope["delete"], "deny": scope["deny"], "prepare": scope["prepare"],
         "checks": scope["checks"], "advisory": scope["advisory"],
         "gate_seconds": scope["gate_seconds"], "linked": links, "reinstalled": reinstalled,
         "state": state, "prompt_marker": f"HOME-OFFICE-WORKTREE: {wt}"})


def summary(scope: dict) -> dict:
    # `gate` first: it is the one field the conductor must always read.
    return {k: scope.get(k) for k in ("gate", "task", "worktree", "gate_blocks", "touched",
                                      "generated", "results", "problems", "advisories",
                                      "started", "last_run")}


LAST_FILE = "home-office-last-task.json"
# Executor reports that send a TASK back, like a failed gate.
REWORK_REPORTS = {"blocked", "needs-plan-change"}


def last_path(wt: str):
    gd = git_dir(wt)
    return os.path.join(gd, LAST_FILE) if gd else None


def load_last(wt: str):
    try:
        with open(last_path(wt), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def save_last(wt: str, last: dict) -> None:
    try:
        with open(last_path(wt), "w", encoding="utf-8") as fh:
            json.dump(last, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass


def record_rework(rec: dict, report) -> dict:
    """Count a TASK that went back (gate fail, or a blocked / needs-plan-change report) once,
    in its feature's STATE.md. `rec` is the scope or the last result; it is updated in place."""
    if report:
        rec["report"] = report
    reason = "gate fail" if rec.get("gate") == "fail" else \
        (f"report {rec.get('report')}" if rec.get("report") in REWORK_REPORTS else None)
    info = {"state": rec.get("state"), "recorded": False}
    if rec.get("rework_count") is not None:  # already counted for this TASK
        info.update(recorded=True, count=rec["rework_count"], reason=rec.get("rework_reason"))
        return info
    if not reason:
        return info
    info["reason"] = reason
    if not rec.get("state"):
        info["note"] = "no feature STATE.md (short lane or task): nothing to record"
        return info
    try:
        rec["rework_count"] = bump_rework(rec["state"])
        rec["rework_reason"] = reason
        info.update(recorded=True, count=rec["rework_count"])
    except Exception as exc:  # never lose the gate over the counter
        info["error"] = f"could not update {rec['state']}: {exc}"
    return info


def cmd_task_status(a) -> None:
    scope = load_scope(os.path.abspath(a.worktree))
    out({"ok": True, "active": bool(scope), **(summary(scope) if scope else {})})


def cmd_task_end(a) -> None:
    wt = os.path.abspath(a.worktree)
    scope = load_scope(wt)
    if not scope:
        # Already closed (a second call): repeat the last TASK's result, so the gate is never lost.
        last = load_last(wt)
        if not last:
            out({"ok": True, "gate": None, "active": False,
                 "note": "no TASK was ever opened in this worktree"})
        rework = record_rework(last, a.report)
        save_last(wt, last)
        release_claims(wt)  # nothing is open here: drop any claim a crash left behind
        out({"ok": True, **{k: last.get(k) for k in last if k not in EXTRA}, "active": False,
             "note": "no TASK open: this is the result of the last one, already closed",
             "gate_by": last.get("gate_by"), "report": last.get("report"), "rework": rework})
    if scope.get("gate") not in ("pass", "fail"):
        if a.no_checks:
            scope["gate"], scope["gate_by"] = "skipped", "task-end --no-checks"
        else:
            # No executor gate ran (delegated tool, tuning, a hook that did not fire): evaluate it
            # here, once, so task-end always answers pass or fail.
            problems = evaluate_task(wt, scope)
            scope["problems"] = problems
            scope["gate"], scope["gate_by"] = ("fail" if problems else "pass"), "task-end"
    scope["gate_by"] = scope.get("gate_by") or "checks gate"
    if "state" not in scope:  # TASK opened by an older ho.py
        scope["state"] = feature_state(scope.get("task"), os.getcwd())
    rework = record_rework(scope, a.report)
    if a.keep:
        save_scope(wt, scope)
    else:
        try:
            os.remove(scope_path(wt))
        except OSError:
            pass
        release_claims(wt, scope.get("task"))
    save_last(wt, {**summary(scope), **{k: scope.get(k) for k in EXTRA}})
    out({"ok": True, **summary(scope), "active": bool(a.keep), "gate_by": scope["gate_by"],
         "report": scope.get("report"), "rework": rework})


# Kept with the last result besides the summary, so a repeated task-end can answer and count once.
EXTRA = ("state", "report", "gate_by", "rework_count", "rework_reason")


def cmd_check(a) -> None:
    wt = os.path.abspath(a.worktree)
    if not git_dir(wt):
        out({"ok": False, "error": f"not a git worktree: {wt}"}, 1)
    res = run_cached_check(wt, a.cmd, timeout=a.timeout, tail=a.tail, use_cache=not a.no_cache)
    out({"ok": res["ok"], "cached": res["cached"], "cmd": a.cmd.strip(), "seconds": res["seconds"],
         "ran_seconds": res.get("ran_seconds"), "at": res.get("at"), "timed_out": res["timed_out"],
         "tail": res["tail"]}, 0 if res["ok"] else 1)


def cmd_context(a) -> None:
    out({"ok": True, "tokens": last_context_tokens(a.transcript)})


def cmd_worktree_remove(a) -> None:
    """Remove a feature worktree (and, if asked, its merged branch), with safety checks."""
    repo, dest = os.path.abspath(a.repo), os.path.abspath(a.dest)
    norm = lambda p: os.path.normcase(os.path.normpath(p))  # noqa: E731
    listed = git(repo, "worktree", "list", "--porcelain").stdout
    paths = [norm(line[9:].strip()) for line in listed.splitlines() if line.startswith("worktree ")]
    present = os.path.exists(dest)
    if present and norm(dest) not in paths:
        out({"ok": False, "error": f"{dest} is not a worktree of {repo}"}, 1)
    if norm(dest) == norm(repo):
        out({"ok": False, "error": "refusing to remove the repo's main checkout"}, 1)

    branch = a.branch
    if present:
        if os.path.exists(scope_path(dest) or ""):
            out({"ok": False, "error": "a TASK is still open in this worktree; close it with task-end first"}, 1)
        dirty = changed_files(dest)
        if dirty:
            out({"ok": False, "error": "uncommitted changes in the worktree; commit or discard them first",
                 "changes": dirty[:30]}, 1)
        if not branch:
            branch = git(dest, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or None

    if a.delete_branch:
        if not branch:
            out({"ok": False, "error": "--delete-branch needs --branch (the worktree is gone)"}, 1)
        if not a.base:
            out({"ok": False, "error": "--delete-branch needs --base to check the branch is merged"}, 1)
        merged = git(repo, "merge-base", "--is-ancestor", branch, a.base).returncode == 0
        if not merged:
            out({"ok": False, "error": f"{branch} is not merged into {a.base}; nothing was removed"}, 1)

    removed = False
    if present:
        res = git(repo, "worktree", "remove", dest)
        if res.returncode != 0 and a.force:
            # Only reached with a clean status: what is left is ignored files or submodules.
            res = git(repo, "worktree", "remove", "--force", dest)
        if res.returncode != 0:
            out({"ok": False, "error": (res.stderr or res.stdout).strip(),
                 "hint": "if only ignored files or submodules are left, retry with --force"}, 1)
        removed = True
    git(repo, "worktree", "prune")
    released = release_claims(dest, git_at=repo)

    branch_deleted = False
    if a.delete_branch:
        res = git(repo, "branch", "-d", branch)  # -d refuses unmerged branches; never -D
        if res.returncode != 0:
            out({"ok": False, "worktree_removed": removed, "error": (res.stderr or res.stdout).strip()}, 1)
        branch_deleted = True
    out({"ok": True, "worktree": dest, "worktree_removed": removed, "branch": branch,
         "branch_deleted": branch_deleted, "claims_released": released})


# ---------------------------------------------------------------- file claims
# Every open TASK claims its closed file list (and delete list) in <common git dir>/
# home-office-claims.json, shared by all worktrees of the repo. task-start reports overlaps with
# other features and refuses a hotspot another feature holds; task-end and worktree-remove release.

CLAIMS_FILE = "home-office-claims.json"


def rp(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def common_dir(wt: str):
    res = git(wt, "rev-parse", "--git-common-dir")
    if res.returncode != 0 or not res.stdout.strip():
        return None
    return os.path.realpath(os.path.join(wt, res.stdout.strip()))


def claims_path(wt: str):
    cd = common_dir(wt)
    return os.path.join(cd, CLAIMS_FILE) if cd else None


def worktree_paths(wt: str) -> list:
    listed = git(wt, "worktree", "list", "--porcelain").stdout
    return [rp(line[9:].strip()) for line in listed.splitlines() if line.startswith("worktree ")]


def feature_of(wt: str, task: str) -> str:
    """The feature a TASK belongs to: its branch `feature/NN-name`, else the `NN-name /` of its label."""
    branch = git(wt, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch.startswith("feature/"):
        return branch[len("feature/"):]
    m = re.match(r"^\s*(\d+-[^\s/]+)\s*/", task or "")
    return m.group(1) if m else (task or branch or "unknown")


class ClaimsLock:
    """Tiny lock around read-modify-write of the claims file. Fail-open after ~2 s."""

    def __init__(self, path):
        self.path, self.fd = (path + ".lock") if path else None, None

    def __enter__(self):
        if not self.path:
            return self
        for _ in range(40):
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                try:  # a lock older than 30 s belongs to a crashed process
                    if time.time() - os.path.getmtime(self.path) > 30:
                        os.remove(self.path)
                        continue
                except OSError:
                    pass
                time.sleep(0.05)
            except OSError:
                break
        return self

    def __exit__(self, *exc):
        if self.fd is not None:
            os.close(self.fd)
            try:
                os.remove(self.path)
            except OSError:
                pass


def read_claims(path) -> list:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return [c for c in data if isinstance(c, dict)]
    except Exception:
        return []


def write_claims(path, claims: list) -> None:
    if not path:
        return
    if not claims:
        try:
            os.remove(path)
        except OSError:
            pass
        return
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(claims, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def live_claims(wt: str):
    """(claims of the repo, how many stale ones were dropped). Stale: the worktree is gone."""
    path = claims_path(wt)
    claims = read_claims(path)
    alive = set(worktree_paths(wt))
    keep = [c for c in claims if c.get("worktree") and os.path.isdir(c["worktree"]) and rp(c["worktree"]) in alive]
    dropped = len(claims) - len(keep)
    if dropped:
        with ClaimsLock(path):
            write_claims(path, [c for c in read_claims(path) if c in keep])
    return keep, dropped


def add_claim(wt: str, claim: dict) -> None:
    """Record a TASK's claim (replacing an older claim of the same worktree and task)."""
    path = claims_path(wt)
    if not path:
        return
    with ClaimsLock(path):
        claims = [c for c in read_claims(path)
                  if not (c.get("worktree") and rp(c["worktree"]) == rp(wt) and c.get("task") == claim["task"])]
        write_claims(path, claims + [claim])


def release_claims(wt: str, task=None, git_at=None) -> int:
    """Drop the claims of one TASK (task given) or of the whole worktree. Returns how many.
    `git_at`: a path of the repo to find the claims file from (the worktree may be gone)."""
    path = claims_path(git_at or wt)
    if not path:
        return 0
    me = rp(wt)
    with ClaimsLock(path):
        claims = read_claims(path)
        keep = [c for c in claims if not (c.get("worktree") and rp(c["worktree"]) == me
                                          and (task is None or c.get("task") == task))]
        if len(keep) != len(claims):
            write_claims(path, keep)
    return len(claims) - len(keep)


def glob_hit(rel: str, pat: str) -> bool:
    """matches(), where a leading `**/` also matches the repo root (`**/strings.xml` ~ `strings.xml`)."""
    pats = [pat]
    if pat.startswith("**/"):
        pats.append(pat[3:])
    return matches(rel, pats)


def overlaps(a: str, b: str) -> bool:
    a, b = a.replace("\\", "/").strip("/"), b.replace("\\", "/").strip("/")
    return a == b or glob_hit(a, b) or glob_hit(b, a)


def claim_entries(claim: dict) -> list:
    """Patterns a claim holds: its files, its delete list, and what a deleted folder covers."""
    pats = list(claim.get("files") or [])
    for d in claim.get("delete") or []:
        pats += [d, d.rstrip("/") + "/**"]
    return pats


def branch_claims(wt: str, base, own_feature: str) -> list:
    """Unmerged feature branches of the repo, as claims of the files they changed against `base`."""
    if not base:
        return []
    res = git(wt, "for-each-ref", "--format=%(refname:short)\t%(committerdate:iso-strict)", "refs/heads/feature/")
    found = []
    for line in res.stdout.splitlines():
        branch, _, when = line.partition("\t")
        feat = branch[len("feature/"):]
        if not branch or feat == own_feature:
            continue
        if git(wt, "merge-base", "--is-ancestor", branch, base).returncode == 0:
            continue  # merged
        diff = git(wt, "diff", "--name-only", f"{base}...{branch}")
        files = [f.strip() for f in diff.stdout.splitlines() if f.strip()]
        if diff.returncode == 0 and files:
            found.append({"feature": feat, "task": None, "worktree": None, "branch": branch,
                          "files": files, "delete": [], "since": when or None, "source": "branch"})
    return found


def find_conflicts(wt: str, feature: str, files: list, hotspots: list, base) -> list:
    """Overlaps of `files` with the claims of other features (open TASKs and unmerged branches)."""
    claims, _ = live_claims(wt)
    others = [c for c in claims if c.get("feature") != feature] + branch_claims(wt, base, feature)
    found, seen = [], set()
    for f in files:
        hot = any(overlaps(f, h) for h in hotspots)
        for c in others:
            if any(overlaps(f, p) for p in claim_entries(c)):
                key = (f, c.get("feature"), c.get("task"))
                if key in seen:
                    continue
                seen.add(key)
                item = {"file": f, "feature": c.get("feature"), "task": c.get("task"),
                        "since": c.get("since"), "source": c.get("source", "task")}
                if hot:
                    item["hotspot"] = True
                found.append(item)
    return found


def cmd_claims(a) -> None:
    repo = os.path.abspath(a.repo)
    if not common_dir(repo):
        out({"ok": False, "error": f"not a git repository: {repo}"}, 1)
    claims, dropped = live_claims(repo)
    branches = branch_claims(repo, a.base, "") if a.base else []
    out({"ok": True, "repo": repo, "file": claims_path(repo), "dropped_stale": dropped,
         "claims": claims, "branches": branches})


def cmd_sync(a) -> None:
    wt = os.path.abspath(a.worktree)
    if not git_dir(wt):
        out({"ok": False, "status": "error", "error": f"not a git worktree: {wt}"}, 1)
    branch = git(wt, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    head = git(wt, "rev-parse", "HEAD").stdout.strip()
    base_sha = git(wt, "rev-parse", "--verify", "--quiet", f"{a.base}^{{commit}}").stdout.strip()
    res = {"worktree": wt, "branch": branch, "base": a.base}

    def refuse(reason, msg, **extra):
        out({"ok": False, "status": "refused", "reason": reason, "message": msg, **res, **extra}, 1)

    if not base_sha:
        out({"ok": False, "status": "error", "error": f"base branch not found: {a.base}", **res}, 1)
    if branch in ("HEAD", a.base):
        refuse("not_a_feature_branch", f"HEAD is {branch}: sync only runs on a feature branch")
    if load_scope(wt):
        refuse("task_open", "a TASK is open in this worktree; close it with task-end first")
    dirty = changed_files(wt)
    if dirty:
        refuse("dirty", "uncommitted changes in the worktree; commit them first", changes=dirty[:30])
    if git(wt, "merge-base", "--is-ancestor", base_sha, head).returncode == 0:
        out({"ok": True, "status": "up_to_date", "head": head, **res})
    merged = git(wt, "merge", "--no-edit", base_sha)
    if merged.returncode == 0:
        new = git(wt, "rev-parse", "HEAD").stdout.strip()
        files = [f for f in git(wt, "diff", "--name-only", f"{head}..{new}").stdout.splitlines() if f]
        out({"ok": True, "status": "merged", "head_before": head, "head": new,
             "fast_forward": git(wt, "rev-parse", "--verify", "--quiet", "HEAD^2").returncode != 0,
             "files": files, **res})
    conflicts = [f for f in git(wt, "diff", "--name-only", "--diff-filter=U").stdout.splitlines() if f]
    if git(wt, "merge", "--abort").returncode != 0:  # no merge in progress: nothing to abort
        git(wt, "reset", "--merge")
    after = git(wt, "rev-parse", "HEAD").stdout.strip()
    clean = not changed_files(wt)
    if not conflicts:
        out({"ok": False, "status": "error", "error": (merged.stderr or merged.stdout).strip(),
             "head": after, "clean": clean, **res}, 1)
    out({"ok": False, "status": "conflict", "files": conflicts, "aborted": True,
         "head": after, "unchanged": after == head and clean, **res}, 1)


# ---------------------------------------------------------------- waiting inbox
# <work>/waiting.md: one row per thing that waits on the user. Two tables, found by position
# (the headings may be translated): Open, then Answered. Answered rows are never deleted.

WAIT_KINDS = ("decision", "push", "merge", "deploy-check", "env", "data", "other")
WAIT_OPEN = ("id", "since", "project", "work", "kind", "action", "blocks")
WAIT_DONE = WAIT_OPEN + ("answered", "answer", "acted")
TS_FMT = "%Y-%m-%d %H:%M"
WAIT_TEMPLATE = os.path.join(os.path.dirname(HERE), "core", "templates", "waiting.md")


def wait_now(a) -> datetime:
    if getattr(a, "now", None):
        try:
            return datetime.strptime(a.now, TS_FMT)
        except ValueError:
            out({"ok": False, "error": f"--now must be 'YYYY-MM-DD HH:MM', got {a.now!r}"}, 1)
    return datetime.now().replace(second=0, microsecond=0)


def wait_file(a) -> str:
    config = os.path.abspath(a.config) if getattr(a, "config", None) else find_up(os.getcwd(), ".home-office.yml")
    if not config or not os.path.isfile(config):
        out({"ok": False, "error": "no .home-office.yml found (run from the work folder or pass --config)"}, 1)
    return os.path.join(work_dir(config), "waiting.md")


def split_row(line: str) -> list:
    s = line.strip()
    s = s[1:] if s.startswith("|") else s
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def cell(text) -> str:
    return " ".join(str(text or "").split()).replace("|", "\\|")


def parse_waiting(text: str) -> dict:
    """Prelude lines, then per `## ` section: heading, table header, separator, rows (dicts)."""
    prelude, tables, cur = [], [], None
    for line in text.splitlines():
        if line.startswith("## "):
            cur = {"heading": line, "header": None, "sep": None, "rows": []}
            tables.append(cur)
        elif cur is None:
            prelude.append(line)
        elif line.strip().startswith("|"):
            if cur["header"] is None:
                cur["header"] = line.strip()
            elif cur["sep"] is None:
                cur["sep"] = line.strip()
            else:
                fields = WAIT_OPEN if len(tables) == 1 else WAIT_DONE
                cells = split_row(line)
                row = dict(zip(fields, cells + [""] * (len(fields) - len(cells))))
                if row.get("id"):
                    cur["rows"].append(row)
    return {"prelude": prelude, "tables": tables}


def load_waiting(path: str) -> dict:
    with open(WAIT_TEMPLATE, encoding="utf-8") as fh:
        defaults = parse_waiting(fh.read())
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            data = parse_waiting(fh.read())
    else:
        data = defaults
    for i in range(2):
        if len(data["tables"]) <= i:
            data["tables"].append({**defaults["tables"][i], "rows": []})
        for key in ("header", "sep"):
            data["tables"][i][key] = data["tables"][i][key] or defaults["tables"][i][key]
    return data


def save_waiting(path: str, data: dict) -> None:
    lines = list(data["prelude"])
    while lines and not lines[-1].strip():
        lines.pop()
    for t, fields in zip(data["tables"], (WAIT_OPEN, WAIT_DONE)):
        lines += ["", t["heading"], "", t["header"], t["sep"]]
        lines += ["| " + " | ".join(cell(r.get(f)) for f in fields) + " |" for r in t["rows"]]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines).lstrip("\n") + "\n")


def parse_ts(text):
    try:
        return datetime.strptime((text or "").strip(), TS_FMT)
    except ValueError:
        return None


def age_text(hours: float) -> str:
    return f"{int(hours // 24)} d" if hours >= 24 else f"{int(hours)} h"


def wait_view(row: dict, state: str, now: datetime) -> dict:
    """The row plus `state` and its age (open) or wait time (answered), in hours."""
    since = parse_ts(row.get("since"))
    end = now if state == "open" else parse_ts(row.get("answered"))
    hours = round((end - since).total_seconds() / 3600, 1) if since and end else None
    view = {**row, "state": state}
    if state == "open":
        view["age_hours"] = hours
        view["age"] = age_text(hours) if hours is not None else None
    else:
        view["wait_hours"] = hours
        view["unacted"] = not row.get("acted")
    return view


def wait_rows(data: dict, a, now: datetime) -> list:
    rows = [wait_view(r, "open", now) for r in data["tables"][0]["rows"]] + \
           [wait_view(r, "answered", now) for r in data["tables"][1]["rows"]]
    for key in ("project", "kind"):
        val = getattr(a, key, None)
        if val:
            rows = [r for r in rows if r.get(key, "").lower() == val.lower()]
    if getattr(a, "feature", None):
        rows = [r for r in rows if r.get("work", "").startswith(a.feature)]
    if getattr(a, "since", None):
        rows = [r for r in rows if r.get("since", "")[:10] >= a.since]
    return rows


def pctl(values: list, p: float):
    """Nearest-rank percentile (p in 0..1)."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p * len(ordered)) - 1)]


def wait_stats(xs: list) -> dict:
    return {"median_hours": round(statistics.median(xs), 1) if xs else None, "p90_hours": pctl(xs, 0.9)}


def cmd_waiting(a) -> None:
    path, now = wait_file(a), wait_now(a)
    data = load_waiting(path)
    op = a.op
    if op == "add":
        if a.kind not in WAIT_KINDS:
            out({"ok": False, "error": f"--kind must be one of {', '.join(WAIT_KINDS)}"}, 1)
        since = a.since or now.strftime(TS_FMT)
        if not parse_ts(since):
            out({"ok": False, "error": f"--since must be 'YYYY-MM-DD HH:MM', got {since!r}"}, 1)
        nums = [int(r["id"][2:]) for t in data["tables"] for r in t["rows"] if re.match(r"^W-\d+$", r["id"])]
        row = {"id": f"W-{max(nums, default=0) + 1:03d}", "since": since, "project": a.project or "",
               "work": a.work or "", "kind": a.kind, "action": a.action, "blocks": a.blocks or "nothing else"}
        data["tables"][0]["rows"].append(row)
        save_waiting(path, data)
        out({"ok": True, "op": "add", "file": path, "row": wait_view(row, "open", now)})
    if op in ("answer", "acted"):
        wid = a.id.upper()
        if op == "answer":
            if a.at and not parse_ts(a.at):
                out({"ok": False, "error": f"--at must be 'YYYY-MM-DD HH:MM', got {a.at!r}"}, 1)
            rows = data["tables"][0]["rows"]
            row = next((r for r in rows if r["id"] == wid), None)
            if not row:
                done = any(r["id"] == wid for r in data["tables"][1]["rows"])
                out({"ok": False, "error": f"{wid} is " + ("already answered" if done else "not in the inbox")}, 1)
            rows.remove(row)
            row = {**row, "answered": a.at or now.strftime(TS_FMT), "answer": a.answer, "acted": ""}
            data["tables"][1]["rows"].insert(0, row)
        else:
            row = next((r for r in data["tables"][1]["rows"] if r["id"] == wid), None)
            if not row:
                out({"ok": False, "error": f"{wid} is not an answered row"}, 1)
            row["acted"] = now.strftime(TS_FMT)
        save_waiting(path, data)
        out({"ok": True, "op": op, "file": path, "row": wait_view(row, "answered", now)})
    if op == "stats":  # rows rotated by `weight --rotate` still count
        archived = os.path.join(os.path.dirname(path), "archive", "waiting.md")
        if os.path.isfile(archived):
            data["tables"][1]["rows"] += load_waiting(archived)["tables"][1]["rows"]
    rows = wait_rows(data, a, now)
    if op == "list":
        shown = [r for r in rows if a.state == "all" or r["state"] == a.state or
                 (a.state == "unacted" and r["state"] == "answered" and r["unacted"])]
        groups = {}
        for r in shown:
            if r["state"] != "open":
                continue
            g = groups.setdefault(r["kind"], {"count": 0, "oldest_hours": 0, "oldest": "0 h"})
            g["count"] += 1
            if (r["age_hours"] or 0) >= g["oldest_hours"]:
                g["oldest_hours"], g["oldest"] = r["age_hours"] or 0, r["age"] or "0 h"
        out({"ok": True, "op": "list", "file": path, "now": now.strftime(TS_FMT), "state": a.state,
             "count": len(shown), "by_kind": groups, "rows": shown})
    answered = [r for r in rows if r["state"] == "answered"]
    opened = [r for r in rows if r["state"] == "open"]
    by_kind = {}
    for k in WAIT_KINDS:
        waits = [r["wait_hours"] for r in answered if r["kind"] == k and r["wait_hours"] is not None]
        n_open = sum(1 for r in opened if r["kind"] == k)
        if waits or n_open or any(r["kind"] == k for r in answered):
            n_ans = sum(1 for r in answered if r["kind"] == k)
            by_kind[k] = {"total": n_ans + n_open, "open": n_open, "answered": n_ans, **wait_stats(waits)}
    buckets = {"<1 d": 0, "1-3 d": 0, "3-7 d": 0, ">7 d": 0}
    for r in opened:
        d = (r["age_hours"] or 0) / 24
        buckets["<1 d" if d < 1 else "1-3 d" if d < 3 else "3-7 d" if d < 7 else ">7 d"] += 1
    oldest = max(opened, key=lambda r: r["age_hours"] or 0, default=None)
    out({"ok": True, "op": "stats", "file": path, "now": now.strftime(TS_FMT), "since": a.since,
         "total": len(rows), "open": len(opened), "answered": len(answered),
         "wait": wait_stats([r["wait_hours"] for r in answered if r["wait_hours"] is not None]),
         "by_kind": by_kind, "open_by_age": buckets,
         "oldest_open": {"id": oldest["id"], "age_hours": oldest["age_hours"], "age": oldest["age"]} if oldest else None})


# ---------------------------------------------------------------- harness weight
# What every session loads before doing anything (config, board, waiting inbox, indexes,
# project and stream pages, open STATE.md files, the repos' CLAUDE.md / AGENTS.md) only
# grows unless something trims it. `weight` measures it against limits; `--rotate` moves
# old log rows and old acted waiting rows to <work>/archive/ (Git keeps everything anyway).

DONE_WORDS = ("done", "closed", "merged", "finished", "complete", "completed", "cancelled", "canceled",
              "hecha", "hecho", "cerrada", "cerrado", "fusionada", "terminada", "completada",
              "cancelada", "descartada", "fait", "fini", "fermé", "erledigt", "abgeschlossen")
REPO_RE = re.compile(r"^[ \t]{2}([A-Za-z0-9_.-]+):\s*\{(.*)\}", re.MULTILINE)


def config_text(a):
    config = os.path.abspath(a.config) if getattr(a, "config", None) else find_up(os.getcwd(), ".home-office.yml")
    if not config or not os.path.isfile(config):
        out({"ok": False, "error": "no .home-office.yml found (run from the work folder or pass --config)"}, 1)
    with open(config, encoding="utf-8") as fh:
        return config, fh.read()


def top_value(text: str, key: str, default=None):
    m = re.search(rf"^{key}\s*:\s*([^#\n]+)", text, re.MULTILINE)
    return m.group(1).strip().strip("'\"") if m else default


def limit_value(text: str, key: str, default: int) -> int:
    m = re.search(rf"^\s+{key}\s*:\s*([0-9_]+)", text, re.MULTILINE)
    return int(m.group(1).replace("_", "")) if m else default


def config_repos(text: str, base: str) -> dict:
    """repo key -> {path, checks (bool: any), mature (True/False/None)} from the inline entries."""
    repos = {}
    for key, body in REPO_RE.findall(text):
        path = re.search(r"\bpath\s*:\s*([^,}]+)", body)
        if not path:
            continue
        checks = re.search(r"\bchecks\s*:\s*\[([^\]]*)\]", body)
        mature = re.search(r"\bmature\s*:\s*(true|false)", body)
        repos[key] = {"path": os.path.normpath(os.path.join(base, path.group(1).strip().strip("'\""))),
                      "checks": bool(checks and checks.group(1).strip()),
                      "mature": None if not mature else mature.group(1) == "true"}
    return repos


def est_tokens(text: str) -> int:
    return round(len(text) / 4)


def state_done(path: str) -> bool:
    try:
        with open(path, encoding="utf-8") as fh:
            head = [next(fh, "") for _ in range(6)]
    except OSError:
        return False
    line = next((l for l in head if re.match(r"^\s*[^:#\n]{2,20}:", l) and not l.startswith("#")), "")
    value = line.split(":", 1)[1] if ":" in line else ""
    words = re.findall(r"[^\W\d_]+", value.lower())
    return bool(words) and words[0] in DONE_WORDS


def table_split(lines: list):
    """(before, header+sep, rows, after) of the first Markdown table in lines."""
    start = next((i for i, l in enumerate(lines) if l.strip().startswith("|")), None)
    if start is None or start + 1 >= len(lines):
        return lines, [], [], []
    end, rows = start + 2, []  # blank lines between rows (hand edits) do not end the table
    while end < len(lines) and (lines[end].strip().startswith("|") or not lines[end].strip()):
        line = lines[end].strip()
        if line and not re.match(r"^\|[\s:|-]+\|?$", line):
            rows.append(lines[end])
        end += 1
    return lines[:start], lines[start:start + 2], rows, lines[end:]


def rotate_log(log: str, archive: str, keep: int) -> int:
    with open(log, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    before, head, rows, after = table_split(lines)
    if len(rows) <= keep or not head:
        return 0
    old, rows = rows[:len(rows) - keep], rows[len(rows) - keep:]
    if os.path.isfile(archive):
        with open(archive, encoding="utf-8") as fh:
            alines = fh.read().splitlines()
        abefore, ahead, arows, aafter = table_split(alines)
        alines = abefore + (ahead or head) + arows + old + aafter
    else:
        alines = before + head + old
    os.makedirs(os.path.dirname(archive), exist_ok=True)
    with open(archive, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(alines).rstrip("\n") + "\n")
    with open(log, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(before + head + rows + after).rstrip("\n") + "\n")
    return len(old)


def rotate_waiting(path: str, archive: str, days: int, now: datetime) -> int:
    if not os.path.isfile(path):
        return 0
    data = load_waiting(path)
    old = [r for r in data["tables"][1]["rows"] if r.get("acted") and parse_ts(r.get("answered"))
           and (now - parse_ts(r["answered"])).days >= days]
    if not old:
        return 0
    arch = load_waiting(archive)
    arch["tables"][1]["rows"] = old + arch["tables"][1]["rows"]
    save_waiting(archive, arch)
    data["tables"][1]["rows"] = [r for r in data["tables"][1]["rows"] if r not in old]
    save_waiting(path, data)
    return len(old)


def cmd_weight(a) -> None:
    config, text = config_text(a)
    base, work = os.path.dirname(config), work_dir(config)
    now = wait_now(a)
    file_tokens = limit_value(text, "file_tokens", 4000)
    log_rows = limit_value(text, "log_rows", 60)
    waiting_days = limit_value(text, "waiting_days", 30)
    archive = os.path.join(work, "archive")
    board = os.path.join(work, top_value(text, "board", "BOARD.md"))
    log = os.path.join(work, top_value(text, "log", "log.md"))
    rotated = {}
    if a.rotate:
        rotated["log"] = rotate_log(log, os.path.join(archive, os.path.basename(log)), log_rows) \
            if os.path.isfile(log) else 0
        rotated["waiting"] = rotate_waiting(os.path.join(work, "waiting.md"),
                                            os.path.join(archive, "waiting.md"), waiting_days, now)

    files = [("config", config), ("board", board), ("log", log), ("waiting", os.path.join(work, "waiting.md"))]
    for m in re.finditer(r"\bpath\s*:\s*([^,}\n]+),\s*index\s*:\s*([^,}\n]+)", text):
        files.append(("index", os.path.join(base, m.group(1).strip(), m.group(2).strip())))
    for kind, pattern in (("project", ("projects", "project.md")), ("stream", ("streams", "stream.md")),
                          ("batch", ("batches", "batch.md")), ("state", ("features", "STATE.md"))):
        folder = os.path.join(work, pattern[0])
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
            path = os.path.join(folder, name, pattern[1])
            if os.path.isfile(path) and not (kind == "state" and state_done(path)):
                files.append((kind, path))
    for key, repo in config_repos(text, base).items():
        for name in ("CLAUDE.md", "AGENTS.md"):
            path = os.path.join(repo["path"], name)
            if os.path.isfile(path) and os.path.normpath(path) not in (os.path.normpath(p) for _, p in files):
                files.append(("agents:" + key, path))

    rows, total, over = [], 0, []
    for kind, path in files:
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as fh:
            body = fh.read()
        tokens = est_tokens(body)
        row = {"kind": kind, "path": os.path.relpath(path, work).replace("\\", "/"),
               "lines": body.count("\n") + (0 if body.endswith("\n") or not body else 1), "tokens": tokens}
        if kind == "log":
            row["rows"] = len(table_split(body.splitlines())[2])
            if row["rows"] > log_rows:
                row["over"] = f"{row['rows']} rows > log_rows {log_rows}: run `ho.py weight --rotate`"
        elif kind == "waiting":
            data = load_waiting(path)
            stale = [r["id"] for r in data["tables"][1]["rows"] if r.get("acted") and parse_ts(r.get("answered"))
                     and (now - parse_ts(r["answered"])).days >= waiting_days]
            if stale:
                row["over"] = f"{len(stale)} acted rows older than {waiting_days} d: run `ho.py weight --rotate`"
        elif tokens > file_tokens:
            row["over"] = f"~{tokens} tokens > file_tokens {file_tokens}: " + (
                "compact it (keep only what is live; Git keeps the rest)" if kind in ("board", "project", "stream", "batch", "state")
                else "trim it" if kind.startswith("agents:") or kind == "index" else "review it")
        row["every_session"] = kind in ("config", "board", "index")
        total += tokens if row["every_session"] else 0
        rows.append(row)
        if "over" in row:
            over.append({"path": row["path"], "why": row["over"]})
    rows.sort(key=lambda r: -r["tokens"])
    out({"ok": True, "work": work, "limits": {"file_tokens": file_tokens, "log_rows": log_rows,
                                               "waiting_days": waiting_days},
         "always_read_tokens": total, "over": over, "rotated": rotated, "files": rows})


# ---------------------------------------------------------------- repo maturity
# The classifier routes more work to the short lane in a mature repo: one with history,
# tests and checks, where an agent learns more from the code than from a SPEC.

def repo_maturity(path: str, has_checks: bool, override) -> dict:
    info = {"path": path, "checks": has_checks}
    if not os.path.isdir(path):
        return {**info, "mature": bool(override), "reason": "repo not found"}
    commits = git(path, "rev-list", "--count", "HEAD")
    first = git(path, "log", "--reverse", "--format=%ct", "--max-parents=0", "HEAD")
    files = git(path, "ls-files")
    tracked = files.stdout.splitlines() if files.returncode == 0 else []
    tests = [f for f in tracked if re.search(r"(^|/)(tests?|__tests__|spec|androidTest|test)/|"
                                           r"(Test|Tests|Spec)\.(php|kt|java|swift)$|\.(test|spec)\.[jt]sx?$", f)]
    info["commits"] = int(commits.stdout.strip() or 0) if commits.returncode == 0 else 0
    stamps = first.stdout.split()
    info["age_days"] = int((time.time() - int(stamps[0])) // 86400) if stamps else 0
    info["files"], info["test_files"] = len(tracked), len(tests)
    measured = info["commits"] >= 200 and info["test_files"] >= 20 and info["age_days"] >= 60 and has_checks
    info["mature"] = measured if override is None else override
    info["source"] = "measured" if override is None else "config"
    if override is None:
        missing = [n for n, ok in (("200 commits", info["commits"] >= 200), ("20 test files", info["test_files"] >= 20),
                                   ("60 days", info["age_days"] >= 60), ("checks", has_checks)) if not ok]
        info["reason"] = "history, tests and checks" if measured else "missing: " + ", ".join(missing)
    return info


def cmd_maturity(a) -> None:
    config, text = config_text(a)
    repos = config_repos(text, os.path.dirname(config))
    keys = a.repo or list(repos)
    unknown = [k for k in keys if k not in repos]
    if unknown:
        out({"ok": False, "error": f"unknown repos: {', '.join(unknown)}"}, 1)
    out({"ok": True, "repos": {k: repo_maturity(repos[k]["path"], repos[k]["checks"], repos[k]["mature"])
                               for k in keys}})


def main() -> None:
    p = argparse.ArgumentParser(prog="ho.py", description="home-office conductor helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("worktree")
    w.add_argument("--repo", required=True)
    w.add_argument("--dest", required=True)
    w.add_argument("--branch", required=True)
    w.add_argument("--base", required=True)
    w.add_argument("--copy", action="append", help="untracked file or folder to copy from the repo, e.g. .env or public/build")
    w.add_argument("--setup", action="append", help="command to run once in a new worktree")
    w.add_argument("--link", action="append",
                   help="dependency folder (vendor, node_modules) to clone from the main checkout with "
                        "hard links instead of installing it, when the lock files are identical (repeat)")
    w.set_defaults(fn=cmd_worktree)

    r = sub.add_parser("worktree-remove")
    r.add_argument("--repo", required=True)
    r.add_argument("--dest", required=True)
    r.add_argument("--branch", help="defaults to the worktree's branch")
    r.add_argument("--base", help="the repo's base branch; required with --delete-branch")
    r.add_argument("--delete-branch", action="store_true",
                   help="also delete the branch with git branch -d (only if merged into --base)")
    r.add_argument("--force", action="store_true",
                   help="only for ignored files or submodules left behind; never with uncommitted changes")
    r.set_defaults(fn=cmd_worktree_remove)

    s = sub.add_parser("task-start")
    s.add_argument("--worktree", required=True)
    s.add_argument("--task", required=True)
    s.add_argument("--file", action="append", help="file the TASK may change (repeat)")
    s.add_argument("--allow", action="append", help="glob the TASK may change (repeat)")
    s.add_argument("--delete", action="append",
                   help="file or folder the TASK may delete with rm / git rm / Remove-Item "
                        "(exact path, no globs; a folder covers everything under it; repeat)")
    s.add_argument("--deny", action="append", help="'glob=reason' that must never change (repeat)")
    s.add_argument("--prepare", action="append",
                   help="command run before the checks, e.g. a code generator (repeat)")
    s.add_argument("--check", action="append", help="command that must pass (repeat)")
    s.add_argument("--advisory", action="append",
                   help="command run after the checks that never blocks, e.g. 'composer audit'; its "
                        "output tail goes to `advisories` in the task result (repeat)")
    s.add_argument("--gate-seconds", type=int, default=540,
                   help="time cap of the checks gate (the app cancels hooks at ~600 s); when it is "
                        "reached the gate records `timeout` and task-end runs what is left")
    s.add_argument("--setup", action="append",
                   help="the repo's setup commands: used to reinstall a cloned dependency folder when "
                        "the TASK changes its manifest or lock file (repeat)")
    s.add_argument("--ignore", action="append",
                   help="glob of generated files that never count as changed (repeat; common "
                        "build and test artifacts are ignored already)")
    s.add_argument("--hotspot", action="append",
                   help="glob of a hot file (the repo's `hotspots`): only one feature edits it at a "
                        "time; refused while another feature holds it, unless --force (repeat)")
    s.add_argument("--base", help="the repo's base branch: unmerged feature branches then count as "
                                  "claims of the files they changed")
    s.add_argument("--attempts", type=int, default=2)
    s.add_argument("--check-timeout", type=int, default=1200)
    s.add_argument("--force", action="store_true")
    s.add_argument("--state", help="the feature's STATE.md, where task-end counts rework; by default "
                                   "found from --task 'NN-name / …' and the .home-office.yml of the "
                                   "current folder")
    s.set_defaults(fn=cmd_task_start)

    t = sub.add_parser("task-status")
    t.add_argument("--worktree", required=True)
    t.set_defaults(fn=cmd_task_status)

    e = sub.add_parser("task-end")
    e.add_argument("--worktree", required=True)
    e.add_argument("--keep", action="store_true", help="print the result but keep the scope file")
    e.add_argument("--report", help="the executor's status (done, blocked, needs-plan-change); "
                                    "blocked and needs-plan-change count as rework, like gate fail")
    e.add_argument("--no-checks", action="store_true",
                   help="close a TASK abandoned before any work, without running the checks "
                        "(gate: skipped)")
    e.add_argument("--run-checks", action="store_true",
                   help="kept for compatibility: when no checks gate ran, task-end now always runs "
                        "prepare, the scope check and the checks itself")
    e.set_defaults(fn=cmd_task_end)

    cl = sub.add_parser("claims", help="the file claims of a repo's open TASKs, as JSON")
    cl.add_argument("--repo", required=True, help="the repo or any of its worktrees")
    cl.add_argument("--base", help="also list unmerged feature branches (files changed against this base)")
    cl.set_defaults(fn=cmd_claims)

    sy = sub.add_parser("sync", help="merge the base into a clean feature worktree with no open TASK")
    sy.add_argument("--worktree", required=True)
    sy.add_argument("--base", required=True, help="the repo's base branch")
    sy.set_defaults(fn=cmd_sync)

    k = sub.add_parser("check", help="run one check through the worktree's result cache")
    k.add_argument("--worktree", required=True)
    k.add_argument("--cmd", required=True, help="the check command, exactly as the repo's `checks` lists it")
    k.add_argument("--timeout", type=int, default=1200)
    k.add_argument("--tail", type=int, default=40, help="lines of output to keep")
    k.add_argument("--no-cache", action="store_true", help="run it even if a passing result is cached")
    k.set_defaults(fn=cmd_check)

    wt = sub.add_parser("waiting", help="the waiting inbox <work>/waiting.md: add | answer | acted | list | stats")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", help="path of .home-office.yml (default: found from the current folder)")
    common.add_argument("--now", help="'YYYY-MM-DD HH:MM' instead of the clock (tests)")
    ws = wt.add_subparsers(dest="op", required=True)
    x = ws.add_parser("add", parents=[common], help="add a row for something that waits on the user")
    x.add_argument("--kind", required=True, choices=WAIT_KINDS)
    x.add_argument("--action", required=True, help="the exact question or action (git commands as git -C <repo> ...)")
    x.add_argument("--project")
    x.add_argument("--work", help="'NN-name / TASK n' or the step")
    x.add_argument("--blocks", help="what it blocks; default 'nothing else'")
    x.add_argument("--since", help="override the timestamp (default: now)")
    x = ws.add_parser("answer", parents=[common], help="record the user's answer and move the row to Answered")
    x.add_argument("id")
    x.add_argument("answer")
    x.add_argument("--at", help="override the timestamp (default: now)")
    x = ws.add_parser("acted", parents=[common], help="mark an answered row as acted on")
    x.add_argument("id")
    x = ws.add_parser("list", parents=[common], help="rows as JSON, with age and counts by kind")
    x.add_argument("--state", choices=["open", "answered", "unacted", "all"], default="open")
    y = ws.add_parser("stats", parents=[common], help="count by kind, median and p90 wait, open rows by age")
    for x in (ws.choices["list"], y):
        x.add_argument("--project")
        x.add_argument("--kind", choices=WAIT_KINDS)
        x.add_argument("--feature", help="only rows whose work starts with this, e.g. 07-x")
        x.add_argument("--since", help="only rows that started on or after YYYY-MM-DD")
    wt.set_defaults(fn=cmd_waiting)

    g = sub.add_parser("weight", help="what every session loads, against limits.file_tokens / log_rows / waiting_days")
    g.add_argument("--config", help="path of .home-office.yml (default: found from the current folder)")
    g.add_argument("--rotate", action="store_true",
                   help="move log rows beyond limits.log_rows and acted waiting rows older than "
                        "limits.waiting_days to <work>/archive/")
    g.add_argument("--now", help="'YYYY-MM-DD HH:MM' instead of the clock (tests)")
    g.set_defaults(fn=cmd_weight)

    m = sub.add_parser("maturity", help="per repo: commits, age, test files, checks and whether it is mature")
    m.add_argument("--config", help="path of .home-office.yml (default: found from the current folder)")
    m.add_argument("--repo", action="append", help="repo key (repeat; default: all)")
    m.set_defaults(fn=cmd_maturity)

    c = sub.add_parser("context")
    c.add_argument("--transcript", required=True)
    c.set_defaults(fn=cmd_context)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
