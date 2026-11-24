---
thread: gmail-delayed-send
status: active
created: 2026-11-24T14:23Z
supersedes: handoffs/archive/gmail-delayed-send/20261124-1411-gmail-delayed-send.md
private_detail: null
---

# Gmail delayed send consolidation review

## Objective

Review-only pass on pull request 26. Find duplicated logic in the delayed-send script that can move into one helper, constant, or call without changing behavior. Do not edit functional files until the owner approves finding numbers.

## Current State

- No functional file changed in this pass. `Code.gs`, the folder README, the stand-in, the manifest, and `docs/decision-notes.md` are untouched.
- Branch `cursor/gmail-delayed-send-2cb1`. Behavior commit remains `8be2dc7`. This note supersedes `handoffs/archive/gmail-delayed-send/20261124-1411-gmail-delayed-send.md`. The script is not deployed.
- `node apps_script/gmail_delayed_send/stand_in_test.mjs` passed on that tree: 32 tests, `all assertions passed`.
- Preflight exits 1 in this environment because the local Docs client file and token directory are absent. That is not a script failure.

## Why This Matters

- The quota latch, sibling label rule, and `Send failed` order are easy to break while "cleaning up" copy-paste. Approved items below are the ones that stay behavior-identical. The rejected list is the set that looks duplicated and is not safe, or does not pay for itself.

## Findings to approve or deny

Implement only the numbers the owner names. Each item keeps current logs, errors, label order, and control flow. Line counts are approximate.

1. **One logger for draft-id plus `formatError_`.** `Code.gs` repeats `Logger.log(template, draftId, formatError_(error))` at 159-163, 208-212, 397-401, 413-417, 430-434, and 529-533. Add `logDraftProblem_(template, draftId, error)` that calls `Logger.log` with those three arguments. Keep each template string exact. About 20 lines saved. Risk: none. Behavior unchanged.

2. **Two quota strings, kept distinct.** The in-loop log `Gmail quota reached. Remaining labeled drafts stay labeled for a later run.` is copied at 166-168 and 216-218. The thrown text `Gmail quota reached. Labeled drafts left unsent stay labeled and are tried on a later run.` is copied at 242 and 252 (`finishRetryLaterQuota_` uses that same throw text). One constant per sentence. Do not merge the two sentences. `finishRetryLaterQuota_` keeps its own log line (`before any draft was sent`). About 6 lines saved. Risk: none. Behavior unchanged.

3. **Membership test for the legal trigger intervals.** `assertTriggerIntervalMinutes_` (497-510) walks `ALLOWED_TRIGGER_INTERVAL_MINUTES` with `===`. `Array.indexOf` is already used in this file and matches `===`. Keep the thrown sentence literal: `TRIGGER_INTERVAL_MINUTES must be 1, 5, 10, 15, or 30. ClockTriggerBuilder.everyMinutes rejects any other value.` Do not build that sentence from the array. About 6 lines saved. Risk: none. Behavior unchanged. Allowed values stay 1, 5, 10, 15, and 30.

4. **Stand-in label drop is copied.** `stand_in_test.mjs` `getDraft` filters `Send in 5` off the thread in both the reread branch (313-320) and the following branch (322-326). Drop the label once, before choosing the spec, then return `makeDraft` of the reread spec or the original spec. Same order: mutate the thread, then build the draft. About 5 lines saved. Risk: none. Behavior unchanged. This is the test double, not `Code.gs`.

5. **Sibling log hardcodes the label name.** `Code.gs` 349 logs `Left Send in 5 on the thread...` while `SEND_LABEL_NAME` is the source of that name. Log `Left %s on the thread. Another labeled draft still needs it. threadId=%s` with `SEND_LABEL_NAME` and `threadId`. About 0 lines saved. Risk: none. With the current constant the log text is identical.

6. **Deleted-draft log template.** `Draft deleted before send. id=%s` is logged at 155, 202, and 297. One template constant, still passed to `Logger.log` with the draft id. About 1 line added. Risk: none. Behavior unchanged. The three sites keep their own counters and returns: the snapshot loop does not increment `labeledCount`; the send loop does; the pre-send `getDraft` catch returns `{ outcome: "canceled" }` and rethrows anything else.

7. **Latch failure logs share a sentence frame.** 605-608 says `Could not update the persistent-failure latch. error=%s`. 625-628 says `Could not clear the persistent-failure latch. error=%s`. One helper that logs `Could not ` + action + ` the persistent-failure latch. error=%s` with action `update` or `clear`, then `formatError_`. About 2 lines saved. Risk: low. The assembled sentence must match those two templates exactly. Latch timing, the property name, and the once-per-hour throw stay put.

8. **Second `draft.getId()`.** The snapshot loop stores `draft.getId()` at 146, then `snapshotLabeledDraft_` calls `draft.getId()` again at 257. Pass the stored id in. If the outer `getId()` throws, the snapshot is still not called and the log id stays `unavailable`. About 1 line saved, and one fewer getter call. Risk: none. Outcomes unchanged.

9. **Unread snapshot field.** `snapshotLabeledDraft_` stores `thread` (273). Settle and send read `threadId`, not `thread`. The local `thread` variable stays so the id and the label check still run. Delete only the stored property. About 1 line saved. Risk: none. Behavior unchanged.

## Considered and rejected

- Merging the two draft-loop `catch` blocks into one classifier. The logs match. The side effects do not. The snapshot loop does not increment `labeledCount` on a missing draft, and it calls `markDraftSendFailed_` immediately for a non-quota error. The send loop increments `labeledCount`, sets `outcome` to `canceled`, `failed`, or `quota`, and does not park there. Quota still increments `failedCount` so the pass log's failed count stays the same. A shared classifier saves about 1 line and makes those differences easy to flatten. Sibling parking and immediate parking of a snapshot failure would drift.
- A `readOrStopOnRetryLaterQuota_` wrapper around the label lookup (102-110) and `getDrafts` (119-127). Both already call `isRetryLaterQuotaError_` and `finishRetryLaterQuota_`. A wrapper needs a sentinel because a missing label is a real `null`, not a quota stop. Net about 8 lines longer.
- `removeLabelOrLog_` shared by `markDraftSendFailed_` and `removeSendLabelFromSentThread_`. On the sent path, `sentMessage.getThread()` is inside the same `try` as `removeLabel`. Pulling `getThread()` out would let that throw escape instead of logging `Sent draft, but removing the label failed`. Net about 0 lines once finding 1 exists. Label order stays remove-`Send in 5`, then add `Send failed`, in separate tries.
- Building the `everyMinutes` error from `ALLOWED_TRIGGER_INTERVAL_MINUTES`. A join drops the `, or ` wording unless a formatter is added, and the formatter spends the lines finding 3 saves. The legal set stays 1, 5, 10, 15, 30. Do not install 2.
- One age helper for the listed check and the recheck (`sendLabeledDraftIfOldEnough_`, 283-286 and 307-310). The helper is larger than the two copies. Each check must call `Date.now()` at its own moment. An edit still resets the five-minute clock. Do not freeze one timestamp for both checks.
- `threadHasOutcome_` plus `firstRecordWithOutcome_` (366-382). Same scan, but folding them saves lines only by deleting the `Missing delayed-send outcome` throw, or saves nothing if that throw stays. First match and the throw stay.
- One `errorSearchText_` for `isRetryLaterQuotaError_` and `isMissingDraftError_`. Quota search is `error.message` plus `formatError_` (stack when present). Missing-draft search is the message, or `String(error)` when there is no message. Unifying the text changes which failures match.
- Turning the quota markers into a new array. They are already one list. The comment that `too many times: email` is not a substring of the `for one day` or `in a short time` forms has to stay. Do not drop a marker.
- Merging `throwPersistentFailureAtMostOncePerHour_` and `clearPersistentFailureLatch_`, or using one exit to clear the latch. Empty drafts, a pass with nothing labeled, and a finished non-quota pass clear it. A quota or missing-label pass must not. `LockService.tryLock(0)` stays 0.
- `assertNonEmptyStringSetting_` for the two label names, and `isPositiveFiniteNumber_` for `DELAY_MINUTES` and the delay argument. About 0 to 2 lines, and the distinct error sentences are the point of the checks.
- Calling `delayMilliseconds_()` only once. `assertDelayedSendConfigured_` validates before the lock. The locked pass computes the delay again. A const cannot change between the calls. Passing the number in saves about 0 lines and couples the locked function to its caller.
- Collapsing README sections that restate quotas, sibling labels, or `label.getThreads()`. Each section is where a reader looks that rule up. Pointing elsewhere drops that local coverage. The folder README and the file header both explain `getDate()` on purpose.
- Rewriting `docs/decision-notes.md` or the root README index lines. The decision notes are a chronological log. The root README is an index line plus a link.
- Drying stand-in assertions, or a test-wide label constant. The assertions are the coverage for quota text, sibling drafts, and a deleted draft. Wide replacement saves about 0 lines.
- `label.getThreads()` or `GmailApp.search` as the draft list. Draft-only threads are missing from both. `getDrafts()` stays the list.

## Key Decisions Already Made

- Decision: This pass records findings and does not edit the script.
- Why: The owner approves or denies each number before any consolidation.
- Tradeoff: The duplication stays until a later commit implements the approved numbers.

- Decision: Behavior commit `8be2dc7` stands. Age is `GmailMessage.getDate()`. Quota text keeps `Send in 5` and throws at most once an hour. A sibling draft keeps the thread label. `Send in 5` is removed before `Send failed`. The trigger stays `everyMinutes(1)`.
- Why: Those are the semantics this review is not allowed to change.
- Tradeoff: Several look-alike blocks stay duplicated. See the rejected list.

## Open Questions

- Which finding numbers are approved? No number is approved yet. Do not implement on silence.

## Constraints and Guardrails

- Public repo. No mailbox address, token, script id, OAuth client, or personal name in git.
- Do not change quota retry handling, the persistent-failure latch, `Send failed` labeling order, sibling-draft handling, `LockService.tryLock(0)`, the five-minute clock reset on edit, or the allowed `everyMinutes` values.
- Scopes stay `gmail.modify` and `script.scriptapp`. No sent-history log or label.
- Do not post a pull-request comment. Do not merge.

## Files / Artifacts / Sources

- `apps_script/gmail_delayed_send/Code.gs`
- `apps_script/gmail_delayed_send/stand_in_test.mjs`
- `apps_script/gmail_delayed_send/README.md`
- Pull request 26, branch `cursor/gmail-delayed-send-2cb1`, behavior commit `8be2dc7`

## Next Best Actions

1. Wait for the owner to approve or deny finding numbers. Implement only the approved numbers, in `Code.gs` and, for finding 4 only, `stand_in_test.mjs`.
2. After that, run `node apps_script/gmail_delayed_send/stand_in_test.mjs`. Quota text must keep `Send in 5`, a sibling draft must keep the label, and a deleted draft must not be parked.
3. Do not deploy. Do not set `TRIGGER_INTERVAL_MINUTES` to 5 unless a real gmail quota failure is reported.

## Known Risks or Failure Modes

- Approving the rejected catch-block merger, or "simplifying" findings 1 and 2 into that merger, changes who gets `Send failed` and whether a quota increments `failedCount`.
- Finding 7 is the only low-risk item. A paraphrased latch sentence changes the execution log.
- The 20,000/day read math, the 6-minute cap, and two Apps Script projects not sharing a lock are unchanged from the previous head.

## Prompt to Resume

Continue from this note on pull request 26, branch `cursor/gmail-delayed-send-2cb1`. Functional files are unchanged since `8be2dc7`. Focus only on finding numbers the owner has approved in this conversation; silence approves nothing. Avoid the rejected list, especially a shared draft-loop catch, a quota-read wrapper, `removeLabelOrLog_`, a generated `everyMinutes` sentence, one shared `Date.now()` for both age checks, and any change to the latch, sibling labels, `Send failed` order, `tryLock(0)`, or the allowed intervals. Validate with `node apps_script/gmail_delayed_send/stand_in_test.mjs`: quota text keeps `Send in 5`, a sibling draft keeps the label, and a deleted draft is not parked.
