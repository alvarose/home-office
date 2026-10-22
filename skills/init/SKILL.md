---
name: init
description: Set up the home-office "office" for a project - creates .home-office.yml, the work folder (board, features, log) and, if the project has none, a knowledge skeleton. Detects multi-repo vs compact projects, stacks, checks and branches. Use only when the user invokes /home-office:init.
disable-model-invocation: true
---

# /home-office:init

Configure home-office for the project in the current working directory. Templates are in `${CLAUDE_PLUGIN_ROOT}/core/templates/`. Ask with short multiple-choice questions; propose sensible defaults; write nothing until the user has confirmed the summary.

## 1. Existing configuration
If `.home-office.yml` exists here, show a summary and ask whether to review it section by section or stop. Never overwrite it silently. If it has no `language`, offer to add it (step 2b).

## 2. Project type
- **multirepo**: the current folder is a dedicated work folder next to several sibling git repos (e.g. `../repo-a`, `../repo-b`). Work lives here; knowledge is one or more separate sources.
- **compact**: the current folder is the main repo. Work goes in `docs/work/`, knowledge in `docs/knowledge/`.
Detect it (sibling `.git` folders vs a single repo) and confirm with the user.

## 2b. Language
Ask in which language home-office should write this project's documents (see "Language" in `${CLAUDE_PLUGIN_ROOT}/core/WORKFLOW.md`). Propose the language the user is writing in as the default, plus English and "other". Save it as `language`. From this point on, ask the remaining questions in the user's language, and write everything this command creates in the chosen language.

## 3. Repos and stacks
List the candidate repos (for compact: this repo plus any the user names). For each, detect the stack from its files — `composer.json`, `package.json`, `build.gradle(.kts)`, `settings.gradle(.kts)`, `*.xcodeproj` / `Package.swift`, `ProjectSettings/` (Unity), `project.godot`, `pubspec.yaml`, `go.mod`, `Cargo.toml`, `pyproject.toml`… — and propose:
- **roles** it hosts (`backend`, `frontend`, or a project-defined role such as `mobile`, `ios`, `game`, with a one-line description);
- **checks**: from its scripts (composer/npm scripts, Gradle tasks, test runners) or from its `AGENTS.md` if it lists them. They must pass before a TASK can close.
- **copy**: untracked files a fresh worktree needs (e.g. `.env`, `local.properties`), if they exist in the repo;
- **setup**: commands to run once in a fresh worktree (e.g. `composer install --no-interaction`, `npm ci`); none for Gradle projects.
- **prepare**: commands to run before the checks of every TASK, when the repo generates code from other code (e.g. client route or API helpers generated from the server's routes, ORM or GraphQL types from a schema); look for generator scripts in its package scripts or docs. Their output must be reproducible; the files they write never count as changed by a TASK. Usually none.
Let the user include or exclude repos.

## 4. Order and rules
Ask for:
- **layers**: the execution order between roles inside a feature (propose one from what you found);
- **base branch** (detect the default branch of each repo; ask if they differ);
- **shared packages**: repos other repos depend on (detect path/VCS dependencies between siblings where possible);
- **risk zones** that trigger the deep review;
- **hard rules** that must never be broken, in words; and, for those that are about paths, the enforceable **guards** (`deny` glob, `except` repos, `reason`) that the hooks will apply;
- **handover**: at a planned cut, should the next session be proposed as a card (`card`, default) or started automatically when nothing waits for the user (`auto`)? Only matters in the Claude desktop app.
- **archive**: should finished sessions (the previous session after a hand-over, the feature's sessions once it is done) be archived after asking once (`ask`, default) or without asking (`auto`)? Only matters in the Claude desktop app. With `auto`, offer to add `"permissions": {"allow": ["mcp__ccd_session_mgmt__archive_session"]}` to the work folder's `.claude/settings.json`, so the desktop app's auto-mode check does not refuse it.
- **commit**: should each TASK that passes its gate be committed on the feature branch after one question per session (`ask`, default) or right away (`auto`)? Merges to the base branch and pushes always stay with the user.
Everything is optional.

## 5. Knowledge sources
- Point to existing documentation (an `AGENTS.md`, `docs/`, a skill folder, a rules repo). Each becomes an entry in `sources`, optionally with an index and a scope.
- If there is no knowledge at all, offer to **create a skeleton**: one card per repo from `knowledge-card.md` (six sections, ~15 KB max) filled with what you can infer, plus `INDEX.md`. The user reviews it afterwards.

## 6. Linters and tools (suggestions only)
- By stack, suggest well-known strictness linters (for TypeScript/JavaScript, for example, anti-slop rules for Oxlint). Never install anything; if the user wants one, add it to that repo's `checks` as a pending item.
- Only if the stack is Android/Google-ecosystem (Android, Kotlin, KMP, Flutter/Dart…) and `gemini --version` works, suggest Gemini for the mobile role. Otherwise do not mention it.

## 7. Write
Show the full summary; on confirmation, create:
- `.home-office.yml` from the template, filled in (defaults for `roles` and `limits`);
- the work folder with `BOARD.md` (or the board name chosen), `log.md`, `features/`, `batches/`, `streams/`, `projects/` (pages are created lazily). Every repo in `repos` is a **project**: tell the user, and that a `project.md` page appears when something is filed under a project;
- the knowledge skeleton, if accepted;
- the conductor's model as this folder's default for the terminal CLI: `"model": "<roles.conductor.model>"` in `.claude/settings.json` next to `.home-office.yml`. Only when `roles.conductor.tool` is `claude`. If the file exists, add or change only that key and keep the rest; if it already has a different `model`, ask first. Subagents are unaffected: each agent sets its own model. Tell the user that in the Claude desktop app the model picker wins over this file (it remembers its own choice per user), so there they choose the conductor's model in the picker, or run `/model <roles.conductor.model>` at the start of the session.
Board, log, cards and indexes are written in `language`: translate the templates' headings and labels, keep their structure.
If the project already has a board, features folder or docs, reuse their names and paths in the config instead of creating new ones.

End with the commands the user will use from now on: `new`, `stream`, `project`, `task`, `resume`, `close`, `status`, `models`, `sources`, `language` — and the rule: sessions are opened in the folder that contains `.home-office.yml`.
