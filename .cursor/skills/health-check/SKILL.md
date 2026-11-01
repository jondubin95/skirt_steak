---
name: health-check
description: Read-only health check for skirt_steak. Trigger when the user asks for a "health check", "repo health", or to run the repo checks without changing anything. Report pass, fail, or did not run for each check. Do not apply to ordinary implementation tasks.
---

# Health Check

Run the repo checks and report what actually happened. Change nothing.

Do not install packages, edit files, stage, commit, push, sync, delete, or change git config as part of this skill. Do not run `setup-hooks` or `preflight --dry-run-sync`. Do not create credential files to flip a failure. Do not weaken a check, a hook, or CI to get a clean result.

From the repo root:

```bash
bash tools/workflow_guardrails/health-check.sh
```

On Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\workflow_guardrails\health-check.ps1
```

The script takes no arguments. It prints one block per check:

- `PASS` — that command ran and exited 0
- `FAIL` — that command ran and exited non-zero
- `DID_NOT_RUN` — that command was not executed. The reason is on the next line. This is not a pass.

`overall: success` appears only when every check is `PASS`. Otherwise the script exits non-zero and prints `overall: not success`. Quote the script output. Do not turn a `FAIL` or `DID_NOT_RUN` into a pass in the summary.

The command list lives in the script. It mirrors the lint job in `.github/workflows/guardrails.yml`, then runs `preflight.sh` and `diagnostics.sh`. Pylint is run without the workflow's `--exit-zero`, so issues are `FAIL` while the role stays `advisory`. Pytest adds `-p no:cacheprovider` so the run does not write `.pytest_cache/`. Syntax checking compiles with `py_compile` into a temp directory so it does not write `__pycache__/`.

`PASS` on diagnostics means the script finished. Read its branch-status line. `FAIL` on preflight because a credential file is missing is a real failure of that check. Say so. Do not treat it as CI, and do not invent the file.

If the script itself cannot be started, say the health check did not run. Do not invent a passing report. You may run the individual commands from the script only when you label each one with the command you actually used and the same three outcomes.
