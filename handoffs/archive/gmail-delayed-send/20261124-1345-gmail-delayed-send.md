---
thread: gmail-delayed-send
status: done
created: 2026-11-24T13:45Z
supersedes: handoffs/archive/gmail-delayed-send/20261124-1334-gmail-delayed-send.md
private_detail: null
---

# Gmail delayed send

## Objective

Add a consumer-Gmail Apps Script that sends a draft once its current message is five minutes old and its thread has the send label.

## Current State

- Script, manifest, and README are in `apps_script/gmail_delayed_send/`. Pull request 26 is open on `cursor/gmail-delayed-send-2cb1`. The script is not deployed.
- `Send in 5` queues a draft. A non-quota send failure parks it on `Send failed` and removes `Send in 5`. A daily recipient-quota error keeps `Send in 5`.
- Prior art is in the folder README. No third-party send-later code was copied. The `Send failed` parking idea is from GmailSendLater and the code is new.

## Why This Matters

- Consumer Gmail Undo Send stops at 30 seconds. This is the longer undo, from any client that can apply a label.

## Key Decisions Already Made

- Decision: Age is `GmailMessage.getDate()` on the current draft message.
- Why: `GmailDraft` has no last-updated getter. A save replaces the message.
- Tradeoff: Labeling an old draft does not start a new five-minute clock.

- Decision: A non-quota send failure applies `Send failed` and removes `Send in 5`.
- Why: Otherwise the minute trigger retries the same broken draft.
- Tradeoff: A transient Gmail error stays parked until someone removes `Send failed` and applies `Send in 5` again.

- Decision: A daily recipient-quota error keeps `Send in 5`, skips the rest of that pass, and fails the run.
- Why: The quota resets later. Parking those drafts would stop the retry.

- Decision: Overlapping runs take `LockService.getScriptLock()` and skip if it is held.
- Why: A slow pass can overlap the next minute.

- Decision: Jon chose to skip a sent-history log and a sent-history label.
- Why: The sent thread is the record. Another label or log was extra scope.
- Tradeoff: There is no separate list of what this script sent.

- Decision: No code was copied from the send-later repos that were reviewed.
- Why: GmailSendLater, the gmail-delay-send export, the label-search gist, and the snooze-outbox add-on have no usable license. Email Studio is MIT and is a different product.
- Tradeoff: The only borrowed idea is GmailSendLater's error label, reimplemented as `Send failed`.

## Constraints and Guardrails

- Public repo. No mailbox address, token, script id, or OAuth client in git.
- Scopes stay `gmail.modify` and `script.scriptapp`.
- Do not add a sent-history log or label unless Jon asks again.

## Files / Artifacts / Sources

- `apps_script/gmail_delayed_send/Code.gs`
- `apps_script/gmail_delayed_send/appsscript.json`
- `apps_script/gmail_delayed_send/README.md`
- Pull request 26

## Next Best Actions

- None in the repo. Deploy from the folder README, in the account that owns the drafts.

## Known Risks or Failure Modes

- A large draft list can spend the consumer trigger-time quota, about 90 minutes per day.
- Consumer send quota is about 100 recipients per day.
- An edit that lands after the pre-send re-read can still go out in that send.
- If applying `Send failed` throws, the original error is logged and `Send in 5` may remain, so the next minute retries.

## Prompt to Resume

Continue from `apps_script/gmail_delayed_send/` on pull request 26. The script is done and not deployed. Focus only if asked to deploy or to change the clock, the labels, or the quota rule. Avoid a sent-history log or label, copying GmailSendLater, and any mailbox address, token, script id, or OAuth client. Validate a behavior change with the message-date clock, `Send failed` only on a non-quota failure, and `Send in 5` kept on a quota failure.
