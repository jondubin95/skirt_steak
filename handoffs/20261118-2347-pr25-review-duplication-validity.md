---
thread: pr25-review-duplication-validity
status: active
created: 2026-11-18T23:47Z
supersedes: null
private_detail: null
---

# PR 25 duplication and validity review

## Objective

Read-only adversarial review of pull request 25 on `feature/board-secretary-friction`. Find remaining safe consolidation and, first, internal validity bugs. Do not change the writer or the tests in this pass. Jon decides what to fix. Jon merges.

## Current State

- This note is a new thread. It does not supersede [20261118-1542-msjc-board-secretary.md](20261118-1542-msjc-board-secretary.md). That head stays the implementation record. Nothing was archived.
- Reviewed HEAD `907a1c7`. No functional code or tests were edited.
- Every fail-open and fail-closed claim below was run against that tree with `python3`. The suite was not the proof. The suite stays green on these holes.
- Validation on 2026-11-18: `python3 -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"` = 63 tests, OK. `python3 -m ruff check python/msjc_board_secretary` with ruff 0.17.2 (the CI pin) passed. The VM had no ruff module until that install.
- `tools/workflow_guardrails/preflight.sh` was not run. It still exits 1 here because the Docs client file and token directory are absent. That is expected.

## Why This Matters

The round-3 gate is what the writer trusts before a Docs replace. A green suite currently accepts a verdict the body contradicts, and refuses some legitimate names and pass-lines. Merging on "63 tests, ruff clean" would ship those holes.

## Key Decisions Already Made

- This pass records findings only. No schema or test edits.
- Verdict direction stays out of the must-fix list. The tests require both `passes` and `fails` for every earned body. The skill's "fails is only for a voted-down motion" is drafter policy. See leave-as-is.
- Single-letter Roman tokens (`D. Schwartz`, `I.e.`) are specified over-match. The phrase test asserts `D. Schwartz` is refused. That is a product call, not an accidental miss.

## Internal validity bugs

Must-fix before merge. Each one was executed.

1. **bug.** `motion_verdict_is_earned` treats "not seconded" as a seconder. `python/msjc_board_secretary/schema.py` line 18 matches `\bseconds\b` or `\bseconded\b`. The negation list at lines 21-29 never says "not seconded", "wasn't seconded", or "seconded by no one". Line 119 returns false only when that list hits. Proved True, and `load_minutes_document` accepts `passes` and `fails`: "The motion was not seconded.", "Not seconded.", "The motion wasn't seconded." (straight and curly apostrophe), "The motion hasn't been seconded.", "The motion was seconded by no one.", "Seconded by nobody.", "Jordan Hale seconds the motion. It was not seconded." Fix: a seconder hit counts only when a negation does not govern that hit. Cover "not seconded", "n't seconded", and the inverted "seconded by no one/nobody". Add those strings to `test_verdict_is_rejected_without_a_seconder_or_a_vote`. The current list never uses them.

2. **bug.** `motion failed`, `motion fails`, and `defeated` still earn a verdict when the failure is failure to be seconded, unless the wording is exactly "lack of a second". Lines 36-39 and 119-121. Proved True: "The motion failed to receive a second.", "The motion failed to get a second.", "Motion fails for lack of the second.", "Motion fails for want of a second.", "Defeated for want of a second." The tests reject only "lack of a second" and "for lack of a second", so these stay green. Fix: a lack-of-second idea suppresses `motion failed` / `defeated`. Include "receive a second", "get a second", "want of a second", and "lack of the second". Keep yea/nay/`voted down`/`vote failed` as the explicit override, after bug 3.

3. **bug.** "not voted down" is treated as the vote it denies. Lines 33-35 match `voted down` inside `not voted down`. That cancels the `not voted` negation at line 119, then line 121 matches the same span as a recorded vote. Proved True: "not voted down", "The motion was not voted down.", "was not voted down". Fix: a vote phrase with `not`, `never`, or `n't` immediately in front is not an explicit vote. Bare "Voted down." must stay earned.

4. **bug.** The negation flag is whole-body, so it both over-vetoes and under-matches. Line 119. Proved False, so a real second is refused: "No one seconded at first. Jordan Hale later seconds.", "No second reading was required. Jordan Hale seconds.", "There is no second location. Jordan Hale seconds." Proved True, so a body that says there was no vote still earns: "Jordan Hale seconds. We did not vote.", "We did not vote on it. Jordan Hale seconds." `\bnot\s+voted\b` and `\bno\s+vote\b` miss "did not vote". `\bno\s+second\b` hits the noun in "no second reading". Fix: judge the clause that contains the seconder. Do not let "no second" swallow a following noun that is not the parliamentary second. "Jordan Hale seconds. No vote was taken." is already False and must stay False.

5. **bug.** A recorded pass is not a recorded vote, and a recorded failure is. Lines 36-39 include `motion fails` and `motion failed`. They omit `motion passes` and `motion passed`. Proved False, and the loader rejects `verdict: passes`: "Motion passes.", "The motion passes.", "The motion passed, 7-0.", "Passed unanimously." Proved True: "Motion fails.", "The motion failed, 4-3." "It failed, 4 to 3." is False. README says a recorded vote earns either verdict. The skill example happens to include "seconds", so that happy path still loads. Fix: add `motion passes` and `motion passed` as the pair of the fail patterns. Do not add bare "passed".

6. **bug.** The name boundary stops a longer name only when this name is a prefix followed by a capital token. A trailing component, and an apostrophe, still match. Lines 344, 351, 370-395. `_NAME_CHAR` is a letter, digit, or hyphen. Apostrophe is not. Continuation looks forward only, and only for whitespace plus a capital. Proved conflicts: absent "Ann" in "Mary Ann said the hall is open."; "Lee" in "Mary Lee said..."; "Ortiz" in "Sam Ortiz said..."; "Brien" in "O'Brien said..." and in the curly-apostrophe form; "Ann" in "O'Ann said..."; "Rivera" in "alex Rivera said...". Proved the comma suffix hits the presented-by path: "Presented by Alex Rivera, Jr." credits absent "Alex Rivera", because the comma blocks continuation and presented-by still matches the prefix. These do not conflict, so do not "fix" them: "Alex Rivera, Jr. said" (the verb is not adjacent), "Alex Rivera Jr. said", "Presented by Alex Rivera Jr.", "Jo-Ann", "Mary-Ann", "JoséAnn", "key2Ann". Fix: a match is not a credit when it is only part of a longer personal name. Treat apostrophe like hyphen. Look backward for a preceding capital token. Treat ", Jr.", ", Sr.", and ", III" like " Jr.", and do that before the presented-by short-circuit.

7. **bug.** "notes", "reports", and "moves" credit speech when they are nouns. The verb list is lines 303 (`moves`), 305 (`notes`), and 318 (`reports`). The matcher at lines 335-339 only requires the word after the name. Proved conflicts: "Taylor Morgan notes were distributed.", "Taylor Morgan reports were late.", "Taylor Morgan moves were recorded." Fix: do not credit the noun reading. A following "was" or "were" is enough to reject those three. Keep "noted", "reported", and "moved".

8. **bug.** A replacement Roman marker is refused only at column 0, and the test locks the bypass in. Line 431 is `^(?:[([]\s*)?([IVXLCDM]+)(?=[.)])`. Line 551 uses that pattern. Proved allowed: " II. Accept Minutes", a leading tab, a leading newline, and " (II. Accept Minutes)". Proved refused: "II. Accept Minutes" and "(II. Accept Minutes)". Section titles use the anywhere-token pattern, so a section title " II. Accept Minutes" is refused. Only the replacement path is open. `tests/test_schema.py` line 558 asserts the leading-space string is allowed. The markdown check already allows up to three leading spaces. Fix: let the Roman-at-start pattern allow the same leading whitespace, including whitespace before the bracket. Keep "See II. above" allowed. Change line 558. Do not treat the green assert as the spec.

9. **bug.** A padded `None.` next to other text is accepted. Lines 497-519. The whitespace error runs only when that paragraph is the sole body and `strip()` equals `None.` but the text is not exactly `None.`. The alongside error calls `is_empty_section_paragraph`, which does not strip. Proved: sole " None." errors; "None." plus a bullet errors; " None." plus a bullet returns no errors. Fix: any closing paragraph whose stripped text is `None.` is the marker. If it is not the one exact `None.` paragraph, error. That covers the sole near-miss and the alongside near-miss in one rule.

10. **bug.** `true` and `1.0` pass the integer checks. Lines 224-226 compare `schemaVersion` with `!= 1`. Lines 186-188 use `isinstance(level, int)`. In Python `True == 1`, `1.0 == 1`, and `bool` is a subclass of `int`. Proved: `schemaVersion: true` loads with version `True`; `schemaVersion: 1.0` loads with version `1.0`; bullet `level: true` loads as `True` and `level: false` loads as `False`. Fix: require `type(version) is int` and `type(level) is int`.

## Risks

Real, not the merge blocker by themselves.

- **risk.** `\bseconds\b` matches the unit of time. "The chair paused for 30 seconds." is True. "a few seconds later Jordan Hale seconds" is True for the same reason, and also for the real seconder. Fix: ignore `seconds` when a number or "few" or "several" precedes it. "Jordan Hale seconds." must stay True.
- **risk.** An incidental yea/nay cancels a lack of a second and counts as the vote. "The yea-sayers were loud. No second; not voted." is True. "No second; not voted. The chair said yea." is True. A hyphen is a word boundary, so `yea-sayers` matches. Fix: yea/nay should be a tally, not a hyphenated word, and should not override a lack-of-second phrase. `voted down` and `vote failed` stay the override.
- **risk.** A one-letter Roman value is also an initial. Proved refused at the start of a replacement, and anywhere in a section title: "D. Schwartz", "D. Schwartz will attend", "I.e. the hall is booked", "M. Rivera called", "C.D. Report". "Dr. Schwartz", "Mr. Smith agreed", and "Presented by D. Schwartz" are allowed. `tests/test_schema.py` line 569 requires "D. Schwartz" to be blocked. Do not delete the check to let initials through. "IIII. Old heading" is allowed because it is not a canonical Roman value. Low. Needs an explicit rule if initials must pass.
- **risk.** An absence category that already ends with ":" renders a doubled colon. `schema.py` lines 355-356 strip the colon for matching. `builder.py` line 87 always appends ": ". Proved: category "Not in attendance:" becomes "Not in attendance:: Taylor Morgan". The sample omits the colon, so the sample render is fine. The test helper uses the colon form and never renders it. Fix: append the colon only when the category does not already end with one.
- **risk.** Presented-by credits only the name glued to that phrase. "Presented by Alex Rivera and Taylor Morgan." does not credit Taylor Morgan.
- **risk.** "Taylor Morgan, who had reported the leak, left." and "Taylor Morgan who said the hall is open." do not credit. "Taylor Morgan, said the hall is open." does not either. That last one is the comma rule in leave-as-is. Auxiliaries are the hole.
- **risk.** "Regrets!" and "Not  in attendance" (two spaces) are not absence categories. "Regrets;", "ABSENT", and "Absent—" are. Internal whitespace is not collapsed.
- **risk.** Only the last three section titles are the closing trio (`schema.py` lines 490-492). An earlier empty Old Business is ignored when a later Old Business, New Business, Adjournment trio is well formed. Proved.
- **risk.** The presenter pattern at line 419 is `^Presented by \S.*\.$`. "Presented by Alex Rivera. He then left." is accepted. "Presented by  Alex Rivera." and a lowercase "presented by" are refused.
- **risk.** Absence and shape run in `write_tab.py` `main`, not in `perform_write`. A direct caller can skip them. `perform_replace` repeats the equal-string check for that reason. The CLI path is guarded.
- **risk.** Flat `names` attendance cannot mark anyone absent. Absence is read only from group categories. Proved: a flat list plus "Taylor Morgan said..." has no conflict. That is the schema. Do not invent an absence guess.

## Tests that do not lock the behavior

- **risk.** In `test_verdict_is_rejected_without_a_seconder_or_a_vote` (`tests/test_schema.py` lines 159-183), these bodies stay rejected if the negation regex is deleted, because they have no seconder word and no recorded-vote word: "No second; not voted", "without a second", "The motion died without a second.", "It failed without a second." Deleting the `without a second` alternative alone does not turn the suite red. The load-bearing negatives are the ones that also contain seconded, motion fails, or defeated: "No one seconded.", "Nobody seconded it.", "never seconded", "Motion fails for lack of a second.", "Defeated for lack of a second." Fix: add the proved fail-open strings from bugs 1-4 as negatives, and keep one bare "Jordan Hale seconds." positive.
- **risk.** `test_sample_has_no_absent_speaker` (line 224) and `test_sample_shape_is_writable` (line 392) stay green if those checks are deleted. The 1542 head already says so. The refusal tests are the coverage. Still true. Not a new defect.
- **risk.** In `test_possessive_is_not_a_speaking_credit` (line 324), "Alex Rivera said Taylor Morgan's report was late." and "Alex Rivera's replacement presented the budget." stay green if the possessive skip is removed. The verb is not adjacent, and presented-by does not end at that name. The two "presented by Taylor Morgan's replacement" strings are the ones that lock the skip.
- **risk.** The Hall Rental asserts at the end of `test_empty_section_marker_is_the_whole_paragraph` (lines 539-546) only show the sample text is not the marker. They do not exercise the rule. The padded sole-paragraph asserts earlier in that test do. There is no swapped-order closing test. The code does refuse New Business, Old Business, Adjournment. Proved.
- **cleanup.** The phrase allow/deny lists have drifted. `tests/test_schema.py` lines 548-574 allow the leading-space Roman string and refuse "D. Schwartz". `tests/test_write_tab.py` lines 226-258 never send either string through the CLI. Sharing one table is safe only after bug 8 is fixed. Copying the current allow-list into the CLI test would cement the bypass.

## Safe consolidation

Not a merge blocker. Do not do these before the verdict fixes.

- **cleanup.** The motion paragraph style dict is copied. `builder.py` lines 211-224 and lines 501-513 use the same `NORMAL_TEXT`, 12pt below, 30pt indent end, and the same field mask. Safe to hoist one constant. The request type around it differs. Share the style dict only.
- **cleanup.** `_EXPLICIT_VOTE` (lines 33-35) and `_RECORDED_VOTE` (lines 36-39) duplicate `voted down`, `vote failed`, and yea/nay. Safe to build the recorded pattern from the explicit pattern plus `motion failed`, `motion fails`, and `defeated`. Not safe to make them one pattern. `motion fails` and `defeated` must not override a lack-of-second phrase. Do this after bugs 1-3, or the shared fragment stays wrong.

## Leave as-is

- The equal-string check in `load_replace_pair` (`write_tab.py` line 352) and again in `perform_replace` (line 367). The CLI rejects the pair, and a direct caller still hits `perform_replace`. The 1542 head already says to keep both.
- The empty-revision check inside the write loop (`write_tab.py` lines 297-298) after `validate_write_guards`. The first pass is redundant. A later pass reloads the revision and can see an empty one. The inner check has to stay.
- `find_tab` casefolds and strips. `validate_target_identity` is exact. A wrong-case output tab is found and then refused. Fail closed.
- `full_tab_replace_is_confirmed` stays its own function. The confirmation tests call it. Blank titles are not confirmation.
- Verdict direction. "Jordan Hale seconds." loads with `fails`. "Voted down." loads with `passes`. `test_verdict_requires_a_seconder_or_a_recorded_vote` loops both verdicts for every earned body. The schema claims "seconder or recorded vote", and that is what it implements, holes above aside. The skill is stricter. Changing direction means changing those tests. Residual: a merely seconded motion can render "Motion Fails."
- Exact marker versus "none." and "NONE.". A closing section whose only paragraph is "none." is accepted as filled text. `strip()` of "none." is not `None.`. The 1542 decision was exact match. A sole " None." is already an error.
- A comma without "who" is not a speaking credit. That includes "Taylor Morgan, the treasurer, said" and the collateral "Taylor Morgan, said". Stated rule.
- "Alex" does not match "Alex Rivera" or "Alex Rivera Jr." without a comma. Continuation does that job. Bug 6 is the comma form and the trailing-component form, not this case.
- Flat names versus groups, as in the risk list.
- The confirmation flags are whatever the caller passes. Nothing binds them to a human message except the skill text. Known since round 3.
- No live Google Doc was written.

## Open Questions

- Should a one-letter Roman token stay refused when it is an initial or "I.e."? The test says yes. Bug 8 (leading whitespace) is separate and should be fixed either way.
- Should the schema reject `fails` on a body that was only seconded? Leave-as-is unless Jon wants the tests changed.

## Constraints and Guardrails

- Branch `feature/board-secretary-friction`. Pushing updates pull request 25. Do not open another pull request. Do not merge.
- Do not pop the stash named `board secretary handoff checkpoint`.
- No Docs write from this review.

## Files / Artifacts / Sources

- Implementation head: `handoffs/20261118-1542-msjc-board-secretary.md`
- Code: `python/msjc_board_secretary/schema.py`, `builder.py`, `write_tab.py`
- Tests: `python/msjc_board_secretary/tests/test_schema.py`, `test_write_tab.py`, `test_builder.py`
- Commands: the unittest and ruff lines in Current State

## Next Best Actions

1. Fix bugs 1-5 in `motion_verdict_is_earned` and add the proved strings as tests. Those are the must-fix set.
2. In the same pass, fix bugs 6-10. Bug 8 requires changing the allow assert at `tests/test_schema.py` line 558.
3. Leave the consolidation until that pass is green. Jon reviews and merges. Do not merge from an agent session.

## Known Risks or Failure Modes

- The 63 passing tests do not cover bugs 1-10. A fix that only adds phrases to the negation list, and does not change line 119 from a whole-body flag, will still miss bug 4.
- Tightening yea/nay or `seconds` (the risks) can refuse a real tally or a real seconder. Keep "3 yeas and 4 nays" and "Jordan Hale seconds." green while adding the negative cases.

## Prompt to Resume

Continue from `feature/board-secretary-friction` and this note. Fix the verdict gate first: "not seconded", "seconded by no one", "failed to receive a second", "not voted down", a later real second after an unrelated "no second ...", and `motion passed` as the pair of `motion failed`. Then fix the trailing-name and apostrophe boundary, the noun readings of notes/reports/moves, the leading-whitespace Roman bypass including the allow assert, padded `None.` beside other text, and bool/float `schemaVersion` and `level`. Avoid verdict-direction changes, deleting the single-letter Roman check, merging the two vote regexes into one, and a new pull request. Validate with `python3 -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"` and `python3 -m ruff check python/msjc_board_secretary`.
