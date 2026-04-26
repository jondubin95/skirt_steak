# Repository Guardrails

These guardrails are mandatory for local development and automation agents.

## Objective

Maximize delivery speed while preventing loss of local work, unsafe history rewrites, and protected-branch violations.

## Branch and Merge Policy

- Never commit directly to `main` or `master`.
- Never push directly to `main` or `master`.
- Always create a feature branch first.
- Branch names must match: `^feature/[a-z0-9-]{3,40}$`.
- Merge through a PR into `main`.

## Command Classification

### Allowed

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
- `git pull --rebase` (recommended when branches diverge)

### Conditional

- `git push --force-with-lease` is allowed only when all are true:
- Branch matches `feature/*`
- Branch is agent-owned (created by current agent workflow and not shared)
- No protected/shared branch impact

### Blocked By Default

- `git reset --hard`
- `git clean -fdx`
- `git checkout -- <path>` when it discards changes
- Destructive `git reset` patterns that discard local work
- Any force push to `main` or `master`
- Any direct commit/push on `main` or `master`

## Safety Heuristic

- If a command rewrites history, discards local changes, or deletes data, treat it as destructive.

## Uncertainty Rule

- If command safety is unclear, block and escalate to the user with rationale.
- Do not guess and do not try random alternatives.

## Override Decision Rule

- Safeguard override is allowed only if all are true:
- Operation is on an agent-owned `feature/*` branch
- Purpose is recovery or cleanup
- No shared/protected branch is affected
- If any condition fails, stop and ask the user.

## Commit Hygiene

- Avoid rapid low-signal commit loops.
- Batch logically related changes into meaningful commits.

## Secret Handling

- Store credentials/tokens only under `Sensitive/`.
- Never stage files under `Sensitive/`.
- Current hook protection blocks staged paths that match `Sensitive/`, but this is not a complete secret-scanning system.

## Recommended Command Flow

1. Run hook setup once: `powershell -ExecutionPolicy Bypass -File .\tools\workflow_guardrails\setup-hooks.ps1`
2. Create a valid feature branch: `git switch -c feature/<short-description>`
3. Run preflight before sync and commit: `powershell -ExecutionPolicy Bypass -File .\tools\workflow_guardrails\preflight.ps1`
4. Use diagnostics if something looks off: `powershell -ExecutionPolicy Bypass -File .\tools\workflow_guardrails\diagnostics.ps1`
5. Sync feature branch with `git pull --rebase` when diverged.
6. Push feature branch and open a PR.

## Runbook

See `docs/workflow-guardrails.md` for full workflow, decision scenarios, and troubleshooting.
