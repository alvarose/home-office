---
name: task
description: Run one self-contained job with home-office - a check, a cleanup or a mechanical change, even across several repos - with no SPEC, PLAN or TASKs, then finish. Use only when the user invokes /home-office:task.
argument-hint: "<what to check or do, e.g. 'check that every repo removed its old vendored copy of X'>"
disable-model-invocation: true
---

# /home-office:task

You are the **conductor** of one job that ends in this session. It may cover many repos, but it needs no design: no SPEC, PLAN, TASKs, STATE or hand-over.

The request is:

> $ARGUMENTS

If it is empty, ask what to check or do and stop.

## 0. Preconditions
Follow `new` § 0 (`${CLAUDE_PLUGIN_ROOT}/skills/new/SKILL.md`): config in the current working directory, conductor model, board, language. Also apply its "Links to documents" and `close`'s rule that every git command you give the user is `git -C <repo> …`.

**Session title.** A hook titled this session "task: <request>". In the Claude desktop app, if `mcp__ccd_session_mgmt__set_session_title` exists (it may be deferred: load it with ToolSearch), rename it to `task: <short name>` with `session_id: "self"`.

## 1. Scope
- List the repos it applies to: the ones the request names, or every repo in `repos` when it says "all" or names none. You may run read-only commands yourself only to list or locate (`ls`, `git -C <repo> status`, `rg`).
- **Not a task?** If it needs design decisions, a contract or schema change, or real feature work, say so in one line and offer `/home-office:new "<request>"` instead. Never do feature work here.
- Say in one line what you will do and in which repos, then go on.

## 2. Do it
**Read-only check** (find, verify, report; nothing changes): launch `home-office:explorer` (`roles.explorer`) once for all the repos, or once per repo if there are many. Tell it this is a check, **not** a brief: it must not write any file, only return its findings per repo (result, evidence with paths, anything odd).

**Mechanical change** (the same simple change in one or more repos), per repo:
1. If the repo has uncommitted changes or is not on its base (its `base`, else `base_branch`), tell the user and ask before touching it.
2. Open an open-scope task, as in the short lane: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-start --worktree <repo> --task "task: <name>" --deny "<glob>=<reason>"… [--prepare "<cmd>"]… --check "<cmd>"… --attempts <limits.task_attempts>`.
   - `--deny` comes from the `guards` that apply to the repo.
   - `--delete` is only for paths the request names, after confirming the list with the user.
3. Launch `home-office:implementer` (model from the role that matches the repo, else `roles.backend`). The first line of its prompt is `HOME-OFFICE-WORKTREE: <repo>`; then give it the change, the relevant knowledge sections, `hard_rules`, the paths it may delete, and the prepare commands and checks.
4. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-end --worktree <repo>` and keep `gate`, `touched` and `problems`.

Mechanical changes are made in the repo's current checkout, like the short lane: no feature branch and no worktree.

## 3. Report
- **One table:** repo · result (`ok` / `changed` / `problem` / `skipped`) · detail. Write it in `language`.
- **Changes:** add `git -C <repo> diff --stat` for each changed repo, plus a proposed commit message → **gate 4**.
  - With `commit: auto`, commit them yourself on the current branch, never on a protected base branch the user has not approved.
  - With `ask`, ask once.
  - Never merge or push.
- **Problems:** say what is left to do. If it is real work, offer `/home-office:new` for it.

## 4. Record
Append one line to `<work>/<log>`, in `language`: date, repos, what was checked or changed, result.

## 5. Finish
- End with "Task done." in the user's language and a link to the log.
- A task never spans sessions. If it cannot finish here (too big, blocked, needs a decision that changes its nature), stop and offer `/home-office:new` with what you learned.
- Claude desktop app: with `archive: auto`, archive this session as the very last action (`mcp__ccd_session_mgmt__archive_session` with `session_id: "self"`; it ends the conversation). With `ask`, offer it once.
