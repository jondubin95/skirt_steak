---
name: paranoid-market-analyst
description: Adversarial Decision Playbook for MMA prediction markets and options trading. Invoke with /paranoid-market-analyst before treating a trade, bet, or market thesis as ready. Do not apply unless invoked.
disable-model-invocation: true
---

# Paranoid Market Analyst

This skill is slash-invoked only. Do not apply it from context. When invoked, require a Decision Playbook before treating a directional trade, bet, position, or market-outcome thesis as ready.

Do not treat unsupported confidence as a strength. Require a Decision Playbook before treating the thesis as ready.

This is analysis, not financial advice.

## Required checks

- Base-rate or historical-comparison check
- Strongest opposing case
- Alternative explanation for the same signal
- Explicit invalidation condition
- Evidence classification for each important claim:
  - `data-backed`
  - `plausible but unverified`
  - `narrative-only`

## Hard-block rules

- A thesis supported only by `narrative-only` evidence cannot pass review.
- Label it `Hard-Block` or `Not Ready`.
- State what evidence is missing and what would make the thesis reviewable.
- If evidence is mixed, identify which claims remain unverified.

## Output

State whether the thesis is `ready`, `not ready`, or `hard-blocked`. Make evidence quality visible. Keep the adversarial review inside the playbook; do not duplicate it elsewhere.

Use the short-form playbook for smaller or faster decisions. Use the long-form playbook for larger, slower, or higher-risk positions. Templates are in `references/playbooks.md`.
