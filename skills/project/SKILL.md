---
name: project
description: Manage projects - the logical grouping of home-office work, one per repo. Lists projects with counts, shows or creates a project's page (backlog, shared decisions, tasks done), or adds a backlog idea. Use only when the user invokes /home-office:project.
argument-hint: '[<repo> [add "<idea>"]]'
disable-model-invocation: true
---

# /home-office:project

A **project** is a logical grouping, one per repo: every repo in `repos` is a project, named by its repo key. Nothing moves on disk; each feature, stream and task says which project it belongs to (`Project:` line, log lines). See "Projects" in `${CLAUDE_PLUGIN_ROOT}/core/WORKFLOW.md`. The optional page of a project is `<work>/projects/<repo>/project.md` (template `project.md`).

The arguments are:

> $ARGUMENTS

Preconditions: follow `new` § 0 (`${CLAUDE_PLUGIN_ROOT}/skills/new/SKILL.md`): config in the current working directory, language (pages are written in `language`). Apply its "Links to documents" too. `<repo>` is a key of `repos` (a unique part of the name is enough; ask if ambiguous or unknown).

## No arguments: list

One table, a row per repo in `repos`: project (link to its `project.md` if it exists), features in flight (driving, from the `Project:` line of each `STATE.md` not marked done; features without it count as the first repo of their `Branches` line), features that only touch it, streams (from each `stream.md`'s `Project:` line), tasks (lines in the log). Read only headers and the board. End with `/home-office:project <repo>` and `/home-office:status <repo>`.

## `<repo>`: show

If `projects/<repo>/project.md` exists, show it (summary of each section and a link). If not, say so and ask once whether to create it from the template: "what it is" from the repo's knowledge card if there is one, backlog seeded from planned roadmap rows of its streams, "Tasks done" from its log lines. Write nothing before the user says yes.

## `<repo> add "<idea>"`: backlog

Append one line to the page's Backlog (`- <idea>`), creating the page first if missing (no question needed: the user is filing something). Link it to a feature or stream if the idea names one. Confirm in one line, with the link.

## Sidebar group

Claude desktop app only. If `mcp__ccd_sidebar__create_group` and `mcp__ccd_sidebar__move_sessions` exist (they may be deferred: load them with ToolSearch `select:mcp__ccd_sidebar__create_group,mcp__ccd_sidebar__move_sessions,mcp__ccd_sidebar__list_groups`), keep one sidebar group per project named `<office> · <repo>`:
- `<office>`: the work folder's name without a trailing `-work` (for a compact project, the repo folder's name); `<repo>`: the project's repo key.
- Check `list_groups` first; create the group only if none has that name.
- Move this session into it (`session_id: "self"`) when it works on a feature, task or stream of that project — **unless it is a side session nested under another one** (it has a `parentSessionId` and is not a hand-over of the same feature): leave it nested —, and, in the same way, any session of the project's features you start (hand-over sessions: `core/EXECUTE.md` § "Handing over"; `resume`). Stream sessions use their project's group.
- **Hand-overs at the top level.** A session that continues a feature after a planned cut (a hand-over, started or from a card the user clicked) is nested under the previous one in the sidebar; it should not be. Detach it first, then move it: the new session detaches itself with `mcp__ccd_session_mgmt__detach_session` (`session_id: "self"`; `resume` does this at the start), and a session that starts another with `start_session` detaches it right away (its id from the result). Detaching also means archiving the old session can never archive the new one. If the app refuses (e.g. the user moved it by hand), leave it as it is. Sessions started for parallel work next to a feature (side jobs) are the opposite: they stay nested under the session that started them.
- Without these tools (CLI), skip it. A failure here never blocks the work: say it in one line.

## Archiving sessions

`resume`, `close` and `task` archive finished sessions (`archive: ask | auto`). In the Claude desktop app's auto mode, a permission check may refuse `mcp__ccd_session_mgmt__archive_session` even with `archive: auto`, because it wants the user's explicit OK for that session. When a call is refused:
1. Ask the user once in chat, naming the sessions by title (e.g. "Archive `feat: NN-name #3` and `#4`?"). Their yes is that explicit OK; then archive them.
2. If it is refused again, or the user says no, list the titles so the user can archive them from the sidebar, and go on. Never retry in a loop.

To skip the question for good, the user can allow the tool in the work folder's `.claude/settings.json` (`"permissions": {"allow": ["mcp__ccd_session_mgmt__archive_session"]}`); offer it once if archiving keeps being refused.
