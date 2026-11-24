# Gmail delayed send

Sends a Gmail draft after it has been left alone for 5 minutes. Gmail's own Undo Send stops at 30 seconds, and it cannot hold a normal send longer than that.

Use this on a personal Gmail account (`you@gmail.com`), not a Google Workspace mailbox. The script runs as the Google account that authorized it, and it only sees that account's drafts.

This folder is in a public repo. Do not put a mailbox address, token, script id, OAuth client, or `.clasp.json` here.

## What it does

Write the email in Drafts and leave it. About 5 to 6 minutes after the last save, it goes out. A late trigger can make that closer to 7. Gmail's normal Send button still sends instantly, because the message is no longer a draft.

Add the label `Hold` to keep a draft. The script never auto-sends a thread with that label. Take `Hold` off, or add `Release`, and the draft sends about 5 minutes after the script notices. Both clocks have to be done: 5 minutes from the last save, and 5 minutes from that release. A draft you just saved still waits. An old draft does not go out on the next run just because you removed `Hold`.

Once a pass has seen `Hold`, an edit does not drop that protection. The draft id stays the same and the message id changes. The script remembers the draft id and the message id. If a later pass finds no `Hold` and the message id changed, it puts `Hold` back and keeps the draft. That includes removing `Hold` and editing in the same minute: the message id changed, so it stays held. If the message id is the same, you removed `Hold`, and the 5-minute release clock starts. `Release` does the same clock and wins over `Hold`. The script takes `Release` and `Hold` off the thread when it sees `Release`.

Live check on 2026-11-24: editing a draft through the Gmail API (`drafts.update`, including a connector `update_draft`) creates a new message that does not carry `Hold`. The thread loses `Hold`. Gmail forbids setting labels on drafts through create or update. The sticky `Hold` above is the fix, and it is not live-deployed or live-tested yet. The remaining gap is an API edit in the first minute, before the first pass has seen `Hold`. After that first pass, an API edit does not clear it. If putting `Hold` back throws, the draft stays remembered and the next pass tries again. It is not marked `Send failed`.

No label is required for a send. `Send in 5` is the old opt-in label. This version does not look at it when deciding whether to send. If it is still on a thread, the script takes it off after a successful send, or after it applies `Send failed`, and only when no other draft on that thread is still waiting or held back by a quota error. Leaving `Send in 5` on a draft does not queue it and does not block it.

Before the first install, look through Drafts. Anything already older than 5 minutes sends on the next run unless the thread has `Hold` or `Send failed`. Put `Hold` on every draft you want to keep, then run `installDelayedGmailSend`.

Change the wait and the trigger interval with `DELAY_MINUTES` and `TRIGGER_INTERVAL_MINUTES` at the top of `Code.gs`. Label names are `HOLD_LABEL_NAME`, `RELEASE_LABEL_NAME`, `SEND_FAILED_LABEL_NAME`, and `LEGACY_SEND_LABEL_NAME`. `installDelayedGmailSend` stores the Hold, Release, and Send failed label ids in script properties. A thread matches if the stored id is on it or the name is exactly `Hold`, `Release`, or `Send failed`. Renaming, nesting, or recasing that same label still matches. A label created later with the exact name matches too. An older install that has not stored the id yet looks the label up by that exact name on the first run and stores the id. `TRIGGER_INTERVAL_MINUTES` must be 1, 5, 10, 15, or 30. After changing it, run `installDelayedGmailSend` again so the installed trigger picks up the new interval. Run it again after this sticky-Hold update so `Release` exists. The remembered drafts are script properties `delayedSendHeldDrafts` (draft id to last seen message id) and `delayedSendReleasedAt` (draft id to the time the release clock started). A pass reads each once, drops ids that are no longer drafts, and writes back only if the value changed. Each value is capped under the 9KB script-property limit. A dropped id is logged.

## Deploy

The Apps Script project has to live in the same Google account as the mailbox. A private script uses Google's own consent screen. Do not create an OAuth client, and do not commit one.

### Paste into script.google.com

1. Open [script.google.com](https://script.google.com) while signed in as `you@gmail.com`. Create a project.
2. Replace the default `Code.gs` with the `Code.gs` in this folder.
3. Open Project Settings and turn on "Show 'appsscript.json' manifest file in editor". Replace that file with the `appsscript.json` in this folder. The manifest pins the V8 runtime and the two scopes below.
4. Save.
5. Put `Hold` on drafts you do not want sent. Then choose `installDelayedGmailSend` and Run it once. That creates the labels if they are missing, stores their ids, and installs the trigger. The manifest scopes do not change for this.
6. Approve the consent screen. It should ask to manage Gmail (read, send, and change labels) and to manage triggers in this script. Those are the two scopes in `appsscript.json`. No new scope is required.

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

An install from the older opt-in script calls `sendLabeledDraftsAfterDelay`. That name still runs this pass. `installDelayedGmailSend` deletes a trigger on that name and leaves one trigger on `sendDraftsAfterDelay`.

### Smoke test before real use

Do this once in the account that owns the drafts, before the first real message. It takes about 15 minutes because the draft has to age. Nothing in this repo can run it. Put `Hold` on every draft you want to keep before step 1.

1. Run `installDelayedGmailSend` and approve the consent screen. `Hold`, `Release`, and `Send failed` should exist. `Send in 5` is not created.
2. Compose a new draft addressed to yourself, with a subject you can recognize. Leave it in Drafts and close the compose window.
3. In the Apps Script editor, choose `sendDraftsAfterDelay` and Run. The draft is only a few seconds old, so the log should say `Waiting to send draft` and the draft should still be in Drafts.
4. Wait until that draft's last save is at least 5 minutes ago. Run `sendDraftsAfterDelay` again. The log should include `Sent draft` with that draft id and subject. The message should be in Sent.
5. Create another draft, add `Hold`, and wait past 5 minutes. Run `sendDraftsAfterDelay`. That draft must still be in Drafts. Remove `Hold`. The next run must not send it. Wait 5 minutes from that run and run it again. The log should include `Sent draft`. Adding `Release` instead of removing `Hold` does the same wait.
6. Create a draft and delete it. Run `sendDraftsAfterDelay`. That draft must not send, and the thread must not gain `Send failed`. Deleting the draft is the cancel.

## Keep a draft

Run `installDelayedGmailSend` before the first use so `Hold`, `Release`, and `Send failed` exist. You can also create those labels yourself with those exact names.

Desktop, including Edge and any other browser:

1. Compose the message and leave it in Drafts. Gmail autosaves while the compose window is open. If you leave it, it sends itself about 5 to 6 minutes after the last save.
2. To keep it, open Drafts, select the draft, and apply the label `Hold` (Labels menu, or drag the draft onto the label).

Phone, in the Gmail app:

1. Compose, then leave the draft so it saves. Close compose so you are looking at the Drafts list.
2. Touch and hold the draft in that list. Do not open it. Opening a draft on the phone opens compose, and compose has no label control.
3. Tap More, then Labels. On some Android versions the menu says Label as. Check `Hold` and confirm. Gmail's [iPhone and iPad help](https://support.google.com/mail/answer/118708?co=GENIE.Platform%3DiOS&hl=en) is: touch and hold the mail, then More, then Labels. The app moves these menus. If the wording differs, apply the label from the list selection, not from inside compose.

Gmail's Schedule send is not a draft this script sends. Live check on 2026-11-24: a message scheduled in Gmail web for the next morning was not returned by `getDrafts()`. It had no `DRAFT` label, only Important and the scheduled state, and this script did not send it across more than 7 minutes. `GmailThread.getLabels()` returns user labels, not the `SCHEDULED` system label, and `GmailMessage` has no label method. Seeing that system label would mean the advanced Gmail service, which this script does not enable. There is no extra scheduled-message skip. Schedule send and this 5-minute clock stay separate.

An open compose window that keeps autosaving keeps the message young, so the send waits until 5 minutes after the last save.

`Hold`, `Release`, and `Send failed` are thread labels. Every draft on that thread shares them. Holding one draft in a conversation holds the others. `Send failed` on a conversation skips the others until you remove it. If one remembered draft on that thread changes message id and `Hold` is gone, the script puts `Hold` back for the whole thread. It cannot tell a label you removed from a label an edit stripped, so the other drafts stay held too. A draft the script has never seen on `Hold` still sends 5 minutes after its last save.

## Cancel

Before the script sends, either:

- add the label `Hold`, or
- delete the draft.

Editing and saving also starts the 5 minutes over. Gmail's Send button sends now and leaves nothing for this script to send.

The save clock is the draft's last save. Gmail does not tell the script when a label was added or removed. The release clock is the pass that saw `Hold` come off, or saw `Release`. The script stores that time.

## Uninstall

Run `uninstallDelayedGmailSend` in the Apps Script editor. That removes this project's delayed-send trigger, including the older `sendLabeledDraftsAfterDelay` handler and duplicates. The Gmail labels stay. Delete `Hold`, `Release`, and `Send failed` in Gmail if you no longer want them. Delete `Send in 5` too if an older install created it.

Running `installDelayedGmailSend` again is safe. It reuses `Hold`, `Release`, and `Send failed` and leaves exactly one trigger, at `TRIGGER_INTERVAL_MINUTES`.

## Quotas

Consumer Google accounts, not Workspace. Quotas are per user and reset 24 hours after the first request, not at midnight. A failure in the afternoon can still be in force the next morning. The numbers are the [Apps Script quota table](https://developers.google.com/apps-script/guides/services/quotas). Google can change them.

- Trigger runtime is about 90 minutes per day. A one-minute trigger runs up to 1,440 times per day, so the average budget is about 3.7 seconds per run. This script returns as soon as there are no drafts. It reads every draft in the folder.
- Each execution also stops at 6 minutes. Immediately before `send()`, the script stores the draft id, the message id, and the time in script properties. If the run is killed inside `send()` and that same message is still a draft, the next run does not send it. It applies `Send failed` and logs `possible interrupted send, check Sent`. Check Sent before you remove that label: the message may already have gone out. That label is on the thread, so a sibling draft on the same thread is skipped too. If `send()` returns or throws, the stored record is cleared. A kill after a successful send, and before a leftover `Send in 5` is removed, can still leave that old label on the sent thread. Remove it by hand if you still use it.
- Email read/write, excluding send, is 20,000 per day. `MailApp.getRemainingDailyQuota()` does not report this number, and calling it would need the extra `script.send_mail` scope. Google does not publish the units per GmailApp call. This pass calls `getDrafts()` once, then `getMessage()`, `getThread()`, and `getLabels()` for each draft. A second draft on a thread already checked in that pass skips `getLabels()`. A draft that is old enough pays another `getDraft`, `getMessage`, `getThread`, and `getLabels` immediately before send. Those extra calls are rare next to the every-pass scan. Until the Hold, Release, and Send failed label ids are stored, a pass also calls `getUserLabelByName` for each missing id. Install stores all three, so that lookup is not part of the steady scan. Putting `Hold` back after an edit is one `addLabel` on that pass, not on every pass. Counted as one unit per call, a one-minute trigger's scan costs about `1,440 × (1 + 3 × drafts)` per day: about 5,760 at 1 draft, about 18,720 at 4 drafts, and about 23,040 at 5 drafts. Held or not, every draft in the folder is read. A folder of about four drafts is near the cap, and about five is over it, if that per-call guess is right.
- `label.getThreads()` and `GmailApp.search` are not used to shrink that list. Draft-only threads are often missing from both, and a new compose is usually a draft-only thread. Filtering that way would skip the send.
- `ClockTriggerBuilder.everyMinutes` allows 1, 5, 10, 15, or 30. It rejects 2, so a two-minute trigger cannot be installed. This script stays at 1 minute so a draft that is already 5 minutes old is seen about a minute later. Set `TRIGGER_INTERVAL_MINUTES` to 5 and run `installDelayedGmailSend` again if the gmail daily quota starts firing: 288 passes a day is about 18,720 units at 20 drafts under the same guess, and an already-old draft can wait about 5 minutes instead of about 1.
- A slow pass can still spend the 90 minutes of trigger time on a very large draft list. Triggers then stop until the quota resets.
- `GmailDraft.send()` counts toward the send quota, about 100 recipients per day on a consumer account. The same retry-later rule covers that daily recipient quota, the Gmail read/write quota (`for one day: gmail`, and the documented `Service invoked too many times: gmail.`), a short burst (`in a short time: gmail` or `in a short time: email`), and the daily computer-time cap (`Service using too much computer time for one day.`). The draft stays eligible, `Send failed` is not applied, the rest of that run does not send, and the run fails at most once an hour so the execution list shows it. A later run tries again. Add `Hold` or delete the draft to stop the retries.
- Triggers can overlap if a run is slow. The script takes `LockService.getScriptLock()` with a wait of 0 milliseconds and skips the pass when another run in this project holds it, so two passes in one project cannot send the same draft. The wait is 0 so a blocked pass does not sit on the daily trigger-time budget. A second Apps Script project has its own lock. See Deploy.
- With the one-minute trigger, delivery is about 5 to 7 minutes after the last save, not exactly 5:00. Triggers drift.

## If a send fails

A read error before `send()` is logged and tried on the next run. It does not apply `Send failed`. A one-time `Service error: Gmail` from `getLabels` is that kind of error. The daily computer-time limit is a retry-later quota, described above, not a parked draft.

A non-quota `send()` failure is logged with the draft id, the subject, and the error. The script records that draft id and message id and does not call `send()` again for that message. It applies `Send failed` when no other draft on the thread is still waiting, not yet processed, held back by a quota error, or waiting on a read error. Until then the log says another draft on the thread is still waiting. The thread label cannot park one draft and keep another. If you edit the draft, the message id changes, that record is cleared, and the normal 5-minute clock applies. If applying `Send failed` throws, `send()` is still not called again until the message id changes. The log says the failure label could not be applied. A leftover `Send in 5` is removed only after `Send failed` is actually on the thread. If that remove throws, `Send failed` stays and the draft is still skipped. Once the label is on, the failure record is cleared, so removing `Send failed` makes an old draft eligible on the next run.

A thread that already has `Send failed` is skipped. The first skip for each draft is logged with the draft id and not the subject. Later runs do not log that draft again.

A draft with no To, Cc, and no Bcc is logged as `Draft has no recipient` and parked on `Send failed`. `send()` is not called. Empty To with a Cc or a Bcc is sent. A reply draft is an ordinary draft: `GmailDraft.send()` keeps the thread, and a reply with no recipient is parked the same way.

The draft stays in Drafts until a send works or you delete it. The idea of parking a failed draft on its own label comes from [GmailSendLater](https://github.com/devietti/GmailSendLater). That repository has no license, so this script does not copy its code. `Send failed` is this script's label, created by `installDelayedGmailSend`, and it is applied only after a non-quota failure.

To spot one: open the `Send failed` label in Gmail, or read the execution log. The log has the draft id, the subject, and the error. It does not include the body or the recipients.

To retry: fix the draft and remove `Send failed`. Do not add `Hold` unless you want to keep it. The clock is still the draft's last save. An old draft sends on the next run. Touch the draft if you want another 5 minutes.

A Gmail quota failure does not do this. Those drafts stay eligible and are tried on a later run. That includes the daily recipient quota, the daily Gmail read/write quota, and a short-time Gmail or email quota.

## If a run fails

A non-quota draft failure is logged and the run still finishes, so the other drafts in that pass are still sent. A Gmail quota error fails the run. A missing `Hold` label does not. With no `Hold` label, nothing is held, and old drafts still send, unless the script already remembered that draft under `Hold`. If `delayedSendHeldDrafts` or `delayedSendReleasedAt` cannot be read or parsed, that pass holds every draft and does not overwrite the stored value.

A quota error throws at most once per hour. The script stores the time of the last throw in script properties, under `delayedSendPersistentFailureLatchedAt`. That value is a timestamp, not a draft id. Properties need no extra scope. Later runs in that hour log the same condition and finish without throwing, so a one-minute failure loop does not pile up. A pass that is not in that state clears the timestamp.

To get an email when a run fails: in the Apps Script editor open Triggers, open this trigger, and set failure notifications. "Once daily" is the setting that matches a one-minute trigger. The script does not send its own error mail. That would spend the same send quota and, on a one-minute trigger, repeat until you removed the cause.

If drafts silently stop sending, open [script.google.com](https://script.google.com), then My Triggers, and look for this handler. Google's trigger page says a failure email includes a link to deactivate the trigger, and a deactivated trigger also stops those emails. The page does not publish how many consecutive failures cause that. Re-enable the trigger after fixing the cause, or run `installDelayedGmailSend` again. That deletes and recreates it.

## How draft age is decided

`GmailDraft` exposes `getId()`, `getMessage()`, `getMessageId()`, `send()`, `update()`, and `deleteDraft()`. There is no last-updated method.

Live check on 2026-11-24: a draft created through the Gmail API at about 1:15 PM, then rewritten with `drafts.update` at 1:19:25 PM, was not sent at 5 minutes after the original create. `getDate()` moved with the edit. The draft sent at 1:25:21 PM, about 5 minutes 56 seconds after the edit. A draft edited in Gmail web behaved the same way. The clock followed the edit, not the original create.

`GmailDraft` has no last-updated method. This script uses `GmailMessage.getDate()` on the draft's current message and does not read the RFC 2822 `Date` header. Gmail's drafts guide describes a save as replacing the message, and the `GmailDraft.send()` sample logs `getDate()` after send. Those pages agree with this result. The live check is the evidence that an edit resets the 5 minutes.

Consequences:

- An edit or autosave replaces the message, so the age falls under 5 minutes and the send waits. If this script has already seen `Hold` on that draft, the edit also makes it put `Hold` back.
- Taking `Hold` off, or adding `Release`, starts a 5-minute release clock stored in script properties. The last save does not have to be redone. The draft sends when both that clock and the save clock are done.
- Just before send, the script loads the draft again with `GmailApp.getDraft(id)`. That picks up a save, a new `Hold`, a new `Release`, or a new `Send failed` that happened after the scan started. If the remembered held entry is still there, it does not send even when the thread no longer shows `Hold`. An edit that lands after that re-read and before `send()` returns can still go out in that send. That gap is one send call.

## Why Hold and Send failed are on the thread

The Gmail API says a draft message cannot have any label except the `DRAFT` system label. `GmailDraft` has no label method. The way to see the label you applied in Gmail is `draft.getMessage().getThread().getLabels()`.

That is a thread label. `label.getThreads()` is not used, because draft-only threads are often missing from thread lists. `GmailApp.search` has the same hole. `getDrafts()` is the list. The pass skips a thread that has `Hold` or `Send failed`, matched by the stored label id or the exact name. It also skips a draft it has remembered under `Hold` when an edit removed the label, and it puts `Hold` back. `Release`, matched the same way, starts the release clock and clears `Hold`.

`GmailDraft.send()` deletes the draft message and creates a new sent message. New messages do not inherit thread labels. The script still calls `removeLabel` for a leftover `Send in 5` on the sent thread when every draft on that thread is finished, so a conversation that already had that old label does not keep it. If the mail was sent and label removal throws, the error is logged and the draft is not sent again. The label is not a gate.

A draft deleted or sent by hand before `send()` is a cancel. `GmailApp.getDraft` throws when that id is gone. The script logs `Draft deleted before send` and does not apply `Send failed`.

## Scopes

`appsscript.json` requests only:

- `https://www.googleapis.com/auth/gmail.modify` — read drafts, send them, create the labels, and add or remove them. Sticky `Hold` uses those same label calls plus script properties. It does not need a new scope. `gmail.compose` can send drafts and cannot change labels. `gmail.labels` can edit label definitions and cannot send. `https://mail.google.com/` is broader than this script needs. GmailApp's own docs list `https://mail.google.com/` on each method and also allow the matching REST scope. If Google's consent screen refuses to authorize with `gmail.modify` alone, stop and treat that as a real scope failure rather than guessing a wider scope in this repo.
- `https://www.googleapis.com/auth/script.scriptapp` — create and delete the trigger.

## Logs

`Logger` writes to the Apps Script execution log for this project. A pass with no drafts writes nothing. `Hold` writes `Holding draft` with the draft id and not the subject, on every run, because that draft is still being held. Putting `Hold` back after an edit logs `Re-applied Hold after an edit dropped it` with the draft id. A failed put-back logs `Could not re-apply Hold` and does not apply `Send failed`. Removing `Hold` logs `Hold removed. Release clock started`. `Release` logs `Release label wins`. Those lines have the draft id and not the subject. Waiting lines also log the draft id and not the subject. A release that is still inside 5 minutes uses `stage=release`. A thread that already has `Send failed` logs `Skipping draft on Send failed` once per draft, with the draft id and not the subject, and later runs add no line for that draft. `Sent draft` logs the draft id and the subject. A real send failure logs the draft id, the subject, and the error. The log does not include the body or the recipients. One bad draft does not stop the others. A quota error, including the daily computer-time cap, fails the run so the execution list shows it, at most once an hour while that condition is still failing. Those repeating quota lines do not include the subject.

Logs stay in the Google account. They are not written to this repo.

## Prior art

Nothing below was copied. The lock and the quota stop were written for this script from Apps Script's [LockService](https://developers.google.com/apps-script/reference/lock/lock-service) and the documented quota errors for the `email` and `gmail` services.

- [devietti/GmailSendLater](https://github.com/devietti/GmailSendLater) — no license. A label such as "send at 9am tomorrow" schedules a clock time, on about a 15-minute trigger. It also parks a draft it could not handle by applying an error label. Adopted: that parking idea only, reimplemented here as `Send failed` after a non-quota send failure. No code was copied. The clock-time schedule was not adopted.
- [google-code-export/gmail-delay-send](https://github.com/google-code-export/gmail-delay-send) — the old Google Code project page listed MIT. This export has no `LICENSE` file. It is a spreadsheet of settings, a 5-minute trigger, retries that sleep, and an optional error email. Rejected: no license file in the export, and sleep-retries would spend the consumer trigger-time quota.
- [labnol/email-studio-gmail-addon](https://github.com/labnol/email-studio-gmail-addon) — MIT, Amit Agarwal. A Gmail add-on that stores scheduler rules. An older public write-up sends a reconstructed copy with `GmailApp.sendEmail` and trashes the draft. Rejected: different product. `GmailDraft.send()` keeps the draft's recipients, attachments, and thread.
- [hadasfester/81bfc5668cb7b666b4fd6eeb6db804c3](https://gist.github.com/hadasfester/81bfc5668cb7b666b4fd6eeb6db804c3) — no license. Searches `in:draft label:` and throws if a send fails, which stops the rest of the drafts. Rejected: no license, search misses some drafts, and one failure blocks the others.
- [jiehan1029/snooze-outbox-gmail-addon](https://github.com/jiehan1029/snooze-outbox-gmail-addon) — no `LICENSE` file. A label-based schedule-send add-on. Rejected: no license, and it schedules a clock time.

Gmail's own Undo Send stops at 30 seconds. Gmail's Schedule send picks a clock time. Neither is this delay.

Gmail does not say when a label was applied or removed. The release clock is the time this script noticed, stored per draft id. The save clock stays the draft message date.
