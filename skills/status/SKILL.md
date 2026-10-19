---
name: status
description: Show the state of all home-office work in this project at a glance - features in flight, the gate each one is at, blockers and stalled work. Reads only small files. Use only when the user invokes /home-office:status.
disable-model-invocation: true
---

# /home-office:status

1. Read `.home-office.yml` in the current working directory (if absent, say so and stop), then the board.
2. For each feature not marked done, read only the header and the "Next" and "Blocked" sections of its `STATE.md`. Documents may be in the project's `language`: find each section by its position in the template, not by its English title.
3. Show one table: feature, status / gate, next step, blocked (yes/no), last session, days since. Mark anything idle for more than 3 days. Make each feature's name a link to its `STATE.md` (Markdown link, path relative to the current working directory).
4. Below the table: features in flight vs `limits.parallel_warning`, open campaigns with their repo progress (from each `campaign.md`), and the last 5 lines of the short-lane log.

Read nothing else. Do not suggest work unless something is blocked.
