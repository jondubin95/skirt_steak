# Gmail delayed send

Sends a Gmail draft after it has been left alone for 5 minutes. Gmail's own Undo Send stops at 30 seconds, and it cannot hold a normal send longer than that.

Use this on a personal Gmail account (`you@gmail.com`), not a Google Workspace mailbox. The script runs as the Google account that authorized it, and it only sees that account's drafts.

This folder is in a public repo. Do not put a mailbox address, token, script id, OAuth client, or `.clasp.json` here.

## What it does

1. You write the email and leave it as a draft.
2. You apply the Gmail label `Send in 5`.
3. A trigger runs every minute, loads drafts with `GmailApp.getDrafts()`, and keeps the ones whose thread has that label.
4. If that draft's current message date is at least 5 minutes old, the script calls `GmailDraft.send()` and then removes the label from the sent thread.
5. If the message date is newer than that, the script waits. Saving the draft again resets the clock.
6. If the send fails for a reason other than the daily recipient quota, the script logs the error, applies `Send failed` to the thread, and removes `Send in 5`. That draft is not retried. A quota failure keeps `Send in 5`.

Change the wait and the label names with `DELAY_MINUTES`, `SEND_LABEL_NAME`, and `SEND_FAILED_LABEL_NAME` at the top of `Code.gs`. Each label name must match exactly.

## Deploy

The Apps Script project has to live in the same Google account as the mailbox. A private script uses Google's own consent screen. Do not create an OAuth client, and do not commit one.

### Paste into script.google.com

1. Open [script.google.com](https://script.google.com) while signed in as `you@gmail.com`. Create a project.
2. Replace the default `Code.gs` with the `Code.gs` in this folder.
3. Open Project Settings and turn on "Show 'appsscript.json' manifest file in editor". Replace that file with the `appsscript.json` in this folder. The manifest pins the V8 runtime and the two scopes below.
4. Save.
5. Choose `installDelayedGmailSend` and Run it once.
6. Approve the consent screen. It should ask to manage Gmail (read, send, and change labels) and to manage triggers in this script.

### clasp

From this folder, on your own machine:

1. Install clasp and run `clasp login` as `you@gmail.com`. clasp stores that login in your home directory, not in this repo.
2. Create a standalone project and leave the script id only in a local `.clasp.json` (gitignored):

```json
{
  "scriptId": "<your-script-id>",
  "rootDir": "."
}
```

3. `clasp push`
4. Open the project and run `installDelayedGmailSend` once, then approve permissions.

`clasp create --type standalone --title "Gmail delayed send" --rootDir .` from this folder also writes that local `.clasp.json`. Do not commit it.

Only one Apps Script project may run this trigger. The lock is per project. Two installed copies can send the same draft twice. Run `uninstallDelayedGmailSend` in the old project before installing another copy.

Before the first real use, check the mechanism against your own mailbox:

1. Compose a draft to yourself, apply `Send in 5`, and run `sendLabeledDraftsAfterDelay` from the editor after the draft is at least 5 minutes old. The execution log should say `Sent draft`, and `Send in 5` should be gone from the thread.
2. Label a second draft `Send in 5`, delete that draft, and run the function again. It should not send, and it should not apply `Send failed`.

## Use the label

Run `installDelayedGmailSend` before the first use so `Send in 5` and `Send failed` exist. You can also create those labels yourself with those exact names.

Desktop, including Edge and any other browser:

1. Compose the message and leave it in Drafts. Gmail autosaves while the compose window is open.
2. Open Drafts, select the draft, and apply the label `Send in 5` (Labels menu, or drag the draft onto the label).
3. Leave the draft alone.

Phone, in the Gmail app:

1. Compose, then leave the draft so it saves.
2. In the Drafts list, touch and hold the draft, then choose Labels (some phones say Label as). Applying the label from inside the open compose window is not available in the Gmail app.
3. Leave the draft alone.

Do not use Gmail's own Schedule send on a draft whose thread has `Send in 5`. The script cannot see that scheduled state. Remove `Send in 5` first, or the script can send the draft on its own clock.

An open compose window that keeps autosaving keeps the message young, so the send waits until 5 minutes after the last save.

## Cancel

The script sends only while the draft exists and the thread still has `Send in 5`. Before that happens, either:

- remove the label `Send in 5`, or
- delete the draft.

Editing and saving also starts the 5 minutes over.

The clock is the draft's last save, not the moment you applied the label. Gmail does not tell the script when a label was added. A draft you just saved still has about 5 minutes. A draft last saved more than 5 minutes ago becomes eligible on the next trigger after you label it, which is about a minute, not another 5. Touch the draft (open it and let it save) if you want the full wait on an older draft.

## Uninstall

Run `uninstallDelayedGmailSend` in the Apps Script editor. That removes this project's minute trigger, including duplicates of the same handler. The Gmail labels stay. Delete `Send in 5` and `Send failed` in Gmail if you no longer want them.

Running `installDelayedGmailSend` again is safe. It reuses both labels and leaves exactly one minute trigger.

## Quotas

Consumer Google accounts, not Workspace:

- Trigger runtime is about 90 minutes per day. A one-minute trigger runs up to 1,440 times per day, so the average budget is about 3.7 seconds per run. This script returns as soon as there are no drafts, and it only sends drafts whose thread has the label.
- A mailbox with a very large draft list can make `GmailApp.getDrafts()` plus a label check on each draft slow enough to spend that 90 minutes. Triggers then stop until the next day. One execution is also capped at about 6 minutes. A run killed at that cap writes nothing, so `Send in 5` can remain on a thread that was already sent.
- Gmail read and write, excluding send, is about 20,000 operations a day on a consumer account. This script reads every draft once a minute, so the budget can run out without a huge mailbox. A Gmail service-quota error (`for one day: gmail` or `in a short time: gmail`) is treated like the send quota below: `Send in 5` stays, `Send failed` is not applied, and the rest of that pass does not send.
- `GmailDraft.send()` counts toward the Gmail Apps Script send quota, about 100 recipients per day on a consumer account. When a send fails with a daily recipient-quota error, or with a short-time email rate limit, `Send in 5` stays on the thread, `Send failed` is not applied, the rest of that run does not send, and the run fails so the execution list shows it. A later run tries again. Quotas reset 24 hours after the first request, not at midnight. Remove `Send in 5` or delete the draft to stop the retries. `MailApp.getRemainingDailyQuota()` is not used: it needs the extra `script.send_mail` scope.
- Minute triggers can overlap if a run is slow. The script takes `LockService.getScriptLock()` and skips the pass when another run holds it, so two passes cannot send the same draft. The wait is 0 milliseconds so a blocked pass does not sit on the daily trigger-time budget.
- Minute triggers drift. Delivery is about 5 to 7 minutes after the last save, not exactly 5:00.

## If a send fails

A non-quota failure is logged. `Send in 5` is removed first, then `Send failed` is applied. The draft stays in Drafts. The next minute does not send it again. If another labeled draft is still queued on that same thread, `Send in 5` stays so the other draft can send, and `Send failed` is still applied. The idea of parking a failed draft on its own label comes from [GmailSendLater](https://github.com/devietti/GmailSendLater). That repository has no license, so this script does not copy its code. `Send failed` is this script's label, created by `installDelayedGmailSend`, and it is applied only after a non-quota failure.

To spot one: open the `Send failed` label in Gmail, or read the execution log. The log has the draft id, the subject, and the error. It does not include the body or the recipients.

To retry: fix the draft, remove `Send failed`, and apply `Send in 5` again. The clock is still the draft's last save. An old draft sends on the next run. Touch the draft if you want another 5 minutes.

A daily send-quota failure, a short-time email rate limit, and a Gmail read-quota failure do not do this. Those threads keep `Send in 5` and are tried on a later run.

A draft that disappears before `send()` (you deleted it, or you sent it yourself) is not parked on `Send failed`.

## If a run fails

A non-quota draft failure is logged and the run still finishes, so the other labeled drafts in that pass are still sent. A missing `Send in 5` label, or a service quota error, fails the run. The same persistent failure is thrown at most once an hour. Later passes log it and return, so a minute trigger does not stack a long streak of failed executions. Repeated failures are reported to disable time triggers; that limit is not in the official quota table.

If labeled drafts stop sending, open the script's Triggers page. A trigger that turned itself off is listed there and can be turned back on after the cause is fixed.

To get an email when a run fails: in the Apps Script editor open Triggers, open this minute trigger, and set failure notifications. "Once daily" is the setting that matches a one-minute trigger. The script does not send its own error mail. That would spend the same send quota and, on a one-minute trigger, repeat until you removed the label.

## How draft age is decided

`GmailDraft` exposes `getId()`, `getMessage()`, `getMessageId()`, `send()`, `update()`, and `deleteDraft()`. There is no last-updated method.

The Gmail drafts guide says the message inside a draft cannot be edited in place. Each save destroys that message and replaces it. The draft id is stable. The new message gets a new id and a new message timestamp (`internalDate`: when that message object was created).

`GmailMessage.getDate()` is the Apps Script value of that timestamp. The official `GmailDraft.send()` example logs `getDate()` immediately after send and treats it as approximately the current time, which matches the message timestamp rather than a stale RFC 2822 `Date` header. This script uses `getDate()` and does not read the `Date` header.

Consequences:

- An edit or autosave replaces the message, so the age falls under 5 minutes and the send waits.
- There is no timestamp for "label applied". An old draft is not given a fresh 5 minutes just by labeling it.
- Just before send, the script loads the draft again with `GmailApp.getDraft(id)`. That picks up a save or a label removal that happened after the scan started. An edit that lands after that re-read and before `send()` returns can still go out in that send. That gap is one send call.

## Why the label is on the thread

The Gmail API says a draft message cannot have any label except the `DRAFT` system label. `GmailDraft` has no label method. The way to see the label you applied in Gmail is `draft.getMessage().getThread().getLabels()`.

That is a thread label. Every draft on that thread is eligible. The script removes `Send in 5` only when that pass has no remaining queued draft on the thread, so a younger draft on the same thread still waits its own 5 minutes. `label.getThreads()` is not used, because draft-only threads are often missing from thread lists. `GmailApp.search` has the same hole. `getDrafts()` is the list, filtered by the thread label.

`GmailDraft.send()` deletes the draft message and creates a new sent message. New messages do not inherit thread labels. The script still calls `removeLabel` on the sent thread so a conversation that already had other labeled messages does not keep `Send in 5`. If the mail was sent and label removal throws, the error is logged and the draft is not sent again.

## Scopes

`appsscript.json` requests only:

- `https://www.googleapis.com/auth/gmail.modify` — read drafts, send them, create the label, and remove the label. `gmail.compose` can send drafts and cannot change labels. `gmail.labels` can edit label definitions and cannot send. `https://mail.google.com/` is broader than this script needs. GmailApp's own docs list `https://mail.google.com/` on each method and also allow the matching REST scope. If Google's consent screen refuses to authorize with `gmail.modify` alone, stop and treat that as a real scope failure rather than guessing a wider scope in this repo.
- `https://www.googleapis.com/auth/script.scriptapp` — create and delete the trigger.

## Logs

`Logger` writes to the Apps Script execution log for this project. A pass with nothing labeled writes nothing. Waiting, sending, label-removal failure, and per-draft errors are logged with the draft id and subject, not the body and not the recipients. One bad draft does not stop the others. A missing label fails the run so the execution list shows it.

Logs stay in the Google account. They are not written to this repo.

## Prior art

Nothing below was copied. The lock and the quota stop were written for this script from Apps Script's [LockService](https://developers.google.com/apps-script/reference/lock/lock-service) and the documented daily recipient-quota errors.

- [devietti/GmailSendLater](https://github.com/devietti/GmailSendLater) — no license. A label such as "send at 9am tomorrow" schedules a clock time, on about a 15-minute trigger. It also parks a draft it could not handle by applying an error label. Adopted: that parking idea only, reimplemented here as `Send failed` after a non-quota send failure. No code was copied. The clock-time schedule was not adopted.
- [google-code-export/gmail-delay-send](https://github.com/google-code-export/gmail-delay-send) — the old Google Code project page listed MIT. This export has no `LICENSE` file. It is a spreadsheet of settings, a 5-minute trigger, retries that sleep, and an optional error email. Rejected: no license file in the export, and sleep-retries would spend the consumer trigger-time quota.
- [labnol/email-studio-gmail-addon](https://github.com/labnol/email-studio-gmail-addon) — MIT, Amit Agarwal. A Gmail add-on that stores scheduler rules. An older public write-up sends a reconstructed copy with `GmailApp.sendEmail` and trashes the draft. Rejected: different product. `GmailDraft.send()` keeps the draft's recipients, attachments, and thread.
- [hadasfester/81bfc5668cb7b666b4fd6eeb6db804c3](https://gist.github.com/hadasfester/81bfc5668cb7b666b4fd6eeb6db804c3) — no license. Searches `in:draft label:` and throws if a send fails, which stops the rest of the drafts. Rejected: no license, search misses some drafts, and one failure blocks the others.
- [jiehan1029/snooze-outbox-gmail-addon](https://github.com/jiehan1029/snooze-outbox-gmail-addon) — no `LICENSE` file. A label-based schedule-send add-on. Rejected: no license, and it schedules a clock time.

Gmail's own Undo Send stops at 30 seconds. Gmail's Schedule send picks a clock time. Neither is this label-plus-delay flow.

A stored "label applied" time was rejected. Gmail does not provide one, and waiting 5 minutes from the first time this script sees the label would change the clock. The clock stays the draft message date.
