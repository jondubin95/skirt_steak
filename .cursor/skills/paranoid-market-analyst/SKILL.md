---
name: paranoid-market-analyst
description: Adversarial Decision Playbook for MMA prediction markets and options trading. Trigger only when the user's message contains "bet", "wager", "moneyline", "trade", "option", "call spread", "position", "thesis", or otherwise makes a directional claim about a market outcome. Do not apply to general coding or writing requests.
---

# Paranoid Market Analyst

Require a Decision Playbook before treating a directional trade, bet, position, or market-outcome thesis as ready.

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

Verdict tokens are exactly `ready`, `not ready`, and `hard-blocked`.

- No `data-backed` claim and no `plausible but unverified` claim: only `hard-blocked`. That includes an empty claim list and a thesis whose claims are all `narrative-only`.
- No `data-backed` claim, but at least one `plausible but unverified` claim: only `not ready`.
- At least one `data-backed` claim: `not ready` is allowed. `ready` is allowed only when at least one claim has `core` true and every core claim is `data-backed`. `hard-blocked` is refused.
- A measured claim that still fails the base rate, the opposing case, or invalidation is `not ready`. `hard-blocked` means the evidence cannot support a review.
- State what evidence is missing and what would make the thesis reviewable.
- When the verdict is `ready` and any claim is `narrative-only`, name those claims in the chat reply.

## Recording

The CLI checks that the JSON fields agree. It does not check that a claim is true. Do not relabel a claim, flip `core`, or invent a `basis_ref` to make `ready` legal. On a refusal, fix the classification or accept the verdict the gates allow.

1. Mint a canonical UUID: lowercase, hyphenated, no braces.
2. Write the playbook to `Sensitive/decisions/playbooks/<id>.md`. Templates are in `references/playbooks.md`. Use the short form for smaller decisions and the long form for larger ones.
3. Write JSON in the shape of `sql/decision_log/example_inbox.json` to `Sensitive/decisions/inbox/<id>.json`. Include `observed_at` (ISO-8601 with a timezone) and `market_snapshot` (the quote that was seen). Put `basis_ref` on every `data-backed` claim. Set `supersedes` only when this review replaces an earlier id. Do not include `playbook_path`.
4. Run `check`, then `record`. A passing `check` does not mean `record` will succeed.
5. Report the verdict and the decision id.
6. When the user later asks how the thesis played out, offer `resolve` for that id, judged against the stored snapshot. `right`, `wrong`, and `inconclusive` describe the direction, not the verdict. When the user asks whether the playbook file still matches the row, offer `verify`.

From the repo root:

```powershell
python python/decision_log/record.py check --input Sensitive/decisions/inbox/<id>.json
python python/decision_log/record.py record --input Sensitive/decisions/inbox/<id>.json
python python/decision_log/record.py resolve --id <uuid> --outcome right --notes "..."
python python/decision_log/record.py verify --id <uuid>
```
