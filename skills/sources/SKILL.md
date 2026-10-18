---
name: sources
description: List, add, edit or remove the knowledge sources home-office agents read in this project (project knowledge, shared rules…). All sources are optional. Use only when the user invokes /home-office:sources.
argument-hint: "[add|edit|remove <name> ...]"
disable-model-invocation: true
---

# /home-office:sources

1. Read `.home-office.yml` in the current working directory (if absent, say so and stop).
2. Without arguments: list `sources` (name, path, index, scope) and whether each path exists and has its index.
3. `add`: ask for name, path (relative to the config, or absolute) and, optionally, the index file and a scope (e.g. `laravel`, `android`: which repos or roles it applies to). Verify the path exists. If there is no index, offer to create one from the `INDEX.md` template by listing the source's files and headings — only after the user agrees. Write it in the project's `language`.
4. `edit` / `remove`: change or delete only that entry, keeping comments and order. Removing a source never deletes its files.
5. Show the resulting list.

Agents read a source only through its index and only the sections a TASK lists. A source with `scope` is passed only to the roles or repos in that scope.
