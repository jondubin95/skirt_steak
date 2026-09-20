# Workflow Guardrail Scripts

Scripts in this folder are non-destructive checks and setup helpers. Each one ships in two forms: PowerShell (`.ps1`, Windows) and Bash (`.sh`, Linux/macOS/Cloud Agents). Both implement the same checks.

## Scripts

- `setup-hooks.ps1` / `setup-hooks.sh`
  - Configures `core.hooksPath` to `.githooks`.
- `preflight.ps1` / `preflight.sh`
  - Validates branch, required paths, and sync script/source paths.
  - Supports optional `-DryRunSync` (PowerShell) / `--dry-run-sync` (Bash).
- `diagnostics.ps1` / `diagnostics.sh`
  - Shows branch status, staged files, hooks path, and sensitive-file staging status.

## Usage (Windows)

From repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\workflow_guardrails\setup-hooks.ps1
powershell -ExecutionPolicy Bypass -File .\tools\workflow_guardrails\preflight.ps1
powershell -ExecutionPolicy Bypass -File .\tools\workflow_guardrails\preflight.ps1 -DryRunSync
powershell -ExecutionPolicy Bypass -File .\tools\workflow_guardrails\diagnostics.ps1
```

## Usage (Linux / macOS / Cloud Agents)

From repo root:

```bash
bash tools/workflow_guardrails/setup-hooks.sh
bash tools/workflow_guardrails/preflight.sh
bash tools/workflow_guardrails/preflight.sh --dry-run-sync
bash tools/workflow_guardrails/diagnostics.sh
```

## Caution: `setup-hooks.sh` on Cloud Agent VMs

Cursor Cloud Agent VMs point `core.hooksPath` at Cursor's own agent-hooks wrapper (under `~/.cursor/agent-hooks/...`), not `.githooks`. Running `setup-hooks.sh`/`setup-hooks.ps1` on a Cloud Agent overwrites that value with `.githooks`, which drops whatever the platform wrapper does. Cloud Agents should rely on `AGENTS.md` and the CI checks in `.github/workflows/guardrails.yml` instead of running `setup-hooks` there. Restore the original value if you run it by mistake:

```bash
git config core.hooksPath "$(cat /path/to/original/value)"  # or unset with: git config --unset core.hooksPath
```

Run `git config --get core.hooksPath` before and after to compare.
