---
name: resume
description: Resume a home-office feature in a fresh session from its STATE.md. Use only when the user invokes /home-office:resume. Never reopens an old conversation.
argument-hint: "[NN or NN-name] [--tuning]"
disable-model-invocation: true
---

# /home-office:resume

You continue a feature as its **conductor** (or, with `--tuning`, as the interactive tuning session). The past conversation does not matter: the files do.

1. Read `.home-office.yml`. In tuning mode the session is opened in a repo worktree: find the work folder from the argument path or ask the user for it, then read its config. In any other mode, the config must be in the current working directory; if it is not, stop and tell the user where to open the session.
2. Pick the feature: the argument ($ARGUMENTS) (`NN` or `NN-name`); without it, read the board and ask which one (list the ones in flight).
3. Read **only** `features/NN-name/STATE.md` (it may be in another language: find each section by its position in the template). Read `TASKS.md` only if the status is "executing", and only the next TASK. Never read the SPEC, PLAN or brief in full: subagents read them by path; if a step needs one detail, read only that section.
4. Tell the user in three lines where it stands: status, next step, anything blocked.
5. Continue from "Next" following the `new` procedure from that point (execution, review or close). Gates still apply.
6. **Execution budget.** Execute at most `limits.tasks_per_session` TASKs in this session (default 2; count them). Keep only each report's status line. Then do the planned cut of `new` § Execute step 7: `STATE.md` with "TASK x of y" and the next TASK, the board's row, and "Continue in a new session with `/home-office:resume NN-name`." If the TASKs run out before the budget, go on to the review (gate 3) in this session.

## Tuning mode (`--tuning`)

The only session that works directly with the user on a running app (browser, emulator, simulator, editor).
- Work inside the feature worktree only. Before the first change, open the tuning task so the guards apply: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-start --worktree <wt> --task "NN-name / tuning" --file <files of the TASK being tuned>… [--delete <path>]… [--prepare "<cmd>"]… --check "<cmd>"…`. If a change needs another file, ask the user and restart the task with the extra file (`--force`).
- Count the user's tuning requests. At `limits.tuning_requests` (or near the context cap), write what is left to `STATE.md` under "Next" and tell the user to run `/home-office:close` and reopen.
- Before closing, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-end --worktree <wt> --run-checks` (it runs the prepare commands, the scope check and the checks); record the result in `STATE.md`.
