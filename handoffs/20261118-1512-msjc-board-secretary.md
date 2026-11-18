---
thread: msjc-board-secretary
status: done
created: 2026-11-18T15:12Z
supersedes: handoffs/archive/msjc-board-secretary/20261118-1502-msjc-board-secretary.md
private_detail: null
---

# MSJC board secretary

## Objective

The approved review fixes for pull request 25 are complete on `feature/board-secretary-friction`. Jon merges. Do not open another pull request.

## Current State

- Pull request 25 is open and unmerged: https://github.com/jondubin95/skirt_steak/pull/25
- Items 1–10 are done. Nothing is half-edited in the worktree.
- `python3 -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"` on 2026-11-18: 62 tests, OK. The setup test prints two `Backed up ... mcp.json.bak` lines. That is the script reporting the backup. `python3 -m ruff check python/msjc_board_secretary` passed. No live Google Doc was written.
- `tools/workflow_guardrails/preflight.sh` exited 1 because the Docs client file and token directory are not on this machine. That check is the Docs sync preflight, not the minutes suite.
- Do not pop the stash named `board secretary handoff checkpoint`. It belongs to `feature/close-stale-handoffs`.

### Item status

1. **Done.** `D'var Torah` no longer trips the Roman-heading check. Commit `4aba579`.
2. **Done.** `fails` stays only for a motion that was voted down. Commit `9ee2b27`.
3. **Done.** Absent-speaker guard uses more verbs, word-boundary full names, and the extra absence labels. Commit `938b099`.
4. **Done.** Step 7 stops unless the request named both the exact document and the output tab. Commit `b274244`.
5. **Done.** `setup_local_mcp.py` uses `sys.executable` and keeps an existing `mcp.json` unless `--replace` backs it up. Commit `3dc421d`.
6. **Done.** `--replace` runs `minutes_phrase_errors` on `replaceWith` before `load_credentials`. Placeholders and heading markers are refused. The `find` text can still be the placeholder being removed. Commit `0b4e90a`.
7. **Done.** The Hall Rental `None.` is gone from `sample_minutes.json`. The empty-section marker is a whole-paragraph `None.` and does not strip spaces. `XXX` is case-insensitive. Commit `530d576`.
8. **Done.** A leading `#` is the markdown heading check. A year in a title is not a numbered heading. Commit `4aba579`.
9. **Done.** Step 8 says a wording fix uses `--replace` together with `--write`, and it keeps the minutes JSON when pass 1 has already replaced the tab. Sign-in text tells the person to approve the prompt where it is shown. Commit `cb1009f`. The word `mover` was restored in `9ee2b27`.
10. **Done.** Tests cover the replace refusal, the whole-paragraph marker, case-insensitive `XXX`, and the step-8 / sign-in wording.

## Key Decisions Already Made

- Keep `fails` only for a motion the notes record as voted down. An unseconded motion with no vote stays plain text, for example `No second; not voted`.
- A full-tab replace stops unless the request named both the exact document and the output tab.
- Do not build native Google Docs code blocks or horizontal rules.
- Do not build tooling to accept or reject Docs suggestions.
- The empty-section check does not strip spaces. `strip_spilled_bullets` strips Docs paragraph text and then uses the same marker.
- A one-phrase replace checks `replaceWith` only. Closing-section shape and absent-speaker checks need a minutes document, so they stay on `--input`.

## Constraints and Guardrails

- Stay on `feature/board-secretary-friction`. Pushing updates pull request 25.
- Do not edit the Notes tab. Do not write an older JSON over hand edits on the Minutes tab.
- Do not commit `Sensitive/` or an `mcp.json` that launches the local server.

## Files / Artifacts / Sources

- Phrase checks: `python/msjc_board_secretary/schema.py` `minutes_phrase_errors`, called from `write_tab.main`.
- Empty marker: `is_empty_section_paragraph`. Builder: `strip_spilled_bullets`.
- Instructions: `.cursor/skills/msjc-board-secretary/SKILL.md` step 8 and Sign-in, `write_tab.REAUTH_MESSAGE`, `python/msjc_board_secretary/README.md`, `reauth.py`.

## Known Risks or Failure Modes

- `motion_fail_is_earned` is a phrase check. A voted-down line that uses none of those words is rejected.
- `_NAME_CONTINUATION` treats a following capitalized token, or Jr./Sr./II/III/IV/V, as a longer name.
- A replacement that contains a Roman heading token, such as `II.`, is refused even when that token is inside a sentence.
- A closing section whose only paragraph is ` None.` or `None. ` is accepted as content, because the schema check does not strip spaces.

## Prompt to Resume

Continue from `feature/board-secretary-friction`. Items 1–10 are complete on pull request 25, so the next action is Jon's merge. Keep `fails` only for a voted-down motion, and keep the step-7 stop unless both the document title and the output tab were named. Avoid Docs code blocks, horizontal rules, suggestion-accept tooling, and a new pull request. Validate any further edit with `python3 -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"`.
