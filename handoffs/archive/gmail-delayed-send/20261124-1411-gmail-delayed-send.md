---
thread: gmail-delayed-send
status: done
created: 2026-11-24T14:11Z
supersedes: handoffs/archive/gmail-delayed-send/20261124-1410-gmail-delayed-send.md
private_detail: null
---

# Gmail delayed send

## Objective

Add a consumer-Gmail Apps Script that sends a draft once its current message is five minutes old and its thread has the send label.

## Current State

- Script, manifest, README, and stand-in are in `apps_script/gmail_delayed_send/`. Pull request 26 is open on `cursor/gmail-delayed-send-2cb1`. Behavior commit `8be2dc7`. The script is not deployed.
- `handoffs/20261124-1410-gmail-delayed-send.md` was a shorter pass of the same review. This head replaces it. The stand-in, the legal trigger intervals, and the documented quota strings are in `8be2dc7`.
- `Send in 5` queues a draft. A non-quota send failure removes `Send in 5` and then applies `Send failed`, unless another labeled draft on that thread still needs the label.
- A recipient quota, a Gmail read/write quota (`for one day: gmail` or `too many times: gmail`), or a short-time Gmail/email quota keeps `Send in 5`, skips the rest of the pass, and throws at most once an hour. A missing `Send in 5` label uses the same latch. The timestamp is script property `delayedSendPersistentFailureLatchedAt`.
- A deleted draft is logged as canceled and is not parked. The subject is read before `send()`.
- The trigger stays `everyMinutes(1)`. `everyMinutes(2)` is not legal. `label.getThreads()` is still not the draft list.

## Why This Matters

- Consumer Gmail Undo Send stops at 30 seconds. This is the longer undo, from any client that can apply a label.
- A misclassified Gmail read quota would park healthy drafts, and a throw every minute can get the trigger deactivated.

## Key Decisions Already Made

- Decision: Age is `GmailMessage.getDate()` on the current draft message.
- Why: `GmailDraft` has no last-updated getter. A save replaces the message.
- Tradeoff: Labeling an old draft does not start a new five-minute clock.

- Decision: Gmail service quota errors are retry-later, same as the recipient quota.
- Why: The documented and observed strings are `Service invoked too many times: gmail.`, `for one day: gmail`, and `in a short time: gmail`. Parking those drafts stops the retry after the quota resets.
- Tradeoff: The pass stops, so later drafts wait until the next run.

- Decision: Persistent quota and missing-label failures throw at most once per 60 minutes.
- Why: A one-minute failure loop can deactivate the trigger. Google's trigger page does not publish the consecutive-failure count. The failure email includes a deactivate link.
- Tradeoff: Later runs in that hour finish successfully and only log the condition. A pass that is not in that state clears the latch.

- Decision: The thread label stays while any labeled draft on that thread is waiting, unprocessed, or held for quota.
- Why: Removing the label after the first send strands the others. The label is on the thread, not the draft.
- Tradeoff: A broken draft next to a younger sibling keeps retrying until it is the only one left, and then it is parked.

- Decision: The trigger stays at one minute.
- Why: `ClockTriggerBuilder.everyMinutes` allows 1, 5, 10, 15, or 30. Two minutes cannot be installed. Five minutes would change the "about a minute" pickup for an already-old draft.
- Tradeoff: A one-minute scan of about four drafts is near the 20,000/day read/write cap if each GmailApp call costs one unit. The README tells the owner to switch `TRIGGER_INTERVAL_MINUTES` to 5 if that quota fires. `label.getThreads()` was not used because it misses draft-only threads.

- Decision: Subjects stay in the execution log.
- Why: The log is account-private and is how a failed draft is found. The body and recipients are not logged.

- Decision: No code was copied from the send-later repos that were reviewed.
- Why: GmailSendLater, the gmail-delay-send export, the label-search gist, and the snooze-outbox add-on have no usable license. Email Studio is MIT and is a different product.
- Tradeoff: The only borrowed idea is GmailSendLater's error label, reimplemented as `Send failed`.

## Constraints and Guardrails

- Public repo. No mailbox address, token, script id, or OAuth client in git.
- Scopes stay `gmail.modify` and `script.scriptapp`.
- Do not add a sent-history log or label unless Jon asks again.

## Files / Artifacts / Sources

- `apps_script/gmail_delayed_send/Code.gs`
- `apps_script/gmail_delayed_send/stand_in_test.mjs`
- `apps_script/gmail_delayed_send/appsscript.json`
- `apps_script/gmail_delayed_send/README.md`
- Pull request 26
- Apps Script quotas: https://developers.google.com/apps-script/guides/services/quotas
- `ClockTriggerBuilder.everyMinutes`: 1, 5, 10, 15, or 30
- Gmail iOS label help: touch and hold, then More, then Labels

## Next Best Actions

- Jon runs the README smoke test in the account that owns the drafts, then uses the script. The repo cannot run that test.

## Known Risks or Failure Modes

- The 20,000/day read math assumes one quota unit per GmailApp call. Google does not publish the per-call cost. About four drafts on a one-minute trigger is near that cap if the guess is right.
- Quotas reset 24 hours after the first request, not at midnight.
- A run killed at the 6-minute execution cap can leave `Send in 5` on an already-sent thread.
- An edit that lands after the pre-send re-read can still go out in that send.
- Two Apps Script projects do not share the script lock and can double-send. The README says to uninstall the old project first.
- Gmail Schedule send is invisible to the script. The README says not to combine it with `Send in 5`.
- A broken draft that shares a thread with a younger draft is not parked until it is the only labeled draft left.

## Prompt to Resume

Continue from `apps_script/gmail_delayed_send/` on pull request 26, commit `8be2dc7`. The script is not deployed. Focus only if asked to deploy, to change the clock, or to set `TRIGGER_INTERVAL_MINUTES` to 5 after a real gmail quota failure. Avoid a sent-history log or label, copying GmailSendLater, `label.getThreads()` as the draft list, `everyMinutes(2)`, and any mailbox address, token, script id, or OAuth client. Validate with `node apps_script/gmail_delayed_send/stand_in_test.mjs`: quota text keeps `Send in 5`, a sibling draft keeps the label, and a deleted draft is not parked.
