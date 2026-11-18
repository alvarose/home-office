"""Shared helpers for home-office hooks and scripts.

Everything here is fail-open: a bug in a helper must never block the user's work.
Standard library only (no PyYAML), so it runs on any machine with Python 3.8+.
"""

import fnmatch
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime

SCOPE_FILE = "home-office-task.json"
IS_WINDOWS = os.name == "nt"


# ---------------------------------------------------------------- io

def read_stdin_json() -> dict:
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def emit(obj: dict) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.flush()


# ---------------------------------------------------------------- paths

def norm(path: str) -> str:
    """Absolute, normalised, case-folded on Windows. For comparisons only."""
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def posix_rel(path: str, root: str) -> str:
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root))
    return rel.replace("\\", "/")


def find_worktree_root(start: str):
    """Closest ancestor (or start itself) that contains a .git file or folder."""
    cur = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def git_dir(worktree: str):
    """The private git dir of a worktree: .git itself, or what a .git file points to."""
    dot = os.path.join(worktree, ".git")
    if os.path.isdir(dot):
        return dot
    try:
        with open(dot, encoding="utf-8") as fh:
            line = fh.read().strip()
        if line.startswith("gitdir:"):
            target = line[len("gitdir:"):].strip()
            if not os.path.isabs(target):
                target = os.path.join(worktree, target)
            return os.path.normpath(target)
    except Exception:
        pass
    return None


def find_up(start: str, name: str):
    cur = os.path.abspath(start)
    while True:
        candidate = os.path.join(cur, name)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


# ---------------------------------------------------------------- task scope

def scope_path(worktree: str):
    gd = git_dir(worktree)
    return os.path.join(gd, SCOPE_FILE) if gd else None


def load_scope(worktree: str):
    path = scope_path(worktree)
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def save_scope(worktree: str, scope: dict) -> None:
    path = scope_path(worktree)
    if not path:
        raise RuntimeError(f"not a git worktree: {worktree}")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(scope, fh, ensure_ascii=False, indent=2)


def matches(rel: str, patterns) -> bool:
    rel_cmp = rel.lower() if IS_WINDOWS else rel
    for pat in patterns or []:
        p = pat.replace("\\", "/")
        p_cmp = p.lower() if IS_WINDOWS else p
        if rel_cmp == p_cmp or fnmatch.fnmatchcase(rel_cmp, p_cmp):
            return True
        # "dir/**" also matches "dir" contents at any depth (fnmatch '*' already crosses '/')
        if p_cmp.endswith("/**") and rel_cmp.startswith(p_cmp[:-2]):
            return True
    return False


# Artifacts that builds and test runs create. They never count as "changed by the TASK".
DEFAULT_IGNORE = [
    "**/__pycache__/**", "**/*.pyc", "**/.pytest_cache/**",
    "**/.phpunit.result.cache", "**/.phpunit.cache/**", "**/coverage/**",
    "**/node_modules/**", "**/vendor/**", "**/bootstrap/cache/**",
    "**/storage/framework/**", "**/storage/logs/**",
    "**/build/**", "**/.gradle/**", "**/.kotlin/**", "**/.cxx/**",
    "**/.idea/**", "**/.DS_Store", "**/Thumbs.db", "**/*.log",
]


def ignored(rel: str, scope: dict) -> bool:
    patterns = DEFAULT_IGNORE + list(scope.get("ignore") or [])
    # "**/x" must also match "x" at the top level
    return matches(rel, patterns) or matches("_/" + rel, patterns)


def in_scope(rel: str, scope: dict) -> bool:
    files = scope.get("files") or []
    allow = scope.get("allow") or []
    if not files and not allow:
        return True  # open scope (short lane): only the deny list applies
    return matches(rel, files) or matches(rel, allow)


def in_delete_list(rel: str, scope: dict) -> bool:
    """Exact paths only (no globs); a listed folder covers everything under it."""
    rel_cmp = rel.lower() if IS_WINDOWS else rel
    for path in scope.get("delete") or []:
        p = path.replace("\\", "/").rstrip("/")
        p_cmp = p.lower() if IS_WINDOWS else p
        if p_cmp and (rel_cmp == p_cmp or rel_cmp.startswith(p_cmp + "/")):
            return True
    return False


def deleted_as_planned(worktree: str, rel: str, scope: dict) -> bool:
    """A file the TASK lists for deletion and that is gone now."""
    return in_delete_list(rel, scope) and not os.path.lexists(os.path.join(worktree, rel))


def denied(rel: str, scope: dict):
    for rule in scope.get("deny") or []:
        if isinstance(rule, str):
            rule = {"glob": rule}
        if matches(rel, [rule.get("glob", "")]):
            return rule.get("reason") or f"matches forbidden path {rule.get('glob')}"
    return None


# ---------------------------------------------------------------- git

def git(worktree: str, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", worktree, *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def changed_files(worktree: str):
    """Modified, added, deleted and untracked files, relative to the worktree, posix style."""
    out = git(worktree, "status", "--porcelain", "--untracked-files=all")
    if out.returncode != 0:
        return []
    files = []
    for line in out.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ")[-1]
        files.append(path.strip('"').replace("\\", "/"))
    return files


def file_hash(worktree: str, rel: str) -> str:
    path = os.path.join(worktree, rel)
    if not os.path.exists(path):
        return "deleted"
    if os.path.isdir(path):
        return "dir"
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(worktree: str) -> dict:
    return {rel: file_hash(worktree, rel) for rel in changed_files(worktree)}


def changed_since(worktree: str, baseline: dict):
    """Files whose content differs from the baseline taken at task start."""
    result = []
    for rel in changed_files(worktree):
        if baseline.get(rel) != file_hash(worktree, rel):
            result.append(rel)
    # files that were dirty at start and are now clean again also count as touched
    current = set(changed_files(worktree))
    for rel in baseline:
        if rel not in current and rel not in result:
            result.append(rel)
    return result


# ---------------------------------------------------------------- commands

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def windows_command(cmd: str) -> str:
    """'./gradlew test' style commands do not run under cmd.exe."""
    if not IS_WINDOWS:
        return cmd
    stripped = cmd.strip()
    if stripped.startswith("./gradlew"):
        return "gradlew.bat" + stripped[len("./gradlew"):]
    if stripped.startswith("./"):
        return stripped[2:]
    return cmd


def save_failed_output(cmd: str, text: str) -> str:
    """Write the full output of a failed check to the temp folder; returns a note with its path.

    The tail kept in the report is often too short to see the real cause of a failure
    (e.g. the underlying message of an exception). Never raises."""
    try:
        import tempfile
        folder = os.path.join(tempfile.gettempdir(), "home-office-checks")
        os.makedirs(folder, exist_ok=True)
        slug = re.sub(r"[^A-Za-z0-9]+", "-", cmd).strip("-")[:40] or "check"
        path = os.path.join(folder, f"{time.strftime('%Y%m%d-%H%M%S')}-{slug}.log")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"$ {cmd}\n\n{text}\n")
        return f"\n(full output: {path})"
    except Exception:
        return ""


def kill_tree(proc) -> None:
    """Kill a process and everything it started (a shell leaves its children running)."""
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


def run_check_ex(cmd: str, cwd: str, timeout: float = 1200, tail: int = 40):
    """Run a shell command: (ok, tail of its output, timed_out).

    Output goes to a temp file, not a pipe, and a timeout kills the whole process tree: a
    pipe held open by a grandchild would otherwise make the call wait for it after the kill."""
    fd, path = tempfile.mkstemp(prefix="ho-check-", suffix=".out")
    try:
        with os.fdopen(fd, "wb") as fh:
            extra = {} if IS_WINDOWS else {"start_new_session": True}
            proc = subprocess.Popen(windows_command(cmd), cwd=cwd, shell=True, stdout=fh,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **extra)
            try:
                proc.wait(timeout=max(1.0, float(timeout)))
            except subprocess.TimeoutExpired:
                kill_tree(proc)
                try:
                    proc.wait(timeout=10)
                except Exception:
                    pass
                return False, f"timed out after {int(timeout)}s", True
        with open(path, "rb") as fh:
            full = ANSI.sub("", fh.read().decode("utf-8", errors="replace")).strip()
        ok = proc.returncode == 0
        note = "" if ok else save_failed_output(cmd, full)
        return ok, "\n".join(full.splitlines()[-tail:]) + note, False
    except Exception as exc:  # command not found, etc.
        return False, f"could not run: {exc}", False
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def run_check(cmd: str, cwd: str, timeout: float = 1200, tail: int = 40):
    ok, text, _ = run_check_ex(cmd, cwd, timeout, tail)
    return ok, text


# ---------------------------------------------------------------- check cache

CHECKS_CACHE = "home-office-checks.json"
CACHE_KEEP = 60


def tree_state(worktree: str):
    """Hash of the worktree's content: `git write-tree` of a temporary index that holds the
    working tree (tracked changes and untracked files that are not ignored). Any edit, new
    file or deletion changes it; the real index is never touched. None when git cannot say."""
    gd = git_dir(worktree)
    if not gd:
        return None
    tmp = os.path.join(gd, f"home-office-index-{os.getpid()}")
    env = dict(os.environ, GIT_INDEX_FILE=tmp)

    def run_git(*args):
        return subprocess.run(["git", "-C", worktree, *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env)
    try:
        real = os.path.join(gd, "index")
        if os.path.isfile(real):
            shutil.copyfile(real, tmp)  # keeps git's stat cache: unchanged files are not rehashed
        else:
            run_git("read-tree", "HEAD")  # fails on an unborn branch: the index then starts empty
        if run_git("add", "-A").returncode != 0:
            return None
        res = run_git("write-tree")
        return (res.stdout.strip() or None) if res.returncode == 0 else None
    except Exception:
        return None
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _cache_file(worktree: str):
    gd = git_dir(worktree)
    return os.path.join(gd, CHECKS_CACHE) if gd else None


def _load_cache(worktree: str) -> dict:
    try:
        with open(_cache_file(worktree), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_cache(worktree: str, cache: dict) -> None:
    path = _cache_file(worktree)
    if not path:
        return
    if len(cache) > CACHE_KEEP:
        keep = sorted(cache.items(), key=lambda kv: kv[1].get("at_epoch", 0))[-CACHE_KEEP:]
        cache = dict(keep)
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass


def run_cached_check(worktree: str, cmd: str, timeout: float = 1200, tail: int = 40,
                     use_cache: bool = True) -> dict:
    """Run one check through the result cache of the worktree.

    The key is (command, tree state): any change to the files invalidates it, and each
    worktree keeps its own entries in its private git dir. Only passes are cached; a failure
    always runs again. Fail-open: if the tree state cannot be computed, the check just runs.
    Returns {ok, cached, tail, seconds, timed_out, tree, at}."""
    started = time.monotonic()
    cmd = cmd.strip()
    tree = tree_state(worktree) if use_cache else None
    key = hashlib.sha256(f"{cmd}\0{tree}".encode("utf-8")).hexdigest() if tree else None
    if key:
        entry = _load_cache(worktree).get(key)
        if entry and entry.get("ok") and entry.get("cmd") == cmd and entry.get("tree") == tree:
            return {"ok": True, "cached": True, "tail": entry.get("tail", ""),
                    "seconds": round(time.monotonic() - started, 3),
                    "ran_seconds": entry.get("seconds"), "timed_out": False, "tree": tree,
                    "at": entry.get("at")}
    ok, text, timed_out = run_check_ex(cmd, worktree, timeout=timeout, tail=tail)
    seconds = round(time.monotonic() - started, 2)
    at = time.strftime("%Y-%m-%d %H:%M:%S")
    if ok and key:
        cache = _load_cache(worktree)
        cache[key] = {"cmd": cmd, "tree": tree, "ok": True, "tail": text, "seconds": seconds,
                      "at": at, "at_epoch": time.time()}
        _save_cache(worktree, cache)
    return {"ok": ok, "cached": False, "tail": text, "seconds": seconds,
            "timed_out": timed_out, "tree": tree, "at": at}


# ---------------------------------------------------------------- task evaluation

def run_prepare(worktree: str, scope: dict, run):
    """Run the TASK's prepare commands (code generators, formatters) before the checks.

    `run(cmd)` runs one command and returns (ok, tail, hit_gate_cap).
    Returns (problems, results, generated): `generated` are the files the commands wrote that
    the TASK did not touch itself; they never count as changed by the TASK (they are
    regenerated from its files). A file the executor had already changed (it differs from the
    task-start baseline) is not generated even if a formatter rewrote it: it stays subject to
    the TASK's file list, so a formatter cannot launder an out-of-scope edit.
    """
    commands = scope.get("prepare") or []
    if not commands:
        return [], [], []

    def state(rel):
        try:
            mtime = os.stat(os.path.join(worktree, rel)).st_mtime_ns
        except OSError:
            mtime = None
        return file_hash(worktree, rel), mtime

    # A generator may rewrite a file with identical content: the mtime changes, the hash not.
    before = {rel: state(rel) for rel in changed_files(worktree)}
    problems, results = [], []
    for cmd in commands:
        ok, tail, hit = run(cmd)
        results.append({"prepare": cmd, "ok": None if hit else ok})
        if hit:
            break
        if not ok:
            problems.append(f"$ {cmd}   (prepare)\n{tail}")
            break
    baseline = scope.get("baseline") or {}
    known = set(scope.get("generated") or [])
    generated = []
    for rel in changed_files(worktree):
        old_hash, old_mtime = before.get(rel, (None, None))
        new_hash, new_mtime = state(rel)
        if old_hash == new_hash and old_mtime == new_mtime:
            continue
        if rel in before and rel not in known and baseline.get(rel) != old_hash:
            continue  # the executor's own edit (a formatter rewrote it): not generated
        generated.append(rel)
    return problems, results, generated


ADVISORY_SECONDS = 180


def evaluate_task(worktree: str, scope: dict, budget=None) -> list:
    """Prepare commands, scope of the changed files, then checks, then advisories.

    Updates `scope` in place. Returns the list of problems (empty when the TASK passes).

    `budget` (seconds) is the checks gate's time cap: the app cancels a SubagentStop hook
    after ~600 s, so the gate must give up cleanly before that. When a command does not
    finish inside it, `scope["gate_timeout"]` says which and nothing is reported as a
    problem for it: the caller leaves the evaluation to `task-end`, which has no cap and
    does not repeat the checks that already passed (`scope["checks_passed"]`).

    Checks go through the worktree's result cache (`run_cached_check`): one that already
    passed on this exact tree, e.g. run by the executor, is not run again.
    """
    timeout = int(scope.get("check_timeout") or 1200)
    deadline = time.monotonic() + budget if budget else None
    redo = set(scope.get("checks_passed") or []) if scope.get("gate") == "timeout" else set()
    scope.pop("gate_timeout", None)

    last = {}

    def run(cmd, cap=timeout, soft=False, cached=False):
        last.clear()
        left = cap
        if deadline is not None:
            left = min(cap, deadline - time.monotonic())
            if left < 1:
                if not soft:
                    scope["gate_timeout"] = {"command": cmd, "seconds": int(budget),
                                             "note": "not started: no time left"}
                return False, f"not run: the gate's {int(budget)}s cap was reached", True
        if cached:
            res = run_cached_check(worktree, cmd, timeout=left)
            ok, tail, expired = res["ok"], res["tail"], res["timed_out"]
            last.update(cached=res["cached"], seconds=res["seconds"])
        else:
            ok, tail, expired = run_check_ex(cmd, worktree, timeout=left)
        hit = expired and deadline is not None and left < cap
        if hit and not soft:
            scope["gate_timeout"] = {"command": cmd, "seconds": int(budget)}
        return ok, tail, hit

    prep_problems, results, generated = run_prepare(worktree, scope, run)
    scope["generated"] = sorted(set(scope.get("generated") or []) | set(generated))
    gen = set(scope["generated"])

    touched = [f for f in changed_since(worktree, scope.get("baseline") or {})
               if not ignored(f, scope)]
    outside = [f for f in touched if f not in gen and not in_scope(f, scope)
               and not deleted_as_planned(worktree, f, scope)]
    forbidden = [f"{f} ({denied(f, scope)})" for f in touched if f not in gen and denied(f, scope)]

    problems = []
    if forbidden:
        problems.append("Forbidden paths changed (hard rules):\n  " + "\n  ".join(forbidden))
    if outside:
        problems.append("Files changed outside the TASK's file list:\n  " + "\n  ".join(outside)
                        + "\nRevert those changes, or stop and report `needs-plan-change`.")
    problems.extend(prep_problems)

    passed = []
    if not problems and not scope.get("gate_timeout"):
        for cmd in scope.get("checks") or []:
            if cmd in redo:
                results.append({"check": cmd, "ok": True,
                                "skipped": "passed before the gate timed out"})
                passed.append(cmd)
                continue
            ok, tail, hit = run(cmd, cached=True)
            if hit:
                results.append({"check": cmd, "ok": None, "timeout": True})
                break
            results.append({"check": cmd, "ok": ok, **({"cached": True} if last.get("cached") else {})})
            if ok:
                passed.append(cmd)
            else:
                problems.append(f"$ {cmd}\n{tail}")
    scope["checks_passed"] = passed

    # Advisories (audits and the like): never blocking, run once the checks are settled.
    scope["advisories"] = []
    if not problems and not scope.get("gate_timeout"):
        for cmd in scope.get("advisory") or []:
            ok, tail, hit = run(cmd, cap=min(timeout, ADVISORY_SECONDS), soft=True)
            scope["advisories"].append({"command": cmd, "ok": None if hit else ok,
                                        "output": "\n".join(tail.splitlines()[-12:])})

    scope["touched"] = touched
    scope["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
    scope["results"] = results
    return problems


# ---------------------------------------------------------------- transcripts

def last_context_tokens(transcript_path: str, tail_bytes: int = 400_000):
    """Context size of the latest main-session model call, from the transcript's usage data."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    try:
        size = os.path.getsize(transcript_path)
        with open(transcript_path, "rb") as fh:
            fh.seek(max(0, size - tail_bytes))
            chunk = fh.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    for line in reversed(chunk.splitlines()):
        if '"usage"' not in line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            continue
        usage = (entry.get("message") or {}).get("usage") or {}
        total = (usage.get("input_tokens") or 0) + (usage.get("cache_creation_input_tokens") or 0) \
            + (usage.get("cache_read_input_tokens") or 0)
        if total:
            return total
    return None


def last_model(transcript_path: str, tail_bytes: int = 400_000):
    """Model id of the latest main-session model call (e.g. "claude-sonnet-…"), or None."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    try:
        size = os.path.getsize(transcript_path)
        with open(transcript_path, "rb") as fh:
            fh.seek(max(0, size - tail_bytes))
            chunk = fh.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    for line in reversed(chunk.splitlines()):
        if '"model"' not in line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            continue
        model = (entry.get("message") or {}).get("model") or ""
        if model and not model.startswith("<"):  # "<synthetic>" for app-made messages
            return model
    return None


def session_start(transcript_path: str):
    """Epoch seconds of the first timestamp in a session transcript, or None."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i > 50:
                    break
                m = re.search(r'"timestamp"\s*:\s*"([^"]+)"', line)
                if m:
                    stamp = m.group(1).replace("Z", "+00:00")
                    return datetime.fromisoformat(stamp).timestamp()
    except Exception:
        return None
    return None


# ---------------------------------------------------------------- work folder and STATE.md

WORK_RE = re.compile(r"^\s*work\s*:\s*['\"]?([^'\"#\s]+)", re.MULTILINE)
FEATURE_RE = re.compile(r"^(\d+)(-\S+)?$")


def work_dir(config_path: str) -> str:
    """The `work:` folder of a `.home-office.yml` (absolute), else the config's folder."""
    base = os.path.dirname(os.path.abspath(config_path))
    try:
        with open(config_path, encoding="utf-8") as fh:
            m = WORK_RE.search(fh.read())
        if m:
            return os.path.normpath(os.path.join(base, m.group(1)))
    except Exception:
        pass
    return base


def feature_state(task: str, start: str):
    """STATE.md of the feature a TASK belongs to ("NN-name / TASK n"), found from the
    `.home-office.yml` at or above `start`. None for short-lane and task runs."""
    feature = (task or "").split("/")[0].strip()
    m = FEATURE_RE.match(feature)
    config = find_up(start, ".home-office.yml") if m else None
    if not config:
        return None
    features = os.path.join(work_dir(config), "features")
    try:
        names = sorted(os.listdir(features))
    except OSError:
        return None
    for name in names:
        if name == feature or (name.startswith(m.group(1) + "-") and name.startswith(feature)):
            path = os.path.join(features, name, "STATE.md")
            return path if os.path.isfile(path) else None
    return None


# Header line that counts the TASKs that went back. Found by label, else by being the only
# header line whose value is a bare number (documents may be translated); a missing line is
# added after the third header line (Branches), as in the template.
REWORK_LABELS = {"rework", "vueltas atrás", "vueltas atras", "retrabajo", "reintentos",
                 "repetición de trabajo"}
COUNT_RE = re.compile(r"^(?P<label>[^:\r\n]{1,40}?)\s*:\s*(?P<n>\d+)(?P<rest>(?:\s.*)?)$")


def bump_rework(path: str) -> int:
    """Add 1 to the rework line of a STATE.md header and return the new count."""
    with open(path, encoding="utf-8", newline="") as fh:
        text = fh.read()
    lines = text.splitlines(keepends=True)
    eol = "\r\n" if "\r\n" in text else "\n"
    start, end = 0, len(lines)
    for i, line in enumerate(lines):
        bare = line.lstrip("﻿")
        if bare.startswith("## "):
            end = i
            break
        if bare.startswith("# ") and start == 0:
            start = i + 1
    header = [i for i in range(start, end) if lines[i].strip()]

    def parse(i):
        return COUNT_RE.match(lines[i].rstrip("\r\n").strip())

    found = next((i for i in header if parse(i) and
                  parse(i).group("label").strip("*-_ ").lower() in REWORK_LABELS), None)
    if found is None:
        found = next((i for i in header if parse(i)), None)
    if found is None:
        at = header[2] + 1 if len(header) >= 3 else (header[-1] + 1 if header else start)
        if at > 0 and not lines[at - 1].endswith(("\n", "\r")):
            lines[at - 1] += eol
        lines.insert(at, f"Rework: 1{eol}")
        count = 1
    else:
        line = lines[found]
        body = line.rstrip("\r\n")
        m = COUNT_RE.match(body.strip())
        count = int(m.group("n")) + 1
        indent = body[:len(body) - len(body.lstrip())]
        lines[found] = (f"{indent}{m.group('label')}: {count}{m.group('rest')}"
                        f"{line[len(body):]}")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write("".join(lines))
    os.replace(tmp, path)
    return count
