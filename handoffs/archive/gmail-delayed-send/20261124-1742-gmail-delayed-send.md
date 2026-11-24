---
thread: gmail-delayed-send
status: active
created: 2026-11-24T17:42Z
supersedes: handoffs/archive/gmail-delayed-send/20261124-1739-gmail-delayed-send.md
private_detail: null
---

# Gmail delayed-send review fixes are green

## Objective

The eight adversarial-review fixes are in the opt-out script. Do not deploy. Do not merge.

## Current State

- On branch `cursor/gmail-delayed-send-opt-out-dea1`, pull request 27. Behavior commit `b764c88`. Not merged. Not deployed.
- GitHub Guardrails on `b764c88` succeeded.
- `node apps_script/gmail_delayed_send/stand_in_test.mjs`: 48 tests, `all assertions passed`.
- The live mailbox still runs the previous opt-out build until `Code.gs` is pasted and `installDelayedGmailSend` is run.
- `appsscript.json` scopes are unchanged: `gmail.modify` and `script.scriptapp`.

## Why This Matters

- A renamed or nested `Hold` was releasing drafts. A one-time Gmail read error parked a thread on `Send failed`. A failed send retried every minute while a sibling was young.

## Key Decisions Already Made

- Decision: A thread is held or parked when the stored label id matches or the name is exactly `Hold` or `Send failed`. Install stores both ids. A missing id is looked up by exact name and stored on that run.
- Why: The review fix is to match the label id so a rename, nest, or recase keeps the same label.
- Tradeoff: If the id cannot be read, that run matches by exact name only.

- Decision: A failure before `send()` is logged and retried. It does not apply `Send failed`. `Service using too much computer time for one day.` is retry-later. A `Send failed` skip is logged once per draft.
- Why: A blip or the daily computer-time cap was parking mail that should have been tried again.
- Tradeoff: A draft with no recipient, and a draft with a missing or invalid date, are still parked. Those are not read errors.

- Decision: The first non-quota `send()` failure stores the draft id and message id and does not call `send()` again. The thread label is applied when no sibling is still open. An edit clears the record. When the label sticks, the record is cleared, so removing `Send failed` retries.
- Why: Waiting for a young sibling was retrying the failed send forever.
- Tradeoff: If the label cannot be applied, only a new message id clears the block.

- Decision: Immediately before `send()`, store `{draftId, messageId, startedAt}`. Clear it when `send()` returns or throws. If that message is still a draft and the record is older than the run, do not send it; label `Send failed` and log `possible interrupted send, check Sent`.
- Why: A kill inside `send()` could send twice.
- Tradeoff: That label is on the thread, so a sibling draft is skipped too. Check Sent before removing it.

- Decision: No logic change for draft age or Schedule send. The README records the 2026-11-24 live checks. `GmailApp` cannot see the `SCHEDULED` system label without the advanced service, so there is no extra skip.
- Why: `getDate()` followed an API rewrite (sent at 1:25:21 PM, about 5:56 after the 1:19:25 PM edit). A message scheduled for the next morning was not in `getDrafts()` and was not sent over more than 7 minutes.
- Tradeoff: A future Gmail change that puts scheduled mail back into `getDrafts()` would not be filtered.

- Decision: Repeating hold and wait lines log the draft id only. `Sent draft` and a real send failure keep the subject.
- Why: The subject was written every minute.
- Tradeoff: The execution log no longer shows the subject of a draft that is only waiting.

## Open Questions

- None. Paste `Code.gs` and run `installDelayedGmailSend`. No manifest change.

## Constraints and Guardrails

- Public repo. No mailbox address, token, script id, OAuth client, or personal name in git.
- Do not merge. Do not deploy. Do not post a pull-request comment.
- Do not make `Send in 5` a gate.

## Files / Artifacts / Sources

- `apps_script/gmail_delayed_send/Code.gs`
- `apps_script/gmail_delayed_send/README.md`
- `apps_script/gmail_delayed_send/stand_in_test.mjs`
- `docs/decision-notes.md` section "Gmail delayed-send adversarial review"
- Pull request 27, branch `cursor/gmail-delayed-send-opt-out-dea1`, behavior commit `b764c88`

## Next Best Actions

1. Paste `Code.gs` and run `installDelayedGmailSend`. Scopes stay the same.
2. Do not merge.
3. Do not set `TRIGGER_INTERVAL_MINUTES` to 5 unless a real Gmail quota failure is reported.

## Known Risks or Failure Modes

- The first trigger after install still sends every draft whose last save is already 5 minutes old, except threads with `Hold` or `Send failed`.
- A possible interrupted send parks the whole thread. A sibling on that thread is skipped until `Send failed` is removed.
- If `Send failed` cannot be applied after a real `send()` failure, that message is not sent again until its id changes.
- The 20,000/day read math, the 6-minute cap, and two Apps Script projects not sharing a lock are unchanged.

## Prompt to Resume

Continue from this note on pull request 27, branch `cursor/gmail-delayed-send-opt-out-dea1`, behavior commit `b764c88`. Guardrails is green. The live mailbox still has the previous build until `Code.gs` is pasted and `installDelayedGmailSend` is run. Focus on a redeploy report or a regression found in the mailbox. Avoid new scopes, putting `Send in 5` back into eligibility, and any mailbox address, token, script id, or OAuth client. Validate with `node apps_script/gmail_delayed_send/stand_in_test.mjs`: 48 tests, including nested or renamed Hold by id, no resend while a sibling is young, a getLabels blip that does not park, computer-time as retry-later, an interrupted-send block, and hold or wait logs with no subject.
