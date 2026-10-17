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

Layer A runs local Python. It makes no model call. `--layer-b` adds `OOC.VOICE` and `CANON.RAILS` notes from the **mock** provider only: info, never a blocker, agreement is not correctness. A real provider is refused by gate G9 (`DOCTOR_G9_OPT_IN=1` after checking Cursor data/retention settings), and none is implemented yet.

```powershell
$env:DOCTOR_HOME = "$env:USERPROFILE\doctor-home"
python -m doctor run <work>
```

Run that from `python/fanfic_story_doctor` with `PYTHONPATH=src`, or install the package.

A rule that is not built is reported as **skipped**. Skipped is not "nothing found."

`CANON.DIVERGENCE` checks event order against the declared branch point. `CANON.RAILS` is a Layer B note, info only, and it is not a fact check.

## Hard rules

- Never produce replacement prose.
- UNKNOWN is not a break and not an all-clear.
- Do not enforce proposed facts.
- Do not open a real book file during implementation or review.
