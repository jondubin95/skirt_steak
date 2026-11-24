---
thread: gmail-delayed-send
status: active
created: 2026-11-24T20:16Z
supersedes: handoffs/archive/gmail-delayed-send/20261124-1957-gmail-delayed-send.md
private_detail: null
---

# Round-2 sticky Hold fixes, still not deployed

## Objective

Close the round-2 holes in sticky Hold: pruning, per-thread incompleteness, and an alert throttle that does not depend on script properties. Do not deploy. Do not merge. Do not touch Gmail.

## Current State

- Branch `cursor/gmail-delayed-send-opt-out-dea1`, pull request 27. Not merged. Not deployed. Not live-tested.
- Pruning requires two consecutive `getDraft` not-found results. One unreadable draft blocks only its thread, or the mailbox for three passes if the thread cannot be identified.
- Failure alerts use `CacheService`, then minute 0 of the hour if the cache cannot be written.
- `node apps_script/gmail_delayed_send/stand_in_test.mjs`: 92 tests, `all assertions passed`.

## Key Decisions Already Made

- Decision: version the release label id as `delayedSendReleaseNowLabelId` and ignore `delayedSendReleaseLabelId`.
- Why: 414016c could have stored a user's own `Release` label, and that build was never deployed.
- Tradeoff: a renamed `Release now` is not kept on reinstall. `Hold` and `Send failed` still survive a rename.

## Constraints and Guardrails

- Do not open a new PR. Do not merge. Do not deploy. Do not touch Gmail.

## Next Best Actions

- Next action: push and wait for Guardrails.
- After that: stop. Jon pastes `Code.gs` and runs install before any live test.

## Known Risks or Failure Modes

- A Hold no pass has saved can still be stripped and sent.
- If an unread draft's thread cannot be identified, after three passes other threads are no longer blocked, including a sibling whose thread was never learned.

## Prompt to Resume

Continue from pull request 27 on `cursor/gmail-delayed-send-opt-out-dea1` after the round-2 sticky Hold commit. Focus on Guardrails if it is not green, then stop. Avoid deploying, merging, a new PR, and any mailbox address or token. Validate with `node apps_script/gmail_delayed_send/stand_in_test.mjs` (92 tests).
