---
thread: gmail-delayed-send
status: active
created: 2026-11-24T19:22Z
supersedes: handoffs/archive/gmail-delayed-send/20261124-1742-gmail-delayed-send.md
private_detail: null
---

# Sticky Hold is in the branch, not in the mailbox

## Objective

Stop an API edit from clearing `Hold` on a Gmail draft the delayed-send script has already seen. Do not deploy. Do not merge.

## Current State

- On branch `cursor/gmail-delayed-send-opt-out-dea1`, pull request 27. Sticky Hold is committed on that branch. Not merged. Not deployed. Not live-tested.
- `node apps_script/gmail_delayed_send/stand_in_test.mjs`: 58 tests, `all assertions passed`.
- The live mailbox still runs the previous opt-out build until `Code.gs` is pasted and `installDelayedGmailSend` is run.
- `appsscript.json` scopes are unchanged: `gmail.modify` and `script.scriptapp`.

## Why This Matters

- `drafts.update` replaces the message and the new message carries no user labels. Gmail rejects labels on draft create or update. A standalone draft lost `Hold` and would send 5 minutes later. The draft id stays; the message id changes.

## Key Decisions Already Made

- Decision: Remember `delayedSendHeldDrafts` (draft id to message id) and `delayedSendReleasedAt` (draft id to epoch ms). Read once per pass, prune ids missing from `getDrafts()`, write back only if changed. Cap each value at 7000 characters.
- Why: The draft id is the stable key. The message id tells an edit apart from a person removing `Hold`.
- Tradeoff: Over the cap, the highest sorted draft ids are dropped and logged. Those drafts are not sticky until `Hold` is seen again and the map has room.

- Decision: A changed message id with no `Hold` puts `Hold` back and skips. The same message id starts a 5-minute release clock. `Release` wins, clears `Release` and `Hold`, and uses that same clock. Send only when the message age and the release clock are both at least `DELAY_MINUTES`.
- Why: Release should not require a re-save, and an edit must not look like a release.
- Tradeoff: Removing `Hold` and editing in the same minute stays held, because the message id changed.

- Decision: If any remembered draft on a thread changed message id, every draft on that thread stays held.
- Why: `Hold` is a thread label. An edit that strips it and a person removing it look the same for a sibling whose message id did not change. When unsure, hold.
- Tradeoff: A sibling does not start the release clock on the pass that restores `Hold`.

- Decision: If putting `Hold` back throws, keep the old message id and retry next pass. Do not mark `Send failed`. If the maps cannot be read or parsed, hold every draft that pass and do not overwrite the properties.
- Why: A label-write failure is not a failed send. An unreadable map would otherwise send mail that was held.
- Tradeoff: While restore keeps failing, removing `Hold` does not start the release clock. Add `Release` to start it.

- Decision: The pre-send re-read treats a remembered draft as held even when the thread has no `Hold`.
- Why: `GmailApp` can serve a stale scan, and the label may already be gone by `send()`.
- Tradeoff: That last check does not turn a remembered entry into a release. The release decision happens in the scan.

## Open Questions

- None for the code. Paste `Code.gs` and run `installDelayedGmailSend` before trusting it in the mailbox. That creates `Release`.

## Constraints and Guardrails

- Public repo. No mailbox address, token, script id, OAuth client, or personal name in git.
- Do not merge. Do not deploy. Do not post a pull-request comment.
- Do not make `Send in 5` a gate. Do not add a scope.

## Files / Artifacts / Sources

- `apps_script/gmail_delayed_send/Code.gs`
- `apps_script/gmail_delayed_send/README.md`
- `apps_script/gmail_delayed_send/stand_in_test.mjs`
- `docs/decision-notes.md` section "Gmail delayed-send sticky Hold"
- Pull request 27, branch `cursor/gmail-delayed-send-opt-out-dea1`

## Next Best Actions

1. Paste `Code.gs` and run `installDelayedGmailSend`. Scopes stay the same. `Release` should appear.
2. Do not merge.
3. Live-check an API edit after the script has seen `Hold`, a plain `Hold` removal that waits 5 minutes, and `Release`.

## Known Risks or Failure Modes

- An API edit in the first minute, before the first pass sees `Hold`, still drops the label. The script has nothing to put back.
- The first trigger after install still sends every draft whose last save is already 5 minutes old, except threads with `Hold` or `Send failed`.
- A possible interrupted send parks the whole thread. A sibling on that thread is skipped until `Send failed` is removed.
- The 20,000/day read math, the 6-minute cap, and two Apps Script projects not sharing a lock are unchanged.

## Prompt to Resume

Continue from this note on pull request 27, branch `cursor/gmail-delayed-send-opt-out-dea1`. Sticky Hold is in the branch and is not deployed. Focus on a live check after paste and `installDelayedGmailSend`, or a regression in the stand-in tests. Avoid new scopes, deploying without that install, putting `Send in 5` back into eligibility, and any mailbox address, token, script id, or OAuth client. Validate with `node apps_script/gmail_delayed_send/stand_in_test.mjs`: 58 tests, including an edit that puts `Hold` back, a 5-minute release clock, `Release`, pruning, a failed label write that is not `Send failed`, and the pre-send hold.
