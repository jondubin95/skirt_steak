---
thread: gmail-delayed-send
status: done
created: 2026-11-24T13:26Z
supersedes: handoffs/archive/gmail-delayed-send/20261124-1311-gmail-delayed-send.md
private_detail: null
---

# Gmail delayed send

## Objective

Add a consumer-Gmail Apps Script that sends a draft once its current message is five minutes old and its thread has the send label.

## Current State

- Script, manifest, and README are in `apps_script/gmail_delayed_send/`.
- Pull request 26 is open. The script is not deployed.

## Key Decisions Already Made

- Decision: Age stays `GmailMessage.getDate()` on the current draft message.
- Why: `GmailDraft` has no last-updated getter. A save replaces the message.
- Tradeoff: Labeling an old draft does not start a new five-minute clock. A stored label-applied time was rejected because it would change that clock.

- Decision: Overlapping runs take `LockService.getScriptLock()` and skip if it is held. A daily recipient-quota error stops the rest of that run and fails the execution.
- Why: A slow pass can overlap the next minute. Quota retries inside one pass only burn the trigger-time budget.
- Tradeoff: No third-party send-later code was copied. `MailApp.getRemainingDailyQuota()` was not added, because it needs `script.send_mail`.

## Constraints and Guardrails

- Public repo. No mailbox address, token, script id, or OAuth client in git.
- Scopes stay `gmail.modify` and `script.scriptapp`.

## Next Best Actions

- None in the repo. The mailbox owner deploys from the folder README.

## Known Risks or Failure Modes

- A large draft list can spend the daily trigger-time quota.
- Consumer send quota is about 100 recipients per day. After it is hit, later runs fail until the quota resets or the label is removed.
- An edit that lands after the pre-send re-read can still go out in that send.

## Prompt to Resume

This thread is done. The script lives in `apps_script/gmail_delayed_send/`. Do not add a mailbox address, token, script id, or OAuth client. Do not replace the message-date clock with a label-applied clock. Do not copy send-later projects that have no license. Deploy only from the account that owns the drafts.
