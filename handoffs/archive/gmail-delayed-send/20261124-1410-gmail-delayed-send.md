---
thread: gmail-delayed-send
status: done
created: 2026-11-24T14:10Z
supersedes: handoffs/archive/gmail-delayed-send/20261124-1345-gmail-delayed-send.md
private_detail: null
---

# Gmail delayed send

## Objective

Add a consumer-Gmail Apps Script that sends a draft once its current message is five minutes old and its thread has the send label.

## Current State

- Script, manifest, and README are in `apps_script/gmail_delayed_send/`. Pull request 26 is open. The script is not deployed.
- `Send in 5` queues a draft. A non-quota send failure removes `Send in 5` and then applies `Send failed`, unless another queued draft remains on that thread. A send-quota or Gmail read-quota error keeps `Send in 5` and stops the rest of the pass.
- The same missing-label or quota failure throws at most once an hour. Later passes log it and return.
- Prior art is in the folder README. No third-party code was copied.

## Key Decisions Already Made

- Decision: Age is `GmailMessage.getDate()` on the current draft message.
- Why: `GmailDraft` has no last-updated getter. A save replaces the message.

- Decision: Gmail read-quota errors are not draft failures.
- Why: `Service invoked too many times for one day: gmail` is the read/write quota, about 20,000 operations a day. Parking those drafts would stop them after the quota resets.
- Tradeoff: The pass stops and the labels stay, same as a recipient-quota stop.

- Decision: Jon chose to skip a sent-history log and a sent-history label.
- Why: The sent thread is the record.

- Decision: The trigger interval stays one minute.
- Why: A slower trigger was not requested. The read quota is documented instead.

## Constraints and Guardrails

- Public repo. No mailbox address, token, script id, or OAuth client in git.
- Scopes stay `gmail.modify` and `script.scriptapp`. Script Properties for the failure latch add no scope.
- Do not add a sent-history log or label unless Jon asks again.
- Only one Apps Script project may hold the trigger.

## Files / Artifacts / Sources

- `apps_script/gmail_delayed_send/Code.gs`
- `apps_script/gmail_delayed_send/README.md`
- Pull request 26

## Next Best Actions

- None in the repo. The README smoke test is for the mailbox owner, before the first real use.

## Known Risks or Failure Modes

- A minute trigger that reads every draft can spend the Gmail read quota.
- Live Gmail was not called from this environment. The smoke test in the README is the check.
- An edit that lands after the pre-send re-read can still go out in that send.

## Prompt to Resume

Continue from `apps_script/gmail_delayed_send/` on pull request 26. The script is done and not deployed. Focus only if asked to deploy or to change the clock, the labels, or the quota rule. Avoid a sent-history log or label, a slower trigger, copying GmailSendLater, and any mailbox address, token, script id, or OAuth client. Validate with the message-date clock, `Send failed` only on a non-quota failure, and `Send in 5` kept on a send-quota or Gmail read-quota error.
