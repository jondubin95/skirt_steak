---
thread: guardrails-cleanup
status: active
created: 2026-11-01T14:22Z
supersedes: null
private_detail: null
---

# Guardrails cleanup

## Objective

One coding-rules source, a read-only health check, approvals beyond git, a pickup re-check, and a done checklist.

## Current State

- Pull request 22 on `feature/guardrails-cleanup`. Do not merge.
- Health-check logic is `tools/workflow_guardrails/health_check.py`. The shell scripts only call it. Handoff notes are not an input.
- Latest run: `pass=7 fail=3 did_not_run=0`, `overall: not success`. Passes: syntax (44 files), demo hook tests (3), board secretary (28), decision log (25), fanfic (145), fanfic gitignore, ruff. Fails: black (25 existing files), pylint (5.73/10, exit 30), preflight (credential files absent; not created).
- Pull request 21's commits are on this branch. `operating-behavior` and `handoff-notes` use the same five headings. Do not close pull request 21 from here.

## Next Best Actions

- Owner reviews pull request 22 and merges it. Do not merge unless the owner says so again in that conversation.

## Prompt to Resume

Continue from pull request 22. Focus on review comments. Avoid merging, editing `Sensitive/`, and weakening a check to force `overall: success`. Validate with `bash tools/workflow_guardrails/health-check.sh`.
