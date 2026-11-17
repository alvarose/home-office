# Changelog

## Unreleased
- **Keeping features small** (new WORKFLOW section). In the pilot, minor fixes grew into features of 16–20 TASKs with several review rounds.
  - Size at gate 1: the SPEC header has two new lines, `Unblocks:` and `Estimate:` (TASKs and sessions, with the limit). The conductor shows both when asking for gate 1; an estimate over the limit adds a "trim or split" decision.
  - New `limits.tasks_per_feature` (default 8). The conductor passes it to the architect, whose plan summary starts with `tasks: n (limit m)` and, over it, a trim or split proposal. The conductor says the number before asking for gate 2; keeping an over-limit PLAN needs the user's explicit word, recorded in `DECISIONS.md`. What is left out goes to the project's backlog.
  - New `limits.review_rounds` (default 1). One round; another only to check fixes of high or medium findings, and it reviews only the fix commits. Low findings are written to `REVIEW.md` plus one line in the project's backlog, and never become TASKs or another round unless the user asks. `new` § "Review → gate 3", `resume`, the short lane, `reviewer` (severity guide, verdict line `high n · medium n · low n · another round: yes|no`), `deep-reviewer` and the `REVIEW.md` template follow it.
  - Classifier: minor fixes (audit or review findings, cleanups, style) go to `short` or the new `lane: task` by default, even across repos or over ~5 files, unless they change a contract or a schema. `new` offers `/home-office:task` for `lane: task`; `task` accepts them.
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
