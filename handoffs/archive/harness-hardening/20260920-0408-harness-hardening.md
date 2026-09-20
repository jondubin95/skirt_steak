---
thread: harness-hardening
status: active
created: 2026-09-20T04:08Z
supersedes: null
private_detail: Sensitive/handoffs/20260920-0408-harness-hardening.md
---

# Harness Hardening

## Objective

Absorb the repository's existing agent conventions into Cursor skills, then harden the surrounding harness before starting a new project.

## Current State

Done and pushed on `cursor/absorb-repo-skills-3803` (PR #11, draft, CI green):

- Four keyword-triggered project skills in `.cursor/skills/`: `handoff-notes`, `clarity-concision-editor`, `paranoid-market-analyst`, `operating-behavior`.
- CI workflow `.github/workflows/guardrails.yml`: branch-name check (accepts `feature/*` and `cursor/*-<id>`), `Sensitive/` block, PR-body placeholder check, blocking `py_compile`, advisory `black`/`pylint`.
- Bash ports of the three PowerShell guardrail scripts in `tools/workflow_guardrails/`.
- Branch policy reconciled across `AGENTS.md`, `docs/workflow-guardrails.md`, CI, and the PR template.
- `Sensitive/README.md` scaffold tracked; everything else under `Sensitive/` blocked by `.gitignore`, pre-commit, and CI.
- Two-tier handoff workflow implemented (this note is the first public head).

## Key Decisions Already Made

- Skills are keyword-triggered, not slash-only and not always-on. Tradeoff: relies on description matching, so triggers may need tuning.
- Handoffs are two-tier: private `Sensitive/handoffs/` and public sanitized `handoffs/`. The repo is public, so candid detail stays local. Tradeoff: Cloud Agents only see the sanitized tier.
- Checkpoint writes both tiers automatically with no confirmation gate. Tradeoff: a push publishes immediately, and no CI secret-scan backstop was added.
- Each checkpoint writes a new immutable file; thread continuity comes from frontmatter plus `INDEX.md` and `archive/`.
- Notes land on the current working branch and reach `main` through the normal PR flow.
- Pre-existing local notes were not imported; the convention starts fresh.

## Open Questions

- Flip `black`/`pylint` from advisory to blocking after reformatting existing Python?
- Add a pytest scaffold before or alongside the new project?
- Is branch protection enabled on `main`? Not verifiable from the agent environment (API returned 403).

## Constraints and Guardrails

- Never commit under `Sensitive/` except `Sensitive/README.md`.
- Working branches: `feature/[a-z0-9-]{3,40}` locally, `cursor/<name>-<id>` for Cloud Agents.
- No direct commits or pushes to `main`/`master`.
- Do not run `tools/workflow_guardrails/setup-hooks.sh` on a Cloud Agent VM; it overwrites Cursor's own `core.hooksPath`.

## Files / Artifacts / Sources

- `.cursor/skills/` — four skills plus README
- `.github/workflows/guardrails.yml`
- `tools/workflow_guardrails/{setup-hooks,preflight,diagnostics}.sh`
- `AGENTS.md`, `docs/workflow-guardrails.md`, `README.md`, `.github/pull_request_template.md`
- `Sensitive/README.md`, `handoffs/README.md`, `handoffs/INDEX.md`
- PR: https://github.com/jondubin95/skirt_steak/pull/11

## Next Best Actions

- Next: review PR #11 and mark it ready when satisfied.
- After that: enable branch protection on `main` in GitHub Settings (the agent cannot do this).
- Optional: pytest scaffold; reformat Python and make lint blocking; CI secret-scan on `handoffs/`.
- Then: start the new project, folding project-specific harness needs into this setup.

## Known Risks or Failure Modes

- Auto-writing the public tier without a secret-scan backstop relies on the sanitization rules alone.
- Keyword triggers may misfire; "checkpoint" could collide with ML model-checkpoint discussion in this Python/data repo.
- Local hooks are inactive unless a contributor runs setup-hooks. CI is the real backstop, and CI does not prevent a merge without branch protection.

## Prompt to Resume

Continue from PR #11 on `cursor/absorb-repo-skills-3803`, which is green and awaiting review. Focus on whatever the review surfaces, or on the new project being planned. Avoid touching `main` directly, running setup-hooks on a Cloud Agent VM, or committing anything under `Sensitive/`. Validate with `gh run list` for CI and by re-reading `.cursor/skills/README.md` for current trigger keywords.
