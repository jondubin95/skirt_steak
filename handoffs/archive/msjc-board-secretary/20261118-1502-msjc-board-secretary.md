---
thread: msjc-board-secretary
status: active
created: 2026-11-18T15:02Z
supersedes: handoffs/archive/msjc-board-secretary/20261116-1620-msjc-board-secretary.md
private_detail: null
---

# MSJC board secretary

## Objective

Finish the approved review fixes on pull request 25. Push them to `feature/board-secretary-friction`. Do not open a new pull request. Do not merge.

## Current State

- Pull request 25 is open and unmerged: https://github.com/jondubin95/skirt_steak/pull/25
- Branch `feature/board-secretary-friction`. Reviewed at `117c120`. Five local commits sit on top of that and were not on the remote when this note was written. Push them with this handoff.
- Implementation stopped on purpose. Nothing is half-edited in the worktree.
- `python3 -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"` on 2026-11-18: 55 tests, OK, 0.012s. The setup test prints two `Backed up ... mcp.json.bak` lines. That is the script reporting the backup, not a failure. Ruff was not run. No live Google Doc was written.
- Do not pop the stash named `board secretary handoff checkpoint`. It belongs to `feature/close-stale-handoffs`.

### Item status

1. **Done.** `D'var Torah` no longer trips the Roman-heading check. A heading numeral must be followed by `.` or `)`. Commit `4aba579`.
2. **Done.** `fails` stays, and only for a motion that was voted down. No seconder and no vote is rejected. The body stays plain text such as `No second; not voted`, with no verdict. Commit `9ee2b27`.
3. **Done.** Absent-speaker guard uses more speaking, presenting, moving, and seconding verbs, word-boundary full names, and the labels Not in attendance, Absent, Not present, and Regrets. Commit `938b099`.
4. **Done.** Step 7 stops for a human confirmation unless the request named both the exact document title and the output tab. The writer checks the live output tab title exactly, not only the document title. Commit `b274244`.
5. **Done.** `setup_local_mcp.py` uses `sys.executable`. An existing `mcp.json` is kept unless `--replace` is passed, and that path copies the file to a sibling backup first and says so. Commit `3dc421d`.
6. **Not started.** `--replace` still returns from `write_tab.main` before `minutes_shape_errors` and `absent_speaker_conflicts`. `perform_replace` does call `validate_target_identity` (title, exact tab, revision) because of item 4. The phrase itself is not checked for placeholders or heading markers.
7. **Not started.** `sample_minutes.json` still has a stray `None.` paragraph under Hall Rental. `_EMPTY_SECTION` is still the exact string `None.` compared with `==`. `_PLACEHOLDER_XXX` is still case-sensitive `\bXXX\b`.
8. **Done**, in the same commit as item 1. A leading `#` is the markdown heading check. `Item #4` passes. `2027 Membership Pricing` passes. The spec no longer calls a year a numbered heading.
9. **Partial.** The word `mover` is back in the motion rule (commit `9ee2b27`). Step 8 still says a wording fix uses `--replace` instead of `--write`, while Corrections requires `--replace` with `--write`. Step 8 also says to delete the JSON if the write fails before Google accepts it, which fights `write_tab.RECOVERY_MESSAGE` when pass 1 already succeeded. Sign-in text in `SKILL.md`, `write_tab.load_credentials`, and the package README still says to wait for a browser approval.
10. **Partial.** Tests cover items 1, 2, 3, 4, 5, and 8. Items 6, 7, and the unfinished part of 9 have no new tests.

### Commits on this branch since `117c120`

- `4aba579` Accept section titles that contain an apostrophe or a year.
- `9ee2b27` Record fails only when a motion was voted down.
- `938b099` Catch absent speakers by full name and more verbs.
- `b274244` Require confirmation of the document and the output tab.
- `3dc421d` Point local Docs MCP at this interpreter and keep the old config.

## Key Decisions Already Made

- Keep `fails` only for a motion the notes record as voted down. Never use it when there is no seconder and no vote. That case is plain text, for example `No second; not voted`, and the verdict is omitted. Do not reopen this.
- Restore the step-7 stop before a destructive full-tab replace unless the request already named both the exact document and the output tab. A document title alone is not confirmation. Do not weaken this.
- Do not build native Google Docs code blocks or horizontal rules. The Docs API cannot create them.
- Do not build tooling to accept or reject Docs suggestions. Google does not support that.
- Do not make one-off style edits that do not change behavior.

## Constraints and Guardrails

- Stay on `feature/board-secretary-friction`. Push updates pull request 25. Do not open another pull request. Do not merge.
- Do not edit the Notes tab. Do not write an older JSON over hand edits on the Minutes tab.
- Do not commit `Sensitive/` or an `mcp.json` that launches the local server. `.cursor/mcp.json.bak` is gitignored.
- Schema empty-marker work must keep exact `None.` behavior. Do not strip leading or trailing spaces in that check. `builder.strip_spilled_bullets` already strips Docs paragraph text before it compares. Tests depend on that difference.

## Files / Artifacts / Sources

Done, by item:

- 1 and 8: `python/msjc_board_secretary/schema.py` (`_MARKDOWN_HEADING`, `_ROMAN_HEADING_TOKEN`, `_ROMAN_VALUE`, `_roman_heading_token`, `minutes_shape_errors`). Tests `test_november_2026_section_titles_pass`, `test_roman_heading_needs_a_marker_and_a_year_is_a_title`, `test_hash_inside_a_title_is_not_a_markdown_heading`. Also `.cursor/skills/msjc-board-secretary/template-spec.md` and `python/msjc_board_secretary/README.md`.
- 2: `schema.py` (`_SECONDER`, `_NO_SECOND_OR_VOTE`, `_RECORDED_VOTE`, `motion_fail_is_earned`, motion parse). Tests `test_fails_requires_a_seconder_or_a_recorded_vote`, `test_fails_is_rejected_when_nobody_seconded_or_voted`. Skill motion bullet, template-spec Motions, README verdict sentence.
- 3: `schema.py` (`_SPEAKING_VERBS`, `_SPEAKING_VERB`, `_PRESENTED_BY`, `_NAME_CONTINUATION`, `_ABSENCE_CATEGORIES`, `_absence_category`, `_absent_names`, `_name_spans`, `_speaking_credit`, `absent_speaker_conflicts`). Tests `test_absent_speaker_more_verbs_and_absence_labels`, `test_absent_name_does_not_match_inside_a_longer_name`, `test_full_absent_name_still_conflicts`.
- 4: `schema.py` `validate_target_identity` and `validate_write_guards` (now takes `actual_output_tab` and `expected_output_tab`). `write_tab.py` `tab_title_of`, `full_tab_replace_is_confirmed`, `require_full_tab_confirmation`, flags `--confirmed-document-title` and `--confirmed-output-tab`. `perform_write` and `perform_replace` both call the identity check. Skill steps 7 and 8. Tests `test_output_tab_must_match_exactly`, `test_replace_refuses_an_inexact_output_tab`, `test_unconfirmed_write_refuses_before_credentials`, `ConfirmationTests`.
- 5: `python/msjc_board_secretary/setup_local_mcp.py` (`google_docs_server`, `backup_path`, `write_local_mcp`, `main`). `tests/test_setup_local_mcp.py`. `.gitignore` entries `.cursor/mcp.json.bak` and `.cursor/mcp.json.bak-*`.

Still to edit:

- 6: `write_tab.main` replace branch, before `load_credentials`. Reuse the placeholder and heading checks. Add a test that a replacement containing `___` or `XXX` is refused before credentials load.
- 7: `sample_minutes.json` (delete the Hall Rental `None.` only). `schema.py` `_EMPTY_SECTION` and `_closing_section_errors`. `_PLACEHOLDER_XXX`. `tests/test_schema.py` `test_sample_loads` kinds list. `builder.strip_spilled_bullets` may call the same marker only after its existing strip.
- 9: `.cursor/skills/msjc-board-secretary/SKILL.md` step 8 and the Sign-in section. Matching lines in `write_tab.load_credentials` and `python/msjc_board_secretary/README.md`. `reauth.py` docstring still says "Browser sign-in".

## Next Best Actions

- Validate the `--replace` phrase with the same placeholder and heading checks before credentials are loaded.
- Remove the stray Hall Rental `None.`, match the empty-section marker only as the whole paragraph `None.`, and make `XXX` case-insensitive. Do not strip spaces in the schema check.
- Fix step 8 so a wording fix uses `--replace` together with `--write`. Keep the JSON when pass 1 succeeded and a later pass failed. Drop the assumption that reauth always happens in a local browser.
- Add tests for those three, re-run the suite above, and push this branch.

## Known Risks or Failure Modes

- `motion_fail_is_earned` is a phrase check (`seconds` / `seconded`, or a recorded-vote phrase). `No second; not voted` is rejected. A voted-down line that uses none of those words would also be rejected.
- `_NAME_CONTINUATION` treats a following capitalized token, or Jr./Sr./II/III/IV/V, as a longer name. `Alex` does not match `Alex Rivera Jr.`
- Step 8 still contradicts Corrections and the pass-1 recovery message until item 9 is finished.

## Prompt to Resume

Continue from `feature/board-secretary-friction` and this handoff. Finish items 6, 7, and 9, and add the missing tests from item 10. Keep `fails` only for a voted-down motion, and keep the step-7 stop unless both the document title and the output tab were named. Do not add Docs code blocks, horizontal rules, or suggestion-accept tooling, and do not merge. Validate with `python3 -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"`.
