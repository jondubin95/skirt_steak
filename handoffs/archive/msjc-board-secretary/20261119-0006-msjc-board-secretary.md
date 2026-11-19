---
thread: msjc-board-secretary
status: active
created: 2026-11-19T00:06Z
supersedes: handoffs/archive/msjc-board-secretary/20261118-1542-msjc-board-secretary.md
private_detail: null
---

# MSJC board secretary

## Objective

The ten internal-validity bugs from the 23:50 review are fixed on `feature/board-secretary-friction`. Jon merges pull request 25. Do not open another pull request.

## Current State

- Pull request 25 is open: https://github.com/jondubin95/skirt_steak/pull/25
- Fix commit `541b1fa`. This checkpoint is the head. The 23:50 review note is archived under `pr25-review-duplication-validity` and that thread is done.
- Verdicts are clause-scoped. The last seconder hit counts only when its own clause does not negate it (`not` / `never` / `n't` / `no one` / `nobody`, including `hasn't been seconded`, and `seconded by no one` / `nobody`). `did not vote`, `didn't vote`, `no vote`, and `not voted` block a seconder. They do not block an explicit vote or a recorded pass.
- `motion failed` / `motion fails` / `defeated` earn only when that clause does not say the motion died for lack of a second (`without a second`, `lack of a second`, `lack of the second`, `want of a second`, `receive a second`, `get a second`). `motion passes` / `motion passed` and `passed unanimously` earn. Bare `passed` does not. `not` / `never` / `n't` immediately before `voted down`, `vote failed`, or a pass phrase is not that vote.
- A name match is not a credit when it is only part of a longer name. Apostrophe is a name character. A preceding name token counts, including lowercase `alex Rivera`, except a function word or a speaking verb (`by`, `said`). `, Jr.` / `, Sr.` / `, III` / `, II` / `, IV` are continuations, checked before `Presented by`. `notes` / `reports` / `moves` followed by `was` or `were` are nouns. `noted` / `reported` / `moved` stay verbs.
- A replacement Roman marker is judged after leading whitespace and Unicode format characters are stripped (space, tab, newline, NBSP, zero-width space, BOM), then the start pattern, including a bracket. `See II. above` stays allowed. `D. Schwartz` stays blocked.
- Any closing paragraph whose stripped text is `None.` is the marker. The only legal form is one paragraph whose text is exactly `None.`. `none.` stays ordinary text.
- `schemaVersion` and bullet `level` must be `type(...) is int`. `true`, `false`, and `1.0` are refused.
- Validation on 2026-11-19: `python3 -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"` = 65 tests, OK. `python3 -m ruff check python/msjc_board_secretary` with ruff 0.17.2 passed. No live Google Doc was written.
- `tools/workflow_guardrails/preflight.sh` exits 1 because `Sensitive/credentials.json` and `Sensitive/google/` are absent. That is the Docs sync preflight.
- Do not pop the stash named `board secretary handoff checkpoint`. It belongs to `feature/close-stale-handoffs`.

## Key Decisions Already Made

- Verdict direction stays as it was. `Jordan Hale seconds.` still loads with `fails`. `Voted down.` still loads with `passes`. Changing that means changing `test_verdict_requires_a_seconder_or_a_recorded_vote`.
- The two vote patterns stay separate. A lack-of-second phrase must not cancel yea/nay or `voted down`.
- `alex Rivera` needed a case-insensitive preceding token. Capital-only lookback misses it. Function words and speaking verbs are excluded so `Presented by Alex Rivera` and `said Taylor Morgan moved` still credit.
- `passed unanimously` is the recorded-pass phrase that is not `motion passed`. Bare `passed` stays out.
- `, II` and `, IV` use the same continuation as `, Jr.` / `, Sr.` / `, III`.
- Safe consolidation (the shared motion-paragraph style dict, and building the recorded-vote pattern from the explicit one) was not done. The risk list in the 23:50 note was not done. `D. Schwartz` stays refused.

## Open Questions

- Should a one-letter Roman token stay refused when it is an initial or `I.e.`? The test still says yes.
- Should the schema reject `fails` on a body that was only seconded? Leave it unless Jon wants the tests changed.

## Constraints and Guardrails

- Branch `feature/board-secretary-friction`. Pushing updates pull request 25. Do not open another pull request. Do not merge.
- Do not pop the stash named `board secretary handoff checkpoint`.
- No Docs write from this pass.

## Files / Artifacts / Sources

- Code: `541b1fa` in `python/msjc_board_secretary/schema.py` and `tests/test_schema.py`
- Review that named the bugs: `handoffs/archive/pr25-review-duplication-validity/20261118-2350-pr25-review-duplication-validity.md`
- Commands: the unittest and ruff lines in Current State

## Next Best Actions

1. Jon reviews and merges pull request 25. Do not merge from an agent session.
2. A later pass can do the safe consolidation and the risk list in the 23:50 note. Do not fold those into a drive-by on this branch after Jon has started review unless he asks.

## Known Risks or Failure Modes

- `The chair paused for 30 seconds.` and `The seconded motion passed.` still earn. `yea-sayers` still counts as yea. Those were risks, not this pass.
- A Roman token in a paragraph or bullet is still not checked. `II . Accept` (space before the period) is still allowed on a replacement.
- `hasn't yet been seconded` is not negated. The gap is only optional `been`.
- `We did not vote. Motion passes.` still earns, because a recorded pass wins over `did not vote`.
- No live Google Doc write has been exercised.

## Prompt to Resume

Continue from `feature/board-secretary-friction` and this handoff; pushing updates pull request 25 and Jon merges. The ten validity bugs from the 23:50 review are fixed in `541b1fa`, so do not reopen them without a new failing case. Avoid verdict-direction changes, deleting the single-letter Roman check, merging the two vote patterns, the safe-consolidation items, and a new pull request. Validate with `python3 -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"` and `python3 -m ruff check python/msjc_board_secretary`.
