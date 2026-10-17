# Fanfic Story Doctor

Diagnose continuity and canon divergence. Do not rewrite prose.

Spec: [handoffs/fanfic-story-doctor-spec-v0.4.3.md](../../handoffs/fanfic-story-doctor-spec-v0.4.3.md). Earlier drafts (v0.4.2 and before) are kept privately and are not in this repo.

## Run

```powershell
cd python/fanfic_story_doctor
$env:PYTHONPATH = "src"
python -m pytest -q
python -m doctor run tests/fixtures/ashfall
```

Real drafts and books go in `$DOCTOR_HOME` (default `%USERPROFILE%\doctor-home` on Windows, `~/doctor-home` elsewhere), not in this repo. If `$DOCTOR_HOME/canon/<primary_canon_source>/facts.json` exists, `doctor run` loads it (and checks quotes against `text/` when present). Tests point `DOCTOR_HOME` at an empty temp folder.

`CANON.DIVERGENCE` checks event order against the declared branch. `CANON.RAILS` is a Layer B note. Layer A makes no model call.

Layer B is wired to the **mock provider only**. `doctor run <work> --layer-b` runs `OOC.VOICE` (main-cast mentions) and `CANON.RAILS` (passages after a declared AU branch; skipped as `no_declared_branch` otherwise) three times per passage, votes, and adds `note` items. Notes are severity `info`, never findings or blockers, carry closed labels, an exact quote checked against the cited paragraph, and `observed` separate from `interpretation`. Agreement (`2_of_3`, `3_of_3`, `low_agreement`) is not correctness. Invalid responses are rejected and counted. Without `--layer-b` both rules report `skipped (layer_a_only)`.

**Gate G9.** Any `--provider` other than `mock` is refused unless `DOCTOR_G9_OPT_IN=1` is set after checking Cursor data and retention settings on the actual account. Even with the opt-in, no real provider is implemented in this package, so it still refuses. No draft text leaves the machine.

Code: `src/doctor/layerb.py` (runner, mock, G9 gate, contract check) on top of the `later.py` helpers (vote, cache key).
