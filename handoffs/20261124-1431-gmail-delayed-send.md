---
thread: gmail-delayed-send
status: active
created: 2026-11-24T14:31Z
supersedes: handoffs/archive/gmail-delayed-send/20261124-1423-gmail-delayed-send.md
private_detail: null
---

# Gmail delayed send consolidation

## Objective

Apply the nine approved consolidations in the delayed-send script and its stand-in. Change no behavior. Leave the rejected list untouched.

## Current State

- Applied on branch `cursor/gmail-delayed-send-2cb1`, pull request 26. Consolidation commit `9380621`. Behavior commit remains `8be2dc7`. The script is not deployed.
- `Code.gs` is 623 lines (was 640). `stand_in_test.mjs` is 1007 lines (was 1012).
- Findings 1, 2, 3, 5, 6, 7, 8, and 9 are in `Code.gs`. Finding 4 is in `stand_in_test.mjs`.
- `node apps_script/gmail_delayed_send/stand_in_test.mjs` passed: 32 tests, `all assertions passed`. Repo checks on this VM: `py_compile`, board-secretary unittest (65), decision-log unittest (25), fanfic pytest (145), the gitignore check, and `ruff check python` all passed.
- Preflight still exits 1 here because the local Docs client file and token directory are absent. That is not a script failure.

## Why This Matters

- The quota latch, sibling label rule, and `Send failed` order stay easy to break. This pass only shares strings and calls that already did the same thing.

## What was applied

1. `logDraftProblem_(template, draftId, error)` calls `Logger.log` with the template, the draft id, and `formatError_`. Six sites. Each template string is unchanged.
2. `QUOTA_REMAINING_LABELED_DRAFTS_LOG_MESSAGE` is the in-loop log. `QUOTA_LABELED_DRAFTS_LEFT_UNSENT_THROW_MESSAGE` is the thrown sentence. They stay different sentences. `finishRetryLaterQuota_` still logs `before any draft was sent`.
3. `assertTriggerIntervalMinutes_` uses `ALLOWED_TRIGGER_INTERVAL_MINUTES.indexOf`. The thrown sentence is still the literal `1, 5, 10, 15, or 30` text. Allowed values stay 1, 5, 10, 15, and 30.
4. The stand-in `getDraft` drops `Send in 5` once, then builds the reread spec or the original spec.
5. The sibling log is `Left %s on the thread. Another labeled draft still needs it. threadId=%s` with `SEND_LABEL_NAME` and the thread id. With the current constant the rendered line is `Left Send in 5 on the thread...`.
6. `DRAFT_DELETED_BEFORE_SEND_LOG_TEMPLATE` is `Draft deleted before send. id=%s`. The three sites keep their own counters and returns.
7. `logPersistentFailureLatchProblem_(action, error)` logs `Could not ` + action + ` the persistent-failure latch. error=%s` for `update` and `clear`. Latch timing, the property name, and the once-per-hour throw are unchanged.
8. `snapshotLabeledDraft_` takes the id already stored by the snapshot loop. It no longer calls `draft.getId()` again.
9. The snapshot object no longer stores `thread`. The local `thread` variable still supplies the id and the label check.

## Key Decisions Already Made

- Decision: The owner approved findings 1 through 9. The rejected list was not implemented.
- Why: The approval was explicit in this conversation. Silence was not the approval.
- Tradeoff: Look-alike catch blocks, the two age checks, and the two quota sentences stay separate.

- Decision: Behavior commit `8be2dc7` still defines the semantics. Age is `GmailMessage.getDate()`. Quota text keeps `Send in 5` and throws at most once an hour. A sibling draft keeps the thread label. `Send in 5` is removed before `Send failed`. The trigger stays `everyMinutes(1)`. `LockService.tryLock(0)` stays 0.
- Why: This commit is a consolidation, not a behavior change.
- Tradeoff: A few shared helpers are longer than a single call site.

## Open Questions

- None for this consolidation. Do not re-apply the rejected list without a new approval.

## Constraints and Guardrails

- Public repo. No mailbox address, token, script id, OAuth client, or personal name in git.
- Do not change quota retry handling, the persistent-failure latch, `Send failed` labeling order, sibling-draft handling, `LockService.tryLock(0)`, the five-minute clock reset on edit, or the allowed `everyMinutes` values.
- Scopes stay `gmail.modify` and `script.scriptapp`. No sent-history log or label.
- Do not post a pull-request comment. Do not merge. Do not deploy.

## Files / Artifacts / Sources

- `apps_script/gmail_delayed_send/Code.gs`
- `apps_script/gmail_delayed_send/stand_in_test.mjs`
- Pull request 26, branch `cursor/gmail-delayed-send-2cb1`, consolidation commit `9380621`, behavior commit `8be2dc7`

## Next Best Actions

1. Wait for Guardrails on `9380621` (and this handoff commit) to finish green. Do not merge.
2. Do not deploy. Do not set `TRIGGER_INTERVAL_MINUTES` to 5 unless a real Gmail quota failure is reported.
3. The live check is still the README smoke test, before the first real use. This environment has no mailbox.

## Known Risks or Failure Modes

- The rejected catch-block merger would change who gets `Send failed` and whether a quota increments `failedCount`. It was not applied.
- Finding 7's sentence is assembled. `update` and `clear` are the only actions, and the rendered lines match the old templates.
- The 20,000/day read math, the 6-minute cap, and two Apps Script projects not sharing a lock are unchanged.

## Prompt to Resume

Continue from this note on pull request 26, branch `cursor/gmail-delayed-send-2cb1`. Findings 1 through 9 are already in `9380621`; do not apply them again. Focus on Guardrails if it is not green, and otherwise leave the script undeployed. Avoid the rejected list, especially a shared draft-loop catch, a quota-read wrapper, `removeLabelOrLog_`, a generated `everyMinutes` sentence, one shared `Date.now()` for both age checks, and any change to the latch, sibling labels, `Send failed` order, `tryLock(0)`, or the allowed intervals. Validate with `node apps_script/gmail_delayed_send/stand_in_test.mjs`: quota text keeps `Send in 5`, a sibling draft keeps the label, and a deleted draft is not parked.
