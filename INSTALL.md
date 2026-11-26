# Installing and starting with home-office

A step-by-step guide for a first-time user. The method itself is in [`core/WORKFLOW.md`](core/WORKFLOW.md); the commands are listed in the [README](README.md#commands).

## 1. Before you start

- [Claude Code](https://claude.com/claude-code) (terminal, desktop app or IDE extension).
- `git`.
- Python 3.8 or newer, callable as `python3`. The hooks and `scripts/ho.py` use only the standard library.
- On Windows: Git for Windows. Claude Code runs hook commands in Git Bash, so `python3` must work there (`python3 --version` in Git Bash). If it only answers to `python`, add an alias or a `python3` shim to your `PATH`.

## 2. Install the plugin

From GitHub, inside Claude Code:

```text
/plugin marketplace add alvarose/home-office
/plugin install home-office@home-office
```

Or from a local clone (useful if you want to read or change the plugin):

```text
git clone https://github.com/alvarose/home-office.git
/plugin marketplace add <path to the clone>
/plugin install home-office@home-office
```

Restart Claude Code (or start a new session) so the hooks and skills load. Check with `/plugin`: `home-office` should be listed as enabled, and typing `/home-office:` should offer the commands.

## 3. Set up a project

Open Claude Code in the right folder and run `/home-office:init`:

- **One main repo** (compact): open it at the repo's root. `init` writes `.home-office.yml` there, plus `docs/work/` (board, features, log) and `docs/knowledge/`.
- **Several repos** (multirepo): create an empty work folder next to them (e.g. `../my-project-work`, a git repo of its own) and open it there. `init` finds the sibling repos.

`init` asks short questions and writes nothing until you confirm the summary: the documents' language, the repos and their stack, the checks each repo must pass, setup commands for fresh worktrees, base branches, risk zones and hard rules. Accept the defaults you are unsure about; everything can be changed later in `.home-office.yml` (the template, with comments, is [`core/templates/home-office.yml`](core/templates/home-office.yml)).

Commit `.home-office.yml` and the work folder: they are the project's memory between sessions.

## 4. First piece of work

```text
/home-office:new "add an export button to the orders list"
```

A classifier decides the lane:

- **Short lane**: a small change is made right away, with the repo's checks.
- **Feature lane**: explore → **SPEC** (gate 1, you approve) → **PLAN + TASKS** (gate 2) → executors, one TASK each, in a git worktree of their own → review (gate 3) → commit (gate 4). Each gate waits for you.

For a check, a cleanup or a mechanical change across repos, with no design: `/home-office:task "…"`.

Feature sessions are short on purpose. When one is cut (after the PLAN, after a few TASKs or near the context cap) it proposes the next session; elsewhere, continue with `/home-office:resume NN`. Everything needed is in the feature's `STATE.md`, never in the old conversation.

## 5. Day to day

| You want to… | Run |
|---|---|
| See what waits for you, features in flight, blockers | `/home-office:status` |
| Continue a feature | `/home-office:resume [NN]` |
| Close a feature or session (hand-over, board, commits to propose) | `/home-office:close` (a finished feature also offers it in one click) |
| Change the model or tool of a role | `/home-office:models` |
| Add or edit knowledge sources | `/home-office:sources` |
| Change the documents' language | `/home-office:language` |

home-office never merges or pushes on its own: it proposes, you do it (or tell it to).

## 6. Updating

```text
/plugin marketplace update home-office
/plugin update home-office@home-office
```

From a local clone, `git pull` in the clone first. Restart the session afterwards; open sessions keep the old version. Changes are listed in [`CHANGELOG.md`](CHANGELOG.md).

## 7. If something goes wrong

- **Hooks do nothing or fail with "python3: not found"**: Python is not reachable as `python3` from the shell Claude Code uses (Git Bash on Windows). See section 1.
- **An edit is blocked "outside the TASK's files"**: that is the scope guard. The executor may only touch the files its TASK lists; change the TASK (or the PLAN) instead of forcing it.
- **A TASK cannot finish**: the checks gate found failing checks. The reason is in the result's `problems`; fix them or ask the conductor to replan.
- **"Session over the context cap"**: close and resume in a fresh session, as proposed. Nothing is lost: state lives in files.
- **Too heavy to load**: `python3 <plugin>/scripts/ho.py weight` lists the files over the limits and how to compact them.
