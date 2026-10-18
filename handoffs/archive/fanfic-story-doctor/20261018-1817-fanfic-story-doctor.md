---
thread: fanfic-story-doctor
status: active
created: 2026-10-18T18:17Z
supersedes: handoffs/archive/fanfic-story-doctor/20261018-1759-fanfic-story-doctor.md
private_detail: Sensitive/handoffs/20261018-1817-fanfic-story-doctor.md
---

# Fanfic Story Doctor

## Objective

Make Layer B voice notes and name checks trustworthy after the paid trial, without rewriting prose.

## Current State

- Branch `feature/trial7-voice-report`, not pushed. On top of `main` at `daebe37`: `574d730` names and mentions, `3ad6689` voice profiles and majority vote, `a9d7904` HTML/JSON review files, `12ff5fc` profile field limit, then the handoff commit that carries this note.
- 138 tests pass. Each of the three split commits passed its own suite before it was made (120, 135, and 136 tests).
- Fixed this session: intake refuses override text that quotes, straight or curly, or suggests a rewrite, using the same rule as the profile validator, so a bad override fails before any model call. The profile cache holds only the model's own profile. The profile prompt states the 200-character field limit, and a cached rejection is retried when the profile prompt changes.
- Two paid reruns on the trial work finished with no provider failures. The first lost two of three profiles to the unstated field limit. The second, after the fix, judged every planned target. Counts and chapter results: see private detail.

## Key Decisions Already Made

- A voice profile is an early-work sample. Later chapters do not regenerate it. `--refresh-voice-profiles` does.
- A shown label needs more than half of the attempted runs. Only a thin concern counts as `not_enough_evidence`; a thin `in_voice` still counts as `in_voice`.
- Narration and untagged speech are outside OOC.VOICE.
- A cached profile rejection holds only for the prompt that produced it.
- Profile sampling stays as built until results show that short sample turns hurt.

## Constraints and Guardrails

- No push unless asked. Do not commit `Sensitive/`.
- Do not read real draft text, `cache/layerb.json`, or profile fields from `cache/profiles.json` into chat.
- A paid opt-in goes only to the provider for that one run.

## Files / Artifacts / Sources

- `handoffs/fanfic-story-doctor-spec-v0.4.4.md`
- `python/fanfic_story_doctor/`
- Trial outputs, counts, and expectations: see private detail: `Sensitive/handoffs/20261018-1817-fanfic-story-doctor.md`

## Next Best Actions

- Decide whether a thin `in_voice` read should count as `not_enough_evidence`, like a thin concern. About half of the rerun's `in_voice` results rest on mostly thin reads.
- Push the branch and open a PR when asked.
- Smaller follow-ups: select voice targets only among characters that have a profile, so a rejected profile does not waste chapter slots; stop the HTML review page from repeating the chapter heading before every paragraph; decide whether profile samples should skip turns of three words or fewer.

## Known Risks or Failure Modes

- Most passages the previous run flagged were not judged this time. They moved into profile samples, fell out of scope, or lost their slot. A cleaner report is largely a coverage change.
- Strict attribution leaves most quote segments on the trial work unattributed.
- Identical paragraph text in different chapters shares a judgment cache entry.

## Prompt to Resume

Continue on `feature/trial7-voice-report`, which is not pushed. Focus next on the thin `in_voice` decision, then a PR if asked. Avoid reading drafts, caches, or profile fields into chat, and avoid another paid run until asked. Validate with `python -m pytest -q` in `python/fanfic_story_doctor` using `PYTHONPATH=src`.
