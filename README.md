# home-office

A tool-agnostic way of working with coding agents.

- **Think with a strong model, execute with cheaper ones.** Every role ("department") has its own tool and model, editable per project.
- **State lives in files, not in conversations.** Sessions are short and disposable; a new one resumes from `STATE.md`.
- **Minimal context per agent.** Each task lists exactly the files it may touch and the knowledge it must read.
- **You approve, agents work.** Four gates: SPEC, PLAN + TASKS, diff, commit.

Why: the cost of an agent grows with *number of calls × context size*. Long sessions re-process huge contexts on every call. Short sessions, minimal context and the right model per step keep both small.

The plugin contains nothing about any particular project. Everything project-specific lives in the project's `.home-office.yml` and its knowledge sources. The full method is in [`core/WORKFLOW.md`](core/WORKFLOW.md).

## Install (Claude Code)

```text
/plugin marketplace add alvarose/home-office
/plugin install home-office@home-office
```

From a local clone: `/plugin marketplace add <path to the clone>`.

## Commands

| Command | What it does |
|---|---|
| `/home-office:init` | Set up the office for a project (once) |
| `/home-office:new "<task>"` | Start new work; a classifier picks the short lane or the feature lane |
| `/home-office:resume [NN]` | Resume a feature in a fresh session from its `STATE.md` (`--tuning` for interactive tuning) |
| `/home-office:close` | Write the handoff, decisions and board; propose commits and merges |
| `/home-office:status` | Features in flight, gates, blockers, stalled work |
| `/home-office:models` | Show or change the tool and model of each department |
| `/home-office:sources` | List, add, edit or remove knowledge sources |
| `/home-office:language [lang]` | Show or change the language of the project's documents |
| `/home-office:task "<job>"` | One self-contained check, cleanup or mechanical change, even across repos; no SPEC or PLAN, ends in the same session |

Open sessions in the folder that contains `.home-office.yml`.

## Requirements

- `git` and Python 3.8+ available as `python3` (the guards and the helper script use only the standard library).
- On Windows, Claude Code runs hook commands in Git Bash.

## Guards

The workflow's rules are enforced by hooks inside active task worktrees: edits outside the TASK's file list or forbidden by the project's `guards` are blocked (deletions only for the files the TASK lists under `Delete:`), an executor cannot finish with failing checks (after the repo's `prepare` commands, e.g. code generators), and sessions are told to close when they reach the context cap. Conductor sessions are also cut on purpose: after the PLAN is approved and after every `limits.tasks_per_session` TASKs (default 2), continuing with `/home-office:resume`. See [`core/WORKFLOW.md`](core/WORKFLOW.md#guards-hooks).

## Language

The plugin itself is written in English. The documents it writes for a project (SPEC, PLAN, TASKS, STATE, board, log, knowledge cards) use that project's `language`: `init` proposes the language you write in, and `/home-office:language` changes it at any time. See [`core/WORKFLOW.md`](core/WORKFLOW.md#language).

## Project types

- **compact**: one main repo. `.home-office.yml` at its root, `docs/work/` and `docs/knowledge/`.
- **multirepo**: a dedicated work folder next to the repos; knowledge in one or more separate sources.

## Roles

| Role | Default model | Does |
|---|---|---|
| conductor (main session) | sonnet | Launches subagents, keeps summaries, runs the gates |
| `classifier` | haiku | Short lane or feature lane |
| `explorer` | haiku | Finds files and knowledge, writes the brief |
| `architect` | opus | SPEC; then PLAN, contract and TASKS |
| `backend`, `frontend` | sonnet | One TASK each, only its files |
| `implementer` | sonnet | Project-defined roles (mobile, ios, game…) and short-lane changes |
| `reviewer` | sonnet | Review against the project's knowledge |
| `deep-reviewer` | opus | Strict audit, only for risk zones |

A role can be delegated to another CLI tool (e.g. Gemini CLI, Codex). Delegated tools always run inside the feature worktree and are verified by diff and checks afterwards.

## License

MIT

## Status

0.3.0 — agents, commands, templates, guards (scope guard, checks gate, context cap) and per-project document language. Not yet included: the Codex adapter.
