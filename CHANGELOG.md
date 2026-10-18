# Changelog

## Unreleased
- `HOME_OFFICE_CAP=0` disables the context cap for a session, like `HOME_OFFICE_GUARD=0` and `HOME_OFFICE_GATE=0`.

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
