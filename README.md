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
- Workflow runbook: [docs/workflow-guardrails.md](docs/workflow-guardrails.md)
- Guardrail scripts reference: [tools/workflow_guardrails/README.md](tools/workflow_guardrails/README.md)
- Google Maps Linker guide: [python/Project/Google_Maps_Linker/README.md](python/Project/Google_Maps_Linker/README.md)
- Clarity & Concision Editor gem: [python/Project/Gem_Factory/Jons_Gems/clarity-concision-editor/README.md](python/Project/Gem_Factory/Jons_Gems/clarity-concision-editor/README.md)

## Handoff Convention

- For substantial work, create a handoff note in `handoffs/` using `handoff-template.md`.
- Name handoffs with a short topic and timestamp for easy recovery.
- Include objective, current state, decisions, constraints, next actions, and a short resume prompt.
- Treat handoffs as continuity artifacts, not full transcripts.

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
- Feature branch pattern: `^feature/[a-z0-9-]{3,40}$`
- Recommended sync command on divergence: `git pull --rebase`
- `git push --force-with-lease` is conditional and only for agent-owned `feature/*` branches
- If a command is destructive or unclear, block and escalate instead of guessing

See [AGENTS.md](AGENTS.md) and [docs/workflow-guardrails.md](docs/workflow-guardrails.md) for full policy and decision rules.
