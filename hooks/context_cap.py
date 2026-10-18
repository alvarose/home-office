"""UserPromptSubmit / PostToolUse(Agent|Task) hook: keep sessions short.

Acts only in sessions opened under a folder that has a `.home-office.yml`.
Reads the size of the current context from the session transcript and:
  - at 80 % of `limits.context_tokens` (default 150,000): warns once;
  - at 100 %: warns the user and tells the model to wrap up with /home-office:close
    (on every prompt; after tools, only once).

It never blocks anything. Fail-open. `HOME_OFFICE_CAP=0` disables it for a session.
"""

import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import emit, find_up, last_context_tokens, read_stdin_json  # noqa: E402

DEFAULT_CAP = 150_000
CAP_RE = re.compile(r"^\s*context_tokens\s*:\s*([0-9_]+)", re.MULTILINE)
INLINE_CAP_RE = re.compile(r"context_tokens\s*:\s*([0-9_]+)")


def cap_from(config_path: str) -> int:
    try:
        with open(config_path, encoding="utf-8") as fh:
            text = fh.read()
        m = CAP_RE.search(text) or INLINE_CAP_RE.search(text)
        if m:
            return int(m.group(1).replace("_", ""))
    except Exception:
        pass
    return DEFAULT_CAP


def state_path(session_id: str) -> str:
    base = os.environ.get("CLAUDE_PLUGIN_DATA") or tempfile.gettempdir()
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "unknown")
    return os.path.join(base, f"home-office-ctx-{safe}.json")


def load_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_state(path: str, state: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
    except Exception:
        pass


def main() -> None:
    if os.environ.get("HOME_OFFICE_CAP") == "0":
        return
    data = read_stdin_json()
    if data.get("agent_id"):
        return  # subagents are short-lived by design
    event = data.get("hook_event_name") or "UserPromptSubmit"
    config = find_up(data.get("cwd") or os.getcwd(), ".home-office.yml")
    if not config:
        return
    cap = cap_from(config)
    tokens = last_context_tokens(data.get("transcript_path"))
    if not tokens or tokens < 0.8 * cap:
        return

    spath = state_path(data.get("session_id"))
    state = load_state(spath)
    k = f"{tokens // 1000}k"

    if tokens >= cap:
        if event != "UserPromptSubmit" and state.get("hard"):
            return
        state["hard"] = True
        save_state(spath, state)
        emit({
            "systemMessage": f"home-office: this session is at {k} tokens (cap {cap // 1000}k). "
                             f"Run /home-office:close and continue in a new session.",
            "hookSpecificOutput": {
                "hookEventName": event,
                "additionalContext": (
                    f"[home-office] Context is {tokens} tokens, over the cap of {cap}. Do not start "
                    f"new work in this session. Finish the current step, update STATE.md, and ask the "
                    f"user to run /home-office:close and continue with /home-office:resume in a new "
                    f"session."),
            },
        })
        return

    if state.get("soft"):
        return
    state["soft"] = True
    save_state(spath, state)
    emit({
        "systemMessage": f"home-office: this session is at {k} tokens (80 % of the "
                         f"{cap // 1000}k cap). Plan to close it soon.",
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": (
                f"[home-office] Context is {tokens} tokens, 80 % of the {cap} cap. Keep the rest of "
                f"this session short; prefer finishing the current step and closing."),
        },
    })


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # fail-open
        sys.stderr.write(f"home-office context_cap: {exc}\n")
