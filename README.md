# Skirt Steak

Experimental workspace for Python, SQL, notebooks, and agent-oriented project tooling.
This repo is intentionally iterative, so structure and workflows will continue to evolve.

## Repo Overview

### Top-Level Areas

- `.githooks/` - Git hook enforcement for local guardrails.
- `docs/` - Runbooks and workflow documentation.
- `notebooks/` - Jupyter notebooks for exploration.
- `python/` - Python projects and scripts.
- `sql/` - SQL scripts and data work.
- `tools/` - Utility scripts, including workflow guardrail helpers.
- `Sensitive/` - Local-only credentials/tokens (never stage this path).

### Key Projects

- `python/Project/Gem_Factory/`
- Gem authoring and sync workflows, including `Jons_Gems/clarity-concision-editor/`.
- `python/Project/Google_Maps_Linker/`
- Utilities that enrich Google Sheets rows with Google Maps links and place metadata.

## Project Index

- Root guardrails contract: [AGENTS.md](AGENTS.md)
- GitHub Copilot repo instructions: [.github/copilot-instructions.md](.github/copilot-instructions.md)
- Cross-model continuity template: [handoff-template.md](handoff-template.md)
- Cursor project skills (keyword-triggered): [.cursor/skills/](.cursor/skills/)
- Handoff notes, public tier: [handoffs/README.md](handoffs/README.md)
- Secrets layout (gitignored contents): [Sensitive/README.md](Sensitive/README.md)
- Workflow runbook: [docs/workflow-guardrails.md](docs/workflow-guardrails.md)
- Guardrail scripts reference: [tools/workflow_guardrails/README.md](tools/workflow_guardrails/README.md)
- Google Maps Linker guide: [python/Project/Google_Maps_Linker/README.md](python/Project/Google_Maps_Linker/README.md)
- Clarity & Concision Editor gem: [python/Project/Gem_Factory/Jons_Gems/clarity-concision-editor/README.md](python/Project/Gem_Factory/Jons_Gems/clarity-concision-editor/README.md)

## Handoff Convention

- Say "checkpoint" to write a handoff; say "pickup" to resume from one.
- Notes are two-tier: full detail in `Sensitive/handoffs/` (never committed), sanitized thread heads in `handoffs/` (tracked).
- Name handoffs `YYYYMMDD-HHMM-<thread>.md` and keep one thread per line of work.
- Include objective, current state, decisions, constraints, next actions, and a short resume prompt.
- Treat handoffs as continuity artifacts, not full transcripts.
- This repo is public. A pushed branch is published, so keep sensitive detail in the private tier.

## What Each File Does

- [AGENTS.md](AGENTS.md) - Mandatory repo safety rules for branches, git commands, and protected workflows.
- [.github/copilot-instructions.md](.github/copilot-instructions.md) - Repo-scoped behavior guide for GitHub Copilot, including decision-quality and market-analysis guardrails.
- [handoff-template.md](handoff-template.md) - Reusable template for handing work between AI models without losing the reasoning context.
- [docs/workflow-guardrails.md](docs/workflow-guardrails.md) - Full operational runbook with setup, daily flow, and troubleshooting for local guardrails.
- [tools/workflow_guardrails/README.md](tools/workflow_guardrails/README.md) - Reference for helper scripts that enforce or diagnose workflow guardrails.

## Quick Start (Local Python + DuckDB)

1. Create a virtual environment:
```powershell
python -m venv .venv
```
2. Activate it (Windows PowerShell):
```powershell
.\.venv\Scripts\Activate.ps1
```
3. Install baseline packages:
```powershell
pip install duckdb pandas black pylint
```
4. Start from `python/duckdb_starter.py` for local DuckDB examples.

## Git Guardrails (v2 Summary)

- Protected branches: `main`, `master`
- Working branch patterns: `^feature/[a-z0-9-]{3,40}$` (local) or `^cursor/[a-z0-9-]+-[a-z0-9]+$` (Cloud Agents)
- Recommended sync command on divergence: `git pull --rebase`
- `git push --force-with-lease` is conditional and only for agent-owned `feature/*` or `cursor/*` branches
- If a command is destructive or unclear, block and escalate instead of guessing

See [AGENTS.md](AGENTS.md) and [docs/workflow-guardrails.md](docs/workflow-guardrails.md) for full policy and decision rules.
