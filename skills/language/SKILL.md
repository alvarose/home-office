---
name: language
description: Show or change the language home-office writes this project's documents in (SPEC, PLAN, TASKS, STATE, board, log, knowledge cards). Optionally translates existing documents. Use only when the user invokes /home-office:language.
argument-hint: "[language, e.g. 'es', 'English', 'pt-BR']"
disable-model-invocation: true
---

# /home-office:language

The rules are in "Language" in `${CLAUDE_PLUGIN_ROOT}/core/WORKFLOW.md`.

1. Read `.home-office.yml` in the current working directory (if absent, say so and stop).
2. Without arguments: show the current `language` (or "not set: the language you write in is used") and stop.
3. With an argument: set `language` to it. Edit only that line, keeping comments and order; add the line after `type` if it is missing. Confirm the change in one line: new documents will be written in that language.
4. Offer, once, to translate the existing documents that are still in use: the board, the log, `STATE.md` of the features in flight and the knowledge cards and indexes the plugin created. Approved SPECs, PLANs and finished features stay as they are unless the user names them. Translate only after the user agrees, and only the files they choose. Keep file names, sections and their order, paths, code and identifiers.
