"""Shared helpers for home-office hooks and scripts.

Everything here is fail-open: a bug in a helper must never block the user's work.
Standard library only (no PyYAML), so it runs on any machine with Python 3.8+.
"""

import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import time

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


def run_check(cmd: str, cwd: str, timeout: int = 1200, tail: int = 40):
    try:
        res = subprocess.run(windows_command(cmd), cwd=cwd, shell=True, capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=timeout)
        full = ANSI.sub("", (res.stdout or "") + (res.stderr or "")).strip()
        lines = full.splitlines()
        note = "" if res.returncode == 0 else save_failed_output(cmd, full)
        return res.returncode == 0, "\n".join(lines[-tail:]) + note
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"
    except Exception as exc:  # command not found, etc.
        return False, f"could not run: {exc}"


# ---------------------------------------------------------------- task evaluation

def run_prepare(worktree: str, scope: dict, timeout: int):
    """Run the TASK's prepare commands (code generators and the like) before the checks.

    Returns (problems, results, generated): `generated` are the files the commands wrote,
    which never count as changed by the TASK (they are regenerated from the TASK's files).
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
        ok, tail = run_check(cmd, worktree, timeout=timeout)
        results.append({"prepare": cmd, "ok": ok})
        if not ok:
            problems.append(f"$ {cmd}   (prepare)\n{tail}")
            break
    generated = []
    for rel in changed_files(worktree):
        old_hash, old_mtime = before.get(rel, (None, None))
        new_hash, new_mtime = state(rel)
        if old_hash != new_hash or old_mtime != new_mtime:
            generated.append(rel)
    return problems, results, generated


def evaluate_task(worktree: str, scope: dict) -> list:
    """Prepare commands, scope of the changed files, then checks. Updates `scope` in place.

    Returns the list of problems (empty when the TASK passes).
    """
    timeout = int(scope.get("check_timeout") or 1200)
    prep_problems, results, generated = run_prepare(worktree, scope, timeout)
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

    if not problems:
        for cmd in scope.get("checks") or []:
            ok, tail = run_check(cmd, worktree, timeout=timeout)
            results.append({"check": cmd, "ok": ok})
            if not ok:
                problems.append(f"$ {cmd}\n{tail}")

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
