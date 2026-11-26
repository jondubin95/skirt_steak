---
thread: msjc-board-secretary
status: active
created: 2026-11-26T14:22Z
pull_request: 28
supersedes: handoffs/archive/msjc-board-secretary/20261126-1352-msjc-board-secretary.md
private_detail: null
---

# MSJC board secretary

## Objective

Keep pull request 28 reviewable on `feature/msjc-port-revisions`. Jon merges. Do not open another pull request.

## Current State

- Tip is `d4062bf`. Pull request 28 is open. Guardrails on that pull request is green: branch naming and blocking lint both passed.
- `d4062bf` archives done handoff heads and teaches the skill to close a thread when its `pull_request` is merged. `INDEX.md` is the live status. The top of `handoffs/` holds this active head, the index, and the readme.
- `gmail-delayed-send` is `done` because pull request 27 is merged. The fanfic head is archived as a manual `done`. The Fanfic Story Doctor specs live in `python/fanfic_story_doctor/spec/`. v0.4.4 still amends v0.4.3.
- Reconcile on this checkpoint: the only `active` row was this thread, `pull_request: 28`, state `OPEN`. It stays active. The head was about half an hour old.
- Do not pop the stash `board secretary handoff checkpoint` on `feature/close-stale-handoffs`.

## Key Decisions Already Made

- `pull_request` is the only new frontmatter field. The branch name comes back from `gh pr view`.
- A merged pull request marks the thread `done` and moves the head. Age only causes the check.
- Links to other notes are relative to the file that contains them. The three pull request 25 review links now use `../msjc-board-secretary/`.

## Open Questions

- None for the archive rule. Pull request 28 is still waiting on review.

## Constraints and Guardrails

- Branch `feature/msjc-port-revisions`. Pushing updates pull request 28. Do not open another pull request. Do not merge.
- A checkpoint on this branch commits only the handoff files and pushes. It does not stage unrelated files.
- Public notes publish on push.

## Files / Artifacts / Sources

- `.cursor/skills/handoff-notes/SKILL.md`
- `handoffs/README.md`
- `handoffs/INDEX.md`
- Previous head: `handoffs/archive/msjc-board-secretary/20261126-1352-msjc-board-secretary.md`
- Pull request: https://github.com/jondubin95/skirt_steak/pull/28

## Next Best Actions

1. Jon reviews and merges pull request 28. Do not merge from an agent session.
2. The next checkpoint or pickup reconciles `pull_request: 28`. When that pull request is merged, this thread becomes `done` and this head moves under `handoffs/archive/msjc-board-secretary/`.

## Known Risks or Failure Modes

- Section headings are still `HEADING_3` plus an Arial 13pt bold black run, with `spaceAbove` 0 and `spaceBelow` 0. `disc_requests` still sends `BULLET_DISC_CIRCLE_SQUARE`.
- `reauth.py` updates the writer token only. A failed refresh of the drive-readonly token is fixed by moving that token aside and running the revisions CLI again.
- Older archived notes can still say `status: active`. The index is the live status. Do not edit those files to match.

## Prompt to Resume

Continue from `feature/msjc-port-revisions` at `d4062bf` and pull request 28; Jon merges, and pushing updates that pull request. The handoff skill records `pull_request` and archives a head when that pull request is merged. Focus on review comments. Avoid a new pull request, restoring archived heads to the top of `handoffs/`, and editing notes after they move. Validate with `gh pr view 28 --json state` and `gh pr checks 28`.
