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
| `/home-office:close` | Write the handoff, decisions and board; propose commits and merges. With `close: card` (default) a feature session proposes it as a one-click button once nothing is left to do (`ho.py close-ready`) and runs it on your yes |
| `/home-office:status` | Waiting-for-you block first (by kind, with age and the exact action; answer several at once), then features in flight, gates, blockers, stalled work |
| `/home-office:models` | Show or change the tool and model of each department |
| `/home-office:sources` | List, add, edit or remove knowledge sources |
| `/home-office:language [lang]` | Show or change the language of the project's documents |
| `/home-office:stream [new "<goal>" \| next <stream>]` | Streams: parallel long-running lines of work (e.g. a new app) made of features in sequence; list them, create one with a roadmap, or start its next feature |
| `/home-office:project [<repo> [add "<idea>"]]` | Projects (one per repo): list them with counts, show a project page, or add a backlog idea; `new`, `task` and `stream new` take `--project <repo>`, `status <repo>` filters by it |
| `/home-office:task "<job>"` | One self-contained check, cleanup or mechanical change, even across repos; no SPEC or PLAN, ends in the same session. Long jobs (a watcher, a server) run as one step per session with a hand-over note in `jobs/<name>.md` |

Open sessions in the folder that contains `.home-office.yml`.

Everything that waits on you (decisions, pushes, merges, staging checks) is kept in `<work>/waiting.md` with timestamps, and work goes on with whatever does not depend on it; see ["Waits"](core/WORKFLOW.md#waits). `ho.py waiting stats` measures it.

Parallel features in the same repo claim their files (`ho.py claims`), edit each hotspot (`hotspots` in the config) one feature at a time, and merge the base into their branch early (`ho.py sync`); see ["Parallel features"](core/WORKFLOW.md#parallel-features).

The harness stays light: `ho.py weight` measures what sessions load, `close` moves old log and inbox rows to `<work>/archive/` and keeps the board to what is live, and mature repos (`ho.py maturity`) send more work to the short lane; see ["Harness weight"](core/WORKFLOW.md#harness-weight).

## Requirements

- `git` and Python 3.8+ available as `python3` (the guards and the helper script use only the standard library).
- On Windows, Claude Code runs hook commands in Git Bash.

## Guards

The workflow's rules are enforced by hooks inside active task worktrees: edits outside the TASK's file list or forbidden by the project's `guards` are blocked (deletions only for the files the TASK lists under `Delete:`), an executor cannot finish with failing checks (after the repo's `prepare` commands, e.g. code generators), and sessions are told to close when they reach the context cap and warned once when they run on an older model generation than the current one. Every session the plugin starts passes its `model` explicitly (`ho.py models`), so none inherits an old one. Conductor sessions are also cut on purpose: after the PLAN is approved and after every `limits.tasks_per_session` TASKs (default 2), continuing with `/home-office:resume`. See [`core/WORKFLOW.md`](core/WORKFLOW.md#guards-hooks).

## Keeping features small

- The SPEC says what the feature unblocks and how many TASKs and sessions it should take, so you see its size at gate 1.
- `limits.tasks_per_feature` (default 8): a PLAN over it comes with a proposal to trim or split, and you are told the number before gate 2.
- `limits.review_rounds` (default 1): one review round; another only to check fixes of high or medium findings. Low findings go to `REVIEW.md` and the project's backlog, never to new TASKs unless you ask.
- Minor fixes (audit findings, cleanups, style) go to the short lane or `/home-office:task`, not to a feature, unless they change a contract or a schema.

See [`core/WORKFLOW.md`](core/WORKFLOW.md#keeping-features-small).

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
