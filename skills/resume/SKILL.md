---
name: resume
description: Resume a home-office feature in a fresh session from its STATE.md. Use only when the user invokes /home-office:resume, or when the session's first message has a line `/home-office:resume NN-name` (a hand-over started by the previous session; the app puts a background block before it). Never reopens an old conversation.
argument-hint: "[NN or NN-name] [--tuning]"
---

# /home-office:resume

You continue a feature as its **conductor** (or, with `--tuning`, as the interactive tuning session). The past conversation does not matter: the files do.

1. Read `.home-office.yml`. In tuning mode the session is opened in a repo worktree: find the work folder from the argument path or ask the user for it, then read its config. In any other mode, the config must be in the current working directory; if it is not, stop and tell the user where to open the session.
2. Pick the feature: the argument ($ARGUMENTS) (`NN` or `NN-name`); without it, read the board and ask which one (list the ones in flight).
3. Read **only** `features/NN-name/STATE.md` (it may be in another language: find each section by its position in the template). Read `TASKS.md` only if the status is "executing", and only the next TASK. Never read the SPEC, PLAN or brief in full: subagents read them by path; if a step needs one detail, read only that section.
4. Tell the user in three lines where it stands: status, next step, anything blocked; then one line of links to `STATE.md` and the feature's documents that exist (brief, SPEC, PLAN, TASKS, REVIEW), as in `new` § "Links to documents".
   **Session title** (desktop app only). The title hook names this session `feat: NN-name #n` and records `n` in `features/NN-name/sessions.json`. If this session's title (`mcp__ccd_session_mgmt__get_session` with "self") has no `#n`, rename it with `mcp__ccd_session_mgmt__set_session_title` ("self") to `feat: NN-name #<highest number in sessions.json>` (or `#2` if the file is missing), adding ` · tuning` in tuning mode.
   **Archive the previous session** (not in `--tuning`; desktop app only). If `mcp__ccd_session_mgmt__get_session` with `session_id: "self"` shows a `parentSessionId`, get the parent: when its title is `feat: NN-name` of this same feature (or it handed over from this feature) and it is idle, archive it with `mcp__ccd_session_mgmt__archive_session` and a reason like "replaced by the next session of NN-name". With `archive: ask` ask the user once first, in one line; with `auto` just do it (the app may still ask for approval). Archiving a session also archives its finished, idle side sessions, so first list the parent's children (`list_sessions`): archive only if this session is its only child still alive; if another idle child is still in use, skip it, or detach this session first (`mcp__ccd_session_mgmt__detach_session`) if that makes it safe. If the call is refused, follow `project` § "Archiving sessions". Without these tools (CLI), skip this.
   **Sidebar group** (desktop app): if this session has a `parentSessionId` and is not `detached`, first detach it (`mcp__ccd_session_mgmt__detach_session`, "self") so it sits at the top level, not under the session that started it; then move this session into the group of the project in `STATE.md`'s `Project:` line (`project` § "Sidebar group"); without that line, use the first repo of `Branches`, else skip.
5. Continue from "Next" following the `new` procedure from that point (execution, review or close). Gates still apply.
6. **Execution budget.** Execute at most `limits.tasks_per_session` TASKs in this session (default 2; count them). Keep only each report's status line. Then do the planned cut of `new` § Execute step 8: first the commits of step 5, then `STATE.md` with "TASK x of y" and the next TASK, the board's row, and the hand-over of `new` § "Handing over": when the desktop app's session tool exists, **always** start the next session (`handover: auto` and nothing waits for the user) or propose it as a card — never only the text line — plus the line "Continue in a new session with `/home-office:resume NN-name`." If the TASKs run out before the budget, go on to the review (gate 3) in this session.

## Tuning mode (`--tuning`)

The only session that works directly with the user on a running app (browser, emulator, simulator, editor).
- Work inside the feature worktree only. Before the first change, open the tuning task so the guards apply: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-start --worktree <wt> --task "NN-name / tuning" --file <files of the TASK being tuned>… [--delete <path>]… [--prepare "<cmd>"]… --check "<cmd>"…`. If a change needs another file, ask the user and restart the task with the extra file (`--force`).
- Count the user's tuning requests. At `limits.tuning_requests` (or near the context cap), write what is left to `STATE.md` under "Next" and tell the user to run `/home-office:close` and reopen.
- Before closing, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-end --worktree <wt> --run-checks` (it runs the prepare commands, the scope check and the checks); record the result in `STATE.md`.
