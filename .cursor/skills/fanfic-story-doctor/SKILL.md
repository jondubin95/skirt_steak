---
name: fanfic-story-doctor
description: >-
  Continuity and canon-divergence checks for a fanfic draft. Trigger when the
  user mentions "fanfic story doctor", "story doctor", or "canon divergence"
  for a draft they are checking. Diagnose only. Never rewrite prose.
---

# Fanfic Story Doctor

The tool diagnoses. It does not rewrite. Suggested fixes are directions.

## Privacy

Real drafts and book text stay in `$DOCTOR_HOME` (default `%USERPROFILE%\doctor-home` on Windows, `~/doctor-home` elsewhere), outside the repo. Do not paste chapters, book text, or quote-bearing canon dumps into chat. Do not read those files out of `DOCTOR_HOME`.

Synthetic fixtures in the repo use an invented cast. No series text belongs in git.

## What is built

Layer A runs local Python. It makes no model call. `--layer-b` adds `OOC.VOICE` and `CANON.RAILS` notes: info, never a blocker, agreement is not correctness. Providers: `mock` (default) and `cursor-agent` (Cursor CLI, print mode, ask mode, empty temp workspace, cached in `DOCTOR_HOME/cache`). Any non-mock provider is refused by gate G9 unless `DOCTOR_G9_OPT_IN=1` is set for that run, public work or not. Never set it for a private draft without the author's say-so. Cap cost with `--max-passages`. OOC.VOICE targets are passages where the character speaks or carries the narration, spread across chapters, each with 2-4 earlier-chapter reference passages; a character without enough reference text is skipped with a coverage note.

```powershell
$env:DOCTOR_HOME = "$env:USERPROFILE\doctor-home"
python -m doctor run <work>
```

Run that from `python/fanfic_story_doctor` with `PYTHONPATH=src`, or install the package.

Chapters can be `.md`, `.txt`, or AO3 `.html` (chapter or full work). For a total AU with no canon timeline, set `au.au_kind: alternate_setting`.

A rule that is not built is reported as **skipped**. Skipped is not "nothing found."

`CANON.DIVERGENCE` checks event order against the declared branch point. `CANON.RAILS` is a Layer B note, info only, and it is not a fact check.

## Hard rules

- Never produce replacement prose.
- UNKNOWN is not a break and not an all-clear.
- Do not enforce proposed facts.
- Do not open a real book file during implementation or review.
