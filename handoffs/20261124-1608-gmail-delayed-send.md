---
thread: gmail-delayed-send
status: active
created: 2026-11-24T16:08Z
supersedes: handoffs/archive/gmail-delayed-send/20261124-1431-gmail-delayed-send.md
private_detail: null
---

# Gmail delayed send is opt-out

## Objective

Make the 5-minute delay the default. A draft sends after 5 quiet minutes. `Hold` is the opt-out. Do not deploy.

## Current State

- On branch `cursor/gmail-delayed-send-opt-out-dea1`, commit `c4540e9`. Not merged. Not deployed.
- `main` still has the opt-in script at `0fecd28` until this merges.
- `node apps_script/gmail_delayed_send/stand_in_test.mjs`: 41 tests, `all assertions passed`.
- Local checks on this VM: `py_compile`, board-secretary unittest (65), decision-log unittest (25), fanfic pytest (145), the gitignore check, and `ruff check python` passed. Preflight still exits 1 here because the local Docs client file and token directory are absent.

## Why This Matters

- An unlabeled draft used to sit forever. After this merges, an old draft sends on the next run unless the thread has `Hold` or `Send failed`.

## Key Decisions Already Made

- Decision: Every draft is eligible. `Hold` never auto-sends. Removing `Hold` uses the draft's last save, not a new 5 minutes. `installDelayedGmailSend` creates `Hold` and `Send failed`. It does not create `Send in 5`.
- Why: The owner asked for opt-out, with `Hold` as the only keep label.
- Tradeoff: `Hold` and `Send failed` are thread labels. One draft on a thread holds or parks the others.

- Decision: `Send in 5` is not a gate. After a send, or after `Send failed` is applied, it is removed only when no draft on that thread is still waiting or held back by quota. A younger sibling leaves it in place. Removing it does not change who sends.
- Why: Dropping it from the logic was the recommended choice. The remove stays so an old label does not sit on a finished thread.
- Tradeoff: The label can remain while a sibling is still open. That does not queue or block anything.

- Decision: A draft with no To, Cc, and no Bcc is logged as `Draft has no recipient` and parked on `Send failed`. Empty To with a Cc or Bcc still sends. A reply is an ordinary `GmailDraft.send()`.
- Why: That matches the existing non-quota failure path, so an unsendable draft does not crash the run or retry every minute.
- Tradeoff: If Gmail hides a Bcc from `getBcc()`, a Bcc-only draft would be parked. The stand-in treats a non-empty `getBcc()` as sendable.

- Decision: Quota errors stay eligible, stop the rest of the pass, and throw at most once an hour. `LockService.tryLock(0)` stays 0. The trigger stays `everyMinutes(1)`. A thread that already has `Send failed` is skipped with no log line. The old handler name `sendLabeledDraftsAfterDelay` still runs one pass. Install deletes that trigger.
- Why: Those were the safety rules to keep. The missing-label latch is gone because no label is required to send.
- Tradeoff: If applying `Send failed` throws, the draft stays eligible and the next minute tries again. The old script could stop that retry by taking `Send in 5` off even when the failure label did not stick.

## Open Questions

- None in the script. Before the first real install, put `Hold` on every draft that must not go out. The smoke test is still the README, in the real mailbox. This environment has no mailbox.

## Constraints and Guardrails

- Public repo. No mailbox address, token, script id, OAuth client, or personal name in git.
- Do not merge. Do not deploy. Do not post a pull-request comment.
- Scopes stay `gmail.modify` and `script.scriptapp`. No sent-history log or label.
- Do not make `Send in 5` a gate again without a new decision.

## Files / Artifacts / Sources

- `apps_script/gmail_delayed_send/Code.gs`
- `apps_script/gmail_delayed_send/README.md`
- `apps_script/gmail_delayed_send/stand_in_test.mjs`
- `docs/decision-notes.md` section "Gmail delayed-send is opt-out"
- Commit `c4540e9` on `cursor/gmail-delayed-send-opt-out-dea1`

## Next Best Actions

1. Wait until Guardrails is green. Do not merge.
2. Do not deploy until drafts that must stay are on `Hold`, then run the README smoke test in the real account.
3. Do not set `TRIGGER_INTERVAL_MINUTES` to 5 unless a real Gmail quota failure is reported.

## Known Risks or Failure Modes

- The first trigger after install sends every draft whose last save is already 5 minutes old, except threads with `Hold` or `Send failed`.
- A scheduled Gmail send is still a draft. It goes out on this clock unless the thread has `Hold`.
- A failed draft is not parked while a sibling on that thread is still waiting. It retries until the sibling is done.
- If `Send failed` cannot be applied, a permanent send error retries every minute.
- The 20,000/day read math, the 6-minute cap, and two Apps Script projects not sharing a lock are unchanged.

## Prompt to Resume

Continue from this note on branch `cursor/gmail-delayed-send-opt-out-dea1`, commit `c4540e9`. The 5-minute send is the default, `Hold` is the opt-out, and `Send in 5` is not a gate. Focus on Guardrails if it is not green, and otherwise leave the script undeployed until drafts that must stay have `Hold`. Avoid putting `Send in 5` back into eligibility, dropping the quota latch, `tryLock(0)`, or the `Send failed` skip, and avoid any mailbox address, token, script id, or OAuth client. Validate with `node apps_script/gmail_delayed_send/stand_in_test.mjs`: an unlabeled draft sends after 5 minutes, a `Hold` draft does not, removing `Hold` uses the last save, a `Send failed` draft is skipped, and a draft with no recipient is parked.
