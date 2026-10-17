---
thread: fanfic-story-doctor
status: active
created: 2026-10-11T03:34Z
supersedes: null
private_detail: Sensitive/handoffs/20261010-2334-fanfic-story-doctor.md
---

# Fanfic Story Doctor

## Objective

Diagnose-only continuity tool for fanfic drafts. The first fact check is event-order canon divergence against a declared branch. Book text and real drafts stay out of the public repo.

## Current State

- Branch `feature/fanfic-story-doctor`. Committed and opened as a PR for review on 2026-10-17. Spec v0.4.3 is new. v0.4.2 is unchanged.
- Package `python/fanfic_story_doctor` and skill stub `.cursor/skills/fanfic-story-doctor`. Pull-request CI runs this package's pytest.
- 19 tests passed locally. `CANON.DIVERGENCE` checks event order. Before the branch is a finding. At or after the branch is coverage. Layer B notes are skipped on a normal run.
- Real chapters were not measured. Private files belong under `DOCTOR_HOME`, outside the repo. See private detail: `Sensitive/handoffs/20261010-2334-fanfic-story-doctor.md`.

## Key Decisions Already Made

- Canon divergence here is the genre: a deliberate branch. Post-branch disagreement with canon is coverage, not a finding.
- The fact predicate for that rule is event order. Alive/dead is a later rule. "Still on canon rails" is a Layer B note, info only.
- Another fandom is a new private ledger plus intake, not a code fork.
- Tests use an invented cast only.

## Constraints and Guardrails

- No commit unless asked. No work on `main`.
- No series text, draft text, or quote-bearing canon dumps in git or chat.
- The tool never emits replacement prose.

## Files / Artifacts / Sources

- `handoffs/fanfic-story-doctor-spec-v0.4.3.md`
- `python/fanfic_story_doctor/`
- `.cursor/skills/fanfic-story-doctor/SKILL.md`
- `.github/workflows/guardrails.yml`

## Next Best Actions

- Review the PR against the Known Risks below before merging.
- Wire Layer B into `doctor run --layer-b` with the mock provider.
- Run the measure counter on local chapters under `DOCTOR_HOME` without pasting chapter text back.

## Known Risks or Failure Modes

- One timeline rule was added so a pre-canon work's later chapters stay before the canon event. Confirm that still matches the worked examples before relying on it.
- The large dead-reappears table's expected column was fitted against the implementation. Recheck it before calling the rule validated.
- Confirmation, proposer, cache, and holdout code are helpers, not a finished writer loop.

## Prompt to Resume

Continue from branch `feature/fanfic-story-doctor` and spec v0.4.3. Focus on a commit only if asked, then the Layer B runner and a local measure under `DOCTOR_HOME`. Avoid reading real drafts or book files into chat, and avoid rewriting prose. Validate with `python -m pytest -q` in `python/fanfic_story_doctor`.
