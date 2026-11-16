---
thread: msjc-board-secretary
status: active
created: 2026-11-16T16:20Z
supersedes: handoffs/archive/msjc-board-secretary/20261030-1116-msjc-board-secretary.md
private_detail: Sensitive/handoffs/20261116-1620-msjc-board-secretary.md
---

# MSJC board secretary

## Objective

Land the workflow pull request. Leave the November minutes as they are until a result line is requested.

## Current State

- Pull request 25 is open and unmerged: https://github.com/jondubin95/skirt_steak/pull/25
- Branch `feature/board-secretary-friction` is pushed. It has the skill procedure, the absent-speaker refusal, the local Docs server setup script, and the placeholder and closing-shape refusals.
- Local unit tests: 39 passed. Ruff was not run. The new checks were not exercised against a live Google Doc. Stubbing the shape check made the three refusal tests fail.
- The November Minutes tab has been written and then edited by hand. The Notes tab was not edited. The live Minutes tab is the source of truth. see private detail: Sensitive/handoffs/20261116-1620-msjc-board-secretary.md
- One seconded motion still has no recorded result. Two motions name a mover and neither a seconder nor a result. One hand-added result line has no period.
- `feature/close-stale-handoffs` is a separate branch. A git stash named `board secretary handoff checkpoint` holds an INDEX edit for that branch. Do not pop it here. It does not contain the November note.

## Key Decisions Already Made

- The writer refuses an absent speaker and a bad minutes shape before it loads credentials. It does not read the meeting notes.
- A named motion the notes leave unfinished, with no seconder and no vote, is recorded as fails. A seconded motion with no recorded result has no verdict.
- Keep prefilled attendance and a presenter line the notes do not repeat. Drop blank `___` motions. Drop a prefilled section the notes never discuss.
- `.cursor/mcp.json` stays untracked. `setup_local_mcp.py` writes it on each machine.
- Bullet merging stays the existing skill sentence.

## Open Questions

- Whether to add a result only to the remaining seconded motion.
- Whether the period-less result line should gain a period. A full rewrite would add the period used on the other result lines.

## Constraints and Guardrails

- Do not edit the Notes tab. Do not anonymize the executive session.
- Do not write an older JSON over hand edits. Re-read the live Minutes tab before any structural write.
- Do not commit `Sensitive/` or an `mcp.json` that launches the local server.
- Do not merge pull request 25.

## Next Best Actions

- Wait for review of pull request 25.
- If asked, add a result only to the remaining seconded motion, after re-reading the live tab.
- On a machine without the local pointer, run `python python/msjc_board_secretary/setup_local_mcp.py`, then enable that server in Cursor if it shows up disabled.

## Known Risks or Failure Modes

- The writer cannot tell whether a prefilled presenter or attendance block was dropped, because it never sees the notes.
- `test_sample_shape_is_writable` stays green if the shape check is removed. The refusal tests are the ones that catch that.

## Prompt to Resume

Continue from pull request 25 and the live Minutes tab named in the private detail. Focus on review of that pull request, and on a result line only if one is requested. Avoid rewriting from Notes or from an older draft, and avoid popping the handoff stash onto this branch. Validate a minutes write by re-reading the Minutes tab first. Leave the Notes tab untouched.
