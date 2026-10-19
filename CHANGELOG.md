# Changelog

## Unreleased
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
