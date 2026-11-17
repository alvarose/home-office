---
name: status
description: Show the state of all home-office work in this project at a glance, grouped by project (one per repo) and stream - features in flight, the gate each one is at, blockers and stalled work. Takes an optional project to show only that one. Reads only small files. Use only when the user invokes /home-office:status.
argument-hint: "[<project>]"
disable-model-invocation: true
model: sonnet
---

# /home-office:status

The argument is a project (a repo key from `repos`; a unique part of the name is enough):

> $ARGUMENTS

1. Read `.home-office.yml` in the current working directory (if absent, say so and stop), then the board. If there is an argument, resolve it against `repos` (ask if ambiguous or unknown).
2. For each feature not marked done, read only the header and the "Next" and "Blocked" sections of its `STATE.md`. Documents may be in the project's `language`: find each section by its position in the template, not by its English title.
3. **Group by project, then by stream.** A feature's project is the `Project:` line of its `STATE.md` (migration: the first repo of its `Branches` line, else "Other"). Under a heading per project (`## <repo>`), one table per stream with the stream's name and its roadmap progress `done / total` (read only the Roadmap section of its `stream.md`), then an "Other" table for the project's features with no stream. Features that only touch the project (it is in their `Branches` but not their `Project:`) go in a "Touches this repo" table, with the driving project named. Each table shows: feature, status / gate, next step, blocked (yes/no), last session, days since. Mark anything idle for more than 3 days. Make each feature's name a link to its `STATE.md` (Markdown link, path relative to the current working directory). Skip projects with nothing in them, but list their names in one line.
   **With a project argument**, show only that project: its features (driving, then touching), its streams, the Backlog of its `projects/<repo>/project.md` (if it exists; read only that section) and the last 5 lines of "Tasks done".
4. Below the table: features in flight vs `limits.parallel_warning`, streams with no feature in progress (say what is next), open batches with their repo progress (from each `batch.md`), and the last 5 lines of the short-lane log (only the project's lines when filtered).
5. **Next commands.** End with a short ordered list of what to run next, one line each, as a command in an inline code span the user can copy, with the reason in a few words. Order:
   1. **Waiting for the user** (anything under "Blocked", or a gate, a push or a merge pending): the exact action. Git commands go as `git -C <absolute repo path> …`, one per line; a decision is named, not a command.
   2. **Ready to continue**: `/home-office:resume NN-name` for each feature in flight that is not blocked, most recently active first.
   3. **Ready to close**: `/home-office:close` (in a `resume` session of that feature) for features whose review (gate 3) is accepted.
   4. **Ready to start**: `/home-office:stream next <stream>` for streams with no feature in progress and a planned row; the next repo of an open batch.
   With a project argument, only commands for that project's work. At most ~8 lines; if there are more, keep the order and say how many were left out. In the Claude desktop app, also offer once to start the first "ready to continue" one as a new session (`mcp__ccd_session__start_session`, `initiation: "own_initiative"`, the same fields as `new` § "Handing over"): a card, nothing runs until the user starts it. It is the only offer: no extra question or button about it (`new` § "Handing over" step 4).

Read nothing else. Suggest only these next commands, never new work.

**A snapshot, not a workplace.** This command runs on Sonnet whatever the session's model. Once it has answered, the session's job is done: if the user goes on to ask for work here (fix this, look into that, watch a server), do not do it in this session; point to the command that fits (`/home-office:resume NN-name`, `/home-office:task "<job>"`, `/home-office:new "<request>"`) and, in the Claude desktop app, offer it as a card as above. Answering a question about the snapshot itself is fine.
