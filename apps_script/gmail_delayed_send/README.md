# Gmail delayed send

Sends a Gmail draft after it has been left alone for 5 minutes. Gmail's own Undo Send stops at 30 seconds, and it cannot hold a normal send longer than that.

Use this on a personal Gmail account (`you@gmail.com`), not a Google Workspace mailbox. The script runs as the Google account that authorized it, and it only sees that account's drafts.

This folder is in a public repo. Do not put a mailbox address, token, script id, OAuth client, or `.clasp.json` here.

## What it does

Write the email in Drafts and leave it. About 5 to 6 minutes after the last save, it goes out. A late trigger can make that closer to 7. Gmail's normal Send button still sends instantly, because the message is no longer a draft.

Add the label `Hold` to keep a draft. The script never auto-sends a thread with that label. Add `Release now` and the draft sends about 5 minutes after the script notices. Take `Hold` off and it takes one extra confirming pass before that 5-minute clock starts, so with the one-minute trigger the mail goes out about 6 to 7 minutes after the removal, not 5. Both clocks have to be done: 5 minutes from the last save, and 5 minutes from that release. A draft you just saved still waits. An old draft does not go out on the next run just because you removed `Hold`.

Once a pass has saved `Hold`, an edit does not drop that protection. The draft id stays the same and the message id changes. The script remembers the draft id and the message id. If a later pass finds no `Hold` and the message id changed, it puts `Hold` back and keeps the draft. That includes removing `Hold` and editing in the same minute: the message id changed, so it stays held. If the message id is the same, that is not treated as a release on one look. A fresh draft read has to agree, and the next pass has to agree again, before the 5-minute release clock starts. `Release now` does the same clock and wins over `Hold`. The script takes `Hold` off first, and takes `Release now` off only when those `Hold` removals succeeded. It keeps the original release time while a removal is still failing, including after that time is old enough that an ordinary release entry would be forgotten. The clock is not reset.

Live check on 2026-11-24: editing a draft through the Gmail API (`drafts.update`, including a connector `update_draft`) creates a new message that does not carry `Hold`. On a draft that is alone on its thread, the thread loses `Hold`. An older message on the same thread can still carry it, because labels cannot be set through `drafts.create` or `drafts.update`, and thread labels are the union of the message labels. The sticky `Hold` above is the fix for a draft the script has already saved, and it is not live-deployed or live-tested yet. The gap that remains is a `Hold` that is added and then stripped by an API edit before any pass has successfully saved that draft. A pass that cannot save, a pass killed before that save, and a full property store hold every draft instead of sending. If putting `Hold` back throws, the draft stays remembered and the next pass tries again. It is not marked `Send failed`. The run throws at most once an hour so the trigger failure email can fire. That limit is stored in `CacheService`, not in script properties. If the cache cannot be written, the run throws when the minute of the hour is below `TRIGGER_INTERVAL_MINUTES`, so a properties outage does not fail every minute and a 5-minute trigger still alerts about once an hour.

No label is required for a send. `Send in 5` is the old opt-in label. This version does not look at it when deciding whether to send. If it is still on a thread, the script takes it off after a successful send, or after it applies `Send failed`, and only when no other draft on that thread is still waiting or held back by a quota error. Leaving `Send in 5` on a draft does not queue it and does not block it.

Nothing sends until `installDelayedGmailSend` has run for this version of the script. Saving `Code.gs`, or a `clasp push`, does not send by itself. The trigger from an older install, including the live opt-out build, calls the new code and returns until that install writes `delayedSendArmedVersion`. Put `Hold` on every draft you want to keep before you run install. After install, anything already older than 5 minutes sends on the next run unless the thread has `Hold` or `Send failed`.

Change the wait and the trigger interval with `DELAY_MINUTES` and `TRIGGER_INTERVAL_MINUTES` at the top of `Code.gs`. Label names are `HOLD_LABEL_NAME`, `RELEASE_LABEL_NAME` (`Release now`), `SEND_FAILED_LABEL_NAME`, and `LEGACY_SEND_LABEL_NAME`. `installDelayedGmailSend` stores the Hold, Release now, and Send failed label ids in script properties. `Hold` and `Send failed` match the stored id or the exact name. `Release now` matches the stored id only, so a label you already had with that name does not count. Renaming, nesting, or recasing stored `Hold` or `Send failed` still matches, and running install again keeps that same id. It does not create a second `Hold`. A stored release id is kept only when that label is still named `Release now` or `Release now (delayed send)`. An older `delayedSendReleaseLabelId` value is ignored. If the stored label was deleted, `Hold` and `Send failed` are created again by exact name. If `Release now` already exists and is not the stored label, install creates `Release now (delayed send)` instead of adopting yours. An older install that has not stored the Hold or Send failed id yet looks that label up by exact name at most once an hour. It does not look up `Release now` by name. `TRIGGER_INTERVAL_MINUTES` must be 1, 5, 10, 15, or 30. After changing it, run `installDelayedGmailSend` again so the installed trigger picks up the new interval. Run it again after this update so `Release now` exists. The remembered drafts are script properties `delayedSendHeldDrafts` (draft id to last seen message id) and `delayedSendReleasedAt` (draft id to the time the release clock started), plus `delayedSendReleaseSeenOnce` for a removal that still needs a second agreeing pass. A pass reads them together. It drops an id only after `getDraft` returns not-found on two passes in a row. A generic read error does not count, and a run of absent passes without that not-found result does not drop the id. A draft that `getDraft` keeps finding, but `getDrafts` never lists, is kept and, after 60 passes that still find it, is checked once an hour instead of every pass. Those 60 passes are an hour only while the trigger stays at 1 minute. The maps are written with `setProperties`, including a shard-generation pointer. Extra shards are named for that generation. Old shards are deleted afterward, highest number first. A gap or a duplicate id in the active generation makes the state unreadable, and the pass holds every draft. Each property stays under the 9KB limit by splitting across `delayedSendHeldDraftsShard2Gen<n>` and the same pattern for the other maps. `<n>` is the active shard generation. A live held draft or an active release time is not dropped to fit. If the maps still cannot fit in the script-property store, the pass holds every draft and throws at most once an hour.

## Deploy

The Apps Script project has to live in the same Google account as the mailbox. A private script uses Google's own consent screen. Do not create an OAuth client, and do not commit one.

### Paste into script.google.com

1. Open [script.google.com](https://script.google.com) while signed in as `you@gmail.com`. Create a project.
2. Replace the default `Code.gs` with the `Code.gs` in this folder.
3. Open Project Settings and turn on "Show 'appsscript.json' manifest file in editor". Replace that file with the `appsscript.json` in this folder. The manifest pins the V8 runtime and the two scopes below.
4. Save. Saving does not send. The trigger does nothing until the next step.
5. Put `Hold` on drafts you do not want sent. Then choose `installDelayedGmailSend` and Run it once. That creates the labels if they are missing, stores their ids, writes `delayedSendArmedVersion`, and leaves exactly one trigger. The manifest scopes do not change for this. If this project already has the opt-out trigger, that same run deletes it and creates one trigger. It does not leave two.
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

3. `clasp push`. The push does not send. The existing trigger returns without sending until the next step.
4. Open the project and run `installDelayedGmailSend` once, then approve permissions. That arms this version and leaves one trigger.

`clasp create --type standalone --title "Gmail delayed send" --rootDir .` from this folder also writes that local `.clasp.json`. Do not commit it.

Only one Apps Script project may hold this trigger. `LockService.getScriptLock()` only blocks overlapping runs inside one project. A second project with the same script can send the same draft again. Before installing elsewhere, run `uninstallDelayedGmailSend` in the old project.

An install from the older opt-in script calls `sendLabeledDraftsAfterDelay`. That name still runs this pass, and it also returns without sending until `installDelayedGmailSend` has armed this version. `installDelayedGmailSend` deletes a trigger on that name and leaves one trigger on `sendDraftsAfterDelay`. The mailbox that already runs the opt-out build only needs that one install after the new code is saved.

### Smoke test before real use

Do this once in the account that owns the drafts, before the first real message. It takes about 15 minutes because the draft has to age. Nothing in this repo can run it. Put `Hold` on every draft you want to keep before step 1.

1. Run `installDelayedGmailSend` and approve the consent screen. `Hold`, `Release now`, and `Send failed` should exist. `Send in 5` is not created.
2. Compose a new draft addressed to yourself, with a subject you can recognize. Leave it in Drafts and close the compose window.
3. In the Apps Script editor, choose `sendDraftsAfterDelay` and Run. The draft is only a few seconds old, so the log should say `Waiting to send draft` and the draft should still be in Drafts.
4. Wait until that draft's last save is at least 5 minutes ago. Run `sendDraftsAfterDelay` again. The log should include `Sent draft` with that draft id and subject. The message should be in Sent.
5. Create another draft, add `Hold`, and wait past 5 minutes. Run `sendDraftsAfterDelay`. That draft must still be in Drafts. Remove `Hold`. The next run must not send it. Run once more so the removal is confirmed, then wait 5 minutes from that run and run it again. The log should include `Sent draft`. Adding `Release now` instead of removing `Hold` does the same wait, without the extra confirmation run.
6. Create a draft and delete it. Run `sendDraftsAfterDelay`. That draft must not send, and the thread must not gain `Send failed`. Deleting the draft is the cancel.

## Keep a draft

Run `installDelayedGmailSend` before the first use so `Hold`, `Release now`, and `Send failed` exist. You can also create `Hold` and `Send failed` yourself with those exact names. Create `Release now` by running install. A label you already named `Release now` is not adopted.

Desktop, including Edge and any other browser:

1. Compose the message and leave it in Drafts. Gmail autosaves while the compose window is open. If you leave it, it sends itself about 5 to 6 minutes after the last save.
2. To keep it, open Drafts, select the draft, and apply the label `Hold` (Labels menu, or drag the draft onto the label).

Phone, in the Gmail app:

1. Compose, then leave the draft so it saves. Close compose so you are looking at the Drafts list.
2. Touch and hold the draft in that list. Do not open it. Opening a draft on the phone opens compose, and compose has no label control.
3. Tap More, then Labels. On some Android versions the menu says Label as. Check `Hold` and confirm. Gmail's [iPhone and iPad help](https://support.google.com/mail/answer/118708?co=GENIE.Platform%3DiOS&hl=en) is: touch and hold the mail, then More, then Labels. The app moves these menus. If the wording differs, apply the label from the list selection, not from inside compose.

Gmail's Schedule send is not a draft this script sends. Live check on 2026-11-24: a message scheduled in Gmail web for the next morning was not returned by `getDrafts()`. It had no `DRAFT` label, only Important and the scheduled state, and this script did not send it across more than 7 minutes. `GmailThread.getLabels()` returns user labels, not the `SCHEDULED` system label, and `GmailMessage` has no label method. Seeing that system label would mean the advanced Gmail service, which this script does not enable. There is no extra scheduled-message skip. Schedule send and this 5-minute clock stay separate.

An open compose window that keeps autosaving keeps the message young, so the send waits until 5 minutes after the last save.

`Hold`, `Release now`, and `Send failed` are thread labels. Gmail reports the union of the labels on the messages in the thread, so every draft on that thread shares them. Holding one draft in a conversation holds the others. `Send failed` on a conversation skips the others until you remove it. If one remembered draft on that thread changes message id and `Hold` is gone, the script puts `Hold` back for the whole thread, including a sibling whose message id did not change. It cannot tell a label you removed from a label an edit stripped until a second pass agrees, so the other drafts stay held too. A draft the script has never saved under `Hold` still sends 5 minutes after its last save. `Release now` on a thread starts the release clock for every draft on that thread before the labels come off.

## Cancel

Before the script sends, either:

- add the label `Hold`, or
- delete the draft.

Editing and saving also starts the 5 minutes over. Gmail's Send button sends now and leaves nothing for this script to send.

The save clock is the draft's last save. Gmail does not tell the script when a label was added or removed. The release clock is the pass that confirmed `Hold` came off, or the pass that saw `Release now`. The script stores that time. A release time in the future is treated as the time of the pass that read it.

## Uninstall

Run `uninstallDelayedGmailSend` in the Apps Script editor. That removes this project's delayed-send trigger, including the older `sendLabeledDraftsAfterDelay` handler and duplicates. The Gmail labels stay. Delete `Hold`, `Release now`, and `Send failed` in Gmail if you no longer want them. Delete `Send in 5` too if an older install created it.

Running `installDelayedGmailSend` again is safe. It reuses the stored Hold, Release now, and Send failed labels, including after a rename or a nest, and leaves exactly one trigger, at `TRIGGER_INTERVAL_MINUTES`. It does not replace those stored ids with a new label of the original name.

## Quotas

Consumer Google accounts, not Workspace. Quotas are per user and reset 24 hours after the first request, not at midnight. A failure in the afternoon can still be in force the next morning. The numbers are the [Apps Script quota table](https://developers.google.com/apps-script/guides/services/quotas). Google can change them.

- Trigger runtime is about 90 minutes per day. A one-minute trigger runs up to 1,440 times per day, so the average budget is about 3.7 seconds per run. This script returns as soon as there are no drafts. It reads every draft in the folder.
- Each execution also stops at 6 minutes. Immediately before `send()`, the script stores the draft id, the message id, and the time in script properties. If the run is killed inside `send()` and that same message is still a draft, the next run does not send it. It applies `Send failed` and logs `possible interrupted send, check Sent`. Check Sent before you remove that label: the message may already have gone out. That label is on the thread, so a sibling draft on the same thread is skipped too. If `send()` returns or throws, the stored record is cleared. A kill after a successful send, and before a leftover `Send in 5` is removed, can still leave that old label on the sent thread. Remove it by hand if you still use it.
- Email read/write, excluding send, is 20,000 per day. `MailApp.getRemainingDailyQuota()` does not report this number, and calling it would need the extra `script.send_mail` scope. Google does not publish the units per GmailApp call. This pass calls `getDrafts()` once, then `getMessage()`, `getThread()`, and `getLabels()` for each draft. A second draft on a thread already checked in that pass skips `getLabels()`. A draft that is old enough pays another `getDraft`, `getMessage()`, one `getThread()`, and `getLabels()`, then one more `getLabels()` immediately before `send()`. Those extra calls matter when many drafts are old enough to send. `Release now` is not looked up by name. A missing `Hold` or `Send failed` id is looked up with `getUserLabelByName` at most once an hour, not on every pass. Putting `Hold` back after an edit is one `getUserLabels()` for the pass, cached, plus one `addLabel` on that pass. Confirming a manual removal also calls `getDraft`, `getMessage`, `getThread`, and `getLabels` on that draft. Counted as one unit per call, the every-pass scan alone is about `1,440 × (1 + 3 × drafts)` per day: about 5,760 at 1 draft, about 18,720 at 4 drafts, and about 23,040 at 5 drafts. That scan figure does not include the pre-send reads. At 4 drafts the scan is under 20,000, and drafts that reach the pre-send recheck add about 5 reads each. Held or not, every draft in the folder is read. A folder of about four drafts is near the cap once sends are included, and about five is over the scan alone, if that per-call guess is right. Script properties are a separate quota. A pass reads the sticky maps once with `getProperties()` and writes them with one `setProperties()` when they changed, including the shard-generation pointer. Old shard keys are deleted after that write. Other records, such as the in-flight send and the failed-send map, still use their own `getProperty` calls. A clean pass also reads `delayedSendPersistentFailureLatchedAt` once so it can delete a leftover value. The once-an-hour failure latch itself lives in `CacheService`, not in that property.
- `label.getThreads()` and `GmailApp.search` are not used to shrink that list. Draft-only threads are often missing from both, and a new compose is usually a draft-only thread. Filtering that way would skip the send.
- `ClockTriggerBuilder.everyMinutes` allows 1, 5, 10, 15, or 30. It rejects 2, so a two-minute trigger cannot be installed. This script stays at 1 minute so a draft that is already 5 minutes old is seen about a minute later. Set `TRIGGER_INTERVAL_MINUTES` to 5 and run `installDelayedGmailSend` again if the gmail daily quota starts firing: 288 passes a day is about 18,720 units at 20 drafts under the same guess, and an already-old draft can wait about 5 minutes instead of about 1.
- A slow pass can still spend the 90 minutes of trigger time on a very large draft list. Triggers then stop until the quota resets.
- `GmailDraft.send()` counts toward the send quota, about 100 recipients per day on a consumer account. The same retry-later rule covers that daily recipient quota, the Gmail read/write quota (`for one day: gmail`, and the documented `Service invoked too many times: gmail.`), a short burst (`in a short time: gmail` or `in a short time: email`), and the daily computer-time cap (`Service using too much computer time for one day.`). The draft stays eligible, `Send failed` is not applied, the rest of that run does not send, and the run fails at most once an hour, using the cache latch described above, so the execution list shows it. A quota error during post-send label cleanup uses that same path. A later run tries again. Add `Hold` or delete the draft to stop the retries.
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

A non-quota draft failure is logged and the run still finishes, so the other drafts in that pass are still sent. A Gmail quota error fails the run, including a quota error while putting `Hold` back. That does not apply `Send failed`. A missing `Hold` label does not fail the run by itself. With no `Hold` label, nothing new is held, and old drafts still send, unless the script already remembered that draft under `Hold`. If the sticky properties cannot be read or parsed, that pass holds every draft, does not overwrite the stored value, and throws at most once an hour. The hour is measured in `CacheService`. If that cache cannot be written, the throw happens when the minute of the hour is below `TRIGGER_INTERVAL_MINUTES`. The same once-an-hour throw covers a sticky write that fails, a `Release now` label that cannot be removed, and a `Hold` put-back that keeps failing. A write failure does not remove labels and does not send. The drafts stay held. A later pass that can save, and that still sees `Hold`, keeps the protection. An API edit that strips `Hold` during a stretch when properties cannot be saved is the same gap as a `Hold` that was never saved.

A quota error throws at most once per hour. The script stores the time of the last throw in `CacheService`, not in script properties. A clean pass deletes a leftover `delayedSendPersistentFailureLatchedAt` property from older builds. That value was a timestamp, not a draft id. Cache needs no extra scope. Later runs in that hour log the same condition and finish without throwing. If the cache cannot be written, the run throws when the minute of the hour is below `TRIGGER_INTERVAL_MINUTES`, so a 5, 10, 15, or 30 minute trigger still hits the window once an hour. A pass that is not in that state clears the cache entry.

To get an email when a run fails: in the Apps Script editor open Triggers, open this trigger, and set failure notifications. "Once daily" is the setting that matches a one-minute trigger. The script does not send its own error mail. That would spend the same send quota and, on a one-minute trigger, repeat until you removed the cause.

If drafts silently stop sending, open [script.google.com](https://script.google.com), then My Triggers, and look for this handler. Google's trigger page says a failure email includes a link to deactivate the trigger, and a deactivated trigger also stops those emails. The page does not publish how many consecutive failures cause that. Re-enable the trigger after fixing the cause, or run `installDelayedGmailSend` again. That deletes and recreates it.

## How draft age is decided

`GmailDraft` exposes `getId()`, `getMessage()`, `getMessageId()`, `send()`, `update()`, and `deleteDraft()`. There is no last-updated method.

Live check on 2026-11-24: a draft created through the Gmail API at about 1:15 PM, then rewritten with `drafts.update` at 1:19:25 PM, was not sent at 5 minutes after the original create. `getDate()` moved with the edit. The draft sent at 1:25:21 PM, about 5 minutes 56 seconds after the edit. A draft edited in Gmail web behaved the same way. The clock followed the edit, not the original create.

`GmailDraft` has no last-updated method. This script uses `GmailMessage.getDate()` on the draft's current message and does not read the RFC 2822 `Date` header. Gmail's drafts guide describes a save as replacing the message, and the `GmailDraft.send()` sample logs `getDate()` after send. Those pages agree with this result. The live check is the evidence that an edit resets the 5 minutes.

Consequences:

- An edit or autosave replaces the message, so the age falls under 5 minutes and the send waits. If this script has already saved `Hold` on that draft, the edit also makes it put `Hold` back.
- Taking `Hold` off starts a 5-minute release clock only after two passes agree, including a fresh draft read on each. Adding `Release now` starts that clock on the pass that sees it, for every draft on the thread. The last save does not have to be redone. The draft sends when both that clock and the save clock are done.
- Just before send, the script loads the draft again with `GmailApp.getDraft(id)` and reads the thread once. That picks up a save, a new `Hold`, a new `Release now`, or a new `Send failed` that happened after the scan started. A `Hold` or `Release now` that appears in that read is saved before any label is removed and before a later draft in the same pass can send. One more label read runs immediately before `send()`. An edit that lands after that last read and before `send()` returns can still go out in that send. That gap is one send call. The scan, not this re-read, is what keeps a draft the script already saved under `Hold`.

## Why Hold and Send failed are on the thread

Labels cannot be set on a draft through `drafts.create` or `drafts.update`. An older message can still carry a user label. `GmailDraft` has no label method. The way to see the label you applied in Gmail is `draft.getMessage().getThread().getLabels()`.

That is a thread label, the union of the labels on the messages. `label.getThreads()` is not used, because draft-only threads are often missing from thread lists. `GmailApp.search` has the same hole. `getDrafts()` is the list. The pass skips a thread that has `Hold` or `Send failed`, matched by the stored label id or the exact name. It also skips a draft it has remembered under `Hold` when an edit removed the label, and it puts the stored `Hold` label back. `Release now`, matched only by the stored label id, starts the release clock for every draft on the thread and clears `Hold` before it clears itself.

`GmailDraft.send()` deletes the draft message and creates a new sent message. New messages do not inherit thread labels. The script still calls `removeLabel` for a leftover `Send in 5` on the sent thread when every draft on that thread is finished, so a conversation that already had that old label does not keep it. If the mail was sent and label removal throws, the error is logged and the draft is not sent again. The label is not a gate.

A draft deleted or sent by hand before `send()` is a cancel. `GmailApp.getDraft` throws when that id is gone. The script logs `Draft deleted before send` and does not apply `Send failed`.

## Scopes

`appsscript.json` requests only:

- `https://www.googleapis.com/auth/gmail.modify` — read drafts, send them, create the labels, and add or remove them. Sticky `Hold` uses those same label calls plus script properties. It does not need a new scope. `gmail.compose` can send drafts and cannot change labels. `gmail.labels` can edit label definitions and cannot send. `https://mail.google.com/` is broader than this script needs. GmailApp's own docs list `https://mail.google.com/` on each method and also allow the matching REST scope. If Google's consent screen refuses to authorize with `gmail.modify` alone, stop and treat that as a real scope failure rather than guessing a wider scope in this repo.
- `https://www.googleapis.com/auth/script.scriptapp` — create and delete the trigger.

## Logs

`Logger` writes to the Apps Script execution log for this project. A pass with no drafts writes nothing. `Hold` writes `Holding draft` with the draft id and not the subject, on every run, because that draft is still being held. Putting `Hold` back after an edit logs `Re-applied Hold after an edit dropped it` with the draft id. A failed put-back logs `Could not re-apply Hold` and does not apply `Send failed`. The first agreeing look at a removal logs `Hold removal seen once`. The next agreeing pass logs `Hold removed. Release clock started`. `Release now` logs `Release label wins`. Those lines have the draft id and not the subject. Waiting lines also log the draft id and not the subject. A release that is still inside 5 minutes uses `stage=release`. A thread that already has `Send failed` logs `Skipping draft on Send failed` once per draft, with the draft id and not the subject, and later runs add no line for that draft. `Sent draft` logs the draft id and the subject. A real send failure logs the draft id, the subject, and the error. The log does not include the body or the recipients. One bad send does not stop the others. One unreadable draft blocks every send on its own thread, not only releases, until that draft can be read. If its thread cannot be identified, it blocks every send in the mailbox for three passes and then stops blocking the other threads, and the run alerts. A fresh read that keeps failing on a tracked draft uses its own counter, so the thread stays held and the run still alerts. A quota error, including the daily computer-time cap, fails the run so the execution list shows it, at most once an hour while that condition is still failing. A sticky state that cannot be read or saved, a `Release now` label that cannot be removed, and a `Hold` put-back that keeps failing do the same. Those repeating lines do not include the subject.

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
