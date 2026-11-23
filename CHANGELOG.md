# Changelog

## 0.4.0-pre.33 — 2026-11-23
No session inherits an old model. In the pilot, a session created on an older Opus generation never changed model, and every session it started with `start_session` without `model` was born on it too: 262 `start_session` calls in the pilot's transcripts passed no `model`, while the plugin set it only in the hand-overs of `new`, `resume` and `task`. And `weight` did not count the `@AGENTS.md` that most repos' `CLAUDE.md` import.
- **Every `start_session` passes `model`.** New WORKFLOW section "Session models" and `new` § 0 step 7 (followed by `resume`, `task` and `status`): any session started from a work folder (hand-over, card, side job, own-initiative proposal) gets a full id: `roles.conductor.model` for a conductor session, else the newest id of the family it needs. Never left out.
- **`ho.py models`.** Prints the newest full id of each family (`current`) and each Claude role's model as a full id (`roles`). The list lives in `CURRENT_MODELS` in `hooks/_common.py`, kept up to date with each release; a project can override any family with the new `current_models: { opus: <id>, … }` in `.home-office.yml` (template).
- **Stale-model warning.** The context cap hook now also runs on `SessionStart` and warns every session in the work folder once (flow sessions too) when its model is an older generation of its family than the current one (`claude-opus-5` when `claude-opus-5-5` is current, any dated 4.x id…), with the `/model` to switch to and the reminder to pass `model` to the sessions it starts. The model is the hook input's `model` when the app sends one, else the latest main model call in the transcript (a brand-new session is checked from its first model call on). Aliases and unknown ids are never warned about.
- **`weight` counts imports.** A repo's `CLAUDE.md` / `AGENTS.md` that pulls in files with `@path` lines (relative, `~/`, nested up to 5 hops, not inside code) now weighs its own text plus its imports: `tokens` is the total, with `own_tokens` and `imports: [{path, tokens}]`, so the total counts in `over`. A file already imported is not listed again. In the pilot it raised the repos' `CLAUDE.md` over `file_tokens` from 3 to 7.
- Docs: WORKFLOW "Session models" and Guards, `new`, `task`, README, template.

## 0.4.0-pre.32 — 2026-11-23
A harness that does not grow, and less scaffolding for mature repos. In the pilot after three months, the board alone was ~44,600 estimated tokens (202 lines of struck-through history, loaded by every `new`, `resume` and `status`), the log had 307 rows (~84,000 tokens), a project page ~10,500, and 3 repos' `CLAUDE.md` passed 4,000; 12 of 20 repos have hundreds of commits and tests, yet a change in them took the same SPEC → PLAN → TASKs path as in an empty repo.
- **`ho.py weight [--rotate]`.** Measures what sessions load (config, board, knowledge indexes; project, stream and batch pages; open `STATE.md` files, done ones skipped by their status word in any of several languages; the waiting inbox; each repo's `CLAUDE.md` / `AGENTS.md`), with estimated tokens, `always_read_tokens` for what every session loads, and `over` with the fix. New limits `file_tokens` (4000), `log_rows` (60) and `waiting_days` (30). `--rotate` moves log rows beyond `log_rows` and acted waiting rows older than `waiting_days` to `<work>/archive/` (same format; nothing deleted; idempotent); `waiting stats` still counts archived rows. Log tables with blank lines between rows are read as one table.
- **Compaction.** `close` keeps the board to what is live (one row per feature in flight, no history), removes a finished feature's rows and notes instead of marking them done, runs `weight --rotate` and compacts the files it wrote that are over the limit. `status` shows one "Harness weight" line when something is over and a housekeeping command (`/home-office:task "compact the harness: …"`). New WORKFLOW section "Harness weight" says what each file keeps.
- **`ho.py maturity [--repo]`.** Per repo: commits, age, tracked and test files, checks and `mature` (at least 200 commits, 20 test files, 60 days and some checks), or the repo's new `mature: true|false` in the config. `new` passes it to the classifier: inside one mature repo, a change with no contract, schema, hard-rule or risk-zone impact and no open decision is short up to ~10 files (or a task), and the short-lane implementer reads the code and tests around the change as its guide. Young repos keep the old rules.
- Docs: WORKFLOW "Lanes", "Limits" and "Harness weight", template, README.

## 0.4.0-pre.31 — 2026-11-18
Hot files and integration order between parallel features. In the pilot's last month 27 pairs of features were active at once in the same repo (up to 4); 10 merges had real conflicts, always in hot files (static-analysis baselines, string resources, shared test files, config, the project page), "Crossings" in the PLAN were never enforced, and the base was merged into a feature branch only right before its merge.
- **File claims.** `task-start` records the TASK's closed file list and delete list as claims of its feature in `home-office-claims.json`, in the repo's common git dir (all worktrees share it): feature, task, worktree, files, delete, since. A file already claimed by another feature's open TASK, or changed by another feature's unmerged branch (new `--base <repo base>`), comes back as `conflicts: [{file, feature, task, since, source}]` and never blocks; the conductor says it in one line and follows the PLAN's crossing, or asks. `task-end` releases the TASK's claim, `worktree-remove` the worktree's (`claims_released`), and claims whose worktree is gone are dropped automatically. New `ho.py claims --repo <repo> [--base <base>]` lists them as JSON. A feature's own claims never conflict with itself.
- **Hotspots.** New per-repo `hotspots: [globs]` in `.home-office.yml` (template; `init` proposes them by stack: baselines, `**/values*/strings.xml`, lock files, shared config). `task-start --hotspot <glob>` for a TASK that lists a hotspot another feature holds returns `ok: false` with `hotspots_held` and opens nothing, unless `--force`; the conductor then does other independent TASKs, files a waiting row and retries next session. The architect (mode `plan`) names every hotspot a TASK touches, puts those TASKs as late as possible and small; `PLAN.md` "Crossings" and a new `Hotspots:` line in `TASKS.md` carry it.
- **Early sync.** New `ho.py sync --worktree <wt> --base <repo base>`: merges the base into the feature branch only when the worktree is clean and no TASK is open (`refused` with a reason otherwise, also off a feature branch). Answers `up_to_date`, `merged` (files the base brought, `fast_forward`) or `conflict`: it runs `git merge --abort`, leaves HEAD and files as they were (`unchanged: true`) and lists the files. Never pushes, never rebases. `resume` runs it per worktree after the previous session's commits are in; `close` runs it once more before proposing merges. A conflict becomes a TASK proposal or a waiting row, never a manual fix by the conductor.
- Docs: WORKFLOW "Parallel features" (with how to read `ho.py claims`), Limits and Parallel work, README.

## 0.4.0-pre.30 — 2026-11-18
Don't stop for a wait. In the pilot's last month the "Next" of 44 of 79 features named the user, 20 hand-overs sat for more than 4 h (the longest 71 h), about 10 standing "do not push or deploy without the user" orders existed, and 76 DECISIONS rows were decisions the user had to take, 35 of them pushes; nothing recorded when something started waiting or when it was answered.
- **Waiting inbox `<work>/waiting.md`** (new template `waiting.md`, in `language`, created by `init`). One row per thing that waits on the user: `W-NNN`, `since`, project, feature or task, kind (`decision` / `push` / `merge` / `deploy-check` / `env` / `data` / `other`), the exact question or action (git commands as `git -C <repo> …`), what it blocks. When answered: `answered`, the answer and `acted`. Answered rows move to an "Answered" section and are never deleted.
- **`ho.py waiting add | answer | acted | list | stats`.** All print JSON; ids and timestamps (`YYYY-MM-DD HH:MM`) come from the helper, nobody hand-writes the table (`--now` and `--config` exist for tests). `list [--state open|answered|unacted|all] [--project] [--kind] [--feature] [--since]` gives rows with `age_hours` / `wait_hours` and open counts by kind with the oldest; `stats [--since DATE]` gives the count by kind, median and p90 wait in hours, open rows by age and the oldest. Headings may be translated: the two tables are found by position.
- **Plan around waits.** The architect (mode `plan`) writes a "Waits" section in `PLAN.md` (template), orders TASKs so independent work comes first, and marks the ones that need the user `Waits: <what>` in `TASKS.md` (template); its summary ends with the waits.
- **Keep going.** `new` § Execute and `resume`: when a TASK or step needs the user, the conductor files a row, says it in one line and continues with the next TASK that does not depend on it; it cuts or hands over only when nothing independent is left. A TASK that fails (`blocked`, `needs-plan-change`, gate fail) is filed the same way. `STATE.md` "Blocked" lists the waiting ids. The hand-over `auto` rule now starts the next session when its first step is independent of every open wait.
- **Answering.** The session that hears the answer runs `waiting answer`; `resume` and `close` first act on answered rows nobody has acted on (`waiting acted`). `close` files the pushes and merges it proposes. `status` shows a "Waiting for you" block at the top (by kind, counts, age, each row's exact action), offers to answer several at once, and that block replaces "waiting for the user" in the next-commands list.
- Docs: WORKFLOW "Waits" (with how to read `stats`), Limits and hand-over, STATE.md, README.

## 0.4.0-pre.29 — 2026-11-18
A check cache, so a full suite runs once per state of the code. In the pilot's last month, 1,391 of 2,441 full suites were the same suite in the same worktree within an hour (about 1,126 min), 519 of them rerun by another actor (the conductor after the executor); the hub's `composer test` takes 96 s median, 181 s p90.
- **`ho.py check --worktree <wt> --cmd "<check>" [--timeout] [--tail] [--no-cache]`.** Runs one check and caches a pass keyed by (command, state of the files). The state is `git write-tree` of a temporary index (a copy of the worktree's, so git's stat cache is kept) that holds the working tree: any edit, new untracked file or deletion invalidates it; ignored files do not count; the real index is never touched. Stored in the worktree's private git dir (`home-office-checks.json`: result, tail, duration, timestamp, last 60 entries), so worktrees never share entries. Failures are never cached and always rerun. Output: `ok`, `cached`, `seconds`, `ran_seconds`, `tail`, `timed_out`; exit code 1 on failure. A cached call takes ~0.1 s on a small repo. Fail-open: if git cannot give the state, the check just runs.
- **Everyone goes through it.** The checks gate and `task-end` run the TASK's `checks` via the cache (`cached: true` in `results`); executors (`backend`, `frontend`, `implementer`) iterate on filtered tests and run the full checks once, when done, through the `ho.py check` line the conductor puts in their prompt; `new`, `task`, `resume` (tuning), `close` and `reviewer` say the same.
- **Validation levels** (new WORKFLOW section): executor (filtered tests), TASK (full checks once, cached), before the merge (new `new` § "Review → gate 3" step 0: full checks of every repo touched plus the consumers of a changed `shared_packages` repo, once each through the cache; a failure is a high finding), CI (the repo's own; this flow opens no PRs).

## 0.4.0-pre.28 — 2026-11-18
A checks gate with less noise. In the pilot's last month, 465 gate blocks: 188 were `composer audit` advisories, 107 lint or format, only 21 tests or static analysis; 18 gates were cancelled at exactly 600 s.
- **Advisories.** New per-repo `advisories: [...]` in `.home-office.yml` (`composer audit`, `npm audit`), passed with `task-start --advisory "<cmd>"`. They run after the checks pass, never block, and their output tail goes to `advisories` in the `task-end` / `task-status` result. The conductor records them under a new "Advisories" section of `REVIEW.md` and, when one found something, as one line in the project's backlog. `init` detects a repo whose `checks` run an audit (or a `composer.json` / `package.json` script wrapping one) and suggests moving it.
- **Formatters fix themselves.** `init` and WORKFLOW say to put formatters in `prepare` (`vendor/bin/pint --dirty`, prettier on changed files, `ktlintFormat`). Fix in the generated-files logic: a file the executor had already changed (it differs from the task-start baseline) is no longer exempted as "generated" because a prepare command rewrote it, so a formatter cannot hide an out-of-scope edit; clean files a prepare command writes still count as generated.
- **The 600 s cap.** The app cancels SubagentStop hooks at about 600 s, whatever `hooks.json` says. New `limits.gate_seconds` (default 540, `task-start --gate-seconds`): the gate runs everything within that budget. A command still running is killed with its whole process tree (checks now write to a temp file instead of a pipe, so a grandchild cannot keep the call waiting), the gate records `gate: timeout` with a message, uses no attempt, and lets the executor stop. `task-end` then runs the rest with no cap and skips the checks that already passed. Not a failure, never counted as rework.

## 0.4.0-pre.27 — 2026-11-17
From the 2026-11-09 measurement: almost half of the Opus left came from loose sessions in the work folder (watchers, server chats, a `status` session kept for days), and the rework count in `STATE.md` was almost never written.
- **Rework counted by `ho.py`.** `task-end` adds 1 to the `Rework:` line of the feature's `STATE.md` when a TASK goes back: its gate fails, or the new `--report <status>` (the executor's status line) is `blocked` or `needs-plan-change`. Once per TASK, even if `task-end` runs twice; `rework` in the result says what was recorded. `task-start` finds the `STATE.md` from `--task "NN-name / …"` and the `.home-office.yml` of the current folder (`state` in its result), or takes `--state <path>` (tuning). Existing files keep working: the line is found by its label (`Rework`, `Vueltas atrás`…) or as the header line with a bare number, any note after the number is kept, and a file without it gets `Rework: 1` after the branches line. Short-lane and task runs record nothing. The conductor no longer edits the count.
- **`task-end` always returns the gate.** When no checks gate ran (`gate: null`: delegated tools, tuning, a hook that did not fire), it now runs the prepare commands, the scope check and the checks itself, once, instead of returning a hint to call it again with `--run-checks` (still accepted, now a no-op). Called again after the TASK is closed, it repeats the last TASK's result instead of `{"active": false}`. `gate` is the first field of the output. New `--no-checks` closes a TASK dropped before any work as `gate: skipped`.
- **`status` runs on Sonnet** (`model: sonnet` in the skill) whatever the session's model, and is a snapshot: work asked for afterwards is pointed to `resume`, `task` or `new` in its own session.
- **Loose sessions.** The context cap hook now tells apart sessions started by a home-office command from loose ones (no command, or kept going after `status`). A loose session is warned once when it runs on another model than `roles.conductor`, and once when it has been open for the new `limits.loose_session_hours` (default 12); at the context cap it is told to write a hand-over note and continue in a new session instead of `/home-office:close`.
- **Long jobs** (a watcher, operating a server or a bot) are tasks: `task` § "Long jobs" runs them one step per session, with a hand-over note in `<work>/jobs/<name>.md` (new template `job.md`) and the next step proposed as a card. The classifier sends them to `lane: task`.

## 0.4.0-pre.26 — 2026-11-17
- Fast worktrees: cloning a `link` folder (`vendor`, `node_modules`) skips symlinks and Windows junctions inside it (e.g. path repositories, `node_modules/.bin`) instead of following them or failing on them.

## 0.4.0-pre.25 — 2026-11-17
- **Keeping features small** (new WORKFLOW section). In the pilot, minor fixes grew into features of 16–20 TASKs with several review rounds.
  - Size at gate 1: the SPEC header has two new lines, `Unblocks:` and `Estimate:` (TASKs and sessions, with the limit). The conductor shows both when asking for gate 1; an estimate over the limit adds a "trim or split" decision.
  - New `limits.tasks_per_feature` (default 8). The conductor passes it to the architect, whose plan summary starts with `tasks: n (limit m)` and, over it, a trim or split proposal. The conductor says the number before asking for gate 2; keeping an over-limit PLAN needs the user's explicit word, recorded in `DECISIONS.md`. What is left out goes to the project's backlog.
  - New `limits.review_rounds` (default 1). One round; another only to check fixes of high or medium findings, and it reviews only the fix commits. Low findings are written to `REVIEW.md` plus one line in the project's backlog, and never become TASKs or another round unless the user asks. `new` § "Review → gate 3", `resume`, the short lane, `reviewer` (severity guide, verdict line `high n · medium n · low n · another round: yes|no`), `deep-reviewer` and the `REVIEW.md` template follow it.
  - Classifier: minor fixes (audit or review findings, cleanups, style) go to `short` or the new `lane: task` by default, even across repos or over ~5 files, unless they change a contract or a schema. `new` offers `/home-office:task` for `lane: task`; `task` accepts them.
- Checks gate: when a check fails, its full output is saved to `<temp>/home-office-checks/<date>-<command>.log` and the report adds that path; the report itself still keeps only the tail.
- Docs: a folder in a TASK's file list must be written as a glob (`<folder>/**`); a bare `<folder>/` matches no path and the scope guard blocks every edit under it. Said where the conductor builds the command (`new` step 2), in the guard's own docstring and as a known pitfall in the plugin's card. `--delete` keeps the opposite convention (exact paths, a folder covers its contents).

## 0.4.0-pre.24 — 2026-10-23
- Fast worktrees: new per-repo `link: [vendor, node_modules]`. When a worktree is created and the folder's lock file (`composer.lock`, `package-lock.json`, …) is identical to the main checkout's, `ho.py worktree --link` clones the folder with hard links (the pilot's hub `vendor`, ~16,800 files, in ~9 s instead of a ~3 min `composer install`) and skips the matching install command in `setup`. `vendor/composer` (autoload with `__DIR__` paths) is copied for real, so classes load from the worktree; nested `.git` folders and caches are skipped.
- Safety: edits to a cloned folder are denied during a TASK (it shares files with the main checkout). A TASK whose file list includes the folder's manifest or lock (`composer.json`, `package.json`, …) gets a real install first: `task-start --setup` removes the clone and runs the install. `worktree-remove` only removes the links, never the main checkout's files.

## 0.4.0-pre.23 — 2026-10-23
- No repeated checks: the conductor trusts the checks gate (`gate: pass` means everything ran) and reads failures from `problems`. It never runs the repo's checks by hand; in the pilot, a 5-minute `composer test` ran several times per TASK.
- `task-end` keeps the TASK open when no gate ran (`gate: null`) and returns a `hint` to call it once with `--run-checks`. Before, the first call removed the scope, so the checks could only be rerun by hand.

## 0.4.0-pre.22 — 2026-10-22
- One offer per hand-over: the card is the only place the next session is offered, with no extra "start it?" question or button in the app's next-step box. If the user says to start it, the conductor starts the existing card by its `proposal_id` instead of proposing a new one. Before, a planned cut showed two offers for the same session.

## 0.4.0-pre.21 — 2026-10-22
- Archiving no longer gives up silently when the desktop app's auto-mode permission check refuses it (it wants the user's explicit OK per session). The session asks once in chat, naming the sessions, and archives on a yes; otherwise it lists them for the sidebar. New `project` § "Archiving sessions", used by `resume`, `close` and `task`.
- `init`, with `archive: auto`, offers to allow `mcp__ccd_session_mgmt__archive_session` in the work folder's `.claude/settings.json`.

## 0.4.0-pre.20 — 2026-10-22
- New `ho.py worktree-remove --repo --dest [--branch] [--base] [--delete-branch] [--force]`, the inverse of `worktree`. It refuses while a TASK is open in the worktree, with uncommitted changes (even with `--force`), on the repo's main checkout, and, with `--delete-branch`, when the branch is not merged into `--base`; then nothing is removed. Branches go with `git branch -d`, never `-D`. `--force` only covers what a clean status leaves behind (submodules). JSON output like the other subcommands.
- `close` removes worktrees and branches with it after the user confirms the merges, instead of git by hand.

## 0.4.0-pre.19 — 2026-10-22
- Side sessions for parallel work next to a feature (follow-ups, side jobs) begin with a home-office command (`/home-office:task --project <repo> "…"` or `/home-office:new --project <repo> "…"`), so they run the plugin and get a clear title. They stay nested under the session that started them on purpose; only hand-overs go to the top level.
- `new` and `task` can run when a session's first message has that command line (no more `disable-model-invocation`), like `resume`.
- The title hook finds `new`/`task` on any line too, and leaves `--project`/`--stream` out of the title.

## 0.4.0-pre.18 — 2026-10-22
- Scope guard, fewer false alarms: output redirected to a file **outside** the worktree (`> /tmp/x.log`, `> "$TEMP/out.txt"`, any absolute path elsewhere) is allowed during a TASK, and `->`, `=>` or `>` inside quotes (e.g. `grep "->where("`) no longer count as redirections. Redirections into the worktree, or to a path it cannot resolve, are still blocked.
- Inline scripts that write files (heredocs or `-c`/`-r` with `open(…, 'w')`, `write_text`, `file_put_contents`, `fs.writeFile`…) are now blocked on purpose, with a clear message; before they were only caught by chance.
- The block message suggests redirecting output to `$TEMP` instead.

## 0.4.0-pre.17 — 2026-10-21
- Sessions started by another session (hand-overs, cards) no longer nest under it in the desktop sidebar. The starting session detaches the session it starts, and `resume` detaches itself at the start; then the session goes to its project's group at the top level. As a side effect, archiving an old session never archives its successor.

## 0.4.0-pre.16 — 2026-10-21
- Session titles for `/home-office:status`: `<work folder>: status`, or `<work folder>: status · <project>` with a project argument.
- The title hook also understands slash commands in tag form (`<command-name>…</command-name>` with `<command-args>…</command-args>`), for `new`, `task`, `resume` and `status`.

## 0.4.0-pre.15 — 2026-10-21
- **Projects**: a logical grouping, one per repo (every key in `repos`). Nothing moves on disk: features keep `features/NN-name/` and global numbering; each piece of work records its project. A cross-repo feature belongs to the project that drives it and shows as "touches" in the others.
- `STATE.md` has a sixth header line, `Project:` (after `Stream:`); `stream.md` has `Project:`; the short-lane log has a Project column. New optional page `projects/<repo>/project.md` (template `project.md`: what it is, backlog, shared decisions, tasks done), created lazily.
- `new`, `task` and `stream new` accept `--project <repo>`; `new` defaults to the first repo the classifier lists and asks in one line if ambiguous.
- `status [<repo>]` shows one project or groups by project, then stream; the board has one section per project with streams inside. New `/home-office:project`: list projects, show a page, `add "<idea>"` to the backlog.
- Desktop app: one sidebar group per project, `<office> · <repo>`, replacing pre.11's per-stream group.
- Migration: features without `Project:` count as the first repo of their `Branches` line, or "Other".

## 0.4.0-pre.14 — 2026-10-21
- Numbered titles for hand-over sessions: their first message starts with the app's "Background…" block, so the title hook now finds `/home-office:resume NN` on any line, not only the first. Before, those sessions kept the card's title with no `#n`.
- `resume` checks its own title in the desktop app and renames itself to `feat: NN-name #n` if the number is missing.

## 0.4.0-pre.13 — 2026-10-21
- `/home-office:status` ends with the next commands to run, in order: what waits for the user (blocked items, pushes and merges as `git -C` commands), `resume` for features ready to continue, `close` for features ready to close, `stream next` for streams with nothing in progress. In the desktop app it also offers the first one as a session card.

## 0.4.0-pre.12 — 2026-10-20
- Numbered sessions: a feature's sessions are titled `feat: NN-name #n` in order. `new`'s session is #1 (renamed in the desktop app), and each `resume` session gets the next number from the title hook, kept per session in `features/NN-name/sessions.json` so re-running resume keeps it. The conductor names other sessions of the feature by that number.

## 0.4.0-pre.11 — 2026-10-20
- **Streams**: parallel long-running lines of work inside one office, made of different features in sequence (e.g. building a new app next to ongoing audits). `<work>/streams/NN-name/stream.md` (new template) holds the goal, scope, roadmap (`planned / in progress / done`, linked to `features/NN-name`), shared decisions and status. Batches stay as they are (the same change across many repos).
- New `/home-office:stream`: no args lists streams with roadmap progress; `new "<goal>"` has the architect draft the roadmap in a new `roadmap` mode (writes only `stream.md`) and waits for approval; `next <stream>` starts the next planned feature through the `new` flow.
- `new` links a feature to a stream (`--stream <name>`, or named in the request): `Stream:` header line in `STATE.md` (new, after `Rework`), roadmap row `in progress`, stream's `stream.md` passed to the explorer and architect. `close` marks it `done` and offers the next one.
- The board and `status` group rows by stream ("Other" for the rest) and show roadmap progress. Claude desktop app: a stream's sessions, hand-overs included, go to a sidebar group `<project> · <stream>`; titles stay `feat: NN-name`.
- `init` creates `streams/`. Existing work folders: create `streams/` when you need it; older `STATE.md` files without the `Stream:` line count as no stream.

## 0.4.0-pre.10 — 2026-10-20
- `copy` accepts folders (e.g. built assets git ignores, like `public/build`); before, `ho.py worktree` silently skipped anything that was not a file.
- Per-repo `base` in `repos` overrides `base_branch` for that repo (worktrees, review, merges, `task`), for a repo whose base is `main` in a project whose base is `dev`.

## 0.4.0-pre.9 — 2026-10-19
- New `/home-office:task "<job>"`: one self-contained check, cleanup or mechanical change, even across several repos, with no SPEC, PLAN or TASKs. Read-only checks go to the explorer, changes to one implementer per repo under the usual guards and checks. It reports a results table, logs one line and ends in the same session (archiving itself with `archive: auto`). Requests that need design are sent to `/home-office:new`.
- Session titles: `/home-office:task <job>` sessions are titled `task: <job>`.

## 0.4.0-pre.8 — 2026-10-19
- Commit per TASK on the feature branch: a TASK that passes its gate is committed in its worktree (`NN-name / TASK n: <title>`, only its `touched` files). New `commit: ask | auto` in `.home-office.yml`: `ask` (default) asks once per session, at the planned cut; `auto` commits each TASK as it passes. SHAs go to `STATE.md`. Merges to the base branch and pushes stay with the user.

## 0.4.0-pre.7 — 2026-10-19
- Automatic hand-overs work: `resume` no longer has `disable-model-invocation`, so a session started by a hand-over (its first message is `/home-office:resume NN-name`) can run it. Before, the Skill tool refused it and the new session waited for the user to type the command.

## 0.4.0-pre.6 — 2026-10-19
- Finished sessions are archived (Claude desktop app only; the CLI is unchanged). `resume` archives the previous session of the feature after a hand-over when it is idle, and `close` archives the feature's other idle `feat: NN-name` sessions once it is done, then offers to archive itself as the very last action. A parent with other children still in use is skipped (archiving cascades to idle side sessions).
- New `archive: ask | auto` in `.home-office.yml` (default `ask`: one question before archiving).

## 0.4.0-pre.5 — 2026-10-19
- Hand-overs are mandatory in the Claude desktop app: a planned cut always starts or proposes the next session, never just prints the command (the pilot showed a cut that skipped the card).
- New `handover: card | auto` in `.home-office.yml`. With `auto`, the cut starts the next session by itself unless the next step waits for the user (a gate, a push, a merge, anything under "Blocked"); then it falls back to the card.

## 0.4.0-pre.4 — 2026-10-19
- Session titles: a new UserPromptSubmit hook (`hooks/session_title.py`) titles `/home-office:resume NN` sessions `feat: NN-name` (`· tuning` with `--tuning`) and `/home-office:new <request>` sessions `new: <request>`. In the Claude desktop app, `new` renames the session to `feat: NN-name` or `short: <name>` once the work is named, and hand-over cards use the same `feat: NN-name` title. `HOME_OFFICE_TITLE=0` turns it off.

## 0.4.0-pre.3 — 2026-10-19
- Git commands proposed to the user (commit, merge, push, cleanup) always name the repo with `git -C <absolute repo path>`, so they work from the work folder where the session runs.

## 0.4.0-pre.2 — 2026-10-19
- "Campaigns" are now **batches**: `<work>/batches/NN-name/` with `batch.md` (template renamed from `campaign.md`) and `DECISIONS.md`. Existing work folders: rename `campaigns/` to `batches/` and each `campaign.md` to `batch.md`.

## 0.4.0-pre.1 — 2026-10-19
Pre-release for the pilot; 0.4.0 follows once the pilot batch is reviewed.
- The hand-over card passes the conductor's model to the new session; before, it inherited the model of the session that proposed it (often a top-tier one).
- Links to documents: whenever a step writes or updates a document, the conductor ends its message with clickable Markdown links to it (brief, SPEC, PLAN, TASKS, STATE, REVIEW, DECISIONS). `resume` and `close` link the feature's documents, and `status` links each feature to its `STATE.md`.
- Review findings are saved: the conductor writes the reviewers' findings to `features/NN-name/REVIEW.md` (new template), one dated section per round.
- `HOME_OFFICE_CAP=0` disables the context cap for a session, like `HOME_OFFICE_GUARD=0` and `HOME_OFFICE_GATE=0`.
- Executors can delete files and folders: a TASK lists them under `Delete:` (template `TASKS.md`), the conductor passes them with `ho.py task-start --delete <path>`, and the scope guard allows `rm`, `unlink`, `git rm` and PowerShell `Remove-Item` only when every target is an exact path in that list (a listed folder covers everything under it). The checks gate accepts those deletions as in scope. The short lane can pass `--delete` too, for paths the request names and the user confirms.
- Per-repo `prepare` commands in `.home-office.yml` (e.g. code generators that rebuild client helpers from server routes), passed with `ho.py task-start --prepare "<cmd>"` and run before the checks on every TASK. Files they write never count as changed by the TASK.
- `ho.py task-end --run-checks` runs prepare, the scope check and the checks once when no checks gate ran (delegated tools, tuning sessions).
- The conductor's model becomes the work folder's default for the terminal CLI: `init` writes `"model": "<roles.conductor.model>"` to `.claude/settings.json` next to `.home-office.yml`, `models` keeps it in sync when the conductor changes, and `new` offers it when missing. The Claude desktop app's model picker ignores that file (it remembers its own choice per user), so there the commands tell the user to pick the conductor's model in the picker or run `/model`. Plugins cannot set a session's model themselves.
- Planned session cuts: `new` ends the session after gate 2 (continue with `/home-office:resume NN-name`), and `resume` executes at most `limits.tasks_per_session` TASKs (new limit, default 2) before handing over. The conductor keeps only each report's status line and never rereads the SPEC or PLAN in full.

## 0.3.0 — 2026-10-18
- Document language per project: `language` in `.home-office.yml` now applies to every document the plugin writes (SPEC, PLAN, TASKS, STATE, DECISIONS, brief, board, log, knowledge cards) and to review findings. Sections are found by position, so other commands work in any language. See `core/WORKFLOW.md` § Language.
- `init` asks for the language, proposing the one the user writes in; existing configs without `language` are offered the field.
- New `/home-office:language`: show or change the language, and optionally translate the documents still in use.
- Examples use generic repo names only.

## 0.2.0 — 2026-10-18
- Guards as plugin hooks: scope guard (Edit/Write/Bash), checks gate (SubagentStop) and context cap (UserPromptSubmit, after subagents).
- `scripts/ho.py`: deterministic helper for the conductor (worktree, task-start, task-status, task-end, context).
- Config: per-repo `copy` and `setup` for new worktrees; `guards` for enforceable hard rules.
- Common build and test artifacts (vendor, node_modules, build, caches, __pycache__…) never count as changed by a TASK; `task-start --ignore` adds more.
- `new`, `resume` and `close` use the helper; executors must change files with Edit/Write and report their worktree.

## 0.1.0 — 2026-10-18
- First skeleton: agents (classifier, explorer, architect, backend, frontend, implementer, reviewer, deep-reviewer), commands as skills (init, new, resume, close, status, models, sources), workflow description and templates.
- Not yet: hooks (checks gate, scope guard, context cap) and the Codex adapter.
