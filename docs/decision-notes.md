# Decision notes

What failed or was risky, what changed, the evidence, and the date. Record only what the repo already shows.

## Template

- What failed or was risky:
- What changed:
- Evidence:
- Date:

## Keyword-triggered skills

- What failed or was risky: `disable-model-invocation` made skills slash-only, so they did not load unless someone typed `/skill-name`.
- What changed: That flag was removed the same day. Skills load when the prompt contains their keywords.
- Evidence: Commits `3fcf7d0` and `ff6a004`. `.cursor/skills/README.md`.
- Date: 2026-09-20

## Cloud Agent git hooks

- What failed or was risky: `setup-hooks` sets `core.hooksPath` to `.githooks`, which replaces Cursor's agent-hooks wrapper on a Cloud Agent VM.
- What changed: Cloud Agents are told not to run `setup-hooks`. CI enforces branch names and `Sensitive/` instead.
- Evidence: Commits `cd84a23` and `4d36d3e`. `tools/workflow_guardrails/README.md`.
- Date: 2026-09-20

## Case-variant Sensitive paths

- What failed or was risky: A case-sensitive filter would miss `sensitive/` or `SENSITIVE/`, and a differently cased README could look allowed.
- What changed: CI matches `Sensitive/` without regard to case. The allowlist stays the exact path `Sensitive/README.md`.
- Evidence: Commit `290611e`. `.github/workflows/guardrails.yml`.
- Date: 2026-10-25
