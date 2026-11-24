---
thread: gmail-delayed-send
status: done
created: 2026-11-24T13:34Z
supersedes: handoffs/archive/gmail-delayed-send/20261124-1326-gmail-delayed-send.md
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

- Decision: A non-quota send failure applies `Send failed` and removes `Send in 5`.
- Why: Otherwise the minute trigger retries the same broken draft. The parking idea is from GmailSendLater. That repo has no license, so the code is new.
- Tradeoff: A daily recipient-quota error still keeps `Send in 5` and fails the run.

- Decision: Overlapping runs take `LockService.getScriptLock()` and skip if it is held.

## Constraints and Guardrails

- Public repo. No mailbox address, token, script id, or OAuth client in git.
- Scopes stay `gmail.modify` and `script.scriptapp`.

## Next Best Actions

- None in the repo. The mailbox owner deploys from the folder README.

## Prompt to Resume

This thread is done. The script lives in `apps_script/gmail_delayed_send/`. A non-quota send failure must park the draft on `Send failed` and take off `Send in 5`. A quota failure must leave `Send in 5` in place. Do not copy GmailSendLater's code. Do not add a mailbox address, token, script id, or OAuth client.
