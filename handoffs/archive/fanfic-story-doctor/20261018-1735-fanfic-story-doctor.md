---
thread: fanfic-story-doctor
status: active
created: 2026-10-18T21:35Z
supersedes: handoffs/archive/fanfic-story-doctor/20261018-0057-fanfic-story-doctor.md
private_detail: Sensitive/handoffs/20261018-1735-fanfic-story-doctor.md
---

# Fanfic Story Doctor

## Objective

Make Layer B voice notes and name checks trustworthy after the paid trial, without rewriting prose.

## Current State

- Branch `feature/trial7-voice-report`, based on merged `main` at `daebe37`. Not committed.
- v0.4.4 changes spelling, mentions, speaker turns, cached early-work profiles, and OOC aggregation. `CANON.RAILS` voting and prompt hash are unchanged.
- Optional `--html` and `--json` review output is implemented and refused inside the repo.
- Synthetic suite passed. The paid rerun has not been launched.

## Key Decisions Already Made

- Profiles are early-work samples, refreshed only on request.
- A concern needs a strict majority. Thin evidence counts as not enough evidence.
- Undeclared prefixes become questions only when repeated or when at least two characters are dropped.
- Narration is outside OOC.VOICE.

## Constraints and Guardrails

- No commit unless asked. Do not commit `Sensitive/`.
- Do not read the Layer B cache or real draft text into chat.
- The paid opt-in must be set only for that command and removed afterward.

## Files / Artifacts / Sources

- `handoffs/fanfic-story-doctor-spec-v0.4.4.md`
- `python/fanfic_story_doctor/`
- Where the trial lives: see private detail: `Sensitive/handoffs/20261018-1735-fanfic-story-doctor.md`

## Next Best Actions

- Review the diff, then commit Stage 1a and Stage 1b separately if asked. HTML/JSON can be its own commit.
- Run the paid rerun only when asked. Compare it with the expectations in the private note before trusting the new voice results.

## Known Risks or Failure Modes

- Stricter attribution will lower the number of voice targets. The rerun must report attributed, unattributed, and skipped counts so silence is not mistaken for a clean bill.
- The OOC prompt change misses the old voice cache. Rails cache entries should still hit.
- A stale profile stays in use until `--refresh-voice-profiles`.

## Prompt to Resume

Continue on `feature/trial7-voice-report`. Spec v0.4.4 is in the handoff folder. Focus on committing only if asked, then the paid rerun and its count comparison. Avoid reading real drafts or `cache/layerb.json` into chat. Validate with `python -m pytest -q` and `python -m py_compile` in `python/fanfic_story_doctor` using `PYTHONPATH=src`.
