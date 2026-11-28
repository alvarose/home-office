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

6. **Sessions you start for parallel work** (a follow-up or side job next to this feature, not a hand-over): the first line of their prompt is a home-office command, so they run the plugin and get a clear title: `/home-office:task --project <repo> "<job>"` for a one-off job, `/home-office:new --project <repo> "<request>"` for real work. Use `use_worktree: false`, `model`: the full id of `roles.conductor.model` (step 7), and a `title` like `task: <job>`. They stay **nested** under this session in the sidebar on purpose: do not detach or move them. Only hand-overs (`core/EXECUTE.md` § "Handing over", `resume`) go to the top level.
7. **Every session you start passes `model`.** Any `mcp__ccd_session__start_session` from this work folder — hand-over, card, side job, a session you propose on your own initiative — sets `model` to a full id: `roles.conductor.model` for a session that runs a home-office command (it becomes a conductor), else the newest id of the family it needs. Get both from `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" models` (`roles`, `current`); never write an id from memory and never leave `model` out: the new session would inherit this session's model, however old (WORKFLOW "Session models").

## 1. Classify

Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" maturity` (all repos, a few git calls) and keep, per repo, only `mature`. Launch the `classifier` agent (model from `roles.classifier`) with the request, the repos with their roles and `mature: yes|no`, and the path of each source's index. Show its answer in one line: "Lane: feature (touches api and web). Say 'short' to change it."

If the user overrides, follow the user. If the classifier says `lane: task`, or the request is clearly a one-off check or cleanup across repos with nothing to design, or a long job (watching or operating something for hours or days), say in one line that `/home-office:task "<request>"` fits better and let the user choose (default: task). A long job runs there one step per session, with a hand-over note (`task` § "Long jobs").

**Minor fixes stay small.** Findings from an audit or a review, cleanups and style fixes go to the short lane or to `task`, never to the feature lane, unless one of them changes a contract or a schema (the classifier applies this; do not override it on your own). A long list of them runs as several short-lane changes or tasks, one per repo or per group of related fixes; anything left for later goes to the project's Backlog. Only the user can send minor fixes to the feature lane, and then the feature limit (`limits.tasks_per_feature`) still applies.

## 1b. Project

Every piece of work belongs to a **project** (one per repo; see "Projects" in `${CLAUDE_PLUGIN_ROOT}/core/WORKFLOW.md`). Take it from `--project <repo>` in the request (strip the flag; it must be a key of `repos`, else ask), or from the stream's `Project:` line if the work comes from a stream. Otherwise it is the repo the classifier lists first (the one that drives the work); if two repos are equally likely, ask in one line. Say it with the lane: "Project: api." Other repos the work touches are only "touched": they get a "touches" row on the board. If `<work>/projects/<repo>/project.md` is missing, create it from the `project.md` template (what it is: from the repo's knowledge card if there is one).

## 2a. Short lane

0. If the desktop tool `mcp__ccd_session_mgmt__set_session_title` exists, rename this session to `short: <name from the classifier>` (`session_id: "self"`).
1. Pick the repo (`<repo>` = its absolute path). Open an open-scope task on it, so hard rules and checks still apply:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-start --worktree <repo> --task "short: <name>" [--delete <path>]… --deny "<glob>=<reason>"… --prepare "<cmd>"… --check "<cmd>"… [--advisory "<cmd>"]… --attempts <limits.task_attempts> --gate-seconds <limits.gate_seconds>`
   (`--deny` from the `guards` that apply to this repo; `--prepare` from its `prepare`; `--check` from its `checks`; `--advisory` from its `advisories`; no `--file`. `--delete` only for files or folders the request clearly says to remove, by exact path, after confirming the list with the user.)
2. Launch `home-office:implementer` (model from the role that matches the repo, else `roles.backend`). Its prompt starts with the line `HOME-OFFICE-WORKTREE: <repo>`, then: the request, the relevant knowledge sections (from the index), `hard_rules`, the paths it may delete (if any), the prepare commands and checks, the check command line (§ Execute step 3), and the limit of ~5 files (~10 in a mature repo: there, tell it to read the code and tests around the change first, as its guide, instead of expecting a plan).
3. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-end --worktree <repo> --report <the implementer's status>` and read `gate` (always `pass` or `fail`: it runs the checks itself if no gate ran) and `touched`. `fail`, `blocked` or `needs-plan-change` → tell the user (it may have outgrown the short lane; offer to restart it as a feature).
4. Launch `home-office:reviewer` on the uncommitted diff of that repo (one round, as in `core/EXECUTE.md` § "Review → gate 3"). Show `git -C <repo> diff --stat` and the review → **gate 3**: wait for the user. Fix only high and medium findings the user approves; low ones go as one line to the project's Backlog, not into this change, unless the user asks.
5. Propose a commit message → **gate 4**: the user commits. Give the commands as `git -C <repo> …` (see `close`): the session runs in the work folder.
6. Append one line to `<work>/<log>`: date, project, repo, what was done; also add it to the project's "Tasks done" in its `project.md`. Done.

## 2b. Feature lane

### Set up
1. Assign `NN`: the next free number in `<work>/features/` (two digits). Name: `NN-<name from the classifier>`.
2. Create `<work>/features/NN-name/` with `STATE.md` and `DECISIONS.md` from the templates. If the work belongs to a batch the user mentions, link it in `STATE.md` and the batch's repo table.
3. **Stream and project.** Write `Project: <repo>` in `STATE.md` (§ 1b). The feature belongs to a stream if the request has `--stream <name>` (strip the flag from the request), names a stream, or comes from `/home-office:stream next`. Resolve `<name>` (`NN`, `NN-name` or a unique part of the name) against `<work>/streams/`; if nothing matches, ask. Then: write `Stream: streams/NN-name` in `STATE.md` (otherwise `Stream: none`); in the stream's `stream.md` set this feature's roadmap row to `in progress` and fill its Link with `features/NN-name` (if the request matches no planned row, add one at the end); (a stream's `Project:` is the feature's project unless the user says otherwise). Pass `stream.md` to the explorer and the architect as shared decisions, like a batch's `DECISIONS.md`. Without a stream, write `Stream: none` and skip the roadmap part. Then move this session into the project's sidebar group (see `project` § "Sidebar group").
4. Put it on the board with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" board --write` once `STATE.md` has its Status, `Project:`, `Stream:` and `Branches` lines: it writes the row in the feature's project section (`## <repo>`, created if missing), under its stream heading (`### streams/NN-name`) or under `### Other`, and a "touches" row in the section of each other repo of its branches. Never write a feature row by hand (WORKFLOW "Harness weight", "Generated rows").
5. **Session title.** A hook titled this session "new: <request>". Rename it to `feat: NN-name #1` (this is the feature's first session) if the Claude desktop app's tool `mcp__ccd_session_mgmt__set_session_title` exists (it may be deferred: load it with ToolSearch `select:mcp__ccd_session_mgmt__set_session_title`), with `session_id: "self"`. Elsewhere, leave it. `resume` sessions get `feat: NN-name #n` from the hook, numbered in order (#2, #3…), so when you mention other sessions of the feature to the user, name them by that number.

### Explore
Launch `explorer` (`roles.explorer`) with the request, the brief template path and the destination `features/NN-name/brief.md`. Show its three-line summary and the link to the brief (see "Links to documents").

### SPEC → gate 1
Launch `architect` (`roles.architect`) in mode `spec`, with the brief, the template, `limits.tasks_per_feature` (default 8) and `limits.tasks_per_session`, and, if any, the batch's `DECISIONS.md` and the stream's `stream.md` (its shared decisions and roadmap; raise only what is new). Show the user the SPEC's goal, **what it unblocks**, its **size** (`Estimate:` — e.g. "~6 TASKs in 3 sessions, limit 8"; say so when it is over the limit), scope and **decisions needed** (with the architect's recommendations). **Wait for explicit approval.** Record the user's choices in the feature's `DECISIONS.md` and mark the SPEC approved with the date. If the user changes something, relaunch the architect in mode `spec` with the changes.

### PLAN + TASKS → gate 2
Launch `architect` in mode `plan` with the approved SPEC, the brief, the board, the templates and `limits.tasks_per_feature` (default 8). Show: the approach, the layers and repos, the contract in short, crossings, and the list of TASKs (title, repo, role, number of files, files to delete).

**Over the limit.** If the architect's first line says more TASKs than `limits.tasks_per_feature`, say it **before** asking for gate 2, with the numbers and its proposal, e.g. "14 TASKs, limit 8. The architect proposes splitting: TASKs 1–7 now (delivers …), the rest as a new feature." Let the user choose: **trim** or **split** (relaunch the architect in mode `plan` with that choice; what is left out goes as one line each to the Backlog of `<work>/projects/<repo>/project.md`, never to a hidden TASK), or **keep it** (only on the user's explicit word; record it in `DECISIONS.md`). Never ask for gate 2 on an over-limit PLAN without saying so.

**Wait for explicit approval.**

### Planned cut after gate 2
This session ends here; execution always starts in a fresh one. The conversation now holds the brief, SPEC and PLAN, and execution needs that room.
1. Rewrite `STATE.md`: status "executing — TASK 0 of y", "Next" = TASK 1 (title, repo, role), and the gate 1 and 2 dates under "Decisions this session".
2. Refresh the board: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" board --write`.
3. Hand over (`${CLAUDE_PLUGIN_ROOT}/core/EXECUTE.md` § "Handing over") with the line: "PLAN approved. Continue in a new session with `/home-office:resume NN-name`." Do not start any TASK in this session.

### After gate 2: hand-over, execution, review, close
They live in `${CLAUDE_PLUGIN_ROOT}/core/EXECUTE.md` (sections "Handing over", "Execute", "Review → gate 3", "Close → gate 4"), which every `resume` session reads. Here you only need its "Handing over" section, for the cut above.

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
- Sessions are cut on purpose, not when they are full: after gate 2, and in execution at the planned cut point (`limits.cut_at` % of `limits.context_tokens`, said by the context hook) or after `limits.tasks_per_session` TASKs, whichever comes first (`core/EXECUTE.md` § Execute step 8). Each cut writes `STATE.md` and hands over to `/home-office:resume NN-name` (card plus text line, `core/EXECUTE.md` § "Handing over").
- If this conversation still becomes long (near `limits.context_tokens`), cut the same way at once.
