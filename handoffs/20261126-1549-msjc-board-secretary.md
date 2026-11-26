---
thread: msjc-board-secretary
status: active
created: 2026-11-26T15:49Z
pull_request: 28
supersedes: handoffs/archive/msjc-board-secretary/20261126-1422-msjc-board-secretary.md
private_detail: null
---

# MSJC board secretary

## Objective

Keep pull request 28 reviewable on `feature/msjc-port-revisions`. The seven approved review fixes are in. Jon merges. Do not open another pull request.

## Current State

- Behavior commits are `609a902`, `160ff25`, and `bc59fd2`. Pull request 28 is open. On `bc59fd2`, both Guardrails jobs passed: branch naming and the Sensitive check, and blocking lint and tests.
- An incomplete export exits non-zero. Drive list and get use the client's `num_retries=5`. Export 429s wait five times across six attempts. The token file is replaced from a mode 0600 temporary file. `export --all` plus ids is rejected. The document id is checked before credentials load. The Docs MCP server loads credentials with `interactive=False`.
- Reconcile on this checkpoint: the only `active` row was this thread, `pull_request: 28`, state `OPEN`. It stays active. The previous head was about an hour and a half old.
- Do not pop the stash `board secretary handoff checkpoint` on `feature/close-stale-handoffs`.

## Key Decisions Already Made

- The rejected review items stay out: no page-loop guard, no export-download timeout, no restored schema test, no PR split, no path guards on `--out` or `--token`, no quarantined bad token, no refactors, and no revision-id sanitizing.
- A Drive `HttpError` on one revision is recorded and the export continues. The final 429 still raises, after five waits.
- `pull_request` comes from `gh pr view --json number` on the current branch. A failed `gh pr view` leaves the head active and is reported. It does not archive the head.

## Constraints and Guardrails

- Branch `feature/msjc-port-revisions`. Pushing updates pull request 28. Do not open another pull request. Do not merge.
- A checkpoint on this branch commits only the handoff files and pushes.
- Public notes publish on push. `drive.readonly` can read the whole Drive.

## Files / Artifacts / Sources

- `python/msjc_board_secretary/revisions.py`
- `python/msjc_board_secretary/auth.py`
- `python/msjc_board_secretary/docs_mcp.py`
- `.cursor/skills/handoff-notes/SKILL.md`
- `python/msjc_board_secretary/README.md`
- `README.md`
- Previous head: `handoffs/archive/msjc-board-secretary/20261126-1422-msjc-board-secretary.md`
- Pull request: https://github.com/jondubin95/skirt_steak/pull/28

## Next Best Actions

1. Jon reviews and merges pull request 28. Do not merge from an agent session.
2. The next checkpoint or pickup reconciles `pull_request: 28`. When that pull request is merged, this thread becomes `done` and this head moves under `handoffs/archive/msjc-board-secretary/`.

## Known Risks or Failure Modes

- Section headings are still `HEADING_3` plus an Arial 13pt bold black run, with `spaceAbove` 0 and `spaceBelow` 0. `disc_requests` still sends `BULLET_DISC_CIRCLE_SQUARE`.
- `reauth.py` updates the writer token only. A failed refresh of the drive-readonly token is fixed by moving that token aside and running the revisions CLI again.
- A non-`HttpError` failure during one revision's download still aborts the rest of that export. The sixth 429 is that case.
- Older archived notes can still say `status: active`. The index is the live status. Do not edit those files to match.

## Prompt to Resume

Continue from `feature/msjc-port-revisions` at `bc59fd2` and pull request 28; Jon merges, and pushing updates that pull request. The seven approved review fixes are in, and Guardrails passed on `bc59fd2`. Focus on new review comments. Avoid the rejected items, a new pull request, and editing a handoff after it moves to `archive/`. Validate with `gh pr view 28 --json state` and `gh pr checks 28`.
