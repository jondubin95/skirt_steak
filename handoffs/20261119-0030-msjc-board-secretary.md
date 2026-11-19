---
thread: msjc-board-secretary
status: active
created: 2026-11-19T00:30Z
supersedes: handoffs/archive/msjc-board-secretary/20261119-0006-msjc-board-secretary.md
private_detail: null
---

# MSJC board secretary

## Objective

Safe consolidation on `feature/board-secretary-friction` for pull request 25. Cleanup only. Jon merges. Do not open another pull request.

## Current State

- Tip before this pass: `0d36a8c`. Validity fixes remain `541b1fa`. This pass edits `python/msjc_board_secretary/builder.py` only.
- `MOTION_PARAGRAPH_STYLE` is the shared `NORMAL_TEXT` / 12pt below / 30pt indent-end dict. `requests_for_replace` and `strip_spilled_bullets` both use it. The field mask `namedStyleType,spaceBelow,indentEnd` stays at both call sites. Request ranges are unchanged.
- Sample replace and a spilled `Motion:` paragraph produce the same style JSON as before the hoist.
- `_RECORDED_VOTE` was not rebuilt. After `541b1fa` the name is gone. `_RECORDED_FAILURE` is `motion fail(s|ed)` and `defeated`. `_RECORDED_PASS` is `motion pass(es|ed)` and `passed unanimously`. Neither pattern repeats `voted down`, `vote failed`, or yea/nay. Those stay only in `_EXPLICIT_VOTE`.
- A single union used as the failure search would earn `not voted down`: the match is the phrase, and that clause has no lack-of-second. `motion_verdict_is_earned("not voted down")` is False today and must stay False. `not motion passed` is the same trap for the pass phrases. The three matchers stay.
- The phrase allow/deny lists in `tests/test_schema.py` and `tests/test_write_tab.py` were not shared. They are not the same table. That cleanup sits under "Tests that do not lock the behavior" in the 23:50 note, not under Safe consolidation. Sharing them would change which strings each test sends.
- Leave-as-is and the risk list in the 23:50 note were not touched. `schema.py` was not edited.
- Validation on 2026-11-19: `python3 -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"` = 65 tests, OK. `python3 -m ruff check python/msjc_board_secretary` with ruff 0.17.2 passed. `tools/workflow_guardrails/preflight.sh` exits 1 because `Sensitive/credentials.json` and `Sensitive/google/` are absent.
- `builder.py` is 7 insertions and 10 deletions versus `0d36a8c`, net −3 lines. No live Google Doc was written.
- Do not pop the stash named `board secretary handoff checkpoint`. It belongs to `feature/close-stale-handoffs`.

## Key Decisions Already Made

- Share the style dict only. The two `updateParagraphStyle` requests keep their own ranges and the same field mask string.
- Do not compile one `_RECORDED_VOTE`. The explicit, failure, and pass patterns are already disjoint, and one pattern would undo the negation and want-of-a-second fixes.
- Verdict direction stays as it was. `Jordan Hale seconds.` still loads with `fails`. `Voted down.` still loads with `passes`.
- `D. Schwartz` stays refused. The risk list stays open.

## Open Questions

- Should a one-letter Roman token stay refused when it is an initial or `I.e.`? The test still says yes.
- Should the schema reject `fails` on a body that was only seconded? Leave it unless Jon wants the tests changed.

## Constraints and Guardrails

- Branch `feature/board-secretary-friction`. Pushing updates pull request 25. Do not open another pull request. Do not merge.
- Do not pop the stash named `board secretary handoff checkpoint`.
- No Docs write from this pass.

## Files / Artifacts / Sources

- Code: `python/msjc_board_secretary/builder.py`
- Review that named the cleanup: `handoffs/archive/pr25-review-duplication-validity/20261118-2350-pr25-review-duplication-validity.md`
- Previous implementation head: `handoffs/archive/msjc-board-secretary/20261119-0006-msjc-board-secretary.md`
- Commands: the unittest and ruff lines in Current State

## Next Best Actions

1. Jon reviews and merges pull request 25. Do not merge from an agent session.
2. A later pass can take the risk list in the 23:50 note. Do not fold those into a drive-by. Do not rebuild one recorded-vote regex.

## Known Risks or Failure Modes

- `MOTION_PARAGRAPH_STYLE` is one dict object, same as `HEADING_TEXT_STYLE`. Mutating it, or a nested `spaceBelow` / `indentEnd` dict, would change both requests. The serialized values match the old literals.
- The field mask is still written twice. A new key on the constant does nothing until both mask strings name it.
- `The chair paused for 30 seconds.` and `The seconded motion passed.` still earn. `yea-sayers` still counts as yea.
- A Roman token in a paragraph or bullet is still not checked. `II . Accept` (space before the period) is still allowed on a replacement.
- `hasn't yet been seconded` is not negated. The gap is only optional `been`.
- `We did not vote. Motion passes.` still earns, because a recorded pass wins over `did not vote`.
- No live Google Doc write has been exercised.

## Prompt to Resume

Continue from `feature/board-secretary-friction` and this handoff; pushing updates pull request 25 and Jon merges. The motion paragraph style is `MOTION_PARAGRAPH_STYLE` in `builder.py`. The ten validity bugs from the 23:50 review stay fixed in `541b1fa`, and the recorded-vote patterns stay three separate regexes. Avoid verdict-direction changes, deleting the single-letter Roman check, merging those vote patterns, the risk list, and a new pull request. Validate with `python3 -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"` and `python3 -m ruff check python/msjc_board_secretary`.
