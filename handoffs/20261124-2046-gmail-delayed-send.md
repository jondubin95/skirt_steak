---
thread: gmail-delayed-send
status: active
created: 2026-11-24T20:46Z
supersedes: handoffs/archive/gmail-delayed-send/20261124-2016-gmail-delayed-send.md
private_detail: null
---

# Armed marker before any send

## Objective

Stop the upgraded script from sending until `installDelayedGmailSend` writes `delayedSendArmedVersion`. Do not deploy. Do not merge.

## Current State

- Branch `cursor/gmail-delayed-send-opt-out-dea1`, pull request 27. Not deployed. Not live-tested.
- Saving the new code does not send. The live opt-out trigger returns until install arms version `2` and leaves one trigger.
- `node apps_script/gmail_delayed_send/stand_in_test.mjs`: 100 tests, `all assertions passed`.

## Constraints and Guardrails

- Do not open a new PR. Do not merge. Do not deploy. Do not touch Gmail.

## Prompt to Resume

Continue from pull request 27 on `cursor/gmail-delayed-send-opt-out-dea1`. Focus on Guardrails if it is not green, then stop. Avoid deploying, merging, and any mailbox access. Validate with `node apps_script/gmail_delayed_send/stand_in_test.mjs` (100 tests). Nothing sends until install has armed this version.
