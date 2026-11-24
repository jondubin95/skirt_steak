---
thread: gmail-delayed-send
status: done
created: 2026-11-24T13:11Z
supersedes: null
private_detail: null
---

# Gmail delayed send

## Objective

Add a consumer-Gmail Apps Script that sends a draft once its current message is five minutes old and its thread has the send label.

## Current State

- Script, manifest, and README are in `apps_script/gmail_delayed_send/`.
- The script is not deployed. Deploy is a paste or a local clasp push into the mailbox account, then one run of `installDelayedGmailSend`.

## Key Decisions Already Made

- Decision: Age is `GmailMessage.getDate()` on the draft's current message.
- Why: `GmailDraft` has no last-updated getter. A save replaces the message, so that date moves.
- Tradeoff: Labeling an old draft does not start a new five-minute clock. GmailApp has no label-applied time.

- Decision: The label is read from the draft's thread, then removed from the sent thread.
- Why: A draft message cannot carry a user label. The Gmail UI labels the thread. `getDrafts()` is the list because draft-only threads are often missing from label thread lists.
- Tradeoff: Every draft on that thread is eligible.

- Decision: Scopes are `gmail.modify` and `script.scriptapp`.
- Why: `gmail.compose` can send drafts and cannot change labels.

## Constraints and Guardrails

- Public repo. No mailbox address, token, script id, or OAuth client in git.
- `.clasp.json` and `.clasprc.json` are gitignored.
- Consumer Gmail only. Trigger runtime is about 90 minutes per day.

## Next Best Actions

- None in the repo. The mailbox owner deploys from the folder README.

## Known Risks or Failure Modes

- A large draft list can spend the daily trigger-time quota.
- Consumer send quota is about 100 recipients per day. A failed send stays labeled and retries until the label or the draft is removed.
- An edit that lands after the pre-send re-read can still go out in that send.

## Prompt to Resume

This thread is done. The script lives in `apps_script/gmail_delayed_send/`. Do not add a mailbox address, token, script id, or OAuth client to the repo. Deploy only from the account that owns the drafts, using the folder README. If send behavior changes, re-check age with `GmailMessage.getDate()` and match the thread label, not a label id on the draft message.
