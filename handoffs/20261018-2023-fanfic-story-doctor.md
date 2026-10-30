---
thread: fanfic-story-doctor
status: done
created: 2026-10-18T20:23Z
supersedes: handoffs/archive/fanfic-story-doctor/20261018-1817-fanfic-story-doctor.md
private_detail: Sensitive/handoffs/20261018-2023-fanfic-story-doctor.md
---

# Fanfic Story Doctor

## Objective

Close the remaining Trial 7 review gaps in voice sampling, stale profiles, the HTML review, dialogue nicknames, and JSON flag positions.

## Current State

- Branch `feature/trial7-voice-report`. Do not commit to `main`.
- Voice samples are stratified across the chapter range, cap 16, longer lines preferred. `dialect_or_l2` is a profile field with the 200-character limit.
- A changed sample regenerates the profile. `--reuse-stale-voice-profiles` keeps the old one. `--refresh-voice-profiles` still forces a rebuild.
- HTML resolves chapter from the paragraph id, emits one heading per chapter, starts `j` on the first flag, and puts read reasons in `details` beside the flag.
- A prefix truncation inside dialogue is a nickname question, including one occurrence and a one-character cut. Outside dialogue the older rule stands.
- `--json` adds a `positions` list and still refuses a path inside the repo.
- 145 tests pass with `PYTHONPATH=src python -m pytest` from `python/fanfic_story_doctor`. Mock provider only.

## Key Decisions Already Made

- Regenerate on a changed sample by default. The opt-out is `--reuse-stale-voice-profiles`.
- Profile contract is `voice-profile-2`, so an older cached profile misses and is rebuilt.
- Flag positions follow highlightable prose spans: rule, character, chapter, paragraph id, offset, length, label, agreement.
- Dialogue nicknames stay `question` / info, not findings.

## Constraints and Guardrails

- No real fanfic text, character lines, or personal paths in git.
- No cursor-agent provider runs. Mock only.
- Do not commit `Sensitive/`.

## Files / Artifacts / Sources

- `python/fanfic_story_doctor/src/doctor/layerb.py`
- `python/fanfic_story_doctor/src/doctor/render.py`
- `python/fanfic_story_doctor/src/doctor/rules.py`
- `python/fanfic_story_doctor/src/doctor/intake.py`
- `python/fanfic_story_doctor/src/doctor/cli.py`
- `handoffs/fanfic-story-doctor-spec-v0.4.4.md`
- Private trial detail from the previous note is not in this environment: `Sensitive/handoffs/20261018-1817-fanfic-story-doctor.md`

## Next Best Actions

- Open the PR into `main` and leave it unmerged.
- A paid rerun is still a separate decision. Do not start one from this note.

## Known Risks or Failure Modes

- Cap 16 samples one line from every chapter when the work has 16 chapters or fewer, so identical leftover lines can share a judgment cache entry.
- A cached rejection is reused only when the sample hash still matches.
- HTML index links for a span whose chapter is not flagged still have no target. Baseline `in_voice` notes are in that set.

## Prompt to Resume

Continue on `feature/trial7-voice-report`. The Trial 7 code gaps in this note are implemented; focus next on review comments or a paid rerun only if asked. Avoid real drafts, caches, and profile text, and do not call cursor-agent. Validate with `PYTHONPATH=src python -m pytest` from `python/fanfic_story_doctor`.
