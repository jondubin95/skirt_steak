# Workflow Guardrails

This runbook adds a safe default workflow for this repository.

## Rules (Hard-Block)

- Do not commit directly on `main` or `master`.
- Do not stage files under `Sensitive/`.
- Do not push directly from `main` or `master`.

These rules are enforced by committed hooks in `.githooks/`.

## Agent Git Safety Protocol

### Branch Standard

- Branches must match `^feature/[a-z0-9-]{3,40}$`.
- Protected branches are `main` and `master`.
- Merge path is PR-only into `main`.

### Allowed Commands

- `git status`
- `git diff`
- `git log`
- `git show`
- `git fetch`
- `git add`
- `git commit`
- `git switch -c <branch>`
- `git push` to feature branches
- `git pull --ff-only`
- `git pull --rebase` (recommended when diverged)

### Conditional Commands

- `git push --force-with-lease` is allowed only when all are true:
- Branch is `feature/*`
- Branch is agent-owned (created by current agent workflow and not shared)
- No shared/protected branch impact

### Blocked By Default

- `git reset --hard`
- `git clean -fdx`
- `git checkout -- <path>` when it discards changes
- Destructive reset patterns that discard local work
- Any force push to protected branches
- Direct commit/push on protected branches

### Safety Heuristic

- If a command rewrites history, discards local changes, or deletes data, treat it as destructive.

### Uncertainty Fallback

- If command classification is unclear, block and escalate to the user with rationale.
- Do not guess and do not use random alternatives.

### Override Decision Rule

- Override is allowed only when all are true:
- Branch is agent-owned `feature/*`
- Purpose is recovery or cleanup
- No shared/protected branch impact
- If any condition fails, stop and ask the user.

### Commit Hygiene

- Avoid rapid low-signal commit loops.
- Batch logically related changes.

## One-Time Setup

From repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\workflow_guardrails\setup-hooks.ps1
```

Verify:

```powershell
git config --get core.hooksPath
```

Expected output: `.githooks`

## Daily Workflow

1. Create or switch to a feature branch:

```powershell
git switch -c feature/<short-topic>
```

2. Run preflight before Google Docs sync and before commit:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\workflow_guardrails\preflight.ps1
```

3. Optional dry-run of sync:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\workflow_guardrails\preflight.ps1 -DryRunSync
```

4. Run quick diagnostics anytime:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\workflow_guardrails\diagnostics.ps1
```

5. Commit/push from feature branch, then open PR into `main`.

## Scenario Validation (Policy Dry-Run)

- Diverged feature branch:
- Use `git pull --rebase`.
- Feature-branch history cleanup:
- `git push --force-with-lease` allowed only when ownership criteria pass.
- Protected branch push/force push:
- Always blocked.
- Unknown risky command:
- Treat as destructive and block.
- Ambiguous branch ownership:
- Block and escalate to the user.

## Standard Google Sync Commands

From repo root:

```powershell
.\.venv\Scripts\python.exe python\Project\Gem_Factory\tools\gdocs_sync\sync_gem_folder_to_gdocs.py `
  --src python\Project\Gem_Factory\Jons_Gems\clarity-concision-editor\internal\core\instructions `
  --title-prefix "Polish - " `
  --client-secrets Sensitive\credentials.json `
  --token Sensitive\google\gdocs_token.json `
  --map Sensitive\google\clarity-concision-editor.gdocs-map.json
```

From `python/Project/Gem_Factory`:

```powershell
..\..\..\.venv\Scripts\python.exe tools\gdocs_sync\sync_gem_folder_to_gdocs.py `
  --src Jons_Gems\clarity-concision-editor\internal\core\instructions `
  --title-prefix "Polish - " `
  --client-secrets ..\..\..\Sensitive\credentials.json `
  --token ..\..\..\Sensitive\google\gdocs_token.json `
  --map ..\..\..\Sensitive\google\clarity-concision-editor.gdocs-map.json
```

## Preflight Checklist

- Current branch is not `main`/`master`.
- `Sensitive/credentials.json` exists.
- Parent directories exist for:
  - `Sensitive/google/gdocs_token.json`
  - `Sensitive/google/clarity-concision-editor.gdocs-map.json`
- `python/Project/Gem_Factory/tools/gdocs_sync/sync_gem_folder_to_gdocs.py` exists.
- Sync source folder exists.

## Known Failures and Fixes

`--client-secrets not found`

- Fix the path, or place the file at:
  `C:\Users\jondu\Repos\skirt_steak\Sensitive\credentials.json`

`SERVICE_DISABLED` for `docs.googleapis.com`

- Enable Google Docs API in the same OAuth project as your client ID.
- Wait 2-5 minutes and retry.

`Invalid requests[0].deleteContentRange: The range should not be empty`

- Use the current `sync_gem_folder_to_gdocs.py` (this edge case is fixed).

Accidental commit on `main`

- Hook blocks it. Create a feature branch and commit there instead.

Sensitive file accidentally staged

- Hook blocks it.
- Unstage with: `git restore --staged Sensitive/*`

## Sensitive Path Limitation

- Current hook checks block staged paths matching `Sensitive/`.
- This is not a complete secret-scanning or data-loss-prevention system.
