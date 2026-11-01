---
name: health-check
description: Read-only health check for skirt_steak. Trigger when the user asks for a "health check", "repo health", or to run the repo checks without changing anything. Report pass, fail, or did not run for each check. Do not apply to ordinary implementation tasks.
---

# Health Check

Run the repo checks and report what actually happened. Change nothing.

Do not install packages, edit files, stage, commit, push, sync, delete, or change git config. Do not run `setup-hooks` or `preflight --dry-run-sync`. Do not create credential files to flip a failure.

From the repo root, `bash tools/workflow_guardrails/health-check.sh`. On Windows, `powershell -ExecutionPolicy Bypass -File .\tools\workflow_guardrails\health-check.ps1`. Both call `tools/workflow_guardrails/health_check.py`. The script takes no arguments.

Each check is `PASS`, `FAIL`, or `DID_NOT_RUN`, with the command. `DID_NOT_RUN` is not a pass. `overall: success` appears only when every check is `PASS`. Quote the output. Do not invent a pass for a check that did not run.

The checks are the lint job in `.github/workflows/guardrails.yml` (syntax, the three test suites, the fanfic gitignore step, ruff, black, pylint) and `preflight`. Pylint is run without `--exit-zero`. Handoff notes are not an input.
