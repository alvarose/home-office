"""UserPromptSubmit hook: give home-office sessions a title you can find them by.

Acts only in sessions opened under a folder that has a `.home-office.yml`, and only on
prompts that start a home-office command:
  - `/home-office:resume NN[-name] [--tuning]` -> "feat: NN-name" (" · tuning" for --tuning),
    with the full name taken from `<work>/features/`;
  - `/home-office:new <request>`                -> "new: <request, shortened>".
The conductor can refine the title later (e.g. "feat: NN-name" once `new` assigns NN).

It never blocks anything. Fail-open. `HOME_OFFICE_TITLE=0` disables it.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import emit, find_up, read_stdin_json  # noqa: E402

RESUME_RE = re.compile(r"^\s*/home-office:resume\s+(\S+)(.*)$", re.DOTALL)
NEW_RE = re.compile(r"^\s*/home-office:new\s+(.+)$", re.DOTALL)
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


def shorten(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= MAX_LEN else text[:MAX_LEN - 1].rstrip() + "…"


def title_for(prompt: str, config_path: str):
    m = RESUME_RE.match(prompt)
    if m:
        title = "feat: " + feature_name(config_path, m.group(1))
        return title + (" · tuning" if "--tuning" in m.group(2) else "")
    m = NEW_RE.match(prompt)
    if m:
        return "new: " + shorten(m.group(1).strip().strip("\"'"))
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
    title = title_for(data.get("prompt") or "", config)
    if title:
        emit({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "sessionTitle": title}})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # fail-open
        sys.stderr.write(f"home-office session_title: {exc}\n")
