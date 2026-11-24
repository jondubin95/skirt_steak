# Decision notes

What failed or was risky, what changed, the evidence, and the date. Record only what the repo already shows.

## Template

- What failed or was risky:
- What changed:
- Evidence:
- Date:

## Keyword-triggered skills

- What failed or was risky: `disable-model-invocation` made skills slash-only, so they did not load unless someone typed `/skill-name`.
- What changed: That flag was removed the same day. Skills load when the prompt contains their keywords.
- Evidence: Commits `3fcf7d0` and `ff6a004`. `.cursor/skills/README.md`.
- Date: 2026-09-20

## Cloud Agent git hooks

- What failed or was risky: `setup-hooks` sets `core.hooksPath` to `.githooks`, which replaces Cursor's agent-hooks wrapper on a Cloud Agent VM.
- What changed: Cloud Agents are told not to run `setup-hooks`. CI enforces branch names and `Sensitive/` instead.
- Evidence: Commits `cd84a23` and `4d36d3e`. `tools/workflow_guardrails/README.md`.
- Date: 2026-09-20

## Case-variant Sensitive paths

- What failed or was risky: A case-sensitive filter would miss `sensitive/` or `SENSITIVE/`, and a differently cased README could look allowed.
- What changed: CI matches `Sensitive/` without regard to case. The allowlist stays the exact path `Sensitive/README.md`.
- Evidence: Commit `290611e`. `.github/workflows/guardrails.yml`.
- Date: 2026-10-25

## Gmail delayed-send draft age

- What failed or was risky: `GmailDraft` has no last-updated field, and a draft message cannot hold a user label. Using the label time is impossible from GmailApp. Using a message label id would never match. Either mistake sends during an edit, or never sends.
- What changed: Age is `GmailMessage.getDate()` on the draft's current message. A save replaces that message, so an edit resets the clock. The send label is matched on the draft's thread, then removed from the sent thread.
- Evidence: `apps_script/gmail_delayed_send/Code.gs` and `apps_script/gmail_delayed_send/README.md`.
- Date: 2026-11-24

## Gmail delayed-send prior art

- What failed or was risky: Open send-later scripts schedule a clock time, retry with sleep, reconstruct the message, or stop the whole run on one draft. Several have no license. A stored label-applied time would change the 5-minute message-date clock. `MailApp.getRemainingDailyQuota()` needs an extra scope.
- What changed: No third-party code was copied. Overlapping runs take `LockService.getScriptLock()` and skip if it is held. A daily recipient-quota error stops the rest of that run and fails the execution. Other per-draft errors still do not stop the rest.
- Evidence: `apps_script/gmail_delayed_send/Code.gs` and the Prior art section of `apps_script/gmail_delayed_send/README.md`.
- Date: 2026-11-24

## Gmail delayed-send review follow-up

- What failed or was risky: A Gmail read/write quota error (`for one day: gmail`, `in a short time: gmail`) was parked on `Send failed`, so a healthy draft never retried. The same missing label or quota error could fail every minute. Sending one draft removed the thread label and stranded any other draft on that thread. `Send failed` was applied before `Send in 5` was removed. A draft deleted mid-run was parked. The success log read the subject after `send()`.
- What changed: Those quota errors keep `Send in 5` and stop the pass. A missing label or a quota error throws at most once per hour, using a script-property timestamp. The thread label stays while another labeled draft still needs it. `Send in 5` is removed before `Send failed`, in separate tries. A missing draft is a cancel. The subject is read before `send()`. The trigger stays at one minute because `everyMinutes(2)` is not a legal interval. `label.getThreads()` stays unused because it misses draft-only threads.
- Evidence: `apps_script/gmail_delayed_send/Code.gs`, `apps_script/gmail_delayed_send/README.md`, and `apps_script/gmail_delayed_send/stand_in_test.mjs`.
- Date: 2026-11-24

## Gmail delayed-send failure label

- What failed or was risky: A non-quota send error left `Send in 5` on the thread, so the minute trigger retried it until someone noticed the log.
- What changed: That failure logs the error, applies `Send failed`, and removes `Send in 5`. A daily recipient-quota error still keeps `Send in 5`. The parking idea is from GmailSendLater and the code is new. `installDelayedGmailSend` creates both labels.
- Evidence: `apps_script/gmail_delayed_send/Code.gs` and `apps_script/gmail_delayed_send/README.md`.
- Date: 2026-11-24

## Gmail delayed-send is opt-out

- What failed or was risky: The 5-minute send ran only when the thread had `Send in 5`. A draft with no recipient, or a draft already marked `Send failed`, could not be expressed once every draft was eligible. The first run after install will send every draft whose last save is already 5 minutes old.
- What changed: Every draft sends after 5 quiet minutes. `Hold` opts a thread out and is created by `installDelayedGmailSend`. `Send failed` still parks a non-quota failure, and a thread that already has it is skipped. Quota errors stay eligible and still throw at most once an hour. `Send in 5` is not a gate. It is removed after a finished send, or after `Send failed` is applied, when no draft on that thread is still waiting or held for quota. A draft with no To, Cc, or Bcc is parked instead of calling `send()`. Empty To with a Cc or Bcc still sends. Reply drafts use `GmailDraft.send()`.
- Evidence: `apps_script/gmail_delayed_send/Code.gs`, `apps_script/gmail_delayed_send/README.md`, and `apps_script/gmail_delayed_send/stand_in_test.mjs`.
- Date: 2026-11-24
