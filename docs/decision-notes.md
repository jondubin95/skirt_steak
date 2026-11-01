# Decision notes

Short records of guardrail choices already evidenced in this repo. Each note says what failed or was risky, what changed, where to read the evidence, and the date of that change. Do not add a note for a failure this file cannot point at.

## Template

- What failed or was risky:
- What changed:
- Evidence:
- Date:

## Keyword-triggered skills, not slash-only and not always-on

- What failed or was risky: `disable-model-invocation` made every project skill slash-invoked only, so a prompt would not load the skill unless someone typed `/skill-name`.
- What changed: That flag was removed the same day. Skills stay off until the prompt contains their trigger keywords, instead of requiring `/skill-name` or being always-on.
- Evidence: Commit `3fcf7d0` ("Make project skills slash-invoked only.") and commit `ff6a004` ("Switch project skills to keyword-triggered auto invocation."). `.cursor/skills/README.md` still describes that keyword-triggered shape.
- Date: 2026-09-20

## Do not point Cloud Agent git hooks at `.githooks`

- What failed or was risky: `setup-hooks` sets `core.hooksPath` to `.githooks`. On a Cloud Agent VM that replaces Cursor's own agent-hooks wrapper.
- What changed: The guardrail scripts tell Cloud Agents not to run `setup-hooks`. Branch naming and `Sensitive/` checks are enforced in CI, which accepts both `feature/*` and `cursor/<name>-<id>`.
- Evidence: Commit `cd84a23` ("Add CI guardrails workflow and bash ports of guardrail scripts.") and commit `4d36d3e` ("Align branch policy with Cloud Agents and scaffold Sensitive/."). The caution is in `tools/workflow_guardrails/README.md` and `docs/workflow-guardrails.md`.
- Date: 2026-09-20

## Case-variant `Sensitive/` paths stay blocked

- What failed or was risky: A case-sensitive path filter would miss `sensitive/` or `SENSITIVE/`. A differently cased README could look like the one allowed scaffold file.
- What changed: CI matches `Sensitive/` without regard to case. The README allowlist stays the exact path `Sensitive/README.md`, so a differently cased README is still blocked.
- Evidence: Commit `290611e` ("Match Sensitive paths in CI without regard to case."). The check and the comment are in `.github/workflows/guardrails.yml`.
- Date: 2026-10-25
