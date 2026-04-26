# Workflow Guardrail Scripts

Scripts in this folder are non-destructive checks and setup helpers.

## Scripts

- `setup-hooks.ps1`
  - Configures `core.hooksPath` to `.githooks`.
- `preflight.ps1`
  - Validates branch, required paths, and sync script/source paths.
  - Supports optional `-DryRunSync`.
- `diagnostics.ps1`
  - Shows branch status, staged files, hooks path, and sensitive-file staging status.

## Usage

From repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\workflow_guardrails\setup-hooks.ps1
powershell -ExecutionPolicy Bypass -File .\tools\workflow_guardrails\preflight.ps1
powershell -ExecutionPolicy Bypass -File .\tools\workflow_guardrails\preflight.ps1 -DryRunSync
powershell -ExecutionPolicy Bypass -File .\tools\workflow_guardrails\diagnostics.ps1
```
