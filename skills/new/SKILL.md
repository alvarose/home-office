---
name: new
description: Start new work with home-office. Classifies the request into the short lane or the feature lane and, for features, runs explore → SPEC (gate 1) → PLAN + TASKS (gate 2) → execution → review (gate 3) → close. Use only when the user invokes /home-office:new.
argument-hint: "<what you want to do>"
disable-model-invocation: true
---

# /home-office:new

You are now the **conductor** of this piece of work. You coordinate; you do not write code and you do not read code broadly. Every other role runs as a subagent with an empty context, and you keep only their short reports.

The request is:

> $ARGUMENTS

If it is empty, ask what the user wants to do and stop.

## 0. Preconditions

1. Read `.home-office.yml` in the current working directory. If it is not here, stop: tell the user to open the session in the folder that contains it (or run `/home-office:init` there). Do not search other folders and do not work without it.
2. Paths in the config are relative to that file. Templates live in `${CLAUDE_PLUGIN_ROOT}/core/templates/`.
3. The conductor should run on a cheap model (`roles.conductor`). If this session is on a top-tier model, suggest `/model <roles.conductor.model>` once and continue.
4. Read the board (`<work>/<board>`). If the number of features in flight reaches `limits.parallel_warning`, warn the user once.
5. **Language.** Every document you or a subagent writes (STATE, DECISIONS, brief, SPEC, PLAN, TASKS, board, log) is written in `language` (if missing: the language the user writes in), following "Language" in `${CLAUDE_PLUGIN_ROOT}/core/WORKFLOW.md`. Pass `language` to every subagent that writes a document or findings (explorer, architect, reviewer, deep-reviewer). Talk to the user in the language they write in.

## 1. Classify

Launch the `classifier` agent (model from `roles.classifier`) with the request, the repos and their roles, and the path of each source's index. Show its answer in one line: "Lane: feature (touches api and web). Say 'short' to change it."

If the user overrides, follow the user.

## 2a. Short lane

1. Pick the repo (`<repo>` = its absolute path). Open an open-scope task on it, so hard rules and checks still apply:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-start --worktree <repo> --task "short: <name>" [--delete <path>]… --deny "<glob>=<reason>"… --prepare "<cmd>"… --check "<cmd>"… --attempts <limits.task_attempts>`
   (`--deny` from the `guards` that apply to this repo; `--prepare` from its `prepare`; `--check` from its `checks`; no `--file`. `--delete` only for files or folders the request clearly says to remove, by exact path, after confirming the list with the user.)
2. Launch `home-office:implementer` (model from the role that matches the repo, else `roles.backend`). Its prompt starts with the line `HOME-OFFICE-WORKTREE: <repo>`, then: the request, the relevant knowledge sections (from the index), `hard_rules`, the paths it may delete (if any), the prepare commands and checks, and the limit of ~5 files.
3. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-end --worktree <repo>` and read `gate` and `touched`. `fail`, `blocked` or `needs-plan-change` → tell the user (it may have outgrown the short lane; offer to restart it as a feature).
4. Launch `home-office:reviewer` on the uncommitted diff of that repo. Show `git -C <repo> diff --stat` and the review → **gate 3**: wait for the user.
5. Propose a commit message → **gate 4**: the user commits.
6. Append one line to `<work>/<log>`: date, repo, what was done. Done.

## 2b. Feature lane

### Set up
1. Assign `NN`: the next free number in `<work>/features/` (two digits). Name: `NN-<name from the classifier>`.
2. Create `<work>/features/NN-name/` with `STATE.md` and `DECISIONS.md` from the templates. If the work belongs to a campaign the user mentions, link it in `STATE.md` and the campaign's repo table.
3. Add a row to the board.

### Explore
Launch `explorer` (`roles.explorer`) with the request, the brief template path and the destination `features/NN-name/brief.md`. Show its three-line summary.

### SPEC → gate 1
Launch `architect` (`roles.architect`) in mode `spec`, with the brief, the template and, if any, the campaign's `DECISIONS.md`. Show the user the SPEC's goal, scope and **decisions needed** (with the architect's recommendations). **Wait for explicit approval.** Record the user's choices in the feature's `DECISIONS.md` and mark the SPEC approved with the date. If the user changes something, relaunch the architect in mode `spec` with the changes.

### PLAN + TASKS → gate 2
Launch `architect` in mode `plan` with the approved SPEC, the brief, the board and the templates. Show: the approach, the layers and repos, the contract in short, crossings, and the list of TASKs (title, repo, role, number of files, files to delete). **Wait for explicit approval.**

### Planned cut after gate 2
This session ends here; execution always starts in a fresh one. The conversation now holds the brief, SPEC and PLAN, and execution needs that room.
1. Rewrite `STATE.md`: status "executing — TASK 0 of y", "Next" = TASK 1 (title, repo, role), and the gate 1 and 2 dates under "Decisions this session".
2. Update the feature's row on the board.
3. End with: "PLAN approved. Continue in a new session with `/home-office:resume NN-name`." Do not start any TASK in this session.

### Execute
Runs in sessions opened with `/home-office:resume NN-name`. Each session executes at most `limits.tasks_per_session` TASKs (default 2), then cuts (step 7).

Agents are plugin agents: launch them as `home-office:<role>` (`home-office:backend`, `home-office:frontend`, `home-office:implementer`…), never by the bare name, which may be a different agent defined in the repo.

For each TASK in order (respect `layers` and `Depends on`), reading from `TASKS.md` only that TASK:
1. **Worktree.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" worktree --repo <repo> --dest <worktrees>/<repo-name>/NN-name --branch feature/NN-name --base <base_branch> [--copy <file>]… [--setup "<cmd>"]…`
   (`--copy` and `--setup` from the repo's `copy` and `setup` in the config; they only run when the worktree is created.) Reuse it for later TASKs in the same repo. If `ok` is false, stop and show the user the error.
2. **Open the TASK.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-start --worktree <wt> --task "NN-name / TASK n" --file <path>… [--delete <path>]… --deny "<glob>=<reason>"… [--prepare "<cmd>"]… --check "<cmd>"… --attempts <limits.task_attempts>`
   Files: the TASK's closed list. Delete: the TASK's `Delete:` list, if any. Deny: the `guards` that apply to this repo. Prepare: the repo's `prepare` (run before the checks on every TASK, e.g. code generators). Checks: the repo's `checks`. From now on the hooks block edits outside the list, Bash writes (except deleting the listed files), and finishing with failing checks.
3. **Launch the executor** for the TASK's role (`home-office:backend`, `home-office:frontend`, or `home-office:implementer` for project-defined roles, passing the role's `description`), with the model from `roles.<role>`. The prompt's **first line** is `HOME-OFFICE-WORKTREE: <wt>`; then the TASK text, the path of `PLAN.md` (the executor reads its Contract section), the knowledge sections listed, `hard_rules`, the prepare commands and the checks. Pass nothing else.
   If the role's `tool` is not `claude`, delegate instead: run that tool's non-interactive mode with the worktree as its working directory and the same prompt. No checks gate runs for it, so close the TASK in step 4 with `--run-checks`.
4. **Close the TASK.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-end --worktree <wt>` (add `--run-checks` for delegated work: it runs the prepare commands, the scope check and the checks there) → `gate` (`pass` / `fail` / null), `touched`, `problems`. Update `STATE.md` (done / next / rework) with the essentials only.
5. **Decide.** `gate: pass` and report `done` → next TASK. Anything else (`gate: fail` — the executor already had `task_attempts` tries inside its run —, `blocked`, `needs-plan-change`, or delegated work out of scope) → **no new attempt**: write it under "Blocked" in `STATE.md`, add 1 to "Rework" and ask the user.
6. If a TASK needs interactive tuning (browser, emulator, simulator, editor), finish the others first, then tell the user to open a session in that worktree and run `/home-office:resume NN-name --tuning`.
7. **Planned cut.** After `limits.tasks_per_session` TASKs in this session, stop even if the context looks fine: make sure `STATE.md` says "TASK x of y" and names the next TASK (or "review" if they are all done), update the board's row, and end with: "Continue in a new session with `/home-office:resume NN-name`."

### Review → gate 3
Launch `reviewer` (`roles.reviewer`) on the feature branches against `base_branch` in every repo touched. If any changed path matches `risk_zones`, also launch `deep-reviewer` (`roles.deep-reviewer`). Show `git diff --stat` per repo and the findings by severity. **Wait for the user.** Fixes go back through executors as new TASKs.

### Close → gate 4
Run the `close` procedure (`/home-office:close`).

## Context discipline

- Pass each subagent only what its role needs. Never paste whole files into prompts; pass paths.
- From each subagent's report keep only its status line (`status: …`, the gate result and one line of notes); the rest is in the files. Never reread the SPEC or the PLAN in full: subagents read them by path, and you read only the TASK you are about to open.
- Sessions are cut on purpose, not when they are full: after gate 2, and after `limits.tasks_per_session` TASKs. Each cut writes `STATE.md` and hands over to `/home-office:resume NN-name`.
- If this conversation still becomes long (near `limits.context_tokens`), cut the same way at once.
