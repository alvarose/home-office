# Changelog

## Unreleased

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
