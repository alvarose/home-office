---
name: models
description: Show and change which tool and model each home-office department (role) uses in this project. Use only when the user invokes /home-office:models.
argument-hint: "[role tool/model, e.g. 'architect sonnet' or 'mobile gemini <model>']"
disable-model-invocation: true
---

# /home-office:models

1. Read `.home-office.yml` in the current working directory (if absent, say so and stop).
2. Without arguments: show the `roles` table (role, tool, model, description if any) and stop.
3. With arguments: change only the roles named. Edit only those lines of the file, keeping comments and order.
   - `tool: claude` accepts `haiku`, `sonnet` or `opus`.
   - Any other tool (e.g. `gemini`, `codex`) is a **delegated** role: its model is free text. Check the tool is installed (`<tool> --version`); if not, warn and ask before saving. Remind the user that delegated roles always run inside the feature worktree and are verified by diff and checks afterwards.
   - A new role name creates a project-defined role executed by the generic `implementer`; ask for a one-line description (stack and scope).
4. If `conductor` changed (and its tool is `claude`), also set `"model": "<new model>"` in `.claude/settings.json` next to `.home-office.yml`, changing only that key, so new sessions here start on it. Tell the user it applies from the next session; for this one, `/model <new model>`.
5. Show the resulting table.

Suggestion rule: only if the project's stack is Android/Google-ecosystem (Android, Kotlin, KMP, Flutter/Dart…) and `gemini --version` works, you may suggest Gemini for the mobile role, once. Never change it without confirmation.
