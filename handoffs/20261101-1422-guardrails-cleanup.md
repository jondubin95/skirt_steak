---
thread: guardrails-cleanup
status: active
created: 2026-11-01T14:22Z
supersedes: null
private_detail: null
---

# Guardrails cleanup

## Objective

One coding-rules source, a read-only health check, owner approval beyond git, a pickup re-check, and a done checklist.

## Current State

- Branch `feature/guardrails-cleanup`, based on `main` at `f6ba435`. Review is a pull request into `main`. Do not merge it.
- `.github/copilot-instructions.md` is the coding-rules source. The root shim and `operating-behavior` point at it.
- `bash tools/workflow_guardrails/health-check.sh` and `health-check.ps1` both ran. Result: `pass=8 fail=3 did_not_run=0`, `overall: not success`.
- Blocking checks passed: syntax (43 files), board-secretary tests (28), decision-log tests (25), fanfic tests (145), ruff, and the fanfic gitignore check.
- Failures: advisory `black --check` (25 existing files), advisory pylint (5.73/10, exit 30), and preflight because `Sensitive/credentials.json` and `Sensitive/google/` are absent here. Those credential paths were not created.
- Nothing was withheld.

## Key Decisions Already Made

- The root Copilot file was already a pointer. The skill restated the rules and did not contradict them. The handoff requirement that lived only in the skill is now in the canonical file.
- The health check is not part of CI. Adding it would change a CI rule.
- A working-branch push stays under the existing git rules. Merge, delete, external write, and weakening a check still need a fresh OK.
- `handoff-private-tier` stays `active`. Its note still says pull request 20 is open. Pickup re-checks instead of editing that note.

## Next Best Actions

- Owner reviews the pull request for this branch and merges it. Do not merge from a later session unless the owner says so again in that conversation.
- Leave the black and pylint failures alone unless a later request asks to format or lint them.

## Prompt to Resume

Continue from `feature/guardrails-cleanup` and its pull request against `main`. Focus on review comments. Avoid merging, editing `Sensitive/`, and weakening CI, hooks, or the health check to turn a failure into a pass. Validate with `bash tools/workflow_guardrails/health-check.sh` and report pass, fail, or did not run for each line. `overall: success` is the only clean result.
