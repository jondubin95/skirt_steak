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

Change the wait and the label name with `DELAY_MINUTES` and `SEND_LABEL_NAME` at the top of `Code.gs`. The label name must match exactly, including spaces and the digit.

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

## Use the label

Run `installDelayedGmailSend` before the first use so the label exists. You can also create a label with the exact name `Send in 5` yourself.

Desktop, including Edge and any other browser:

1. Compose the message and leave it in Drafts. Gmail autosaves while the compose window is open.
2. Open Drafts, select the draft, and apply the label `Send in 5` (Labels menu, or drag the draft onto the label).
3. Leave the draft alone.

Phone, in the Gmail app:

1. Compose, then leave the draft so it saves.
2. Open it from Drafts and apply the label `Send in 5` the same way you label any conversation.
3. Leave the draft alone.

An open compose window that keeps autosaving keeps the message young, so the send waits until 5 minutes after the last save.

## Cancel

The script sends only while the draft exists and the thread still has `Send in 5`. Before that happens, either:

- remove the label `Send in 5`, or
- delete the draft.

Editing and saving also starts the 5 minutes over.

The clock is the draft's last save, not the moment you applied the label. Gmail does not tell the script when a label was added. A draft you just saved still has about 5 minutes. A draft last saved more than 5 minutes ago becomes eligible on the next trigger after you label it, which is about a minute, not another 5. Touch the draft (open it and let it save) if you want the full wait on an older draft.

## Uninstall

Run `uninstallDelayedGmailSend` in the Apps Script editor. That removes this project's minute trigger, including duplicates of the same handler. The Gmail label stays. Delete `Send in 5` in Gmail if you no longer want it.

Running `installDelayedGmailSend` again is safe. It reuses the label and leaves exactly one minute trigger.

## Quotas

Consumer Google accounts, not Workspace:

- Trigger runtime is about 90 minutes per day. A one-minute trigger runs up to 1,440 times per day, so the average budget is about 3.7 seconds per run. This script returns as soon as there are no drafts, and it only sends drafts whose thread has the label.
- A mailbox with a very large draft list can make `GmailApp.getDrafts()` plus a label check on each draft slow enough to spend that 90 minutes. Triggers then stop until the next day.
- `GmailDraft.send()` counts toward the Gmail Apps Script send quota, about 100 recipients per day on a consumer account. Over that, the send throws, the draft stays labeled, and a later run tries again. Remove the label or delete the draft to stop the retries.
- Minute triggers drift. Delivery is about 5 to 7 minutes after the last save, not exactly 5:00.

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

That is a thread label. Every draft on that thread is eligible. `label.getThreads()` is not used, because draft-only threads are often missing from thread lists. `GmailApp.search` has the same hole. `getDrafts()` is the list, filtered by the thread label.

`GmailDraft.send()` deletes the draft message and creates a new sent message. New messages do not inherit thread labels. The script still calls `removeLabel` on the sent thread so a conversation that already had other labeled messages does not keep `Send in 5`. If the mail was sent and label removal throws, the error is logged and the draft is not sent again.

## Scopes

`appsscript.json` requests only:

- `https://www.googleapis.com/auth/gmail.modify` — read drafts, send them, create the label, and remove the label. `gmail.compose` can send drafts and cannot change labels. `gmail.labels` can edit label definitions and cannot send. `https://mail.google.com/` is broader than this script needs. GmailApp's own docs list `https://mail.google.com/` on each method and also allow the matching REST scope. If Google's consent screen refuses to authorize with `gmail.modify` alone, stop and treat that as a real scope failure rather than guessing a wider scope in this repo.
- `https://www.googleapis.com/auth/script.scriptapp` — create and delete the trigger.

## Logs

`Logger` writes to the Apps Script execution log for this project. A pass with nothing labeled writes nothing. Waiting, sending, label-removal failure, and per-draft errors are logged with the draft id and subject, not the body and not the recipients. One bad draft does not stop the others. A missing label fails the run so the execution list shows it.

Logs stay in the Google account. They are not written to this repo.
