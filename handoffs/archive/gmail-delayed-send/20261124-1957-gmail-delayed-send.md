---
thread: gmail-delayed-send
status: active
created: 2026-11-24T19:57Z
supersedes: handoffs/archive/gmail-delayed-send/20261124-1922-gmail-delayed-send.md
private_detail: null
---

# Sticky Hold fail-closed fixes, still not deployed

## Objective

Close the adversarial-review holes that could send a draft the user held, or leave a draft stuck with no alert. Do not deploy. Do not merge. Do not touch Gmail.

## Current State

- Branch `cursor/gmail-delayed-send-opt-out-dea1`, pull request 27. Fixes are local until this commit is pushed. Not merged. Not deployed. Not live-tested.
- `Release` was renamed to `Release now` and matches the stored label id only.
- Manual Hold removal needs a fresh `getDraft` and a second agreeing pass. Sticky maps are sharded and saved with `setProperties` before label changes and before send.
- `node apps_script/gmail_delayed_send/stand_in_test.mjs`: 77 tests, `all assertions passed`.

## Why This Matters

A held draft that sends is the failure this script exists to prevent. The first sticky Hold commit still had paths that forgot a hold or started the release clock on a stale read.

## Key Decisions Already Made

- Decision: fail closed and throw at most once an hour when state cannot be read, saved, or repaired.
- Why: a silent hold never pages anyone, and a silent forget sends mail.
- Tradeoff: a manual Hold removal waits one extra minute, and a full property store holds every draft until it fits.
- Decision: do not build an out-of-band registry for Hold that no pass has saved.
- Why: this script cannot see an edit that happens before the first successful save. That gap stays documented.

## Constraints and Guardrails

- Branch: `cursor/gmail-delayed-send-opt-out-dea1`. Do not open a new PR. Do not merge.
- Do not deploy to Apps Script and do not touch Gmail.
- Scopes stay `gmail.modify` and `script.scriptapp`.

## Files / Artifacts / Sources

- `apps_script/gmail_delayed_send/Code.gs`
- `apps_script/gmail_delayed_send/README.md`
- `apps_script/gmail_delayed_send/stand_in_test.mjs`
- Review notes were in the bot store `sticky-hold-review/` and are not in git.

## Next Best Actions

- Next action: push this commit and update PR 27. Wait for Guardrails.
- After that: Jon pastes `Code.gs` and runs `installDelayedGmailSend` before any live test.
- Optional follow-up: live-test rename, `Release now`, and an API edit after the first saved pass.

## Known Risks or Failure Modes

- A Hold added and stripped before any pass saves it can still send.
- If properties are down for the only pass that saw Hold, and an API edit strips Hold before the next successful save, that draft is unprotected. The failing pass itself does not send.
- One label read remains immediately before `send()`.

## Prompt to Resume

Continue from pull request 27 on `cursor/gmail-delayed-send-opt-out-dea1` after the sticky Hold fail-closed commit. Focus on Guardrails if it is not green, then stop. Avoid deploying, merging, opening a new PR, and any mailbox address or token. Validate with `node apps_script/gmail_delayed_send/stand_in_test.mjs` (77 tests) and do not treat the 2026-11-24 live rows as sticky-Hold proof.
