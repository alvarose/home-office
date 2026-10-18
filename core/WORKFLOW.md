# The home-office workflow

Tool-agnostic description of the method. Adapters (Claude Code today, Codex next) implement it with their own mechanisms. Everything project-specific lives in the project's `.home-office.yml` and knowledge sources, never here.

## Principles

1. **Think with a strong model, execute with cheaper ones.** Each role ("department") has its own tool and model, editable per project.
2. **State lives in files, not in conversations.** Sessions are disposable. A new session resumes from `STATE.md`, never from an old conversation.
3. **Minimal context per agent.** Every task says exactly which files it may touch and which knowledge sections it must read.
4. **The human approves, the agents work.** Four gates: SPEC, PLAN + TASKS, diff, commit.

The cost of an agent grows with *number of calls × context size*. Short sessions, minimal context and the right model for each step keep both small.

## Two pieces per project

- **Work** (`docs/work/` in a compact project, a separate repo in a multi-repo project): the board, features, campaigns, log.
- **Knowledge** (`docs/knowledge/` or one or more separate sources): short cards per repo, an `INDEX.md`, architecture, rules.

## Language

Each project chooses the language of the documents home-office writes for it: `language` in `.home-office.yml` (a name or code such as `es`, `en`, `pt-BR`). `init` proposes the language the user writes in; `language` (the command) changes it at any time.

- **Written in `language`**: SPEC, PLAN, TASKS, STATE, DECISIONS, brief, campaigns, board, log, knowledge cards and indexes created by the plugin, and review findings. Headings, header labels and prose are translated from the English templates.
- **Kept as they are**: file names, the sections and their order (other commands find a section by its position in the template, never by its title), paths, commands, branch names, code, identifiers, and the fixed fields agents report to the conductor (`status: done`, `lane: short`…).
- **Messages to the user** follow the language the user writes in.
- **Changing it** affects new writing only. Existing documents are translated only if the user asks.
- If `language` is missing, use the language the user writes in.

The plugin's own files (skills, agents, templates, this document) are always in English.

## Lanes

A classifier decides; the user can override with one word.

- **Short lane**: small fix, small change, question. One implementer subagent, no SPEC or plan. Still goes through review, diff and commit (gates 3 and 4) and leaves one line in `log.md`.
- **Feature lane**: anything that touches more than one repo, changes a contract or schema, or is estimated at more than ~5 files.

## Feature lane

0. **Entry** (`new`): the session opened in the work folder becomes the **conductor** (cheap model). It launches every other role as a subagent and keeps only their summaries.
1. **Explore**: the explorer (cheap model) writes `brief.md`: repos, files, knowledge sections, risks, open questions.
2. **Specify and plan**: the architect (strong model, subagent) writes `SPEC.md` → **gate 1**; then `PLAN.md` (contract between layers, "Crossings" if another in-flight feature touches the same repos) and `TASKS.md` → **gate 2**. **Planned cut**: the session writes `STATE.md` and ends; execution starts in a new session (`resume`).
3. **Execute**: one fresh subagent per TASK, inside the feature's branch/worktree of that repo, in layer order. Only the files listed in the TASK, plus deleting the files in its `Delete:` list. The repo's `prepare` commands (e.g. code generators) run before its checks on every TASK, and the checks must pass. Two attempts at most; then stop and ask. Each session executes at most `tasks_per_session` TASKs, then writes `STATE.md` and hands over to a new one. The conductor keeps only each report's status line and never rereads the SPEC or PLAN in full: subagents read them by path.
4. **Interactive tuning** (optional): the only session opened directly in a repo (browser, emulator, simulator, editor). Max 10 tuning requests or the context cap, then close and reopen.
5. **Review**: reviewer on the diff against the knowledge sources; deep reviewer (strong model) only when the diff touches a risk zone → **gate 3**.
6. **Close** (`close`): `STATE.md`, decisions, board, commit message proposals → **gate 4: the user commits and merges**. Worktrees and branches are cleaned up after the merge.

## STATE.md

Four header lines (status, last session, branches, rework count) and four sections (done, next, blocked/open questions, decisions this session). About 20 lines. It is the only thing `resume` needs to read.

## Limits (defaults, configurable)

- Context cap per session: 150,000 tokens → close and start a new session instead of compacting.
- TASKs per conductor session: 2 → then a planned cut, before the context fills up. The planning session (brief, SPEC, PLAN) also ends at gate 2. Real use shows a conductor's context holds about SPEC + PLAN + two TASKs.
- Tuning: 10 requests per session.
- Attempts per TASK: 2.
- Parallel features: no limit, warning from 4.

## Parallel work

- Branch `feature/NN-name` in every repo the feature touches, each in its own worktree.
- Base branch per project; `close` proposes merges in layer order; the user merges.
- Shared packages (declared in config): with several features in flight, the first one ready publishes; the others update to that version before publishing theirs.
- **Campaigns**: the same kind of change across many repos. Each repo is a feature; the solutions chosen per rule are recorded once in the campaign's `DECISIONS.md` and reused.

## Guards (hooks)

The rules above are enforced, not only requested. They act only inside a worktree with an active task (opened by `scripts/ho.py task-start`, stored in that worktree's private git dir), so normal sessions are never affected.

- **scope guard** (before Edit/Write/Bash): blocks edits outside the TASK's file list, paths forbidden by the project's `guards`, and Bash commands aimed at the worktree that write files or change git state. The one exception: `rm`, `unlink`, `git rm` or `Remove-Item` on exact paths that are all in the TASK's delete list (a listed folder covers everything under it).
- **checks gate** (when an executor finishes): runs the repo's `prepare` commands, compares the files changed since the task started with the list (files written by `prepare` and planned deletions are in scope), and runs the repo's checks. On failure the executor is sent back to fix it, up to `task_attempts` times; then the task is marked `fail` and the conductor escalates. Where no executor gate runs (delegated tools, tuning), `task-end --run-checks` does the same once.
- **context cap** (on each prompt and after each subagent): warns at 80 % of `limits.context_tokens` and, over the cap, tells the session to close and continue in a new one.

All guards are fail-open: an error in a guard never blocks work. `HOME_OFFICE_GUARD=0`, `HOME_OFFICE_GATE=0` and `HOME_OFFICE_CAP=0` disable the scope guard, the checks gate and the context cap for a session (set them before starting it).

## Delegation

A role can be delegated to another CLI tool (e.g. Gemini CLI, Codex). The delegated tool always runs inside the feature worktree; afterwards the conductor checks the diff (only the TASK's files) and the checks with `task-end --run-checks`. Any violation counts as a failed attempt.
