---
thread: fanfic-story-doctor
status: active
created: 2026-10-18T16:59Z
supersedes: handoffs/archive/fanfic-story-doctor/20261018-1735-fanfic-story-doctor.md
private_detail: Sensitive/handoffs/20261018-1759-fanfic-story-doctor.md
---

# Fanfic Story Doctor

## Objective

Make Layer B voice notes and name checks trustworthy after the paid trial, without rewriting prose.

## Current State

- Branch `feature/trial7-voice-report`, from merged `main` at `daebe37`. The v0.4.4 work is uncommitted.
- Implemented: declared pronouns and voice-profile overrides, spelling ignores, letter-boundary mentions, character-level near-name matching, prefix nickname questions, cached early-work profiles, strict speaker turns, OOC-only majority aggregation, and optional `--html` / `--json` review output.
- `CANON.RAILS` vote, prompt bytes, and cache identity were left unchanged.
- `122` tests passed and the changed modules compiled. The paid rerun has not been run.

## Key Decisions Already Made

- A voice profile is an early-work sample. Later chapters do not regenerate it. `--refresh-voice-profiles` does.
- A shown label needs more than half of the attempted runs. Thin evidence counts as not enough evidence.
- Narration and untagged speech are outside OOC.VOICE.
- Undeclared prefixes become questions only when repeated or when at least two characters are dropped.

## Constraints and Guardrails

- No commit or push unless asked. Do not commit `Sensitive/`.
- Do not read real draft text or `cache/layerb.json` into chat.
- A paid opt-in must be set only for that command and removed afterward.

## Files / Artifacts / Sources

- `handoffs/fanfic-story-doctor-spec-v0.4.4.md`
- `python/fanfic_story_doctor/`
- Trial expectations and cost: see private detail: `Sensitive/handoffs/20261018-1759-fanfic-story-doctor.md`

## Next Best Actions

- The synthetic gaps still open are profile rejection and retry, partial and complete overrides, stale cache, refresh, and a scripted end-to-end 2-of-3 drift control. The article-dropping case can only prove that one validated profile is reused.
- Commit only if asked. Keep the name and mention work separate from the voice aggregation, and keep HTML/JSON separate from both.
- Run the paid rerun only if asked, then compare counts with the private expectations.

## Known Risks or Failure Modes

- Stricter attribution lowers the target count. Silence is not success unless attributed, unattributed, skipped, and rejection counts are reported.
- The new OOC prompt misses the old voice cache. Rails cache entries should still hit.
- Identical paragraph text in different chapters shares a judgment cache entry.

## Prompt to Resume

Continue on `feature/trial7-voice-report` with the uncommitted v0.4.4 diff. Focus next on the missing profile and scripted-drift tests, then commit only if asked. Avoid reading real drafts or `cache/layerb.json` into chat, and avoid a paid rerun until asked. Validate with `python -m pytest -q` and `python -m py_compile` in `python/fanfic_story_doctor` using `PYTHONPATH=src`.
