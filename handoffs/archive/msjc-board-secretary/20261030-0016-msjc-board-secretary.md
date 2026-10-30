---
thread: msjc-board-secretary
status: active
created: 2026-10-30T00:16Z
supersedes: handoffs/archive/msjc-board-secretary/20261006-1244-msjc-board-secretary.md
private_detail: Sensitive/handoffs/20261030-0016-msjc-board-secretary.md
---

# MSJC board secretary

## Objective

Fold one monthly Notes tab into the Minutes tab, then stop later wording fixes from rebuilding that tab.

## Current State

- The minutes fold-in for this month is in the existing minutes doc. The executive-session tab was not folded in. see private detail: Sensitive/handoffs/20261030-0016-msjc-board-secretary.md
- The user corrected names, a program label, and a few sentences after the write. Those preferences are in `.cursor/skills/msjc-board-secretary/SKILL.md`. Unresolved wording the user did not correct stays as written. see private detail: Sensitive/handoffs/20261030-0016-msjc-board-secretary.md
- A dead local token was replaced by the new `python/msjc_board_secretary/reauth.py` flow. Do not print credentials.
- Branch `feature/msjc-minutes-skills` has uncommitted edits: the skill, `write_tab.py` (one-phrase `--replace` plus a clearer refresh failure), `reauth.py`, the writer README, and `test_write_tab.py`. No commit or PR yet.

## Constraints and Guardrails

- Do not commit `Sensitive/`. Do not paste minutes into git.
- Do not redraft from Notes for a wording fix, and do not rebuild the Minutes tab unless paragraphs are added, removed, or reordered. Use `write_tab.py --replace` for one exact phrase that occurs once on the output tab.
- A structural rewrite must re-read the live Minutes tab first so hand edits are not overwritten.
- The guarded writer is the only Docs write path.

## Next Best Actions

- Commit the tracked skill and writer files only if the user asks, on this feature branch.
- For another wording fix, use `--replace` and confirm a single match on the Minutes tab.

## Prompt to Resume

Continue from the minutes already written on the Minutes tab. see private detail: Sensitive/handoffs/20261030-0016-msjc-board-secretary.md Focus on a one-phrase `--replace`, or a commit of the uncommitted skill and writer files if asked. Avoid rebuilding the Minutes tab from Notes and avoid the executive-session tab. Validate a replace by a single match on the output tab, and validate a commit with `git status` so `Sensitive/` stays untracked.
