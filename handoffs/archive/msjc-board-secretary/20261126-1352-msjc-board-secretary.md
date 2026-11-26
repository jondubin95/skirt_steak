---
thread: msjc-board-secretary
status: active
created: 2026-11-26T13:52Z
pull_request: 28
supersedes: handoffs/archive/msjc-board-secretary/20261119-0030-msjc-board-secretary.md
private_detail: null
---

# MSJC board secretary

## Objective

Keep pull request 28 reviewable on `feature/msjc-port-revisions`. Jon merges. Do not open another pull request.

## Current State

- Tip is `769cc75` on `feature/msjc-port-revisions`, based on `origin/main` at `b54768e`. Pull request: https://github.com/jondubin95/skirt_steak/pull/28
- The branch already had the shared OAuth loader (`c6deaef`) and the read-only Drive revisions CLI (`1c8a2bb`) before this session.
- `deab835` folds the `handoff-notes` description into a YAML block. The plain description contained `Note: "checkpoint"`, and a colon followed by a space made Cursor report Error Parsing. The wording is unchanged. PyYAML loads it as one 261-character string.
- `769cc75` removes `test_november_2026_section_titles_pass` from `python/msjc_board_secretary/tests/test_schema.py`. That test froze one agenda. A year in a title, an apostrophe in a title, and the closing sections stay in the neighboring schema tests and `sample_minutes.json`.
- Local suite after the deletion: `python -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"` ran 90 tests, OK, in 0.767s. The schema file alone is 33 tests.
- Ruff was not installed in the local interpreter (`No module named ruff`) and was not re-run after `769cc75`. Earlier on the branch, `python3 -m ruff check python/msjc_board_secretary` passed with ruff 0.17.2. `ruff.toml` selects E722, S110, BLE001, and N. CI runs that check.
- Preflight passed on this checkout. Guardrails CI had passed on `deab835`. CI for `769cc75` was not confirmed in this session.
- The pull request body names the folded skill description and the dropped November test. The unit-test toggle says 90 tests. The title stays "Add a read-only MSJC revisions CLI and share OAuth loading".
- Working tree was clean after the push. This checkpoint adds the handoff files only.
- Do not pop the stash `board secretary handoff checkpoint` on `feature/close-stale-handoffs`. It is still `stash@{0}`.

## Key Decisions Already Made

- Put the skill-parse fix on pull request 28. The empty `feature/fix-handoff-skill-parse` branch was deleted before any commit.
- Drop only `test_november_2026_section_titles_pass`. Leave the 26 new auth and revisions tests, the `.gitignore` assertion inside `test_defaults_and_drive_readonly_scope`, and the two sample tests that stay green when their checks are deleted.
- Keep the pull request title. The revisions CLI is still the main change.

## Open Questions

- Did Guardrails pass on `769cc75`? It was not checked after the push.
- `test_sample_has_no_absent_speaker` and `test_sample_shape_is_writable` still pass if the checks they name are deleted, because the sample is already valid. Leave them unless Jon wants that cleanup.

## Constraints and Guardrails

- Branch `feature/msjc-port-revisions`. Pushing updates pull request 28. Do not open another pull request. Do not merge.
- Public notes publish on push.
- `builder.py` was not changed in this session. The heading-style and bullet-preset notes in the pull request body still stand.

## Files / Artifacts / Sources

- `.cursor/skills/handoff-notes/SKILL.md`
- `python/msjc_board_secretary/tests/test_schema.py`
- `ruff.toml`
- Previous head: `handoffs/archive/msjc-board-secretary/20261119-0030-msjc-board-secretary.md`
- Pull request: https://github.com/jondubin95/skirt_steak/pull/28

## Next Best Actions

1. Confirm Guardrails on `769cc75`.
2. Jon reviews and merges pull request 28. Do not merge from an agent session.
3. Optional later: the two sample tests that cannot fail if their checks are deleted.

## Known Risks or Failure Modes

- Section headings are still `HEADING_3` plus an Arial 13pt bold black run, with `spaceAbove` 0 and `spaceBelow` 0. `disc_requests` still sends `BULLET_DISC_CIRCLE_SQUARE`.
- `reauth.py` updates the writer token only. A failed refresh of the drive-readonly token is fixed by moving that token aside and running the revisions CLI again.
- Ruff was not re-run locally after the test deletion. The deletion is unlikely to trip E722, S110, BLE001, or N. CI is the check.

## Prompt to Resume

Continue from `feature/msjc-port-revisions` at `769cc75` and pull request 28; Jon merges, and pushing updates that pull request. The handoff skill description is a folded YAML block, and `test_november_2026_section_titles_pass` is gone. Focus on confirming Guardrails for `769cc75` and on review comments. Avoid a new pull request, restoring the November agenda test, and dropping the auth or revisions tests. Validate with `python -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"` (90 tests) and `python -m ruff check python/msjc_board_secretary` once ruff 0.17.2 is available.
