"""UserPromptSubmit hook: give home-office sessions a title you can find them by.

Acts only in sessions opened under a folder that has a `.home-office.yml`, and only on
prompts that start a home-office command:
  - `/home-office:resume NN[-name] [--tuning]` -> "feat: NN-name #n" (" · tuning" for --tuning),
    with the full name taken from `<work>/features/` and n the session's number in that
    feature: `new`'s session is #1, each resume session gets the next one (kept per session
    id in `<work>/features/NN-name/sessions.json`, so re-running resume keeps the number);
  - `/home-office:new <request>`                -> "new: <request, shortened>";
  - `/home-office:task <request>`               -> "task: <request, shortened>".
The conductor can refine the title later (e.g. "feat: NN-name" once `new` assigns NN).

It never blocks anything. Fail-open. `HOME_OFFICE_TITLE=0` disables it.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import emit, find_up, read_stdin_json  # noqa: E402

# A hand-over session's first message starts with a "Background…" block from the app, so the
# resume command may be on any line, not only the first.
RESUME_RE = re.compile(r"^[ \t]*/home-office:resume[ \t]+(\S+)([^\n]*)$", re.MULTILINE)
NEW_RE = re.compile(r"^\s*/home-office:(new|task)\s+(.+)$", re.DOTALL)
WORK_RE = re.compile(r"^\s*work\s*:\s*['\"]?([^'\"#\s]+)", re.MULTILINE)
MAX_LEN = 60


def work_dir(config_path: str) -> str:
    base = os.path.dirname(config_path)
    try:
        with open(config_path, encoding="utf-8") as fh:
            m = WORK_RE.search(fh.read())
        if m:
            return os.path.normpath(os.path.join(base, m.group(1)))
    except Exception:
        pass
    return base


def feature_name(config_path: str, arg: str) -> str:
    """`03` or `03-x` -> the folder name in <work>/features/ that starts with it, else `arg`."""
    number = arg.split("-", 1)[0]
    try:
        names = sorted(os.listdir(os.path.join(work_dir(config_path), "features")))
    except OSError:
        return arg
    for name in names:
        if name == arg or (name.startswith(number + "-") and name.startswith(arg)):
            return name
    return arg


def session_number(config_path: str, feature: str, session_id: str):
    """This session's number within the feature (#1 is the `new` session), or None."""
    folder = os.path.join(work_dir(config_path), "features", feature)
    if not session_id or not os.path.isdir(folder):
        return None
    path = os.path.join(folder, "sessions.json")
    try:
        with open(path, encoding="utf-8") as fh:
            numbers = json.load(fh)
    except Exception:
        numbers = {}
    if session_id not in numbers:
        numbers[session_id] = max([1] + [n for n in numbers.values() if isinstance(n, int)]) + 1
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(numbers, fh, indent=1)
    return numbers[session_id]


def shorten(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= MAX_LEN else text[:MAX_LEN - 1].rstrip() + "…"


def title_for(prompt: str, config_path: str, session_id: str = ""):
    m = RESUME_RE.search(prompt)
    if m:
        feature = feature_name(config_path, m.group(1))
        title = "feat: " + feature
        n = session_number(config_path, feature, session_id)
        if n:
            title += f" #{n}"
        return title + (" · tuning" if "--tuning" in m.group(2) else "")
    m = NEW_RE.match(prompt)
    if m:
        return m.group(1) + ": " + shorten(m.group(2).strip().strip("\"'"))
    return None


def main() -> None:
    if os.environ.get("HOME_OFFICE_TITLE") == "0":
        return
    data = read_stdin_json()
    if data.get("agent_id"):
        return
    config = find_up(data.get("cwd") or os.getcwd(), ".home-office.yml")
    if not config:
        return
    title = title_for(data.get("prompt") or "", config, data.get("session_id") or "")
    if title:
        emit({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "sessionTitle": title}})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # fail-open
        sys.stderr.write(f"home-office session_title: {exc}\n")
