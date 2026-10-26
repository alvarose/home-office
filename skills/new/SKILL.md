---
name: new
description: Start new work with home-office. Classifies the request into the short lane or the feature lane and, for features, runs explore → SPEC (gate 1) → PLAN + TASKS (gate 2) → execution → review (gate 3) → close. Use only when the user invokes /home-office:new, or when the session's first message has a line `/home-office:new …` (a session another home-office session started for it).
argument-hint: "<what you want to do> [--stream <name>] [--project <repo>]"
---

# /home-office:new

You are now the **conductor** of this piece of work. You coordinate; you do not write code and you do not read code broadly. Every other role runs as a subagent with an empty context, and you keep only their short reports.

The request is:

> $ARGUMENTS

If it is empty, ask what the user wants to do and stop.

## 0. Preconditions

1. Read `.home-office.yml` in the current working directory. If it is not here, stop: tell the user to open the session in the folder that contains it (or run `/home-office:init` there). Do not search other folders and do not work without it.
2. Paths in the config are relative to that file. Templates live in `${CLAUDE_PLUGIN_ROOT}/core/templates/`.
3. The conductor should run on a cheap model (`roles.conductor`). If this session is on a top-tier model, suggest `/model <roles.conductor.model>` once and continue (in the Claude desktop app, choosing it in the model picker also works for later sessions). If `.claude/settings.json` next to the config has no `model`, offer once to add `"model": "<roles.conductor.model>"`: terminal CLI sessions opened here then start on it; the desktop app's picker ignores it (see `init` § 7).
4. Read the board (`<work>/<board>`). If the number of features in flight reaches `limits.parallel_warning`, warn the user once.
5. **Language.** Every document you or a subagent writes (STATE, DECISIONS, brief, SPEC, PLAN, TASKS, board, log) is written in `language` (if missing: the language the user writes in), following "Language" in `${CLAUDE_PLUGIN_ROOT}/core/WORKFLOW.md`. Pass `language` to every subagent that writes a document or findings (explorer, architect, reviewer, deep-reviewer). Talk to the user in the language they write in.

6. **Sessions you start for parallel work** (a follow-up or side job next to this feature, not a hand-over): the first line of their prompt is a home-office command, so they run the plugin and get a clear title: `/home-office:task --project <repo> "<job>"` for a one-off job, `/home-office:new --project <repo> "<request>"` for real work. Use `use_worktree: false`, the conductor's model, and a `title` like `task: <job>`. They stay **nested** under this session in the sidebar on purpose: do not detach or move them. Only hand-overs (`new` § "Handing over", `resume`) go to the top level.

## 1. Classify

Launch the `classifier` agent (model from `roles.classifier`) with the request, the repos and their roles, and the path of each source's index. Show its answer in one line: "Lane: feature (touches api and web). Say 'short' to change it."

If the user overrides, follow the user. If the request is clearly a one-off check or cleanup across repos with nothing to design, say in one line that `/home-office:task "<request>"` fits better and let the user choose.

## 1b. Project

Every piece of work belongs to a **project** (one per repo; see "Projects" in `${CLAUDE_PLUGIN_ROOT}/core/WORKFLOW.md`). Take it from `--project <repo>` in the request (strip the flag; it must be a key of `repos`, else ask), or from the stream's `Project:` line if the work comes from a stream. Otherwise it is the repo the classifier lists first (the one that drives the work); if two repos are equally likely, ask in one line. Say it with the lane: "Project: api." Other repos the work touches are only "touched": they get a "touches" row on the board. If `<work>/projects/<repo>/project.md` is missing, create it from the `project.md` template (what it is: from the repo's knowledge card if there is one).

## 2a. Short lane

0. If the desktop tool `mcp__ccd_session_mgmt__set_session_title` exists, rename this session to `short: <name from the classifier>` (`session_id: "self"`).
1. Pick the repo (`<repo>` = its absolute path). Open an open-scope task on it, so hard rules and checks still apply:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-start --worktree <repo> --task "short: <name>" [--delete <path>]… --deny "<glob>=<reason>"… --prepare "<cmd>"… --check "<cmd>"… --attempts <limits.task_attempts>`
   (`--deny` from the `guards` that apply to this repo; `--prepare` from its `prepare`; `--check` from its `checks`; no `--file`. `--delete` only for files or folders the request clearly says to remove, by exact path, after confirming the list with the user.)
2. Launch `home-office:implementer` (model from the role that matches the repo, else `roles.backend`). Its prompt starts with the line `HOME-OFFICE-WORKTREE: <repo>`, then: the request, the relevant knowledge sections (from the index), `hard_rules`, the paths it may delete (if any), the prepare commands and checks, and the limit of ~5 files.
3. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-end --worktree <repo>` and read `gate` and `touched`. `fail`, `blocked` or `needs-plan-change` → tell the user (it may have outgrown the short lane; offer to restart it as a feature).
4. Launch `home-office:reviewer` on the uncommitted diff of that repo. Show `git -C <repo> diff --stat` and the review → **gate 3**: wait for the user.
5. Propose a commit message → **gate 4**: the user commits. Give the commands as `git -C <repo> …` (see `close`): the session runs in the work folder.
6. Append one line to `<work>/<log>`: date, project, repo, what was done; also add it to the project's "Tasks done" in its `project.md`. Done.

## 2b. Feature lane

### Set up
1. Assign `NN`: the next free number in `<work>/features/` (two digits). Name: `NN-<name from the classifier>`.
2. Create `<work>/features/NN-name/` with `STATE.md` and `DECISIONS.md` from the templates. If the work belongs to a batch the user mentions, link it in `STATE.md` and the batch's repo table.
3. **Stream and project.** Write `Project: <repo>` in `STATE.md` (§ 1b). The feature belongs to a stream if the request has `--stream <name>` (strip the flag from the request), names a stream, or comes from `/home-office:stream next`. Resolve `<name>` (`NN`, `NN-name` or a unique part of the name) against `<work>/streams/`; if nothing matches, ask. Then: write `Stream: streams/NN-name` in `STATE.md` (otherwise `Stream: none`); in the stream's `stream.md` set this feature's roadmap row to `in progress` and fill its Link with `features/NN-name` (if the request matches no planned row, add one at the end); (a stream's `Project:` is the feature's project unless the user says otherwise). Pass `stream.md` to the explorer and the architect as shared decisions, like a batch's `DECISIONS.md`. Without a stream, write `Stream: none` and skip the roadmap part. Then move this session into the project's sidebar group (see `project` § "Sidebar group").
4. Add a row to the board: in the feature's project section (`## <repo>`, created if missing), under its stream heading (`### streams/NN-name`, created if missing) or under `### Other` if it has no stream. For each other repo the feature touches, add a row marked "touches" (with the driving project in the Work column) in that repo's section.
5. **Session title.** A hook titled this session "new: <request>". Rename it to `feat: NN-name #1` (this is the feature's first session) if the Claude desktop app's tool `mcp__ccd_session_mgmt__set_session_title` exists (it may be deferred: load it with ToolSearch `select:mcp__ccd_session_mgmt__set_session_title`), with `session_id: "self"`. Elsewhere, leave it. `resume` sessions get `feat: NN-name #n` from the hook, numbered in order (#2, #3…), so when you mention other sessions of the feature to the user, name them by that number.

### Explore
Launch `explorer` (`roles.explorer`) with the request, the brief template path and the destination `features/NN-name/brief.md`. Show its three-line summary and the link to the brief (see "Links to documents").

### SPEC → gate 1
Launch `architect` (`roles.architect`) in mode `spec`, with the brief, the template and, if any, the batch's `DECISIONS.md` and the stream's `stream.md` (its shared decisions and roadmap; raise only what is new). Show the user the SPEC's goal, scope and **decisions needed** (with the architect's recommendations). **Wait for explicit approval.** Record the user's choices in the feature's `DECISIONS.md` and mark the SPEC approved with the date. If the user changes something, relaunch the architect in mode `spec` with the changes.

### PLAN + TASKS → gate 2
Launch `architect` in mode `plan` with the approved SPEC, the brief, the board and the templates. Show: the approach, the layers and repos, the contract in short, crossings, and the list of TASKs (title, repo, role, number of files, files to delete). **Wait for explicit approval.**

### Planned cut after gate 2
This session ends here; execution always starts in a fresh one. The conversation now holds the brief, SPEC and PLAN, and execution needs that room.
1. Rewrite `STATE.md`: status "executing — TASK 0 of y", "Next" = TASK 1 (title, repo, role), and the gate 1 and 2 dates under "Decisions this session".
2. Update the feature's row on the board.
3. Hand over (see "Handing over" below) with the line: "PLAN approved. Continue in a new session with `/home-office:resume NN-name`." Do not start any TASK in this session.

### Handing over
Every planned cut ends the same way, after `STATE.md` and the board's row are written. **Never skip step 1 when the tool exists**: a cut that only prints the command makes the user copy it and open a session by hand.
1. **Next session.** If the Claude desktop app's session tool `mcp__ccd_session__start_session` exists (it may be deferred: load it with ToolSearch `select:mcp__ccd_session__start_session`), call it before writing your final message. How depends on `handover` in `.home-office.yml` (default `card`):
   - `auto`, and the next step needs nothing from the user (STATE's "Blocked" section is empty, and the next step is not a gate, a push, a merge or any other action that waits for the user's approval): **start** it with `initiation: "user_asked"` — the user asked for automatic hand-overs in the project's config. Then say in one line that it has started, with a link to it.
   - Otherwise (`card`, or the next step waits for the user): **propose** it as a card with `initiation: "own_initiative"`; nothing runs until the user starts it with one click.
   When you **started** it (`auto`), detach it right away (`mcp__ccd_session_mgmt__detach_session` with its id) so it is not nested under this session. Move the new session into the feature's project sidebar group once it exists (`mcp__ccd_sidebar__move_sessions`, see `project` § "Sidebar group"); a card has no session until the user starts it, so `resume` does it then. Same fields either way: `context: "fresh"`, `use_worktree: false` (the session must open in this work folder, where the config is; the plugin makes its own worktrees), `model`: the full model id for `roles.conductor.model` (e.g. `sonnet` → the current Sonnet id) when its tool is `claude` — without it the new session inherits this session's model, not the folder's default, `title`: `feat: NN-name` (the hook adds its number, `#n`, when the session starts), `prompt`: `/home-office:resume NN-name`, and `background`: two sentences in `language` with the feature, its status and next step from `STATE.md`, and that everything lives in `features/NN-name/`. If the app refuses the start (for example on a turn another session started), fall back to the card.
2. **Text.** Always end with the cut's line too (`/home-office:resume NN-name`), so the hand-over works without the app (CLI, other clients) or if the card is refused.
3. Add that this session can be archived once the new one is running (a card lives in this conversation).
4. **One offer only.** The card (or the started session) is the only place the next session is offered. Do not ask about it again: no "Start the next session?" question, no button for it in the app's next-step box (a recap is enough), and no extra line asking to start it. If the user then says to start it ("start it", "yes", "go"), call `start_session` with **only** the card's `proposal_id`, never a new proposal.

### Execute
Runs in sessions opened with `/home-office:resume NN-name`. Each session executes at most `limits.tasks_per_session` TASKs (default 2), then cuts (step 8).

Agents are plugin agents: launch them as `home-office:<role>` (`home-office:backend`, `home-office:frontend`, `home-office:implementer`…), never by the bare name, which may be a different agent defined in the repo.

For each TASK in order (respect `layers` and `Depends on`), reading from `TASKS.md` only that TASK:
1. **Worktree.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" worktree --repo <repo> --dest <worktrees>/<repo-name>/NN-name --branch feature/NN-name --base <repo base> [--copy <file>]… [--link <folder>]… [--setup "<cmd>"]…`
   (`<repo base>` is the repo's `base` if set, else `base_branch`. `--copy` (files or folders), `--link` and `--setup` come from the repo's `copy`, `link` and `setup` in the config; they only run when the worktree is created. A `link` folder (`vendor`, `node_modules`) is cloned from the main checkout with hard links in seconds when its lock file is identical, and its install command in `setup` is then skipped; `linked` in the result says which.) Reuse it for later TASKs in the same repo. If `ok` is false, stop and show the user the error.
2. **Open the TASK.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-start --worktree <wt> --task "NN-name / TASK n" --file <path>… [--delete <path>]… --deny "<glob>=<reason>"… [--prepare "<cmd>"]… --check "<cmd>"… [--setup "<cmd>"]… --attempts <limits.task_attempts>`
   Files: the TASK's closed list — **a folder goes in as a glob, `<folder>/**`, never a bare `<folder>/`**: the scope guard matches each edited path against the list by exact path or glob, so a bare folder path matches no file and every edit under it is blocked (`--allow "<glob>"` is the same list, for patterns). Delete: the TASK's `Delete:` list, if any — the opposite convention, exact paths only, where a listed folder does cover everything under it. Deny: the `guards` that apply to this repo. Setup: the repo's `setup` (only used if the TASK changes a cloned folder's manifest or lock: then `task-start` replaces the clone with a real install). Prepare: the repo's `prepare` (run before the checks on every TASK, e.g. code generators). Checks: the repo's `checks`. From now on the hooks block edits outside the list, Bash writes (except deleting the listed files), and finishing with failing checks.
3. **Launch the executor** for the TASK's role (`home-office:backend`, `home-office:frontend`, or `home-office:implementer` for project-defined roles, passing the role's `description`), with the model from `roles.<role>`. The prompt's **first line** is `HOME-OFFICE-WORKTREE: <wt>`; then the TASK text, the path of `PLAN.md` (the executor reads its Contract section), the knowledge sections listed, `hard_rules`, the prepare commands and the checks. Pass nothing else.
   If the role's `tool` is not `claude`, delegate instead: run that tool's non-interactive mode with the worktree as its working directory and the same prompt. No checks gate runs for it, so close the TASK in step 4 with `--run-checks`.
4. **Close the TASK.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-end --worktree <wt>` (add `--run-checks` for delegated work: it runs the prepare commands, the scope check and the checks there) → `gate` (`pass` / `fail` / null), `touched`, `problems`. Update `STATE.md` (done / next / rework) with the essentials only.
   **Trust the gate; never run the checks by hand.** `gate: pass` means the prepare commands, the scope check and every check already ran and passed: do not run them again. `gate: fail` carries the failing output in `problems`: read it there. If `gate` is null (no executor gate ran), `task-end` keeps the TASK open and says so in `hint`: run `task-end --worktree <wt> --run-checks` **once**. Never launch `composer test`, `npm run …` or the like yourself to check a TASK: on big repos each run costs minutes. Fixes go back to the executor.
5. **Commit.** A TASK with `gate: pass` and report `done` gets its own commit on `feature/NN-name` in its worktree, message `NN-name / TASK n: <title>`. The scope file is gone after `task-end`, so the hooks allow it. Stage only that TASK's files: the `touched` list `task-end` printed (deletions included), or, if it is empty because no gate ran, the TASK's file list plus its `Delete:` paths: `git -C <wt> add -A -- <touched>…`, then `git -C <wt> commit -m "<message>"`.
   - `commit: auto`: commit now and note the SHA in `STATE.md` ("Done").
   - `commit: ask` (default): note the TASK as "passed, not committed" and ask once per session, at the planned cut (step 8) or when execution ends: "Commit TASKs x, y on feature/NN-name?", with the proposed messages. Commit only on the user's yes, one commit per TASK, in order (keep each TASK's `touched` list in `STATE.md` until then).
   - Never commit on the base branch, never push, amend or rebase, and never skip hooks. Files written by `prepare` that git ignores stay out by themselves; tracked ones go in.
6. **Decide.** `gate: pass` and report `done` → next TASK. Anything else (`gate: fail` — the executor already had `task_attempts` tries inside its run —, `blocked`, `needs-plan-change`, or delegated work out of scope) → **no new attempt**: write it under "Blocked" in `STATE.md`, add 1 to "Rework" and ask the user.
7. If a TASK needs interactive tuning (browser, emulator, simulator, editor), finish the others first, then tell the user to open a session in that worktree and run `/home-office:resume NN-name --tuning`.
8. **Planned cut.** After `limits.tasks_per_session` TASKs in this session, stop even if the context looks fine. First settle step 5's commits (with `ask`, the one question; the SHAs go to `STATE.md` "Done"). Then make sure `STATE.md` says "TASK x of y" and names the next TASK (or "review" if they are all done), update the board's row, and hand over (see "Handing over") with the line: "Continue in a new session with `/home-office:resume NN-name`."

### Review → gate 3
Launch `reviewer` (`roles.reviewer`) on the feature branches against each repo's base (`base`, else `base_branch`) in every repo touched. If any changed path matches `risk_zones`, also launch `deep-reviewer` (`roles.deep-reviewer`). Write their findings to `features/NN-name/REVIEW.md` from the template (one dated section per review round, newest first, in `language`; the reviewers are read-only, so you write it from their reports). Show `git diff --stat` per repo, the findings by severity and the link to `REVIEW.md`. **Wait for the user.** Fixes go back through executors as new TASKs.

### Close → gate 4
Run the `close` procedure (`/home-office:close`).

## Links to documents

Whenever a step writes or updates a document, end that message with one line of links so the user can open each one with a click, e.g. `Read: [brief](docs/work/features/07-x/brief.md) · [SPEC](docs/work/features/07-x/SPEC.md)`.
- Markdown links, with paths relative to the current working directory (the folder with `.home-office.yml`) and forward slashes. Most clients make them clickable; the Claude desktop app opens them in its file pane.
- Label them with the document's name in `language`.
- Link only what this step wrote or changed: brief after Explore; SPEC at gate 1; PLAN and TASKS at gate 2; `STATE.md` after each TASK and at every cut; `REVIEW.md` at gate 3; `STATE.md` and `DECISIONS.md` at close.
- Files inside worktrees are outside this folder and may not open from here: name them as `path` in code, never as links.
- Links never replace the summary the step asks for: the user decides from the summary and reads the documents when they want.

## Context discipline

- Pass each subagent only what its role needs. Never paste whole files into prompts; pass paths.
- From each subagent's report keep only its status line (`status: …`, the gate result and one line of notes); the rest is in the files. Never reread the SPEC or the PLAN in full: subagents read them by path, and you read only the TASK you are about to open.
- Sessions are cut on purpose, not when they are full: after gate 2, and after `limits.tasks_per_session` TASKs. Each cut writes `STATE.md` and hands over to `/home-office:resume NN-name` (card plus text line, see "Handing over").
- If this conversation still becomes long (near `limits.context_tokens`), cut the same way at once.
