---
thread: msjc-board-secretary
status: active
created: 2026-11-18T15:42Z
supersedes: handoffs/archive/msjc-board-secretary/20261118-1529-msjc-board-secretary.md
private_detail: null
---

# MSJC board secretary

## Objective

The round-3 review on pull request 25 is implemented. Jon merges. Do not open another pull request.

## Current State

- Pull request 25 is open: https://github.com/jondubin95/skirt_steak/pull/25
- Branch `feature/board-secretary-friction`. This checkpoint is the head. The code commits under it are `b440519` through `1bac838`.
- `passes` and `fails` both require a seconder or a recorded vote. A lack-of-second phrase, including "seconded", "never seconded", "without a second", and "lack of a second", is not a vote. Yeas, nays, "voted down", and "vote failed" still earn a verdict when that phrase is present.
- A replacement refuses a Roman marker only at the start of the phrase, including a leading `(` or `[`. `See II. above` is allowed. Section titles still refuse a Roman token anywhere, including after a bracket. Lowercase `iv.` is title text.
- A closing section whose only paragraph strips to `None.` but is not exactly `None.` is an error. The marker match stays exact.
- Absence labels ignore trailing punctuation. Name boundaries include letters, digits, and hyphens, so `Ann` does not match `Jo-Ann`, `key2Ann`, or `JoséAnn`. Speaking verbs include shared, added, offered, thanked, agreed, and confirmed. `, who <verb>` counts. A comma without `who` does not. A possessive is not a speaking credit.
- Deleted archive checkpoints `20261118-1502` and `20261118-1512`. `20261118-1515` now supersedes `20261116-1620`.
- Validation on 2026-11-18: `python3 -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"` = 63 tests, OK. `python3 -m ruff check python/msjc_board_secretary` passed. No live Google Doc was written.
- `tools/workflow_guardrails/preflight.sh` still exits 1 on this machine because the Docs client file and token directory are absent. That is the Docs sync preflight.
- Do not pop the stash named `board secretary handoff checkpoint`. It belongs to `feature/close-stale-handoffs`.

## Key Decisions Already Made

- `fails` is only for a motion the notes record as voted down. An unseconded or unvoted motion has no verdict.
- Step 7 stops unless the request named both the exact document title and the exact output tab. `--confirmed-document-title` and `--confirmed-output-tab` are whatever the caller passes. Nothing binds those flags to a human's message except the skill text and review.
- Do not implement native Google Docs code blocks or horizontal rules. Do not build tooling to accept or reject Docs suggestions.
- `perform_replace` still rejects two equal strings for a direct caller. The CLI already rejects that pair.
- Blank document and tab titles do not count as confirmation, including for a direct caller.
- `find_tab` matches case and whitespace loosely. `validate_target_identity` is exact, so a wrong-case `--output-tab` is found and then refused.
- `test_sample_shape_is_writable` and `test_sample_has_no_absent_speaker` stay green if those checks are deleted. The refusal tests are the coverage.

## Next Best Actions

1. Jon reviews and merges pull request 25. Do not merge from an agent session.
2. No further code from the round-3 list. A live Docs write is still untested on a machine that has the client file and token.

## Known Risks or Failure Modes

- `motion_verdict_is_earned` is a phrase check. A voted-down line that uses none of the recognized words is refused.
- A comma that is not `, who <verb>` does not credit the name. `Taylor Morgan, the treasurer, said` is allowed.
- No live Google Doc write has been exercised. The credential path is untested end to end.

## Prompt to Resume

Continue from `feature/board-secretary-friction` and this handoff; pushing updates pull request 25 and Jon merges. The round-3 verdict, heading, absence, and consolidation items are done, so do not reopen them without a new failing case. Keep `fails` only for voted-down motions, keep the step-7 stop unless both exact titles were named, and avoid Docs code blocks, horizontal rules, suggestion tooling, and a new pull request. Validate with `python3 -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"` and `python3 -m ruff check python/msjc_board_secretary`.
