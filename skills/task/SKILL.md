---
name: task
description: Run one self-contained job with home-office - a check, a cleanup or a mechanical change, even across several repos - with no SPEC, PLAN or TASKs, then finish. Use only when the user invokes /home-office:task, or when the session's first message has a line `/home-office:task …` (a session another home-office session started for it).
argument-hint: "<what to check or do, e.g. 'check that every repo removed its old vendored copy of X'> [--project <repo>]"
---

# /home-office:task

You are the **conductor** of one job that ends in this session. It may cover many repos, but it needs no design: no SPEC, PLAN, TASKs, STATE or hand-over.

The request is:

> $ARGUMENTS

If it is empty, ask what to check or do and stop.

**Project.** `--project <repo>` (strip it from the request; it must be a key of `repos`, else ask) files the task under that project and makes that repo its default scope. Without it, the project is the single repo the task covers; a task over several repos has no project unless the user names one.

## Long jobs
Ongoing loose work — a watcher, operating a server or a bot, a long migration run by hand — never lives in one session for days: it runs as a chain of tasks, **one step per session**, each ending with a hand-over note.
- **Note.** `<work>/jobs/<name>.md` (template `job.md`, in `language`): what the job is, its state, what was done (one dated line per step) and the next step. If the request names a job or its note, read **only** that note first and continue from its next step; otherwise create it at the end of the first step.
- **One step.** Do the step as a check or a change (§ 2), report (§ 3), record (§ 4). Then update the note: state, one line for this step, the next step.
- **Hand over.** In the Claude desktop app, propose the next step as a card (`mcp__ccd_session__start_session`, `initiation: "own_initiative"`, `context: "fresh"`, `use_worktree: false`, `model`: the full id of `roles.conductor.model` (from `ho.py models`; never omitted, see `new` § 0 step 7), `title`: `task: <name>`, `prompt`: `/home-office:task [--project <repo>] "<name>: <next step> (note: jobs/<name>.md)"`); always end with that command as a text line too. Stop when the step is done or the context nears `limits.context_tokens`, whichever comes first.

## 0. Preconditions
Follow `new` § 0 (`${CLAUDE_PLUGIN_ROOT}/skills/new/SKILL.md`): config in the current working directory, conductor model, board, language. Also apply its "Links to documents" and `close`'s rule that every git command you give the user is `git -C <repo> …`.

**Session title.** A hook titled this session "task: <request>". In the Claude desktop app, if `mcp__ccd_session_mgmt__set_session_title` exists (it may be deferred: load it with ToolSearch), rename it to `task: <short name>` with `session_id: "self"`.

## 1. Scope
- List the repos it applies to: the ones the request names, or the `--project` repo when given, or every repo in `repos` when it says "all" or names none. You may run read-only commands yourself only to list or locate (`ls`, `git -C <repo> status`, `rg`).
- **Not a task?** If it needs design decisions, a contract or schema change, or real feature work, say so in one line and offer `/home-office:new "<request>"` instead. Never do feature work here. Minor fixes (from an audit or a review, cleanups, style) **are** tasks, even across many repos, unless one changes a contract or a schema: do them here, not as a feature.
- Say in one line what you will do and in which repos, then go on.

## 2. Do it
**Read-only check** (find, verify, report; nothing changes): launch `home-office:explorer` (`roles.explorer`) once for all the repos, or once per repo if there are many. Tell it this is a check, **not** a brief: it must not write any file, only return its findings per repo (result, evidence with paths, anything odd).

**Mechanical change** (the same simple change in one or more repos), per repo:
1. If the repo has uncommitted changes or is not on its base (its `base`, else `base_branch`), tell the user and ask before touching it.
2. Open an open-scope task, as in the short lane: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-start --worktree <repo> --task "task: <name>" --deny "<glob>=<reason>"… [--prepare "<cmd>"]… --check "<cmd>"… [--advisory "<cmd>"]… --attempts <limits.task_attempts> --gate-seconds <limits.gate_seconds>`. Report the `advisories` of the result in your summary and, when one found something, add one line to the project's Backlog.
   - `--deny` comes from the `guards` that apply to the repo.
   - `--delete` is only for paths the request names, after confirming the list with the user.
3. Launch `home-office:implementer` (model from the role that matches the repo, else `roles.backend`). The first line of its prompt is `HOME-OFFICE-WORKTREE: <repo>`; then give it the change, the relevant knowledge sections, `hard_rules`, the paths it may delete, the prepare commands and checks, and the check command line `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" check --worktree <repo> --cmd "<check>"` (path resolved): full checks only through it, filtered tests while iterating.
4. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-end --worktree <repo> --report <the implementer's status>` and keep `gate` (always `pass` or `fail`), `touched` and `problems`.

Mechanical changes are made in the repo's current checkout, like the short lane: no feature branch and no worktree.

## 3. Report
- **One table:** repo · result (`ok` / `changed` / `problem` / `skipped`) · detail. Write it in `language`.
- **Changes:** add `git -C <repo> diff --stat` for each changed repo, plus a proposed commit message → **gate 4**.
  - With `commit: auto`, commit them yourself on the current branch, never on a protected base branch the user has not approved.
  - With `ask`, ask once.
  - Never merge or push.
- **Problems:** say what is left to do. If it is real work, offer `/home-office:new` for it.

## 4. Record
**The feature it touched.** If the job concerns a feature (its number or name is in the job, it acted on a waiting row of one, or it merged, published, deployed or removed worktrees of one), update that feature's `STATE.md` (the status word, "Done", "Next", "Blocked"; `done` and its board rows removed when this was its last step) and its board row now, then run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" drift --feature NN-name` and fix what it lists. A task never leaves a feature's state only in the log.

Append one line to `<work>/<log>`, in `language`: date, project (empty if none), repos, what was checked or changed, result. With a project, add the same line to "Tasks done" in `<work>/projects/<repo>/project.md` (create the page from the `project.md` template if missing).

## 5. Finish
- In the Claude desktop app, with a project, move this session into its sidebar group (`project` § "Sidebar group"), unless another session started it for parallel work: then it stays nested under that session.
- End with "Task done." in the user's language and a link to the log.
- A task never spans sessions. If it cannot finish here (too big, blocked, needs a decision that changes its nature), stop and offer `/home-office:new` with what you learned. A **long job** is the exception: see below.
- Claude desktop app: with `archive: auto`, archive this session as the very last action (if refused, `project` § "Archiving sessions") (`mcp__ccd_session_mgmt__archive_session` with `session_id: "self"`; it ends the conversation). With `ask`, offer it once.
