# The home-office workflow

Tool-agnostic description of the method. Adapters (Claude Code today, Codex next) implement it with their own mechanisms. Everything project-specific lives in the project's `.home-office.yml` and knowledge sources, never here.

## Principles

1. **Think with a strong model, execute with cheaper ones.** Each role ("department") has its own tool and model, editable per project.
2. **State lives in files, not in conversations.** Sessions are disposable. A new session resumes from `STATE.md`, never from an old conversation.
3. **Minimal context per agent.** Every task says exactly which files it may touch and which knowledge sections it must read.
4. **The human approves, the agents work.** Four gates: SPEC, PLAN + TASKS, diff, commit. Commits on a feature branch can be delegated (`commit: ask|auto`); merges to the base branch and pushes cannot.

The cost of an agent grows with *number of calls × context size*. Short sessions, minimal context and the right model for each step keep both small.

## Two pieces per project

- **Work** (`docs/work/` in a compact project, a separate repo in a multi-repo project): the board, features, streams, batches, log, the waiting inbox.
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

## Waits

Most stalls are things waiting for the user: a decision, a push, a merge, a check on staging, an environment, data. In the pilot's last month the "Next" of 44 of 79 features named the user, 20 hand-overs sat for more than 4 h (the longest 71 h), and nothing recorded when something started waiting or when it was answered. Four rules:

1. **One inbox: `<work>/waiting.md`** (template `waiting.md`, in `language`). One row per thing that waits on the user: `id` (W-NNN), `since` (date and time), project, work (feature and TASK), kind (`decision` / `push` / `merge` / `deploy-check` / `env` / `data` / `other`), the exact question or action (git commands as `git -C <repo> …`), and what it blocks (a TASK or step, or "nothing else"). When the user answers: `answered` (date and time), the answer and `acted` (when a session carried it out). Nobody writes the table by hand: `ho.py waiting add | answer | acted | list | stats` keeps ids and timestamps. An answered row moves to "Answered" and is **never deleted**: those rows are the measurement.
2. **Plan around waits.** The PLAN has a "Waits" section listing every step that needs the user. TASKs are ordered so independent work comes first; one that needs the user is last or isolated, and carries `Waits: <what>` in `TASKS.md`.
3. **A wait is not a stop.** When a TASK or step needs the user, the conductor files a row, says it in one line, and **continues with the next TASK that does not depend on it**. It cuts or hands over only when nothing independent is left (or at the `tasks_per_session` budget). `STATE.md` "Blocked" lists the waiting ids. Pushes, merges and deploys are never done by the agent: it files the exact command.
4. **Answering.** The user answers in chat; the session that hears it runs `ho.py waiting answer`. Any conductor session (`resume`, `close`) first acts on the answered rows of its feature that nobody has acted on (`acted` empty). `status` shows a "Waiting for you" block at the top, grouped by kind with counts and age ("3 pushes · oldest 2 d"), each row with its exact action, and offers to answer several at once ("approve these 3 pushes?"). That block replaces "waiting for the user" in the list of next commands.

**Hand-over `auto`**: the next session is started when its first step is independent of every open wait, even if the feature has open rows; it is only proposed as a card when the next step itself waits for the user.

**Reading the numbers.** `ho.py waiting stats [--since YYYY-MM-DD] [--project <repo>] [--kind <kind>]` prints JSON: totals, the count by kind (open and answered), the median and p90 wait in hours (answered rows: `answered − since`), and the open rows by age (`<1 d`, `1-3 d`, `3-7 d`, `>7 d`) with the oldest. Read it by kind: a high p90 for `push` means pushes pile up (batch them: "approve these 3 pushes?"); for `decision`, the SPEC or PLAN left questions open; for `deploy-check`, a check that could be moved earlier. A rising "open by age" with a low median means a few rows are forgotten, not that the user is slow.

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

Six header lines (status, last session, branches, rework count, stream, project) and four sections (done, next, blocked/open questions, decisions this session). About 20 lines. It is the only thing `resume` needs to read. "Blocked" lists the feature's open waiting ids (`W-007: push hub`); the detail lives in `waiting.md`.

The rework count is written by `ho.py task-end`, not by the conductor: each TASK that goes back (its gate fails, or its executor reports `blocked` or `needs-plan-change`) adds 1, once per TASK. A `STATE.md` without the line gets it after the branches line; a translated label is found by being the header line with a bare number.

## Loose sessions

A session opened in the work folder without a home-office command (a conversation, a watcher, a server chat) or kept going after `status` is **loose**. It is where long sessions and the strong model creep back in, so:

- `status` runs on Sonnet whatever the session's model, and is a snapshot: the work it lists starts in its own sessions.
- The context cap hook warns a loose session once when it runs on another model than `roles.conductor`, and once when it has been open for `limits.loose_session_hours` (default 12): long jobs go to `/home-office:task`, one step per session with a hand-over note. At the context cap it is told to write that note and continue in a new session.
- Sessions opened outside the work folder (e.g. straight in a repo) are not seen by the hooks.

## Limits (defaults, configurable)

- Context cap per session: 150,000 tokens → close and start a new session instead of compacting.
- Loose sessions: 12 hours (`loose_session_hours`) → one warning to hand over to a new session.
- TASKs per conductor session: 2 → then a planned cut, before the context fills up. In the Claude desktop app the next session is proposed as a card, or started on its own with `handover: auto` when its first step is independent of every open wait (see "Waits"). A wait alone never cuts a session: independent TASKs go first. The planning session (brief, SPEC, PLAN) also ends at gate 2. Real use shows a conductor's context holds about SPEC + PLAN + two TASKs.
- Finished sessions (Claude desktop app only): after a hand-over, `resume` archives the previous session of the feature if idle; `close` archives the feature's other idle sessions when it is done, and offers to archive itself last. `archive: ask` (default) asks once; `auto` does not. A parent with other children still in use is never archived (archiving cascades to idle side sessions).
- TASKs per feature: 8 (`tasks_per_feature`) → over it, trim or split before gate 2 (see "Keeping features small").
- Review rounds: 1 (`review_rounds`) → one more only to check fixes of high or medium findings.
- Tuning: 10 requests per session.
- Attempts per TASK: 2.
- Checks gate time cap: 540 s (`gate_seconds`) → `gate: timeout`, finished by `task-end`.
- Parallel features: no limit, warning from 4 (see "Parallel features" for claims, hotspots and early sync).

## Parallel work

- Branch `feature/NN-name` in every repo the feature touches, each in its own worktree.
- Base branch per project; `close` proposes merges in layer order; the user merges. Parallel features in one repo claim files and share hotspots, and sync the base early (see "Parallel features").
- Shared packages (declared in config): with several features in flight, the first one ready publishes; the others update to that version before publishing theirs.
- **Batches**: the same kind of change across many repos. Each repo is a feature; the solutions chosen per rule are recorded once in the batch's `DECISIONS.md` and reused.

## Parallel features

With several features in flight in one repo, the same few files collide on merge. In the pilot's last month, 27 pairs of features were active at once in the same repo (up to 4), and 10 merges had real conflicts, always in hot files: static-analysis baselines, string resources, shared test files, config, the project page. A PLAN's "Crossings" section said who goes first, but nothing enforced it, and the base was merged into a feature branch only right before its merge. Three mechanisms, all deterministic in `ho.py`:

1. **File claims.** `task-start` records the TASK's closed file list (and its delete list) as claims of its feature in `home-office-claims.json`, in the repo's **common** git dir (`git rev-parse --git-common-dir`), so every worktree of the repo sees them: `feature`, `task`, `worktree`, `files`, `delete`, `since`. If a file is already claimed by **another** feature's open TASK, or changed by another feature's unmerged branch (`--base <repo base>` turns on that part), `task-start` does not block: it returns `conflicts: [{file, feature, task, since, source}]` (`source`: `task` or `branch`). The conductor says them in one line and follows the PLAN's crossing (who goes first), or asks. `task-end` releases the TASK's claim, `worktree-remove` the whole worktree's, and a claim whose worktree is gone is dropped by itself. Claims are advice, never a lock on the filesystem: the scope guard is unchanged.
2. **Hotspots.** `hotspots: [globs]` per repo in `.home-office.yml` (baselines, string resources, lock files, shared config, shared test files). A hotspot is edited by **one feature at a time**: `task-start --hotspot <glob>` (the conductor passes the repo's list) for a TASK that lists a hotspot another feature holds returns `ok: false` with who holds it (`hotspots_held`) and opens nothing, unless `--force`. The conductor then orders the work: other independent TASKs first, a row in the waiting inbox for this one ("wait for 04-x to merge"), and a retry in the next session. The architect names every hotspot a TASK touches (PLAN "Crossings", `Hotspots:` in `TASKS.md`) and puts such TASKs as late as possible and small.
3. **Early sync.** `ho.py sync --worktree <wt> --base <repo base>` merges the base branch into the feature branch **only if** the worktree is clean and no TASK is open there (otherwise `refused`, with the reason). It answers `up_to_date`, `merged` (with the files the base brought) or `conflict`: then it runs `git merge --abort`, leaves HEAD and the files exactly as they were, and lists the conflicting files. It never pushes and never rebases. `resume` runs it for every worktree of the feature at the start of a session, once the previous session's commits are in; `close` runs it once more before proposing merges. A conflict becomes a TASK proposal or a waiting row, never a manual fix by the conductor.

**Reading `ho.py claims --repo <repo> [--base <base>]`**: JSON with `claims` (one per open TASK: feature, task, worktree, files, since), `branches` (with `--base`: unmerged feature branches and the files they changed against it) and `dropped_stale` (claims removed because their worktree is gone). A file or glob that appears under two features is a crossing; one that matches a `hotspots` glob is a hotspot held by that feature until its TASK ends (or, for a branch, until it is merged). An old `since` on a claim means a TASK nobody closed.

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

## Validation levels

Each full suite runs once per state of the code, whoever asks. In the pilot, 1,391 of 2,441 full suites were the same suite in the same worktree within an hour, 519 of them rerun by another actor (conductor after executor).

| Level | Who | What runs |
|---|---|---|
| Iterating | executor, tuning | Only filtered tests: one file or class, `--filter <name>`. Never the whole suite. |
| TASK | the executor once when done, then the checks gate | The repo's full `checks`, once per TASK, through the cache. |
| Before the merge (gate 3 / close) | the conductor, before the reviewers | The full checks of **every repo touched**, plus the checks of the repos that **consume** a changed `shared_packages` repo (an SDK → the hub and the apps). Once each, through the cache. |
| CI | the repo's own pipeline | Whatever it does. This flow opens no PRs, so the local results above are the source of truth. |

**The check cache** (`ho.py check --worktree <wt> --cmd "<check>"`). It runs one check command in a worktree and remembers a pass, keyed by (command, state of the files). The state is `git write-tree` of a temporary index that holds the working tree: tracked changes and untracked files that are not ignored, so any edit, new file or deletion invalidates it, and the real index is never touched. Ignored files (`vendor`, `node_modules`, caches, `.env`) are not part of it: a change of dependencies shows up in the lock file. Entries live in the worktree's private git dir (`home-office-checks.json`), so two worktrees never share one. Only passes are cached; a failure always runs again. A cached call answers `cached: true` in a fraction of a second (a few hundred ms on a small repo; it hashes only what changed). `--no-cache` forces a run; the command must match the repo's `checks` entry exactly. The gate and `task-end` run the TASK's checks through the same cache, so an executor's passing run is not repeated by them, and `task-end` after the gate is instant.

## Guards (hooks)

The rules above are enforced, not only requested. They act only inside a worktree with an active task (opened by `scripts/ho.py task-start`, stored in that worktree's private git dir), so normal sessions are never affected.

- **scope guard** (before Edit/Write/Bash): blocks edits outside the TASK's file list, paths forbidden by the project's `guards`, and Bash commands aimed at the worktree that write files or change git state. The file list is matched **by exact path or glob**, so a whole folder has to be listed as `<folder>/**`: a bare `<folder>/` matches no path and every edit under it is blocked. The one exception: `rm`, `unlink`, `git rm` or `Remove-Item` on exact paths that are all in the TASK's delete list (a listed folder covers everything under it).
- **checks gate** (when an executor finishes): runs the repo's `prepare` commands, compares the files changed since the task started with the list (files written by `prepare` and planned deletions are in scope), runs the repo's checks through the check cache (see "Validation levels") and, if they pass, its advisories. On failure the executor is sent back to fix it, up to `task_attempts` times; then the task is marked `fail` and the conductor escalates. Where no executor gate runs (delegated tools, tuning, a hook that did not fire), `task-end` does the same once, so it always answers `pass` or `fail`; it also counts the TASK's rework in `STATE.md`.
  - **Formatters fix themselves.** Put them in `prepare` (`vendor/bin/pint --dirty`, prettier on changed files, `./gradlew ktlintFormat`), limited to changed files: style fixes happen before the checks. What a prepare command writes counts as generated, except a file the executor had already changed (it differs from the task-start baseline): that one stays subject to the TASK's file list, so a formatter cannot hide an out-of-scope edit.
  - **Advisories** (`advisories` per repo, e.g. `composer audit`, `npm audit`) run after the checks, never block, and their output tail goes into the task result (`advisories`). The conductor records them in `REVIEW.md` and, when they found something, as one line in the project's backlog. An audit does not belong in `checks`: a new CVE would fail every TASK on code nobody touched (`init` suggests moving it).
  - **Time cap.** The app cancels a SubagentStop hook after about 600 s whatever `hooks.json` says, so the gate gives itself `limits.gate_seconds` (default 540). A command still running at the cap is killed with its process tree, the gate records `gate: timeout` (not a failure, no attempt used) and lets the executor stop; `task-end` then runs the rest with no cap, skipping the checks that already passed.
- **context cap** (on each prompt and after each subagent): warns at 80 % of `limits.context_tokens` and, over the cap, tells the session to close and continue in a new one. In loose sessions it also warns about the model and the age (see "Loose sessions").

- **session title** (on each prompt): `/home-office:resume NN` titles the session `feat: NN-name`, and `/home-office:new <request>` titles it `new: <request>`. In the Claude desktop app, `new` then renames it to `feat: NN-name` (or `short: <name>`) once the work has a name.

All guards are fail-open: an error in a guard never blocks work. `HOME_OFFICE_GUARD=0`, `HOME_OFFICE_GATE=0`, `HOME_OFFICE_CAP=0` and `HOME_OFFICE_TITLE=0` disable the scope guard, the checks gate, the context cap and the session titles for a session (set them before starting it).

## Delegation

A role can be delegated to another CLI tool (e.g. Gemini CLI, Codex). The delegated tool always runs inside the feature worktree; afterwards the conductor checks the diff (only the TASK's files) and the checks with `task-end`, which runs them itself when no gate ran. Any violation counts as a failed attempt.
