---
thread: market-decision-log
status: active
created: 2026-10-06T12:44Z
supersedes: null
private_detail: Sensitive/handoffs/20261006-1244-market-decision-log.md
---

# Market decision log

## Objective

Persist a market-analyst review as a local DuckDB row. The playbook stays under `Sensitive/`. Git keeps the schema, the summary query, and the CLI.

## Current State

- Pull request: https://github.com/jondubin95/skirt_steak/pull/14 on `feature/market-decision-log`.
- `05acfd3` adds the log. `02c53ce` publishes the board-secretary handoff head that was already on disk.
- `check` does not create a database. `record` stores a review only after the gates pass. `resolve` records whether the direction happened. `verify` compares the playbook hash.
- 24 unit tests passed, including resolve-leaves-evidence-untouched and a no-orphan scan. A live CLI pass in a temp directory matched those gates.
- `harness-hardening` and `msjc-board-secretary` are marked done in this checkpoint. Do not restart them.

## Key Decisions Already Made

- The CLI checks that fields agree. It does not check that a claim is true. Do not relabel a claim, flip `core`, or invent a `basis_ref` to clear `ready`.
- Narrative-only evidence, including an empty claim list, can be stored only as `hard-blocked`. `ready` requires at least one core claim, and every core claim must be `data-backed`.
- `outcome` means the thesis direction, not whether the verdict was wise.
- Evidence fetchers, price history, brokers, sizing, and order entry stay out. So do another minutes-writer pass, Maps-linker header cleanup, blocking black/pylint, and branch protection on `main`.

## Constraints and Guardrails

- Do not commit anything under `Sensitive/` except `Sensitive/README.md`.
- The database file is gitignored. A missing parent directory is created by `record`, not by `check`.
- DuckDB allows one writer. Close other sessions before `record` or `resolve`.

## Files / Artifacts / Sources

- CLI: `python/decision_log/record.py`
- Docs: `python/decision_log/README.md`
- Schema and summary: `sql/decision_log/`
- Skill: `.cursor/skills/paranoid-market-analyst/SKILL.md`
- Private counterpart: `Sensitive/handoffs/20261006-1244-market-decision-log.md`

## Next Best Actions

- Watch CI on pull request #14. Merge only if the user asks.
- Leave the deferred products alone until the user asks for them.

## Known Risks or Failure Modes

- A model can still mark a narrative claim `data-backed`. The refusal is an instruction, not a control.

## Prompt to Resume

Continue from pull request #14 on `feature/market-decision-log`. Focus on CI or review comments. Avoid `Sensitive/` contents, evidence fetchers, brokers, sizing, and the minutes writer, Maps linker, lint, and branch-protection work that was left out. Validate with `python -m unittest discover -s python/decision_log/tests -p "test_*.py"`. Do not restart `harness-hardening` or `msjc-board-secretary`.
