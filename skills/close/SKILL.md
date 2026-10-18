---
name: close
description: Close a home-office session or feature. Writes the STATE.md handoff, decisions and board, proposes commits and merges (the user does them), cleans up worktrees after merge and flags knowledge to promote. Use only when the user invokes /home-office:close.
disable-model-invocation: true
---

# /home-office:close

Leave everything so that a fresh session can continue from files alone. Then the session ends.

Write STATE, DECISIONS, board and log in the project's `language` (see "Language" in `${CLAUDE_PLUGIN_ROOT}/core/WORKFLOW.md`), keeping the templates' sections and their order.

1. Identify the feature this session worked on (or the short-lane change). If a task is still open in any of its worktrees (`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ho.py" task-status --worktree <wt>` → `active: true`), close it with `task-end` and record the result.
2. **STATE.md**: rewrite it from the template. Four header lines (status, last session = today + role, branches, rework count) and four sections (done, next, blocked/open questions, decisions this session). About 20 lines. Be concrete in "Next": the exact TASK or step.
3. **DECISIONS.md** of the feature: add the decisions taken in this session. If it belongs to a campaign, add rule-level decisions to the campaign's `DECISIONS.md` too.
4. **Board**: update the feature's row (phase/gate, date, next step).
5. **Commits** → gate 4: for each repo with changes, show `git -C <path> diff --stat` and propose a commit message. The user commits. Never commit, push or merge yourself.
6. **Feature finished?** Propose merging `feature/NN-name` into `base_branch` repo by repo, in `layers` order, and mention any shared package that must be published first (see "Shared packages" in the PLAN). The user merges. When the user confirms the merges, offer to remove the worktrees (`git -C <repo> worktree remove <path>`) and delete the branches; deleting needs the user's permission. Mark the feature "done" on the board.
7. **Knowledge**: list what should be promoted to a knowledge source (new rules, architecture changes) so the user can add it. If any file listed in `generated_from` changed, warn that the generated files inside the repos must be regenerated.
8. **Short lane**: make sure its line is in the log.
9. End with: "Session closed. Continue with `/home-office:resume NN-name` in a new session."
