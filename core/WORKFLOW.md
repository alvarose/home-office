# The home-office workflow

Tool-agnostic description of the method. Adapters (Claude Code today, Codex next) implement it with their own mechanisms. Everything project-specific lives in the project's `.home-office.yml` and knowledge sources, never here.

## Principles

1. **Think with a strong model, execute with cheaper ones.** Each role ("department") has its own tool and model, editable per project.
2. **State lives in files, not in conversations.** Sessions are disposable. A new session resumes from `STATE.md`, never from an old conversation.
3. **Minimal context per agent.** Every task says exactly which files it may touch and which knowledge sections it must read.
4. **The human approves, the agents work.** Four gates: SPEC, PLAN + TASKS, diff, commit. Commits on a feature branch can be delegated (`commit: ask|auto`); merges to the base branch and pushes cannot.

The cost of an agent grows with *number of calls × context size*. Short sessions, minimal context and the right model for each step keep both small.

## Two pieces per project

- **Work** (`docs/work/` in a compact project, a separate repo in a multi-repo project): the board, features, streams, batches, log.
- **Knowledge** (`docs/knowledge/` or one or more separate sources): short cards per repo, an `INDEX.md`, architecture, rules.

## Language

Each project chooses the language of the documents home-office writes for it: `language` in `.home-office.yml` (a name or code such as `es`, `en`, `pt-BR`). `init` proposes the language the user writes in; `language` (the command) changes it at any time.

- **Written in `language`**: SPEC, PLAN, TASKS, STATE, DECISIONS, brief, REVIEW, batches, board, log, knowledge cards and indexes created by the plugin, and review findings. Headings, header labels and prose are translated from the English templates.
- **Kept as they are**: file names, the sections and their order (other commands find a section by its position in the template, never by its title), paths, commands, branch names, code, identifiers, and the fixed fields agents report to the conductor (`status: done`, `lane: short`…).
- **Messages to the user** follow the language the user writes in.
- **Changing it** affects new writing only. Existing documents are translated only if the user asks.
- If `language` is missing, use the language the user writes in.

The plugin's own files (skills, agents, templates, this document) are always in English.

## Lanes

A classifier decides; the user can override with one word.

- **Short lane**: small fix, small change, question. One implementer subagent, no SPEC or plan. Still goes through review, diff and commit (gates 3 and 4) and leaves one line in `log.md`.
- **Task** (`/home-office:task`, chosen by the user): one self-contained job — a check, a cleanup, a mechanical change — across any number of repos, with no design. One subagent per repo (the explorer for read-only checks), a results table, one line in `log.md`, and the session ends. Anything that needs decisions goes to the feature lane.
- **Long jobs** (a watcher, operating a server or a bot): tasks too, one step per session, each ending with a hand-over note in `jobs/<name>.md` and the next step offered as a new session. Never one conversation for days, and never on the strong model (see "Loose sessions").
- **Feature lane**: anything that touches more than one repo, changes a contract or schema, or is estimated at more than ~5 files.
- **Minor fixes** (findings from an audit or a review, cleanups, style) go to the short lane or to a task by default, even across repos or over ~5 files, unless one of them changes a contract or a schema. A long list runs as several short changes or tasks; what waits goes to the project's backlog. Only the user can send them to the feature lane.

## Keeping features small

A feature that grows unchecked costs more sessions, more review and more rework than it saves. Three limits keep it in check:

- **Size at gate 1.** The SPEC's header says what the feature **unblocks** (or "nothing on its own") and its **estimate**: TASKs and sessions. The user sees the size when approving it. If the estimate is over `limits.tasks_per_feature`, the SPEC carries a decision: trim or split.
- **TASKs per feature** (`limits.tasks_per_feature`, default 8). If the PLAN needs more, the architect proposes trimming or splitting, and the conductor tells the user, with the number, before asking for gate 2. Keeping an over-limit PLAN is the user's explicit choice, recorded in `DECISIONS.md`. What is trimmed or split off goes to the project's backlog.
- **Review rounds** (`limits.review_rounds`, default 1). One round of review. Another one runs only to check the fixes of high or medium findings, and reviews only those fixes. Low findings are written to `REVIEW.md` and as one line in the project's backlog (`projects/<repo>/project.md`); they never become TASKs or another round unless the user asks.

## Feature lane

0. **Entry** (`new`): the session opened in the work folder becomes the **conductor** (cheap model: the work folder's `.claude/settings.json` makes it the default for new terminal CLI sessions there; in the Claude desktop app, pick it in the model picker). It launches every other role as a subagent and keeps only their summaries.
1. **Explore**: the explorer (cheap model) writes `brief.md`: repos, files, knowledge sections, risks, open questions.
2. **Specify and plan**: the architect (strong model, subagent) writes `SPEC.md`, with what it unblocks and its estimated size → **gate 1**; then `PLAN.md` (contract between layers, "Crossings" if another in-flight feature touches the same repos) and `TASKS.md`, within `tasks_per_feature` or with a proposal to trim or split → **gate 2**. **Planned cut**: the session writes `STATE.md` and ends; execution starts in a new session (`resume`).
3. **Execute**: one fresh subagent per TASK, inside the feature's branch/worktree of that repo, in layer order. Only the files listed in the TASK, plus deleting the files in its `Delete:` list. The repo's `prepare` commands (e.g. code generators) run before its checks on every TASK, and the checks must pass. Two attempts at most; then stop and ask. A TASK that passes is committed on the feature branch (one question per session, or automatically with `commit: auto`), so work never sits uncommitted across sessions. Each session executes at most `tasks_per_session` TASKs, then writes `STATE.md` and hands over to a new one. The conductor keeps only each report's status line and never rereads the SPEC or PLAN in full: subagents read them by path.
4. **Interactive tuning** (optional): the only session opened directly in a repo (browser, emulator, simulator, editor). Max 10 tuning requests or the context cap, then close and reopen.
5. **Review**: reviewer on the diff against the knowledge sources; deep reviewer (strong model) only when the diff touches a risk zone. The conductor writes their findings to `REVIEW.md` → **gate 3**. `review_rounds` rounds (default 1), one more only to check fixes of high or medium findings; low findings go to the backlog.

Whenever a step writes or updates a document, the conductor ends its message with clickable links to it (brief, SPEC, PLAN, TASKS, STATE, REVIEW, DECISIONS), so the user can read it without searching.
6. **Close** (`close`): `STATE.md`, decisions, board, commit message proposals → **gate 4: the user commits and merges**. Worktrees and branches are cleaned up after the merge.

## STATE.md

Six header lines (status, last session, branches, rework count, stream, project) and four sections (done, next, blocked/open questions, decisions this session). About 20 lines. It is the only thing `resume` needs to read.

The rework count is written by `ho.py task-end`, not by the conductor: each TASK that goes back (its gate fails, or its executor reports `blocked` or `needs-plan-change`) adds 1, once per TASK. A `STATE.md` without the line gets it after the branches line; a translated label is found by being the header line with a bare number.

## Loose sessions

A session opened in the work folder without a home-office command (a conversation, a watcher, a server chat) or kept going after `status` is **loose**. It is where long sessions and the strong model creep back in, so:

- `status` runs on Sonnet whatever the session's model, and is a snapshot: the work it lists starts in its own sessions.
- The context cap hook warns a loose session once when it runs on another model than `roles.conductor`, and once when it has been open for `limits.loose_session_hours` (default 12): long jobs go to `/home-office:task`, one step per session with a hand-over note. At the context cap it is told to write that note and continue in a new session.
- Sessions opened outside the work folder (e.g. straight in a repo) are not seen by the hooks.

## Limits (defaults, configurable)

- Context cap per session: 150,000 tokens → close and start a new session instead of compacting.
- Loose sessions: 12 hours (`loose_session_hours`) → one warning to hand over to a new session.
- TASKs per conductor session: 2 → then a planned cut, before the context fills up. In the Claude desktop app the next session is proposed as a card, or started on its own with `handover: auto` when nothing waits for the user. The planning session (brief, SPEC, PLAN) also ends at gate 2. Real use shows a conductor's context holds about SPEC + PLAN + two TASKs.
- Finished sessions (Claude desktop app only): after a hand-over, `resume` archives the previous session of the feature if idle; `close` archives the feature's other idle sessions when it is done, and offers to archive itself last. `archive: ask` (default) asks once; `auto` does not. A parent with other children still in use is never archived (archiving cascades to idle side sessions).
- TASKs per feature: 8 (`tasks_per_feature`) → over it, trim or split before gate 2 (see "Keeping features small").
- Review rounds: 1 (`review_rounds`) → one more only to check fixes of high or medium findings.
- Tuning: 10 requests per session.
- Attempts per TASK: 2.
- Parallel features: no limit, warning from 4.

## Parallel work

- Branch `feature/NN-name` in every repo the feature touches, each in its own worktree.
- Base branch per project; `close` proposes merges in layer order; the user merges.
- Shared packages (declared in config): with several features in flight, the first one ready publishes; the others update to that version before publishing theirs.
- **Batches**: the same kind of change across many repos. Each repo is a feature; the solutions chosen per rule are recorded once in the batch's `DECISIONS.md` and reused.

## Streams

A **stream** is a long-running goal made of different features in sequence (example: "build the mobile app": scaffold, login, list screen…). Several streams run in parallel inside one office, next to ad-hoc features, sharing the project's config, repos, rules and knowledge. A batch is different: the same change across many repos. Both are kept.

- `<work>/streams/NN-name/stream.md` (template `stream.md`): goal, project, scope (repos and roles), **roadmap** (ordered features, each about one session-cut of work, with status `planned` / `in progress` / `done` and a link to `features/NN-name`), shared decisions (or a `DECISIONS.md` beside it) and status.
- Each feature of a stream has the header line `Stream: streams/NN-name` in its `STATE.md`. Features with no stream say `Stream: none`.
- `/home-office:stream new "<goal>"` has the architect (mode `roadmap`) draft the roadmap; the user approves it before anything is written. `/home-office:stream next <stream>` starts the next planned feature through the usual `new` flow; the conductor marks it `in progress`, and gives the architect the stream's shared decisions as it does a batch's `DECISIONS.md`. `close` marks the feature `done` and offers the next one.
- The board and `status` group features by project, then by stream inside it (features with no stream under "Other"), and show each stream's progress (done / total).
- In the Claude desktop app a stream's sessions, hand-overs included, go to its project's sidebar group (see Projects). Session titles stay `feat: NN-name`.

## Projects

A **project** is a logical grouping, one per repo: every repo in `repos` is a project, named by its repo key. Nothing moves on disk: features stay in `<work>/features/NN-name/` with global numbering, tasks and streams keep their places. Each piece of work only says which project it belongs to, and every view can be filtered or grouped by project.

- Hierarchy: **project** (per repo, ongoing) > **stream** (a goal with an end, inside a project) > **feature** / **task**. Batches stay cross-project.
- A feature has `Project: <repo>` in its `STATE.md`; a stream has it in `stream.md`; log lines and task lines record it. A cross-repo feature belongs to the project that **drives** it and also shows in the other projects it touches (board rows marked "touches").
- Optional page `<work>/projects/<repo>/project.md` (template `project.md`): what the project is, backlog, shared decisions, short log of tasks done. Created lazily, the first time something is filed under the project or with `/home-office:project <repo>`.
- `new --project <repo>`, `task --project <repo>` and `stream new --project <repo>` assign it; without the flag `new` takes the repo the classifier lists first and asks in one line if that is ambiguous.
- `/home-office:status <repo>` shows one project; without an argument it groups by project, then by stream. The board has one section per project with streams inside. `/home-office:project` lists projects, shows a page or adds a backlog line.
- Claude desktop app: one sidebar group per project, named `<office> · <repo>` (office = work folder name without `-work`); feature, hand-over and stream sessions go to their project's group.
- **Migration**: features without a `Project:` line count as the first repo of their `Branches` line, or "Other" if none. Nothing needs rewriting; `close` adds the line when it next rewrites `STATE.md`.

## Guards (hooks)

The rules above are enforced, not only requested. They act only inside a worktree with an active task (opened by `scripts/ho.py task-start`, stored in that worktree's private git dir), so normal sessions are never affected.

- **scope guard** (before Edit/Write/Bash): blocks edits outside the TASK's file list, paths forbidden by the project's `guards`, and Bash commands aimed at the worktree that write files or change git state. The file list is matched **by exact path or glob**, so a whole folder has to be listed as `<folder>/**`: a bare `<folder>/` matches no path and every edit under it is blocked. The one exception: `rm`, `unlink`, `git rm` or `Remove-Item` on exact paths that are all in the TASK's delete list (a listed folder covers everything under it).
- **checks gate** (when an executor finishes): runs the repo's `prepare` commands, compares the files changed since the task started with the list (files written by `prepare` and planned deletions are in scope), and runs the repo's checks. On failure the executor is sent back to fix it, up to `task_attempts` times; then the task is marked `fail` and the conductor escalates. Where no executor gate runs (delegated tools, tuning, a hook that did not fire), `task-end` does the same once, so it always answers `pass` or `fail`; it also counts the TASK's rework in `STATE.md`.
- **context cap** (on each prompt and after each subagent): warns at 80 % of `limits.context_tokens` and, over the cap, tells the session to close and continue in a new one. In loose sessions it also warns about the model and the age (see "Loose sessions").

- **session title** (on each prompt): `/home-office:resume NN` titles the session `feat: NN-name`, and `/home-office:new <request>` titles it `new: <request>`. In the Claude desktop app, `new` then renames it to `feat: NN-name` (or `short: <name>`) once the work has a name.

All guards are fail-open: an error in a guard never blocks work. `HOME_OFFICE_GUARD=0`, `HOME_OFFICE_GATE=0`, `HOME_OFFICE_CAP=0` and `HOME_OFFICE_TITLE=0` disable the scope guard, the checks gate, the context cap and the session titles for a session (set them before starting it).

## Delegation

A role can be delegated to another CLI tool (e.g. Gemini CLI, Codex). The delegated tool always runs inside the feature worktree; afterwards the conductor checks the diff (only the TASK's files) and the checks with `task-end`, which runs them itself when no gate ran. Any violation counts as a failed attempt.
