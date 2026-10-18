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

- Branch `feature/fanfic-story-doctor`, PR #15. Opened 2026-10-17. An adversarial review that day found blockers, and a fix commit on the same branch addressed them. Spec v0.4.3 is new. v0.4.2 is unchanged and lives in private notes, not in this repo.
- Package `python/fanfic_story_doctor` and skill stub `.cursor/skills/fanfic-story-doctor`. Pull-request CI runs this package's pytest.
- A trial run on a public posted AO3 work (box only, outside the repo) drove fixes: punctuation-safe name candidates, per-item validation drop, spelling-noise filters, shared-surname ambiguity, AO3 HTML input, `au_kind: alternate_setting`, and conflicts limited to `status` (aliases were all being marked disputed). Findings went from a crash (95 noisy hits once patched) to 8, about 6 of them worth a look.
- 86 tests pass locally (pytest in a venv). `CANON.DIVERGENCE` checks event order. Before the branch is a finding (`should`). At or after the branch is coverage. Not AU, or no divergence event: info (plus an intake question). Stale or disputed canon: unverifiable. Canon edges no longer enter the timeline graph for pairs the ledger orders, so a branch is never a `CONT.TIMELINE_ORDER` blocker.
- `doctor run` loads `$DOCTOR_HOME/canon/<primary>/facts.json` when present. The report schema ships inside the package, and the in-repo guard no longer depends on where the package is installed.
- Layer B runs `OOC.VOICE` and `CANON.RAILS` on the deterministic mock provider or on `cursor-agent` (`src/doctor/layerb.py`): info-only notes, closed labels, exact quotes checked, agreement reported. `cursor-agent` needs `DOCTOR_G9_OPT_IN=1` per run; tests use a fake subprocess, never the real CLI.
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
- G9 is per run: set `DOCTOR_G9_OPT_IN=1` only for works the author agreed to send (first real trial: a public AO3 work). Confirm Cursor data and retention settings before using it on a private draft.
- Run the measure counter on local chapters under `DOCTOR_HOME` without pasting chapter text back.

## Known Risks or Failure Modes

- Pre-canon timeline rule: confirmed over-broad in review (it applied to every event). Now scoped to the intake `window.event` with `relation: before`. E1–E8 still pass. Recheck when a work crosses its window event.
- Name spelling still uses heuristics. Nicknames (a short form of a name) can still be flagged, and a real typo that is also a dictionary word is hidden.
- Dead-reappears table: confirmed in review that the old `expect()` mirrored the code. It has been replaced by a hand-written literal table that also covers alive, unspecified, and out-of-set statuses. That table is still one author's reading of the spec, not a second annotator's.
- Confirmation, proposer, and holdout code are helpers, not a finished writer loop.
- Mock labels are hash-derived and say nothing about the text. `cursor-agent` sends passage text to Cursor's service; the CLI's OS sandbox is unavailable on Windows, so read-only rests on `--mode ask`, no `--force`, and an empty temp workspace. Cost is 3 calls per passage. The real-provider cache persists in `DOCTOR_HOME/cache/layerb.json` (contains model quotes of the text; it lives outside the repo).

## Prompt to Resume

Continue from branch `feature/fanfic-story-doctor` and spec v0.4.3. Focus on a commit only if asked, then the G9 decision and a local measure under `DOCTOR_HOME`. Avoid reading real drafts or book files into chat, and avoid rewriting prose. Validate with `python -m pytest -q` in `python/fanfic_story_doctor`.
