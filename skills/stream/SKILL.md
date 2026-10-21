---
name: stream
description: Manage streams - long-running lines of work made of different features in sequence (e.g. "build the mobile app"), run in parallel with other streams in one office. Lists streams, creates one with a drafted roadmap, or starts the next planned feature. Use only when the user invokes /home-office:stream.
argument-hint: '[new "<goal>" [--project <repo>] | next <stream>]'
disable-model-invocation: true
---

# /home-office:stream

A **stream** is a long-running goal made of different features in sequence (scaffold, login, list screen…). It shares the project's config, repos, rules and knowledge, and has its own roadmap and shared decisions. A stream belongs to one **project** (a repo; see `project`). A **batch** is different: the same change across many repos. Both live in the work folder (`streams/` and `batches/`).

The arguments are:

> $ARGUMENTS

Preconditions: follow `new` § 0 (`${CLAUDE_PLUGIN_ROOT}/skills/new/SKILL.md`): config in the current working directory, board, language (documents are written in `language`). Apply its "Links to documents" too.

## No arguments: list

Read each `streams/*/stream.md` (Goal and Roadmap only). Show one table: stream (link to its `stream.md`), project, goal, roadmap progress `done / total`, the feature in progress (if any) and the next planned one. If there are none, say so and show `/home-office:stream new "<goal>"`.

## `new "<goal>"`

1. **Ask** (short questions, in the user's language) for what is missing: the goal if the argument is empty, the project (`--project <repo>`, a key of `repos`; propose the main repo it touches), and the repos it touches with their roles (propose from `repos`; a repo that does not exist yet is allowed, say so in Scope).
2. **Number and folder.** `NN` is the next free number in `<work>/streams/` (two digits); name `NN-<short name from the goal>`. Do not write anything yet.
3. **Draft.** Launch `architect` (`roles.architect`) in mode `roadmap` with: the goal, the project (written to the `Project:` line), repos and roles, `hard_rules` and `layers`, the knowledge index paths of the sources that apply, the `stream.md` template path, `language`, and the destination `streams/NN-name/stream.md`. Show the user the roadmap (ordered features with their one-line outcomes) and the shared decisions.
4. **Approve.** Wait for explicit approval. If the user changes something, relaunch the architect with the changes. The architect writes only `stream.md`.
5. **Write.** Create `streams/NN-name/` with the approved `stream.md` (add `DECISIONS.md` from the template only if the shared decisions are too long for `stream.md`). Add a `### streams/NN-name` heading to the board under the project's `## <repo>` section if it has none (create the section if missing), and create the project's `project.md` from its template if missing. Link the files and offer `/home-office:stream next NN-name`.
6. **Sidebar group** (Claude desktop app): move this session into the project's group, see `project` § "Sidebar group".

## `next <stream>`

`<stream>` is `NN`, `NN-name` or a unique part of the name; ask if it is ambiguous or missing.

1. Read only `stream.md`. If a roadmap row is `in progress`, say which feature and offer `/home-office:resume <that feature>` instead; start another only if the user insists (features of a stream can overlap when they touch different repos).
2. Take the first `planned` row. Say in one line which one, and go on.
3. Run the **same flow as `/home-office:new`** (`${CLAUDE_PLUGIN_ROOT}/skills/new/SKILL.md`, feature lane) with the roadmap row's outcome as the request and the stream linked. `new` § "Set up" step 3 does the linking: `Stream:` line in `STATE.md`, roadmap row `in progress` with its link, the board under the project and stream, `stream.md` passed to the explorer and architect, and the project's sidebar group. The feature's `Project:` is the stream's. Skip the classifier: it is a feature.

## Sidebar group

Streams have no sidebar group of their own: their sessions, hand-overs included, go to their project's group (`<office> · <repo>`). See `project` § "Sidebar group" (`${CLAUDE_PLUGIN_ROOT}/skills/project/SKILL.md`). Without the desktop tools (CLI), skip it. A failure there never blocks the work: say it in one line.
