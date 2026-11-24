# Gmail delayed send

Sends a Gmail draft after it has been left alone for 5 minutes. Gmail's own Undo Send stops at 30 seconds, and it cannot hold a normal send longer than that.

Use this on a personal Gmail account (`you@gmail.com`), not a Google Workspace mailbox. The script runs as the Google account that authorized it, and it only sees that account's drafts.

This folder is in a public repo. Do not put a mailbox address, token, script id, OAuth client, or `.clasp.json` here.

## What it does

1. You write the email and leave it as a draft.
2. You apply the Gmail label `Send in 5`.
3. A trigger runs every minute, loads drafts with `GmailApp.getDrafts()`, and keeps the ones whose thread has that label.
4. If that draft's current message date is at least 5 minutes old, the script calls `GmailDraft.send()`. It removes the label from the sent thread only when no other labeled draft on that thread still needs it.
5. If the message date is newer than that, the script waits. Saving the draft again resets the clock.
6. If the send fails for a reason other than a Gmail quota, the script logs the error, removes `Send in 5`, and applies `Send failed`. That draft is not retried. A quota failure keeps `Send in 5`. If another labeled draft on the same thread still needs the label, the label stays and the failure is not parked.

Change the wait, the trigger interval, and the label names with `DELAY_MINUTES`, `TRIGGER_INTERVAL_MINUTES`, `SEND_LABEL_NAME`, and `SEND_FAILED_LABEL_NAME` at the top of `Code.gs`. Each label name must match exactly. `TRIGGER_INTERVAL_MINUTES` must be 1, 5, 10, 15, or 30. After changing it, run `installDelayedGmailSend` again so the installed trigger picks up the new interval.

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

Only one Apps Script project may hold this trigger. `LockService.getScriptLock()` only blocks overlapping runs inside one project. A second project with the same script can send the same draft again. Before installing elsewhere, run `uninstallDelayedGmailSend` in the old project.

### Smoke test before real use

Do this once in the account that owns the drafts, before the first real message. It takes about 15 minutes because the draft has to age. Nothing in this repo can run it.

1. Run `installDelayedGmailSend` and approve the consent screen.
2. Compose a new draft addressed to yourself, with a subject you can recognize. Leave it in Drafts and close the compose window.
3. Apply `Send in 5` from the Drafts list. On a phone, use the long-press steps below.
4. In the Apps Script editor, choose `sendLabeledDraftsAfterDelay` and Run. The draft is only a few seconds old, so the log should say `Waiting to send draft` and the draft should still be in Drafts with `Send in 5`.
5. Wait until that draft's last save is at least 5 minutes ago. Run `sendLabeledDraftsAfterDelay` again. The log should include `Sent draft` with that draft id and subject. The message should be in Sent. The thread should no longer have `Send in 5`.
6. Create a second draft, apply `Send in 5`, then delete the draft. Run `sendLabeledDraftsAfterDelay` again. That draft must not send, and the thread must not gain `Send failed`. Deleting the draft is the cancel.

## Use the label

Run `installDelayedGmailSend` before the first use so `Send in 5` and `Send failed` exist. You can also create those labels yourself with those exact names.

Desktop, including Edge and any other browser:

1. Compose the message and leave it in Drafts. Gmail autosaves while the compose window is open.
2. Open Drafts, select the draft, and apply the label `Send in 5` (Labels menu, or drag the draft onto the label).
3. Leave the draft alone.

Phone, in the Gmail app:

1. Compose, then leave the draft so it saves. Close compose so you are looking at the Drafts list.
2. Touch and hold the draft in that list. Do not open it. Opening a draft on the phone opens compose, and compose has no label control.
3. Tap More, then Labels. On some Android versions the menu says Label as. Check `Send in 5` and confirm. Gmail's [iPhone and iPad help](https://support.google.com/mail/answer/118708?co=GENIE.Platform%3DiOS&hl=en) is: touch and hold the mail, then More, then Labels. The app moves these menus. If the wording differs, apply the label from the list selection, not from inside compose.
4. Leave the draft alone.

Do not use Gmail's Schedule send on a draft whose thread has `Send in 5`. Remove the label first. The script cannot see the Scheduled state. A scheduled draft is still in the drafts list, and this script will send it on the 5-minute clock and consume it.

An open compose window that keeps autosaving keeps the message young, so the send waits until 5 minutes after the last save.

## Cancel

The script sends only while the draft exists and the thread still has `Send in 5`. Before that happens, either:

- remove the label `Send in 5`, or
- delete the draft.

Editing and saving also starts the 5 minutes over.

The clock is the draft's last save, not the moment you applied the label. Gmail does not tell the script when a label was added. A draft you just saved still has about 5 minutes. A draft last saved more than 5 minutes ago becomes eligible on the next trigger after you label it, which is about a minute, not another 5. Touch the draft (open it and let it save) if you want the full wait on an older draft.

## Uninstall

Run `uninstallDelayedGmailSend` in the Apps Script editor. That removes this project's delayed-send trigger, including duplicates of the same handler. The Gmail labels stay. Delete `Send in 5` and `Send failed` in Gmail if you no longer want them.

Running `installDelayedGmailSend` again is safe. It reuses both labels and leaves exactly one trigger, at `TRIGGER_INTERVAL_MINUTES`.

## Quotas

Consumer Google accounts, not Workspace. Quotas are per user and reset 24 hours after the first request, not at midnight. A failure in the afternoon can still be in force the next morning. The numbers are the [Apps Script quota table](https://developers.google.com/apps-script/guides/services/quotas). Google can change them.

- Trigger runtime is about 90 minutes per day. A one-minute trigger runs up to 1,440 times per day, so the average budget is about 3.7 seconds per run. This script returns as soon as there are no drafts, and it only sends drafts whose thread has the label.
- Each execution also stops at 6 minutes. A run killed on that cap writes nothing further. If the kill lands after `GmailDraft.send()` and before the label is removed, `Send in 5` can remain on the sent thread. Remove it by hand. There may be no log line for that draft.
- Email read/write, excluding send, is 20,000 per day. `MailApp.getRemainingDailyQuota()` does not report this number, and calling it would need the extra `script.send_mail` scope. Google does not publish the units per GmailApp call. This pass calls `getDrafts()` once, then `getMessage()`, `getThread()`, and `getLabels()` for each draft. A second draft on a thread already checked in that pass skips `getLabels()`. A draft that is old enough pays another `getDraft`, `getMessage`, `getThread`, and `getLabels` immediately before send. Those extra calls are rare next to the every-pass scan. Counted as one unit per call, a one-minute trigger's scan costs about `1,440 × (1 + 3 × drafts)` per day: about 5,760 at 1 draft, about 18,720 at 4 drafts, and about 23,040 at 5 drafts. Labeled or not, every draft in the folder is read. A folder of about four drafts is near the cap, and about five is over it, if that per-call guess is right.
- `label.getThreads()` and `GmailApp.search` are not used to shrink that list. Draft-only threads are often missing from both, and a new compose is usually a draft-only thread. Filtering that way would skip the send.
- `ClockTriggerBuilder.everyMinutes` allows 1, 5, 10, 15, or 30. It rejects 2, so a two-minute trigger cannot be installed. This script stays at 1 minute so a draft that is already 5 minutes old is seen about a minute later. Set `TRIGGER_INTERVAL_MINUTES` to 5 and run `installDelayedGmailSend` again if the gmail daily quota starts firing: 288 passes a day is about 18,720 units at 20 drafts under the same guess, and an already-old draft can wait about 5 minutes instead of about 1.
- A slow pass can still spend the 90 minutes of trigger time on a very large draft list. Triggers then stop until the quota resets.
- `GmailDraft.send()` counts toward the send quota, about 100 recipients per day on a consumer account. The same retry-later rule covers that daily recipient quota, the Gmail read/write quota (`for one day: gmail`, and the documented `Service invoked too many times: gmail.`), and a short burst (`in a short time: gmail` or `in a short time: email`). `Send in 5` stays, `Send failed` is not applied, the rest of that run does not send, and the run fails at most once an hour so the execution list shows it. A later run tries again. Remove `Send in 5` or delete the draft to stop the retries.
- Triggers can overlap if a run is slow. The script takes `LockService.getScriptLock()` and skips the pass when another run in this project holds it, so two passes in one project cannot send the same draft. The wait is 0 milliseconds so a blocked pass does not sit on the daily trigger-time budget. A second Apps Script project has its own lock. See Deploy.
- With the one-minute trigger, delivery is about 5 to 7 minutes after the last save, not exactly 5:00. Triggers drift.

## If a send fails

A non-quota failure is logged. The script then removes `Send in 5` and, only if that remove succeeds, applies `Send failed`. If the remove throws, `Send in 5` stays and the next run retries. If the remove succeeds and applying `Send failed` throws, the draft is not retried and the log says the failure label could not be applied. The draft stays in Drafts. The idea of parking a failed draft on its own label comes from [GmailSendLater](https://github.com/devietti/GmailSendLater). That repository has no license, so this script does not copy its code. `Send failed` is this script's label, created by `installDelayedGmailSend`, and it is applied only after a non-quota failure.

If another labeled draft on that thread is still waiting, not yet processed, or held back by a quota error, the label stays and `Send failed` is not applied. The thread label cannot park one draft and keep another. The log says another labeled draft still needs `Send in 5`.

To spot one: open the `Send failed` label in Gmail, or read the execution log. The log has the draft id, the subject, and the error. It does not include the body or the recipients.

To retry: fix the draft, remove `Send failed`, and apply `Send in 5` again. The clock is still the draft's last save. An old draft sends on the next run. Touch the draft if you want another 5 minutes.

A Gmail quota failure does not do this. Those threads keep `Send in 5` and are tried on a later run. That includes the daily recipient quota, the daily Gmail read/write quota, and a short-time Gmail or email quota.

## If a run fails

A non-quota draft failure is logged and the run still finishes, so the other labeled drafts in that pass are still sent. A missing `Send in 5` label, or a Gmail quota error, fails the run.

Those two conditions throw at most once per hour. The script stores the time of the last throw in script properties, under `delayedSendPersistentFailureLatchedAt`. That value is a timestamp, not a draft id. Properties need no extra scope. Later runs in that hour log the same condition and finish without throwing, so a one-minute failure loop does not pile up. A pass that is not in that state clears the timestamp. The drafts stay labeled either way.

To get an email when a run fails: in the Apps Script editor open Triggers, open this trigger, and set failure notifications. "Once daily" is the setting that matches a one-minute trigger. The script does not send its own error mail. That would spend the same send quota and, on a one-minute trigger, repeat until you removed the label.

If labeled drafts silently stop sending, open [script.google.com](https://script.google.com), then My Triggers, and look for this handler. Google's trigger page says a failure email includes a link to deactivate the trigger, and a deactivated trigger also stops those emails. The page does not publish how many consecutive failures cause that. Re-enable the trigger after fixing the cause, or run `installDelayedGmailSend` again. That deletes and recreates it.

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

That is a thread label. Every draft on that thread is eligible. The label comes off only after every labeled draft on that thread has been sent, canceled, or parked. A younger draft on the same thread keeps `Send in 5` after an older one sends. `label.getThreads()` is not used, because draft-only threads are often missing from thread lists. `GmailApp.search` has the same hole. `getDrafts()` is the list, filtered by the thread label.

`GmailDraft.send()` deletes the draft message and creates a new sent message. New messages do not inherit thread labels. The script still calls `removeLabel` on the sent thread so a conversation that already had other labeled messages does not keep `Send in 5`, unless another draft on that thread still needs the label. If the mail was sent and label removal throws, the error is logged and the draft is not sent again.

A draft deleted or sent by hand before `send()` is a cancel. `GmailApp.getDraft` throws when that id is gone. The script logs `Draft deleted before send` and does not apply `Send failed`.

## Scopes

`appsscript.json` requests only:

- `https://www.googleapis.com/auth/gmail.modify` — read drafts, send them, create the label, and remove the label. `gmail.compose` can send drafts and cannot change labels. `gmail.labels` can edit label definitions and cannot send. `https://mail.google.com/` is broader than this script needs. GmailApp's own docs list `https://mail.google.com/` on each method and also allow the matching REST scope. If Google's consent screen refuses to authorize with `gmail.modify` alone, stop and treat that as a real scope failure rather than guessing a wider scope in this repo.
- `https://www.googleapis.com/auth/script.scriptapp` — create and delete the trigger.

## Logs

`Logger` writes to the Apps Script execution log for this project. A pass with nothing labeled writes nothing. Waiting, sending, label-removal failure, and per-draft errors are logged with the draft id and subject, not the body and not the recipients. The subject stays in the log because that is how you find the draft. One bad draft does not stop the others. A missing label fails the run so the execution list shows it, at most once an hour while the label is still missing.

Logs stay in the Google account. They are not written to this repo.

## Prior art

Nothing below was copied. The lock and the quota stop were written for this script from Apps Script's [LockService](https://developers.google.com/apps-script/reference/lock/lock-service) and the documented quota errors for the `email` and `gmail` services.

- [devietti/GmailSendLater](https://github.com/devietti/GmailSendLater) — no license. A label such as "send at 9am tomorrow" schedules a clock time, on about a 15-minute trigger. It also parks a draft it could not handle by applying an error label. Adopted: that parking idea only, reimplemented here as `Send failed` after a non-quota send failure. No code was copied. The clock-time schedule was not adopted.
- [google-code-export/gmail-delay-send](https://github.com/google-code-export/gmail-delay-send) — the old Google Code project page listed MIT. This export has no `LICENSE` file. It is a spreadsheet of settings, a 5-minute trigger, retries that sleep, and an optional error email. Rejected: no license file in the export, and sleep-retries would spend the consumer trigger-time quota.
- [labnol/email-studio-gmail-addon](https://github.com/labnol/email-studio-gmail-addon) — MIT, Amit Agarwal. A Gmail add-on that stores scheduler rules. An older public write-up sends a reconstructed copy with `GmailApp.sendEmail` and trashes the draft. Rejected: different product. `GmailDraft.send()` keeps the draft's recipients, attachments, and thread.
- [hadasfester/81bfc5668cb7b666b4fd6eeb6db804c3](https://gist.github.com/hadasfester/81bfc5668cb7b666b4fd6eeb6db804c3) — no license. Searches `in:draft label:` and throws if a send fails, which stops the rest of the drafts. Rejected: no license, search misses some drafts, and one failure blocks the others.
- [jiehan1029/snooze-outbox-gmail-addon](https://github.com/jiehan1029/snooze-outbox-gmail-addon) — no `LICENSE` file. A label-based schedule-send add-on. Rejected: no license, and it schedules a clock time.

Gmail's own Undo Send stops at 30 seconds. Gmail's Schedule send picks a clock time. Neither is this label-plus-delay flow.

A stored "label applied" time was rejected. Gmail does not provide one, and waiting 5 minutes from the first time this script sees the label would change the clock. The clock stays the draft message date.
