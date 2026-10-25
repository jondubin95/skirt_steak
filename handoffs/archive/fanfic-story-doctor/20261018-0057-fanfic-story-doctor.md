---
thread: fanfic-story-doctor
status: active
created: 2026-10-18T04:57Z
supersedes: handoffs/archive/fanfic-story-doctor/20261010-2334-fanfic-story-doctor.md
private_detail: Sensitive/handoffs/20261018-0057-fanfic-story-doctor.md
---

# Fanfic Story Doctor

## Objective

Diagnose-only continuity tool for fanfic drafts. The first fact check is event-order canon divergence against a declared branch. Book text and real drafts stay out of the public repo.

## Current State

- Branch `feature/fanfic-story-doctor`, PR #15. Head `c024915`, pushed. Both Guardrails checks passed. Not merged.
- Six commits after `61319eb`: opted-out Layer B rules no longer call the provider; blank `observed` and `quote` fail the contract, and punctuation is normalized on a copy before the note is stored; explicit chapter files merge in chapter order and a duplicate explicit chapter exits; the Layer B cache key hashes reference id and sent text; two weak asserts are pinned; CI installs this package from `requirements.lock`.
- 114 tests passed locally. `PROMPT_VERSION` is still `voice-refs-2`. `rules.py`, `detect.py`, `timeline.py`, and the rubrics were not edited.
- The paid trial exercised `CANON.NAME_SPELLING` (8 findings) and `OOC.VOICE` (116 tasks, 122 notes). The work was `alternate_setting` with no status facts, and the canon ledger rows were all `proposed`, so `CANON.DIVERGENCE`, `CANON.RAILS`, `CONT.DEAD_REAPPEARS`, and `LEDGER.CONFLICT` did not run on the prose. Counts are in the PR body. Where the trial lives: see private detail: `Sensitive/handoffs/20261018-0057-fanfic-story-doctor.md`.
- This machine's only Python is 3.14. `rpds-py==0.24.0` has no 3.14 wheel, so the local venv uses `0.26.0`. CI is Python 3.12 and installs the lockfile.

## Key Decisions Already Made

- Post-branch disagreement with canon is coverage, not a finding. The predicate is event order.
- Layer B is info only. Opt-out is checked before a provider call. The `build_report` filter stays as a backstop.
- Only explicit chapter numbers take part in the duplicate check. A no-digit file and a multi-chapter HTML file do not raise. An HTML `chapter-N` colliding with a sibling `.md` is still out of scope.
- `vote()` still keeps one minority note beside a majority. That contract was not changed.
- Tests use an invented cast only.

## Constraints and Guardrails

- No commit unless asked. No work on `main`. Do not commit `Sensitive/`.
- No series text, draft text, or quote-bearing canon dumps in git or chat. Do not open the Layer B cache; it holds passage text.
- The tool never emits replacement prose.
- Do not bump `PROMPT_VERSION` for a wording change. Both rules share it, and the cache key does not hash the built prompt.

## Files / Artifacts / Sources

- `handoffs/fanfic-story-doctor-spec-v0.4.3.md`
- `python/fanfic_story_doctor/`
- `.cursor/skills/fanfic-story-doctor/SKILL.md`
- `.github/workflows/guardrails.yml`
- PR: https://github.com/jondubin95/skirt_steak/pull/15

## Next Best Actions

- Merge is the user's call. CI is already green.
- Left for a later decision, each with its own check against a real input: quieter `vote()`, a higher voice-presence bar, dead-reappears dedupe, rails prompt wording, and rails passage selection.
- An optional rerun of the paid trial is the user's checkpoint. The merge does not wait on it. A rerun needs `DOCTOR_G9_OPT_IN=1` on that command only.

## Known Risks or Failure Modes

- Two files that name the same explicit chapter used to merge and now exit.
- Hashing reference text orphans `OOC.VOICE` cache entries that carry references. Rails hashes did not move. The next real run pays for those voice calls again.
- Name spelling is still a heuristic. The dead-reappears table is one author's reading of the spec.
- The fact rules and the timeline engine have not run on real prose.
- Mock labels are hash-derived. `cursor-agent` has no OS sandbox on Windows. Read-only rests on `--mode ask`, no `--force`, and an empty temp workspace.

## Prompt to Resume

Continue from branch `feature/fanfic-story-doctor` at `c024915` and spec v0.4.3. PR #15 is open and green; merge only if asked. Focus next on one deferred behavior at a time, and only after a real input exists for it. Avoid reading real drafts, book files, or `cache/layerb.json` into chat, and avoid rewriting prose. Validate with `python -m pytest -q` in `python/fanfic_story_doctor` using `PYTHONPATH=src` for `python -m doctor`.
