"""UserPromptSubmit / PostToolUse(Agent|Task) hook: keep sessions short.

Acts only in sessions opened under a folder that has a `.home-office.yml`.
Reads the size of the current context from the session transcript and:
  - at 80 % of `limits.context_tokens` (default 150,000): warns once;
  - at 100 %: warns the user and tells the model to wrap up with /home-office:close
    (on every prompt; after tools, only once).

Loose sessions (opened in the work folder without a home-office command: a long-running
watcher, a server chat, a conversation) and `status` sessions also get, on a prompt, once each:
  - a warning when they run on another model than `roles.conductor` (e.g. a top-tier one);
  - a warning when they have been open for `limits.loose_session_hours` (default 12):
    long jobs go to `/home-office:task`, one step per short session with a hand-over note.
At the cap they are told to hand over to a new session instead of /home-office:close.

It never blocks anything. Fail-open. `HOME_OFFICE_CAP=0` disables it for a session.
"""

import json
import os
import re
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (emit, find_up, last_context_tokens, last_model,  # noqa: E402
                     read_stdin_json, session_start)

DEFAULT_CAP = 150_000
DEFAULT_LOOSE_HOURS = 12
CAP_RE = re.compile(r"^\s*context_tokens\s*:\s*([0-9_]+)", re.MULTILINE)
INLINE_CAP_RE = re.compile(r"context_tokens\s*:\s*([0-9_]+)")
LOOSE_RE = re.compile(r"loose_session_hours\s*:\s*([0-9.]+)")
CONDUCTOR_RE = re.compile(r"^\s*conductor\s*:\s*\{[^}\n]*\bmodel\s*:\s*['\"]?([\w.-]+)", re.MULTILINE)
# Any home-office command but status makes a session part of the flow (new, resume, task, close…).
FLOW_RE = re.compile(r"/home-office:(?!status\b)[a-z][\w-]*")
STATUS_CMD_RE = re.compile(r"/home-office:status\b")
JOB = ("Long jobs (a watcher, a server, a bot) run as /home-office:task \"<job>\", one step per "
       "short session that ends with a hand-over note for the next one.")


def read_config(config_path: str) -> str:
    try:
        with open(config_path, encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return ""


def cap_from(text: str) -> int:
    m = CAP_RE.search(text) or INLINE_CAP_RE.search(text)
    try:
        return int(m.group(1).replace("_", "")) if m else DEFAULT_CAP
    except ValueError:
        return DEFAULT_CAP


def loose_hours(text: str) -> float:
    m = LOOSE_RE.search(text)
    try:
        return float(m.group(1)) if m else DEFAULT_LOOSE_HOURS
    except ValueError:
        return DEFAULT_LOOSE_HOURS


def conductor_model(text: str):
    m = CONDUCTOR_RE.search(text)
    model = m.group(1).lower() if m else "sonnet"
    return None if model in ("inherit", "default") else model


def head(transcript_path: str, size: int = 131_072) -> str:
    try:
        with open(transcript_path, "rb") as fh:
            return fh.read(size).decode("utf-8", errors="replace")
    except Exception:
        return ""


def session_kind(data: dict, state: dict) -> str:
    """flow (a home-office command started it), status, or loose. Once flow, always flow."""
    prompt = data.get("prompt") or ""
    if state.get("kind") == "flow" or FLOW_RE.search(prompt):
        return "flow"
    if state.get("kind"):
        return state["kind"]
    text = head(data.get("transcript_path")) + "\n" + prompt
    return "flow" if FLOW_RE.search(text) else ("status" if STATUS_CMD_RE.search(text) else "loose")


def loose_warning(data: dict, config_text: str, state: dict, kind: str):
    """(message for the user, context for the model) for a loose or status session, or None."""
    what = ("a status session (status is a snapshot: the work it lists runs in its own sessions)"
            if kind == "status" else "a loose session (not started by a home-office command)")
    model, want = last_model(data.get("transcript_path")), conductor_model(config_text)
    if model and want and want not in model.lower() and not state.get("model_warned"):
        state["model_warned"] = True
        return (f"home-office: this is {what}, running on {model}. Loose work runs on the "
                f"conductor's model: switch with /model {want}, or start it as /home-office:task. {JOB}",
                f"[home-office] This is {what}, on {model}, not the conductor's model ({want}). Tell "
                f"the user once, in their language, that loose work should run on {want} (/model "
                f"{want}) and that a long job goes to /home-office:task in short sessions with a "
                f"hand-over note. Then do what they asked.")
    started, hours = session_start(data.get("transcript_path")), loose_hours(config_text)
    if started and not state.get("age_warned"):
        age = (time.time() - started) / 3600
        if age >= hours:
            state["age_warned"] = True
            return (f"home-office: this is {what}, open for {age:.0f} h (limit {hours:g} h). "
                    f"Write a short hand-over note and continue in a new session. {JOB}",
                    f"[home-office] This is {what}, open for {age:.0f} hours (limit {hours:g}). "
                    f"Finish the current step, then propose to the user a short hand-over note "
                    f"(what is done, the state, the next step) and a new session for the next step, "
                    f"started with /home-office:task. Do not keep this session going for days.")
    return None


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
    config_text = read_config(config)
    cap = cap_from(config_text)
    spath = state_path(data.get("session_id"))
    state = load_state(spath)
    kind = session_kind(data, state)
    if state.get("kind") != kind:
        state["kind"] = kind
        save_state(spath, state)

    if kind != "flow" and event == "UserPromptSubmit":
        warning = loose_warning(data, config_text, state, kind)
        if warning:
            save_state(spath, state)
            emit({"systemMessage": warning[0],
                  "hookSpecificOutput": {"hookEventName": event, "additionalContext": warning[1]}})
            return

    tokens = last_context_tokens(data.get("transcript_path"))
    if not tokens or tokens < 0.8 * cap:
        return
    k = f"{tokens // 1000}k"

    if tokens >= cap:
        if event != "UserPromptSubmit" and state.get("hard"):
            return
        state["hard"] = True
        save_state(spath, state)
        if kind == "flow":
            tell = "Run /home-office:close and continue in a new session."
            context = ("update STATE.md, and ask the user to run /home-office:close and continue "
                       "with /home-office:resume in a new session.")
        else:
            tell = "Write a short hand-over note and continue in a new session."
            context = ("write a short hand-over note (what is done, the state, the next step) and "
                       "propose a new session for the next step, started with /home-office:task.")
        emit({
            "systemMessage": f"home-office: this session is at {k} tokens (cap {cap // 1000}k). {tell}",
            "hookSpecificOutput": {
                "hookEventName": event,
                "additionalContext": (
                    f"[home-office] Context is {tokens} tokens, over the cap of {cap}. Do not start "
                    f"new work in this session. Finish the current step, {context}"),
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
