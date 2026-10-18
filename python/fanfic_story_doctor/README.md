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

Layer B has two providers: `mock` (default, deterministic, no network) and `cursor-agent` (the Cursor CLI). `doctor run <work> --layer-b` runs `OOC.VOICE` (main-cast mentions) and `CANON.RAILS` (passages after a declared AU branch; skipped as `no_declared_branch` otherwise) three times per passage, votes, and adds `note` items. Notes are severity `info`, never findings or blockers, carry closed labels, an exact quote checked against the cited paragraph, and `observed` separate from `interpretation`. Agreement (`2_of_3`, `3_of_3`, `low_agreement`) is not correctness. Invalid responses are rejected and counted. Without `--layer-b` both rules report `skipped (layer_a_only)`.

**Gate G9.** Any `--provider` other than `mock` is refused unless `DOCTOR_G9_OPT_IN=1` is set for that run, after checking Cursor data and retention settings on the actual account. There is no per-work exception: a public AO3 work needs the same opt-in as a private draft. Set it only for the command that should send text, not in your profile.

**cursor-agent provider.** `DOCTOR_G9_OPT_IN=1 doctor run <work> --layer-b --provider cursor-agent [--max-passages N]`. Each call sends one rubric and one passage to `cursor-agent -p --output-format json --mode ask --trust --workspace <empty temp dir>`, prompt on stdin, run in that empty temp directory, never with `--force`. The answer must be one strict JSON object matching the contract; anything else (prose, extra fields, CLI error, timeout after 180 s) is a rejected response, counted with its reason in a coverage note. Three runs per passage (3 calls), at most `--max-passages` passages per rule (default 20). Responses are cached in `DOCTOR_HOME/cache/layerb.json` keyed on text, ruleset, model and prompt, so reruns are free; timeouts and CLI errors are not cached. CLI lookup: `DOCTOR_CURSOR_AGENT` (path to `cursor-agent`, `.cmd` or `.ps1`), else `cursor-agent`/`agent` on PATH, else `%LOCALAPPDATA%\cursor-agent\cursor-agent.cmd`. `DOCTOR_CURSOR_MODEL` picks a model (default: the CLI's). Calls, seconds, failure reasons and token usage go to stderr as one JSON line. The CLI's `--sandbox` is not used: it is unavailable on Windows.

Code: `src/doctor/layerb.py` (runner, mock, cursor-agent, G9 gate, contract check) on top of the `later.py` helpers (vote, cache key).

## Inputs

A work folder holds `intake.yaml`, optional `tags.yaml`, `facts.json`, `profile.yaml`, and chapters as `.md`, `.txt`, or `.html`. An `.html` file can be one AO3 chapter page or a full-work download (`view_full_work=true` or the AO3 HTML download). Chapters come from the page's `chapter-N` blocks. Author notes, summary, preface, kudos, and comments are stripped.

`au.au_kind` is `branch` (default) or `alternate_setting`. In an alternate setting (a full AU with no canon timeline), canon status and event-order facts do not apply, so there is no `CANON.DIVERGENCE` or canon-driven `CONT.DEAD_REAPPEARS`. Canon aliases still apply. A `branch` AU with no `divergence_event` gets an intake question.

`CANON.NAME_SPELLING` ignores possessives (`'s`, `s'`), stammers and interrupted names (`Mara-`), plural surnames (`the Venns`), and dictionary words (a small built-in list plus the work's own lowercase vocabulary). A surname shared by several cast members is reported as ambiguous and is not attributed. A report item that fails validation is dropped and counted in a `REPORT.VALIDATION` note; the rest of the report still renders.
