---
thread: guardrails-skills-hook
status: active
created: 2026-11-01T14:19Z
supersedes: null
private_detail: null
---

# Skill shape and demo hook

## Objective

Give four project skills one shared shape, add a fail-open demonstration hook that blocks edits to one dummy fixture, and record three guardrail decisions the repo already evidences.

## Current State

- Branch `feature/guardrails-skills-hook`, opened against `main`. Not merged.
- `clarity-concision-editor`, `paranoid-market-analyst`, `msjc-board-secretary`, and `fanfic-story-doctor` use purpose, inputs, steps, limits, and report. Trigger text and the old rules are still there.
- `.cursor/hooks.json` runs `python3 .cursor/hooks/protect_demo_fixture.py` on `preToolUse` for `Write|Delete|StrReplace`. `failClosed` is false. The only denied path is `python/cursor_hook_demo/fixtures/hook_demo_protected_file.txt`.
- `docs/decision-notes.md` has three entries, from commits `3fcf7d0`, `ff6a004`, `cd84a23`, `4d36d3e`, and `290611e`.
- Hook unit tests passed (9). `ruff check python .cursor/hooks` passed. Board secretary (28), decision log (25), and fanfic story doctor (145) tests passed. `preflight.sh` exited 1 because the local client-secrets file and its parent directories are not on this machine. They were not created.
- After `hooks.json` was added, an edit to the fixture in this same Cloud Agent session was not blocked. The script denies that path when invoked on stdin. Editor enforcement was not observed here.

## Key Decisions Already Made

- The demo hook fails open. Malformed input exits 0 with `{"permission":"allow"}`. A forced error exits 1 with empty stdout. `failClosed` stays false so a crash cannot freeze other edits. Exit 0 with invalid JSON would still block, so the error path prints no JSON.
- `StrReplace` is in the matcher even though the hooks reference does not list it. Unknown tool names and unknown path keys are allowed.
- `operating-behavior` and `handoff-notes` were not reshaped. Another change is editing those files, plus `AGENTS.md`, the copilot instruction files, and `docs/workflow-guardrails.md`.

## Constraints and Guardrails

- Do not merge. Jon reviews and merges.
- Do not edit `operating-behavior`, `handoff-notes`, `AGENTS.md`, the copilot instruction files, or `docs/workflow-guardrails.md` in this thread.
- Do not stage anything under `Sensitive/`. Nothing was withheld into a private supplement.
- The hook is a demonstration, not a security control. Do not point it at real files.

## Files / Artifacts / Sources

- `.cursor/skills/README.md` and the four skill files named above.
- `.cursor/hooks.json`, `.cursor/hooks/protect_demo_fixture.py`, `docs/cursor-hook-demo.md`.
- `python/cursor_hook_demo/tests/test_protect_demo_fixture.py` and the fixture beside it.
- `docs/decision-notes.md`, `README.md`, `.github/workflows/guardrails.yml`.
- Hook format checked against https://cursor.com/docs/hooks.

## Next Best Actions

- Review the pull request. Do not merge unless Jon asks.
- After the other skill edit lands, apply the same five headings to `operating-behavior` and `handoff-notes`.
- In a fresh Cursor session, confirm an edit to the fixture is denied and that a broken hook still allows another file.

## Known Risks or Failure Modes

- This session did not show the editor loading the new project hook. Script tests are the evidence that exists.
- A file edit whose path is not in `path` or `file_path`, or whose tool name is not `Write`, `Delete`, or `StrReplace`, is allowed. Shell commands are not inspected.
- `preflight.sh` cannot pass on a machine that has no local client secrets. That failure is not a regression in this change.

## Prompt to Resume

Continue from branch `feature/guardrails-skills-hook`. Focus on review comments. Avoid merging, and avoid edits to `operating-behavior`, `handoff-notes`, `AGENTS.md`, the copilot instruction files, and `docs/workflow-guardrails.md`. Validate with `python -m unittest discover -s python/cursor_hook_demo/tests -p "test_*.py"` and with `docs/cursor-hook-demo.md`.
