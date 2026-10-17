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

Layer B is **not wired** into `doctor run` yet. `--layer-b` is accepted, but `OOC.VOICE` and `CANON.RAILS` still report `skipped` with reason `layer_b_not_wired`. `src/doctor/later.py` holds helpers (mock provider, voting, cache, holdout gate) only.
