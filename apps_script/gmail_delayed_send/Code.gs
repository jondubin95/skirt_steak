/**
 * Consumer Gmail delayed send.
 *
 * Gmail Undo Send holds a message for at most 30 seconds. This script
 * sends every draft once its current message is DELAY_MINUTES old.
 * No label is required. Gmail's own Send button still sends immediately,
 * because that draft is gone before this script sees it.
 *
 * GmailDraft has no last-updated getter. A save does not edit the
 * message in place: Gmail replaces it. The draft id stays; the message
 * id and message date change. draft.getMessage().getDate() is the
 * timestamp of that replacement message, so an edit resets the wait.
 * This script does not read the RFC 2822 Date header.
 *
 * HOLD_LABEL_NAME on the thread opts that thread out. The draft is not
 * sent. Install stores that label's id. A thread matches Hold when the
 * label id is the stored one or the name is exactly HOLD_LABEL_NAME, so a
 * rename, a nest, or a recase of the same label still holds. An older
 * install with no stored id looks the label up by name once and stores it.
 *
 * Once a pass has saved Hold, the script stores draft id to message id.
 * The draft id stays across an edit. The message id does not. Gmail API
 * drafts.update replaces the message and cannot set user labels, so a
 * standalone draft loses Hold. An older message on the thread can still
 * carry the label. If Hold is gone and the message id changed, the edit
 * dropped it: put Hold back and skip. If Hold is gone and the message id
 * is the same, that is not a release on one look. A fresh getDraft plus
 * a fresh label read must agree, and the next pass must agree again,
 * before the held entry is forgotten and the release clock starts.
 * Release now, matched by its stored label id only, wins over Hold.
 * The draft sends only when the message is DELAY_MINUTES old and the
 * release clock is unset or also DELAY_MINUTES old. If putting Hold back
 * throws, keep the held entry and try again next pass. Do not mark that
 * Send failed. When the sticky state cannot be read or saved, hold
 * rather than send, and throw at most once an hour.
 *
 * SEND_FAILED_LABEL_NAME on the thread means a previous non-quota
 * send() failure, or a draft this script refused to send again after
 * a kill inside send(). The same id-or-exact-name match applies.
 * Those drafts are skipped so a one-minute trigger does not send them
 * again. The skip is logged once per draft, not on every run.
 * Removing the label makes them eligible again. A read error before
 * send(), and a daily computer-time limit, do not apply this label.
 *
 * LEGACY_SEND_LABEL_NAME ("Send in 5") is not an eligibility gate.
 * Older versions of this script required it. It is removed after a
 * send, or after Send failed is applied, only when no draft on that
 * thread is still waiting or held back by a quota error. Leaving it
 * in place does not change who sends.
 *
 * Labels cannot be set on a draft through drafts.create or drafts.update.
 * An older message can still carry Hold, Release now, or Send failed.
 * GmailApp reports thread labels, the union of the message labels.
 * Every draft on that thread shares that union. If any remembered draft
 * on a thread changed message id while Hold is gone, the other drafts
 * on that thread stay held too. A removed label and an edit that
 * stripped it look the same until a second pass agrees.
 *
 * A recipient-quota error and a Gmail read/write quota error leave the
 * draft eligible and stop the rest of the pass. Those throw at most
 * once per hour so a one-minute trigger does not fail on every run.
 * Any other send() failure is recorded by draft id and message id and
 * is not sent again. SEND_FAILED_LABEL_NAME is applied when no other
 * draft on that thread is still waiting or held back by quota.
 * If that message id changes, the record is cleared and the normal
 * clock applies. Once Send failed is on the thread, that record is
 * cleared, so removing the label makes the draft eligible again.
 * A kill inside send() leaves an in-flight record. The next run does
 * not send that same message again. It applies Send failed immediately,
 * even when another draft on the thread is still waiting.
 * A draft with no To, Cc, or Bcc is logged and parked without calling
 * send(), and it does not stop the pass. Empty To with a Cc or Bcc is
 * sendable. Reply drafts are ordinary drafts; GmailDraft.send()
 * keeps the thread.
 */

const DELAY_MINUTES = 5;
const HOLD_LABEL_NAME = "Hold";
const RELEASE_LABEL_NAME = "Release now";
const SEND_FAILED_LABEL_NAME = "Send failed";
const LEGACY_SEND_LABEL_NAME = "Send in 5";
// ClockTriggerBuilder.everyMinutes allows only these values. 2 is rejected.
const ALLOWED_TRIGGER_INTERVAL_MINUTES = [1, 5, 10, 15, 30];
// 1 keeps an already-old draft about a minute from the next look.
// 5 would cut the daily Gmail read count by about five and add up to
// about four minutes of wait. See the README quotas section.
const TRIGGER_INTERVAL_MINUTES = 1;
// Do not wait. A queued run would sit on the consumer trigger-time quota.
const LOCK_WAIT_MILLISECONDS = 0;
// Timestamp of the last thrown persistent failure. Not a draft id.
const PERSISTENT_FAILURE_LATCH_PROPERTY = "delayedSendPersistentFailureLatchedAt";
const PERSISTENT_FAILURE_THROW_INTERVAL_MILLISECONDS = 60 * 60 * 1000;
const HOLD_LABEL_ID_PROPERTY = "delayedSendHoldLabelId";
// Versioned so an id stored by the never-deployed 414016c build is ignored.
const RELEASE_LABEL_ID_PROPERTY = "delayedSendReleaseNowLabelId";
const LEGACY_RELEASE_LABEL_ID_PROPERTY = "delayedSendReleaseLabelId";
const SEND_FAILED_LABEL_ID_PROPERTY = "delayedSendSendFailedLabelId";
// Map of draft id to the message id last seen while the thread had Hold.
const HELD_DRAFTS_PROPERTY = "delayedSendHeldDrafts";
// Map of draft id to the epoch ms when Hold came off or Release now was seen.
const RELEASED_AT_PROPERTY = "delayedSendReleasedAt";
// Map of draft id to the message id confirmed once as a manual Hold removal.
const RELEASE_SEEN_ONCE_PROPERTY = "delayedSendReleaseSeenOnce";
// Consecutive getDraft not-found results. A generic read error does not count.
const STICKY_ABSENT_PASSES_PROPERTY = "delayedSendStickyAbsentPasses";
// How many passes getDraft found a draft that getDrafts did not list.
// A value at or above UNLISTED_COOLDOWN_SENTINEL (1e12) is the next epoch ms
// when that lookup may run again. Counts stay below that.
const STICKY_UNLISTED_FOUND_PROPERTY = "delayedSendStickyUnlistedFound";
// Consecutive passes a listed draft could not be read.
const STICKY_UNREAD_PASSES_PROPERTY = "delayedSendStickyUnreadPasses";
// Active shard generation. Extra shards are named with this generation.
const STICKY_SHARD_GENERATION_PROPERTY = "delayedSendStickyShardGeneration";
// "1" while sticky state did not fit. Every draft stays held.
const STICKY_OVERFLOW_PROPERTY = "delayedSendStickyOverflow";
// Miss timestamps for Hold and Send failed name lookups. Not Release now.
const LABEL_LOOKUP_COOLDOWN_PROPERTY = "delayedSendLabelLookupCooldown";
// Script properties allow 9KB per value. Shards stay under that.
const STICKY_PROPERTY_CHAR_CAP = 7000;
// Whole script-property store is 500KB. Leave room for the other keys.
const STICKY_TOTAL_CHAR_CAP = 200000;
const STICKY_MAX_SHARDS = 40;
const LABEL_LOOKUP_COOLDOWN_MILLISECONDS = 60 * 60 * 1000;
const RELEASED_AT_PRUNE_MARGIN_MILLISECONDS = 60 * 1000;
const MISSING_DRAFT_CONFIRMS_BEFORE_PRUNE = 2;
const UNREADABLE_PASSES_BEFORE_EXCLUDE = 3;
const UNLISTED_FOUND_PASSES_BEFORE_COOLDOWN = 60;
const UNLISTED_RECHECK_MILLISECONDS = 60 * 60 * 1000;
const UNLISTED_COOLDOWN_SENTINEL = 1000000000000;
const DELAYED_SEND_ARMED_PROPERTY = "delayedSendArmedVersion";
const DELAYED_SEND_ARMED_VERSION = "2";
// Stored when Hold must be restored and this pass has no prior message id.
// It matches no Gmail message id, so the next pass tries the restore again.
const STICKY_HOLD_PENDING_MESSAGE_ID = "pending-hold-restore";
const STICKY_UNREADABLE_MESSAGE =
  "Could not read sticky Hold state. Holding every draft until fixed.";
const STICKY_STORE_FAILED_MESSAGE =
  "Could not store sticky Hold state. Holding every draft until fixed.";
const STICKY_OVERFLOW_MESSAGE =
  "Sticky Hold state does not fit in script properties. Holding every draft until fixed.";
const RELEASE_STUCK_MESSAGE =
  "Could not remove Release now. Holding that thread until the label can be removed.";
const RESTORE_FAILED_MESSAGE =
  "Could not re-apply Hold. Holding the draft and trying again.";
const UNREADABLE_DRAFT_MESSAGE =
  "A draft stayed unreadable for several passes. Other threads are no longer blocked on it.";
const UNLISTED_DRAFT_MESSAGE =
  "A remembered draft is missing from the draft list but getDraft still finds it. Later lookups wait an hour.";
// Map of draft id to the message id that already failed send().
const FAILED_SEND_BY_DRAFT_ID_PROPERTY = "delayedSendFailedSendByDraftId";
// One {draftId, messageId, startedAt} written immediately before send().
const IN_FLIGHT_SEND_PROPERTY = "delayedSendInFlightSend";
// Draft ids already logged for a Send failed skip.
const SEND_FAILED_SKIP_LOGGED_PROPERTY = "delayedSendSendFailedSkipLoggedDraftIds";
const QUOTA_REMAINING_DRAFTS_LOG_MESSAGE =
  "Gmail quota reached. Remaining drafts stay for a later run.";
const QUOTA_DRAFTS_LEFT_UNSENT_THROW_MESSAGE =
  "Gmail quota reached. Drafts left unsent stay eligible and are tried on a later run.";
const DRAFT_DELETED_BEFORE_SEND_LOG_TEMPLATE = "Draft deleted before send. id=%s";
const LEGACY_DELAYED_SEND_HANDLER_NAME = "sendLabeledDraftsAfterDelay";

/**
 * Creates the Hold, Release now, and Send failed labels when missing and
 * installs one time trigger. Running this again deletes duplicate
 * triggers for the current handler and for the older opt-in handler first.
 * A stored label id is reused even when that label was renamed or nested.
 * Release now is not adopted from a pre-existing label of the same name.
 * "Send in 5" is not created.
 */
function installDelayedGmailSend() {
  assertDelayedSendConfigured_();
  const properties = PropertiesService.getScriptProperties();
  const holdLabel = labelForInstall_(
    properties.getProperty(HOLD_LABEL_ID_PROPERTY),
    HOLD_LABEL_NAME,
    false
  );
  const releaseLabel = releaseLabelForInstall_(properties);
  const failedLabel = labelForInstall_(
    properties.getProperty(SEND_FAILED_LABEL_ID_PROPERTY),
    SEND_FAILED_LABEL_NAME,
    false
  );
  storeLabelId_(HOLD_LABEL_ID_PROPERTY, holdLabel);
  storeLabelId_(RELEASE_LABEL_ID_PROPERTY, releaseLabel);
  storeLabelId_(SEND_FAILED_LABEL_ID_PROPERTY, failedLabel);
  const removedTriggerCount = deleteDelayedSendTriggers_();
  ScriptApp.newTrigger(sendDraftsAfterDelay.name)
    .timeBased()
    .everyMinutes(TRIGGER_INTERVAL_MINUTES)
    .create();
  properties.setProperty(DELAYED_SEND_ARMED_PROPERTY, DELAYED_SEND_ARMED_VERSION);
  Logger.log(
    "Installed delayed send. holdLabel=%s releaseLabel=%s failedLabel=%s removedTriggers=%s intervalMinutes=%s handler=%s",
    holdLabel.getName(),
    releaseLabel.getName(),
    failedLabel.getName(),
    removedTriggerCount,
    TRIGGER_INTERVAL_MINUTES,
    sendDraftsAfterDelay.name
  );
}

/**
 * Removes every trigger in this project whose handler is the delayed send,
 * including the older opt-in handler name. Does not delete Gmail labels.
 */
function uninstallDelayedGmailSend() {
  const removedTriggerCount = deleteDelayedSendTriggers_();
  Logger.log("Removed delayed-send triggers. count=%s", removedTriggerCount);
}

/**
 * Time-driven entry point. One run at a time. Lists drafts and sends each
 * one that is old enough, not on Hold, and not already marked Send failed.
 * One draft's error is logged and does not stop the rest, except a Gmail
 * quota error, which leaves the remaining drafts for a later run.
 * Returns immediately when there are no drafts, or when another run holds
 * the script lock.
 */
function delayedSendIsArmed_() {
  try {
    const stored = PropertiesService.getScriptProperties().getProperty(DELAYED_SEND_ARMED_PROPERTY);
    return stored === DELAYED_SEND_ARMED_VERSION;
  } catch (error) {
    Logger.log(
      "Could not read the delayed-send armed marker. Nothing was sent. error=%s",
      formatError_(error)
    );
    return false;
  }
}

function sendDraftsAfterDelay() {
  assertDelayedSendConfigured_();
  if (!delayedSendIsArmed_()) {
    Logger.log("Delayed send is not armed. Run installDelayedGmailSend. Nothing was sent.");
    return;
  }
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(LOCK_WAIT_MILLISECONDS)) {
    Logger.log("Delayed send skipped. Another run holds the script lock.");
    return;
  }
  try {
    sendDraftsWithLockHeld_();
  } finally {
    lock.releaseLock();
  }
}

/**
 * Older installs call this name. Same pass as sendDraftsAfterDelay.
 * installDelayedGmailSend replaces a trigger on this name.
 */
function sendLabeledDraftsAfterDelay() {
  sendDraftsAfterDelay();
}

function sendDraftsWithLockHeld_() {
  const passStartedAtMilliseconds = Date.now();
  const delayMilliseconds = delayMilliseconds_();
  const passFlags = newPassFlags_();
  let sticky = unreadableStickyHoldState_();
  let failureMessage = null;
  let clearLatch = false;
  let drafts = [];
  try {
    let snapshot = null;
    try {
      snapshot = PropertiesService.getScriptProperties().getProperties();
    } catch (error) {
      Logger.log(
        "Could not read sticky Hold state. Holding every draft this pass. error=%s",
        formatError_(error)
      );
      failureMessage = STICKY_UNREADABLE_MESSAGE;
      return;
    }
    sticky = readStickyHoldState_(snapshot, passStartedAtMilliseconds);
    if (!sticky.readable) {
      Logger.log("Could not read sticky Hold state. Holding every draft this pass.");
      failureMessage = STICKY_UNREADABLE_MESSAGE;
      return;
    }
    try {
      drafts = GmailApp.getDrafts();
    } catch (error) {
      if (isRetryLaterQuotaError_(error)) {
        Logger.log(
          "Gmail quota reached before any draft was sent. error=%s",
          formatError_(error)
        );
        failureMessage = QUOTA_DRAFTS_LEFT_UNSENT_THROW_MESSAGE;
        return;
      }
      throw error;
    }
    if (drafts.length === 0) {
      pruneStickyDrafts_(sticky, {}, true, passFlags, passStartedAtMilliseconds);
      clearLatch = !passFlags.quota;
      if (passFlags.quota) {
        failureMessage = QUOTA_DRAFTS_LEFT_UNSENT_THROW_MESSAGE;
      }
      return;
    }
    let labelIds;
    try {
      labelIds = rememberedLabelIds_(passStartedAtMilliseconds, snapshot);
    } catch (error) {
      if (isRetryLaterQuotaError_(error)) {
        Logger.log(
          "Gmail quota reached before any draft was sent. error=%s",
          formatError_(error)
        );
        failureMessage = QUOTA_DRAFTS_LEFT_UNSENT_THROW_MESSAGE;
        return;
      }
      throw error;
    }
    const eligibleDrafts = [];
    const draftViews = [];
    const threadLabelStateByThreadId = {};
    const skippedSendFailedDraftIds = [];
    const liveIds = {};
    let sawUnavailableDraftId = false;
    let eligibleCount = 0;
    let sentCount = 0;
    let waitingCount = 0;
    let failedCount = 0;
    let canceledCount = 0;
    for (let draftIndex = 0; draftIndex < drafts.length; draftIndex++) {
      const draft = drafts[draftIndex];
      let draftId = "unavailable";
      try {
        draftId = draft.getId();
        liveIds[draftId] = true;
        draftViews.push(
          readDraftView_(draft, draftId, threadLabelStateByThreadId, labelIds)
        );
        delete sticky.unreadPasses[draftId];
      } catch (error) {
        // A not-found error during an edit must not forget Hold. Pruning
        // confirms a draft that is actually gone.
        logDraftProblem_("Delayed send will retry this draft. id=%s error=%s", draftId, error);
        if (draftId === "unavailable") {
          sawUnavailableDraftId = true;
        }
        if (isRetryLaterQuotaError_(error)) {
          failedCount++;
          passFlags.quota = true;
          Logger.log(QUOTA_REMAINING_DRAFTS_LOG_MESSAGE);
          break;
        }
        const threadId = threadIdForUnreadDraft_(draftId, passFlags);
        if (passFlags.quota) {
          failedCount++;
          Logger.log(QUOTA_REMAINING_DRAFTS_LOG_MESSAGE);
          break;
        }
        noteUnreadDraft_(sticky, draftId, threadId, passFlags);
      }
    }
    if (!sawUnavailableDraftId) {
      delete sticky.unreadPasses["unavailable-draft"];
    }
    const startedWithOverflowLatch = sticky.overflowLatch;
    applyStickyHoldForPass_(
      draftViews,
      sticky,
      labelIds,
      passStartedAtMilliseconds,
      passFlags
    );
    if (!passFlags.quota) {
      pruneStickyDrafts_(sticky, liveIds, true, passFlags, passStartedAtMilliseconds);
    }
    if (passFlags.alertUnreadable) {
      failureMessage = failureMessage || UNREADABLE_DRAFT_MESSAGE;
    }
    if (passFlags.alertUnlisted) {
      failureMessage = failureMessage || UNLISTED_DRAFT_MESSAGE;
    }
    const checkpoint = persistStickyHoldState_(
      sticky,
      passStartedAtMilliseconds,
      delayMilliseconds
    );
    const blockSends =
      !checkpoint.ok || startedWithOverflowLatch || passFlags.quota;
    if (blockSends) {
      forceHoldAllDraftViews_(draftViews);
      passFlags.skipLabelWrites = true;
    }
    if (!checkpoint.ok) {
      failureMessage = checkpoint.overflow
        ? STICKY_OVERFLOW_MESSAGE
        : STICKY_STORE_FAILED_MESSAGE;
    } else if (passFlags.quota) {
      failureMessage = QUOTA_DRAFTS_LEFT_UNSENT_THROW_MESSAGE;
    } else if (startedWithOverflowLatch && sticky.overflowLatch) {
      failureMessage = STICKY_OVERFLOW_MESSAGE;
    }
    if (!passFlags.skipLabelWrites) {
      applyStickyLabelMutations_(draftViews, sticky, labelIds, passFlags);
      if (passFlags.quota) {
        failureMessage = QUOTA_DRAFTS_LEFT_UNSENT_THROW_MESSAGE;
        passFlags.skipLabelWrites = true;
      } else {
        if (passFlags.releaseStuck) {
          failureMessage = failureMessage || RELEASE_STUCK_MESSAGE;
        }
        if (passFlags.restoreFailed) {
          failureMessage = failureMessage || RESTORE_FAILED_MESSAGE;
        }
      }
    }
    if (!passFlags.quota && checkpoint.ok && !startedWithOverflowLatch) {
      for (let viewIndex = 0; viewIndex < draftViews.length; viewIndex++) {
        const view = draftViews[viewIndex];
        if (view.labelState.sendFailed) {
          skippedSendFailedDraftIds.push(view.draftId);
          continue;
        }
        if (
          passFlags.blockAllReleases ||
          passFlags.incompleteThreadIds[view.threadId] ||
          view.decision === "hold" ||
          view.decision === "release-pending"
        ) {
          Logger.log("Holding draft. id=%s", view.draftId);
          continue;
        }
        eligibleDrafts.push({
          draft: view.draft,
          draftId: view.draftId,
          message: view.message,
          threadId: view.threadId,
          outcome: "pending",
          sentMessage: null,
        });
      }
      for (let eligibleIndex = 0; eligibleIndex < eligibleDrafts.length; eligibleIndex++) {
        if (passFlags.quota || passFlags.persistFailed) {
          break;
        }
        const snapshot = eligibleDrafts[eligibleIndex];
        try {
          const result = sendDraftIfOldEnough_(
            snapshot,
            delayMilliseconds,
            passStartedAtMilliseconds,
            labelIds,
            sticky,
            passFlags,
            draftViews
          );
          snapshot.outcome = result.outcome;
          snapshot.sentMessage = result.sentMessage || null;
          if (result.outcome === "sent") {
            clearStickyDraft_(sticky, snapshot.draftId);
          }
          if (passFlags.persistFailed) {
            failureMessage = failureMessage || STICKY_STORE_FAILED_MESSAGE;
          }
          if (passFlags.releaseStuck) {
            failureMessage = failureMessage || RELEASE_STUCK_MESSAGE;
          }
          if (passFlags.quota) {
            failureMessage = QUOTA_DRAFTS_LEFT_UNSENT_THROW_MESSAGE;
            break;
          }
          if (
            result.outcome === "held" ||
            result.outcome === "skipped" ||
            result.outcome === "retry"
          ) {
            continue;
          }
          eligibleCount++;
          if (result.outcome === "sent") {
            sentCount++;
          } else if (result.outcome === "waiting") {
            waitingCount++;
          } else if (result.outcome === "canceled") {
            canceledCount++;
          } else if (result.outcome === "failed") {
            failedCount++;
          } else {
            throw new Error("Unexpected delayed-send outcome: " + result.outcome);
          }
        } catch (error) {
          if (isMissingDraftError_(error)) {
            snapshot.outcome = "canceled";
            eligibleCount++;
            canceledCount++;
            Logger.log(DRAFT_DELETED_BEFORE_SEND_LOG_TEMPLATE, snapshot.draftId);
            continue;
          }
          snapshot.outcome = "failed";
          eligibleCount++;
          failedCount++;
          if (isRetryLaterQuotaError_(error)) {
            snapshot.outcome = "quota";
            passFlags.quota = true;
            failureMessage = QUOTA_DRAFTS_LEFT_UNSENT_THROW_MESSAGE;
            logDraftProblem_(
              "Delayed send failed for one draft. id=%s error=%s",
              snapshot.draftId,
              error
            );
            Logger.log(QUOTA_REMAINING_DRAFTS_LOG_MESSAGE);
            break;
          }
          Logger.log(
            "Delayed send failed for one draft. id=%s subject=%s error=%s",
            snapshot.draftId,
            subjectForLog_(snapshot),
            formatError_(error)
          );
        }
      }
      try {
        settleThreadLabels_(eligibleDrafts, labelIds, passFlags);
      } catch (error) {
        if (isRetryLaterQuotaError_(error)) {
          passFlags.quota = true;
          failureMessage = QUOTA_DRAFTS_LEFT_UNSENT_THROW_MESSAGE;
          Logger.log(QUOTA_REMAINING_DRAFTS_LOG_MESSAGE);
        } else {
          throw error;
        }
      }
      logSendFailedSkipsOnce_(skippedSendFailedDraftIds);
      if (
        !failureMessage &&
        (eligibleCount > 0 || failedCount > 0 || canceledCount > 0)
      ) {
        Logger.log(
          "Delayed send pass finished. drafts=%s eligible=%s sent=%s waiting=%s failed=%s canceled=%s elapsedMs=%s",
          drafts.length,
          eligibleCount,
          sentCount,
          waitingCount,
          failedCount,
          canceledCount,
          Date.now() - passStartedAtMilliseconds
        );
      }
    }
    if (!failureMessage) {
      clearLatch = true;
    }
  } finally {
    if (sticky.readable) {
      const persisted = persistStickyHoldState_(
        sticky,
        passStartedAtMilliseconds,
        delayMilliseconds
      );
      if (!persisted.ok) {
        failureMessage = persisted.overflow
          ? STICKY_OVERFLOW_MESSAGE
          : failureMessage || STICKY_STORE_FAILED_MESSAGE;
        if (!failureMessage) {
          failureMessage = STICKY_STORE_FAILED_MESSAGE;
        }
        clearLatch = false;
      }
    }
    if (failureMessage) {
      throwPersistentFailureAtMostOncePerHour_(failureMessage);
    } else if (clearLatch) {
      clearPersistentFailureLatch_();
    }
  }
}

function newPassFlags_() {
  return {
    scanComplete: true,
    incompleteThreadIds: {},
    blockAllReleases: false,
    alertUnreadable: false,
    alertUnlisted: false,
    quota: false,
    skipLabelWrites: false,
    persistFailed: false,
    restoreFailed: false,
    releaseStuck: false,
    userLabels: null,
    userLabelsLoaded: false,
  };
}

function threadIdForUnreadDraft_(draftId, passFlags) {
  if (!draftId || draftId === "unavailable") {
    return null;
  }
  try {
    const freshDraft = GmailApp.getDraft(draftId);
    return freshDraft.getMessage().getThread().getId();
  } catch (error) {
    if (isRetryLaterQuotaError_(error)) {
      passFlags.quota = true;
    }
    return null;
  }
}

function freshReadFailureKey_(draftId) {
  return "fresh:" + draftId;
}

function noteFreshReadFailure_(sticky, draftId, passFlags) {
  const key = freshReadFailureKey_(draftId);
  sticky.unreadPasses[key] = (sticky.unreadPasses[key] || 0) + 1;
  if (sticky.unreadPasses[key] > UNREADABLE_PASSES_BEFORE_EXCLUDE) {
    passFlags.alertUnreadable = true;
  }
}

function noteUnreadDraft_(sticky, draftId, threadId, passFlags) {
  const countedId = !draftId || draftId === "unavailable" ? "unavailable-draft" : draftId;
  sticky.unreadPasses[countedId] = (sticky.unreadPasses[countedId] || 0) + 1;
  const unreadPasses = sticky.unreadPasses[countedId];
  const pastExclude = unreadPasses > UNREADABLE_PASSES_BEFORE_EXCLUDE;
  if (threadId) {
    passFlags.incompleteThreadIds[threadId] = true;
    if (pastExclude) {
      passFlags.alertUnreadable = true;
    }
    return;
  }
  if (pastExclude) {
    passFlags.alertUnreadable = true;
    return;
  }
  passFlags.blockAllReleases = true;
}

function forceHoldAllDraftViews_(views) {
  for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
    views[viewIndex].decision = "hold";
    views[viewIndex].labelAction = null;
  }
}

function readDraftView_(draft, draftId, threadLabelStateByThreadId, labelIds) {
  const message = draft.getMessage();
  const thread = message.getThread();
  const threadId = thread.getId();
  let labelState = threadLabelStateByThreadId[threadId];
  if (labelState === undefined) {
    labelState = readThreadLabelState_(thread, labelIds);
    threadLabelStateByThreadId[threadId] = labelState;
  }
  return {
    draft: draft,
    draftId: draftId,
    message: message,
    messageId: message.getId(),
    thread: thread,
    threadId: threadId,
    labelState: labelState,
    decision: "open",
  };
}

function readThreadLabelState_(thread, labelIds) {
  const labelsOnThread = thread.getLabels();
  const state = { hold: false, sendFailed: false, release: false };
  const resolvedLabelIds = labelIds || { holdId: null, sendFailedId: null, releaseId: null };
  for (let labelIndex = 0; labelIndex < labelsOnThread.length; labelIndex++) {
    const label = labelsOnThread[labelIndex];
    const name = label.getName();
    const labelId = label.getId();
    if (labelMatches_(name, labelId, HOLD_LABEL_NAME, resolvedLabelIds.holdId, true)) {
      state.hold = true;
    }
    // Release now matches the stored id only. A same-named user label does not.
    if (labelMatches_(name, labelId, RELEASE_LABEL_NAME, resolvedLabelIds.releaseId, false)) {
      state.release = true;
    }
    if (labelMatches_(name, labelId, SEND_FAILED_LABEL_NAME, resolvedLabelIds.sendFailedId, true)) {
      state.sendFailed = true;
    }
  }
  return state;
}

function labelMatches_(name, labelId, expectedName, storedId, matchByName) {
  if (matchByName !== false && name === expectedName) {
    return true;
  }
  return Boolean(storedId) && labelId === storedId;
}

function sendDraftIfOldEnough_(
  snapshot,
  delayMilliseconds,
  passStartedAtMilliseconds,
  labelIds,
  sticky,
  passFlags,
  views
) {
  const draftId = snapshot.draftId;
  const listedMessage = snapshot.message;
  const listedMessageId = listedMessage.getId();
  const interruptedResult = handleInterruptedSend_(
    draftId,
    listedMessageId,
    passStartedAtMilliseconds,
    labelIds,
    passFlags
  );
  if (interruptedResult) {
    return interruptedResult;
  }
  const knownFailureResult = handleKnownFailedSend_(draftId, listedMessageId);
  if (knownFailureResult) {
    return knownFailureResult;
  }
  const listedAgeMilliseconds = messageAgeMilliseconds_(listedMessage.getDate(), Date.now());
  if (
    !draftClocksAllowSend_(
      sticky,
      draftId,
      listedAgeMilliseconds,
      delayMilliseconds,
      passStartedAtMilliseconds
    )
  ) {
    logWaitingDraft_(
      draftId,
      listedAgeMilliseconds,
      listedAgeWaitsOnReleaseClock_(
        sticky,
        draftId,
        listedAgeMilliseconds,
        delayMilliseconds,
        passStartedAtMilliseconds
      )
        ? "release"
        : "listed"
    );
    return { outcome: "waiting" };
  }

  // Re-read before send so a save, Hold, Release now, or Send failed during
  // this run still resets or cancels. GmailApp can serve a stale message
  // from the earlier getDrafts() result. One getThread is reused below.
  if (passFlags && (passFlags.persistFailed || passFlags.quota)) {
    return { outcome: "held" };
  }
  let freshDraft;
  let freshMessage;
  let freshMessageId;
  let freshThread;
  let freshState;
  try {
    freshDraft = GmailApp.getDraft(draftId);
    freshMessage = freshDraft.getMessage();
    freshMessageId = freshDraft.getMessageId();
    freshThread = freshMessage.getThread();
    freshState = readThreadLabelState_(freshThread, labelIds);
  } catch (error) {
    if (isMissingDraftError_(error)) {
      Logger.log(DRAFT_DELETED_BEFORE_SEND_LOG_TEMPLATE, draftId);
      return { outcome: "canceled" };
    }
    if (isRetryLaterQuotaError_(error)) {
      throw error;
    }
    logDraftProblem_("Delayed send will retry this draft. id=%s error=%s", draftId, error);
    return { outcome: "retry" };
  }
  if (freshState.sendFailed) {
    Logger.log("Draft gained Send failed before send. id=%s", draftId);
    return { outcome: "skipped" };
  }
  if (freshMessageId !== listedMessageId) {
    clearFailedSendRecord_(draftId);
    clearInFlightIfDraft_(draftId);
  }
  if (
    preSendStickySaysHold_(
      sticky,
      draftId,
      freshMessageId,
      freshState,
      freshThread,
      labelIds,
      passStartedAtMilliseconds,
      passFlags,
      views,
      delayMilliseconds
    )
  ) {
    return { outcome: "held" };
  }
  const freshAgeMilliseconds = messageAgeMilliseconds_(freshMessage.getDate(), Date.now());
  if (
    !draftClocksAllowSend_(
      sticky,
      draftId,
      freshAgeMilliseconds,
      delayMilliseconds,
      passStartedAtMilliseconds
    )
  ) {
    logWaitingDraft_(
      draftId,
      freshAgeMilliseconds,
      listedAgeWaitsOnReleaseClock_(
        sticky,
        draftId,
        freshAgeMilliseconds,
        delayMilliseconds,
        passStartedAtMilliseconds
      )
        ? "release"
        : "recheck"
    );
    return { outcome: "waiting" };
  }
  if (!draftHasRecipient_(freshMessage)) {
    throw new Error("Draft has no recipient");
  }

  const subject = freshMessage.getSubject();
  snapshot.subject = subject;
  let lastState;
  try {
    lastState = readThreadLabelState_(freshThread, labelIds);
  } catch (error) {
    if (isRetryLaterQuotaError_(error)) {
      throw error;
    }
    logDraftProblem_("Delayed send will retry this draft. id=%s error=%s", draftId, error);
    return { outcome: "retry" };
  }
  if (lastState.sendFailed) {
    Logger.log("Draft gained Send failed before send. id=%s", draftId);
    return { outcome: "skipped" };
  }
  if (lastState.hold || lastState.release) {
    if (
      preSendStickySaysHold_(
        sticky,
        draftId,
        freshMessageId,
        lastState,
        freshThread,
        labelIds,
        passStartedAtMilliseconds,
        passFlags,
        views,
        delayMilliseconds
      )
    ) {
      return { outcome: "held" };
    }
    const lastAgeMilliseconds = messageAgeMilliseconds_(freshMessage.getDate(), Date.now());
    if (
      !draftClocksAllowSend_(
        sticky,
        draftId,
        lastAgeMilliseconds,
        delayMilliseconds,
        passStartedAtMilliseconds
      )
    ) {
      logWaitingDraft_(draftId, lastAgeMilliseconds, "recheck");
      return { outcome: "waiting" };
    }
  }
  if (!writeInFlight_(draftId, freshMessageId)) {
    logDraftProblem_("Delayed send will retry this draft. id=%s error=%s", draftId, "in-flight record was not stored");
    return { outcome: "retry" };
  }
  let sentMessage;
  try {
    sentMessage = freshDraft.send();
  } catch (error) {
    if (!isRetryLaterQuotaError_(error)) {
      recordFailedSend_(draftId, freshMessageId);
    }
    throw error;
  } finally {
    clearInFlight_();
  }
  if (!sentMessage) {
    recordFailedSend_(draftId, freshMessageId);
    throw new Error("GmailDraft.send() returned no message");
  }
  clearFailedSendRecord_(draftId);
  Logger.log("Sent draft. id=%s subject=%s", draftId, subject);
  return { outcome: "sent", sentMessage: sentMessage };
}

function draftHasRecipient_(message) {
  return (
    recipientText_(message.getTo()) !== "" ||
    recipientText_(message.getCc()) !== "" ||
    recipientText_(message.getBcc()) !== ""
  );
}

function recipientText_(value) {
  if (typeof value !== "string") {
    return "";
  }
  return value.trim();
}

function settleThreadLabels_(eligibleDrafts, labelIds, passFlags) {
  const threadIds = [];
  for (let draftIndex = 0; draftIndex < eligibleDrafts.length; draftIndex++) {
    const threadId = eligibleDrafts[draftIndex].threadId;
    if (threadIds.indexOf(threadId) === -1) {
      threadIds.push(threadId);
    }
  }
  for (let threadIndex = 0; threadIndex < threadIds.length; threadIndex++) {
    settleOneThread_(eligibleDrafts, threadIds[threadIndex], labelIds, passFlags);
  }
}

function settleOneThread_(eligibleDrafts, threadId, labelIds, passFlags) {
  const records = [];
  for (let draftIndex = 0; draftIndex < eligibleDrafts.length; draftIndex++) {
    if (eligibleDrafts[draftIndex].threadId === threadId) {
      records.push(eligibleDrafts[draftIndex]);
    }
  }
  const stillOpen =
    threadHasOutcome_(records, "waiting") ||
    threadHasOutcome_(records, "pending") ||
    threadHasOutcome_(records, "quota") ||
    threadHasOutcome_(records, "held") ||
    threadHasOutcome_(records, "retry");
  let failedThread = null;
  if (threadHasOutcome_(records, "failed")) {
    if (stillOpen) {
      Logger.log(
        "Did not apply %s. Another draft on the thread is still waiting. threadId=%s",
        SEND_FAILED_LABEL_NAME,
        threadId
      );
    } else {
      const failedRecord = firstRecordWithOutcome_(records, "failed");
      failedThread = markDraftSendFailed_(
        failedRecord.draft,
        failedRecord.draftId,
        labelIds,
        passFlags
      );
      if (failedThread) {
        clearFailedSendRecordsFor_(records);
      }
    }
  }
  if (stillOpen) {
    return;
  }
  if (threadHasOutcome_(records, "sent")) {
    const sentRecord = firstRecordWithOutcome_(records, "sent");
    removeLegacySendLabelFromSentThread_(sentRecord.sentMessage, sentRecord.draftId);
    return;
  }
  if (failedThread) {
    const failedRecord = firstRecordWithOutcome_(records, "failed");
    removeLegacySendLabelFromThread_(
      failedThread,
      failedRecord.draftId,
      "Send failed is applied, but removing the legacy label failed. id=%s error=%s"
    );
  }
}

function clearFailedSendRecordsFor_(records) {
  for (let recordIndex = 0; recordIndex < records.length; recordIndex++) {
    if (records[recordIndex].outcome === "failed") {
      clearFailedSendRecord_(records[recordIndex].draftId);
    }
  }
}

function threadHasOutcome_(records, outcome) {
  for (let recordIndex = 0; recordIndex < records.length; recordIndex++) {
    if (records[recordIndex].outcome === outcome) {
      return true;
    }
  }
  return false;
}

function firstRecordWithOutcome_(records, outcome) {
  for (let recordIndex = 0; recordIndex < records.length; recordIndex++) {
    if (records[recordIndex].outcome === outcome) {
      return records[recordIndex];
    }
  }
  throw new Error("Missing delayed-send outcome: " + outcome);
}

function getOrCreateLabel_(labelName) {
  const existingLabel = GmailApp.getUserLabelByName(labelName);
  if (existingLabel) {
    return existingLabel;
  }
  return GmailApp.createLabel(labelName);
}

function releaseLabelNameIsScriptOwned_(labelName) {
  return (
    labelName === RELEASE_LABEL_NAME ||
    labelName === RELEASE_LABEL_NAME + " (delayed send)"
  );
}

function releaseLabelForInstall_(properties) {
  const storedId = properties.getProperty(RELEASE_LABEL_ID_PROPERTY);
  const storedLabel = labelWithStoredId_(storedId);
  if (storedLabel && releaseLabelNameIsScriptOwned_(storedLabel.getName())) {
    return storedLabel;
  }
  return createLabelWithoutAdoptingExisting_(RELEASE_LABEL_NAME);
}

function labelForInstall_(storedId, canonicalName, refuseExistingName) {
  const existingStoredLabel = labelWithStoredId_(storedId);
  if (existingStoredLabel) {
    return existingStoredLabel;
  }
  if (refuseExistingName) {
    return createLabelWithoutAdoptingExisting_(canonicalName);
  }
  return getOrCreateLabel_(canonicalName);
}

function labelWithStoredId_(storedId) {
  if (typeof storedId !== "string" || storedId === "") {
    return null;
  }
  const labels = GmailApp.getUserLabels();
  for (let labelIndex = 0; labelIndex < labels.length; labelIndex++) {
    if (labels[labelIndex].getId() === storedId) {
      return labels[labelIndex];
    }
  }
  return null;
}

function createLabelWithoutAdoptingExisting_(labelName) {
  if (!GmailApp.getUserLabelByName(labelName)) {
    return GmailApp.createLabel(labelName);
  }
  const alternateName = labelName + " (delayed send)";
  if (GmailApp.getUserLabelByName(alternateName)) {
    throw new Error(
      "Refusing to adopt an existing " +
        labelName +
        " label. Rename that label and run install again."
    );
  }
  Logger.log("Did not adopt existing label %s. Created %s.", labelName, alternateName);
  return GmailApp.createLabel(alternateName);
}

/**
 * Applies Send failed. Returns the thread when the label is on the thread
 * after this call, including when it was already there. Returns null when
 * the thread could not be read or the label could not be applied. A null
 * return leaves the draft eligible, so a later run tries again.
 */
function markDraftSendFailed_(draft, draftId, labelIds, passFlags) {
  let thread;
  try {
    thread = draft.getMessage().getThread();
  } catch (error) {
    if (isRetryLaterQuotaError_(error)) {
      throw error;
    }
    logDraftProblem_("Could not mark draft send failed. id=%s error=%s", draftId, error);
    return null;
  }
  let labelsOnThread;
  try {
    labelsOnThread = thread.getLabels();
  } catch (error) {
    if (isRetryLaterQuotaError_(error)) {
      throw error;
    }
    logDraftProblem_("Could not mark draft send failed. id=%s error=%s", draftId, error);
    return null;
  }
  const storedId = labelIds && labelIds.sendFailedId;
  for (let labelIndex = 0; labelIndex < labelsOnThread.length; labelIndex++) {
    const label = labelsOnThread[labelIndex];
    if (
      labelMatches_(label.getName(), label.getId(), SEND_FAILED_LABEL_NAME, storedId, true)
    ) {
      return thread;
    }
  }
  try {
    const failedLabel = sendFailedLabelForApply_(storedId, passFlags);
    thread.addLabel(failedLabel);
    Logger.log(
      "Marked draft send failed. id=%s appliedLabel=%s",
      draftId,
      failedLabel.getName()
    );
  } catch (error) {
    if (isRetryLaterQuotaError_(error)) {
      throw error;
    }
    logDraftProblem_("Could not apply the failure label. id=%s error=%s", draftId, error);
    return null;
  }
  return thread;
}

function sendFailedLabelForApply_(storedId, passFlags) {
  if (storedId) {
    const labels = userLabelsForPass_(passFlags);
    for (let labelIndex = 0; labelIndex < labels.length; labelIndex++) {
      if (labels[labelIndex].getId() === storedId) {
        return labels[labelIndex];
      }
    }
  }
  return getOrCreateLabel_(SEND_FAILED_LABEL_NAME);
}

function threadHasLabelName_(thread, labelName) {
  let labelsOnThread;
  try {
    labelsOnThread = thread.getLabels();
  } catch (error) {
    if (isRetryLaterQuotaError_(error)) {
      throw error;
    }
    Logger.log("Could not read labels. error=%s", formatError_(error));
    return false;
  }
  for (let labelIndex = 0; labelIndex < labelsOnThread.length; labelIndex++) {
    if (labelsOnThread[labelIndex].getName() === labelName) {
      return true;
    }
  }
  return false;
}

function deleteDelayedSendTriggers_() {
  const handlerNames = delayedSendHandlerNames_();
  const triggers = ScriptApp.getProjectTriggers();
  let removedTriggerCount = 0;
  for (let triggerIndex = 0; triggerIndex < triggers.length; triggerIndex++) {
    const trigger = triggers[triggerIndex];
    if (handlerNames.indexOf(trigger.getHandlerFunction()) !== -1) {
      ScriptApp.deleteTrigger(trigger);
      removedTriggerCount++;
    }
  }
  return removedTriggerCount;
}

function delayedSendHandlerNames_() {
  return [sendDraftsAfterDelay.name, LEGACY_DELAYED_SEND_HANDLER_NAME];
}

function messageAgeMilliseconds_(messageDate, nowMilliseconds) {
  if (!(messageDate instanceof Date)) {
    throw new Error("Draft message has no date");
  }
  const messageTimeMilliseconds = messageDate.getTime();
  if (!isFinite(messageTimeMilliseconds)) {
    throw new Error("Draft message date is invalid");
  }
  if (typeof nowMilliseconds !== "number" || !isFinite(nowMilliseconds)) {
    throw new Error("Current time is invalid");
  }
  return nowMilliseconds - messageTimeMilliseconds;
}

function isOldEnoughToSend_(ageMilliseconds, delayMilliseconds) {
  if (typeof ageMilliseconds !== "number" || !isFinite(ageMilliseconds)) {
    throw new Error("Draft age is invalid");
  }
  if (
    typeof delayMilliseconds !== "number" ||
    !(delayMilliseconds > 0) ||
    !isFinite(delayMilliseconds)
  ) {
    throw new Error("Delay is invalid");
  }
  return ageMilliseconds >= delayMilliseconds;
}

function delayMilliseconds_() {
  if (typeof DELAY_MINUTES !== "number" || !(DELAY_MINUTES > 0) || !isFinite(DELAY_MINUTES)) {
    throw new Error("DELAY_MINUTES must be a positive finite number");
  }
  return DELAY_MINUTES * 60 * 1000;
}

function assertTriggerIntervalMinutes_(intervalMinutes) {
  if (ALLOWED_TRIGGER_INTERVAL_MINUTES.indexOf(intervalMinutes) !== -1) {
    return;
  }
  throw new Error(
    "TRIGGER_INTERVAL_MINUTES must be 1, 5, 10, 15, or 30. ClockTriggerBuilder.everyMinutes rejects any other value."
  );
}

function assertLabelName_(labelName, constantName) {
  if (typeof labelName !== "string" || labelName.trim() === "") {
    throw new Error(constantName + " must be a non-empty string");
  }
}

function assertDelayedSendConfigured_() {
  delayMilliseconds_();
  assertTriggerIntervalMinutes_(TRIGGER_INTERVAL_MINUTES);
  assertLabelName_(HOLD_LABEL_NAME, "HOLD_LABEL_NAME");
  assertLabelName_(RELEASE_LABEL_NAME, "RELEASE_LABEL_NAME");
  assertLabelName_(SEND_FAILED_LABEL_NAME, "SEND_FAILED_LABEL_NAME");
  assertLabelName_(LEGACY_SEND_LABEL_NAME, "LEGACY_SEND_LABEL_NAME");
}

function removeLegacySendLabelFromSentThread_(sentMessage, draftId) {
  let thread;
  try {
    thread = sentMessage.getThread();
  } catch (error) {
    logDraftProblem_("Sent draft, but removing the label failed. id=%s error=%s", draftId, error);
    return;
  }
  removeLegacySendLabelFromThread_(
    thread,
    draftId,
    "Sent draft, but removing the label failed. id=%s error=%s"
  );
}

function removeLegacySendLabelFromThread_(thread, draftId, failureTemplate) {
  if (!threadHasLabelName_(thread, LEGACY_SEND_LABEL_NAME)) {
    return;
  }
  let label;
  try {
    label = GmailApp.getUserLabelByName(LEGACY_SEND_LABEL_NAME);
  } catch (error) {
    logDraftProblem_(failureTemplate, draftId, error);
    return;
  }
  if (!label) {
    return;
  }
  try {
    thread.removeLabel(label);
  } catch (error) {
    logDraftProblem_(failureTemplate, draftId, error);
  }
}

function logDraftProblem_(template, draftId, error) {
  Logger.log(template, draftId, formatError_(error));
}

function logWaitingDraft_(draftId, ageMilliseconds, stage) {
  Logger.log(
    "Waiting to send draft. stage=%s id=%s ageSeconds=%s",
    stage,
    draftId,
    Math.round(ageMilliseconds / 1000)
  );
}

/**
 * Quotas that clear later. Parking those drafts on Send failed would
 * stop the retry. Documented Apps Script text, with the service name
 * substituted, is "Service invoked too many times: gmail." for a daily
 * cap and "Service invoked too many times in a short time: gmail." for
 * a short burst. Live failures also use "for one day: gmail".
 * "too many times: email" matches the documented daily form. It is not
 * a substring of the "for one day" or "in a short time" forms.
 * "Service using too much computer time for one day." is the documented
 * daily computer-time cap. That one retries too. It is not a send failure.
 */
function isRetryLaterQuotaError_(error) {
  const parts = [];
  if (error && error.message) {
    parts.push(String(error.message));
  }
  parts.push(formatError_(error));
  const text = parts.join("\n").toLowerCase();
  return (
    text.indexOf("email recipients per day") !== -1 ||
    text.indexOf("for one day: email") !== -1 ||
    text.indexOf("for one day: gmail") !== -1 ||
    text.indexOf("in a short time: email") !== -1 ||
    text.indexOf("in a short time: gmail") !== -1 ||
    text.indexOf("too many times: email") !== -1 ||
    text.indexOf("too many times: gmail") !== -1 ||
    text.indexOf("too much computer time") !== -1
  );
}

/**
 * GmailApp.getDraft throws when no draft has that id. The message text
 * is not a fixed string in the reference. Match the documented reason
 * and the entity-not-found text Gmail returns for a deleted draft.
 */
function isMissingDraftError_(error) {
  const text = (error && error.message ? String(error.message) : String(error)).toLowerCase();
  return (
    text.indexOf("no draft") !== -1 ||
    text.indexOf("draft not found") !== -1 ||
    text.indexOf("cannot be found") !== -1 ||
    text.indexOf("requested entity was not found") !== -1
  );
}

function logPersistentFailureLatchProblem_(action, error) {
  Logger.log(
    "Could not " + action + " the persistent-failure latch. error=%s",
    formatError_(error)
  );
}

function persistentFailureCache_() {
  try {
    if (typeof CacheService === "undefined" || !CacheService.getScriptCache) {
      return null;
    }
    return CacheService.getScriptCache();
  } catch (error) {
    return null;
  }
}

function throwPersistentFailureAtMostOncePerHour_(message) {
  const nowMilliseconds = Date.now();
  const cache = persistentFailureCache_();
  if (cache) {
    try {
      const stored = cache.get(PERSISTENT_FAILURE_LATCH_PROPERTY);
      const latchedAtMilliseconds = stored === null ? NaN : Number(stored);
      if (
        isFinite(latchedAtMilliseconds) &&
        nowMilliseconds - latchedAtMilliseconds < PERSISTENT_FAILURE_THROW_INTERVAL_MILLISECONDS
      ) {
        Logger.log("Persistent delayed-send failure. Not throwing again this hour. %s", message);
        return;
      }
      cache.put(
        PERSISTENT_FAILURE_LATCH_PROPERTY,
        String(nowMilliseconds),
        PERSISTENT_FAILURE_THROW_INTERVAL_MILLISECONDS / 1000
      );
      throw new Error(message);
    } catch (error) {
      if (error && error.message === message) {
        throw error;
      }
      Logger.log(
        "Could not use the failure-alert cache. error=%s",
        formatError_(error)
      );
    }
  }
  if (!minuteFallsInPersistentFailureWindow_(nowMilliseconds, TRIGGER_INTERVAL_MINUTES)) {
    Logger.log("Persistent delayed-send failure. Not throwing again this hour. %s", message);
    return;
  }
  throw new Error(message);
}

function minuteFallsInPersistentFailureWindow_(nowMilliseconds, intervalMinutes) {
  const minuteOfHour = Math.floor(nowMilliseconds / 60000) % 60;
  return minuteOfHour < intervalMinutes;
}

function clearPersistentFailureLatch_() {
  const cache = persistentFailureCache_();
  if (cache) {
    try {
      cache.remove(PERSISTENT_FAILURE_LATCH_PROPERTY);
    } catch (error) {
      Logger.log("Could not clear the failure-alert cache. error=%s", formatError_(error));
    }
  }
  try {
    const properties = PropertiesService.getScriptProperties();
    if (properties.getProperty(PERSISTENT_FAILURE_LATCH_PROPERTY) === null) {
      return;
    }
    properties.deleteProperty(PERSISTENT_FAILURE_LATCH_PROPERTY);
  } catch (error) {
    logPersistentFailureLatchProblem_("clear", error);
  }
}

function storeLabelId_(propertyName, label) {
  const labelId = label.getId();
  if (typeof labelId !== "string" || labelId === "") {
    throw new Error("Label has no id");
  }
  PropertiesService.getScriptProperties().setProperty(propertyName, labelId);
}

function rememberedLabelIds_(nowMilliseconds, snapshot) {
  const labelIds = { holdId: null, sendFailedId: null, releaseId: null };
  const stored = snapshot || {};
  labelIds.holdId = stored[HOLD_LABEL_ID_PROPERTY] || null;
  labelIds.releaseId = stored[RELEASE_LABEL_ID_PROPERTY] || null;
  labelIds.sendFailedId = stored[SEND_FAILED_LABEL_ID_PROPERTY] || null;
  let properties;
  try {
    properties = PropertiesService.getScriptProperties();
  } catch (error) {
    Logger.log(
      "Could not read stored label ids. Matching Hold and Send failed by name only. error=%s",
      formatError_(error)
    );
    return labelIds;
  }
  const cooldown = labelLookupCooldownMap_(stored[LABEL_LOOKUP_COOLDOWN_PROPERTY]);
  if (!labelIds.holdId) {
    labelIds.holdId = lookupAndStoreLabelId_(
      properties,
      HOLD_LABEL_NAME,
      HOLD_LABEL_ID_PROPERTY,
      nowMilliseconds,
      cooldown
    );
  }
  // Release now is never resolved by name. A missing id does not match.
  if (!labelIds.sendFailedId) {
    labelIds.sendFailedId = lookupAndStoreLabelId_(
      properties,
      SEND_FAILED_LABEL_NAME,
      SEND_FAILED_LABEL_ID_PROPERTY,
      nowMilliseconds,
      cooldown
    );
  }
  return labelIds;
}

function labelLookupCooldownMap_(raw) {
  if (raw === null || raw === undefined || raw === "") {
    return {};
  }
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || typeof parsed.length === "number") {
      return {};
    }
    return parsed;
  } catch (error) {
    return {};
  }
}

function lookupAndStoreLabelId_(properties, labelName, propertyName, nowMilliseconds, cooldown) {
  const lastMiss = cooldown[propertyName];
  if (
    typeof lastMiss === "number" &&
    isFinite(lastMiss) &&
    nowMilliseconds - lastMiss < LABEL_LOOKUP_COOLDOWN_MILLISECONDS
  ) {
    return null;
  }
  try {
    const label = GmailApp.getUserLabelByName(labelName);
    if (!label) {
      cooldown[propertyName] = nowMilliseconds;
      try {
        properties.setProperty(LABEL_LOOKUP_COOLDOWN_PROPERTY, JSON.stringify(cooldown));
      } catch (error) {
        Logger.log(
          "Could not store label lookup cooldown. label=%s error=%s",
          labelName,
          formatError_(error)
        );
      }
      return null;
    }
    const labelId = label.getId();
    if (typeof labelId !== "string" || labelId === "") {
      return null;
    }
    try {
      properties.setProperty(propertyName, labelId);
      if (Object.prototype.hasOwnProperty.call(cooldown, propertyName)) {
        delete cooldown[propertyName];
        properties.setProperty(LABEL_LOOKUP_COOLDOWN_PROPERTY, JSON.stringify(cooldown));
      }
    } catch (error) {
      Logger.log("Could not store label id. label=%s error=%s", labelName, formatError_(error));
    }
    return labelId;
  } catch (error) {
    if (isRetryLaterQuotaError_(error)) {
      throw error;
    }
    Logger.log(
      "Could not look up label id. Matching by name only. label=%s error=%s",
      labelName,
      formatError_(error)
    );
    return null;
  }
}

function handleInterruptedSend_(
  draftId,
  listedMessageId,
  passStartedAtMilliseconds,
  labelIds,
  passFlags
) {
  const inFlight = readInFlight_();
  if (!inFlight || inFlight.draftId !== draftId) {
    return null;
  }
  if (inFlight.messageId !== listedMessageId) {
    clearInFlight_();
    Logger.log("Cleared interrupted-send record after the draft changed. id=%s", draftId);
    return null;
  }
  if (!(inFlight.startedAt < passStartedAtMilliseconds)) {
    return null;
  }
  let freshDraft;
  try {
    freshDraft = GmailApp.getDraft(draftId);
  } catch (error) {
    if (isMissingDraftError_(error)) {
      clearInFlight_();
      Logger.log("possible interrupted send, check Sent. id=%s", draftId);
      Logger.log(DRAFT_DELETED_BEFORE_SEND_LOG_TEMPLATE, draftId);
      return { outcome: "canceled" };
    }
    if (isRetryLaterQuotaError_(error)) {
      throw error;
    }
    logDraftProblem_("Delayed send will retry this draft. id=%s error=%s", draftId, error);
    return { outcome: "retry" };
  }
  if (freshDraft.getMessageId() !== inFlight.messageId) {
    clearInFlight_();
    Logger.log("Cleared interrupted-send record after the draft changed. id=%s", draftId);
    return null;
  }
  Logger.log("possible interrupted send, check Sent. id=%s", draftId);
  const failedThread = markDraftSendFailed_(freshDraft, draftId, labelIds, passFlags);
  if (failedThread) {
    clearInFlight_();
    clearFailedSendRecord_(draftId);
    removeLegacySendLabelFromThread_(
      failedThread,
      draftId,
      "Send failed is applied, but removing the legacy label failed. id=%s error=%s"
    );
  }
  return { outcome: "skipped" };
}

function handleKnownFailedSend_(draftId, listedMessageId) {
  const recordedMessageId = recordedFailedSendMessageId_(draftId);
  if (!recordedMessageId) {
    return null;
  }
  if (recordedMessageId !== listedMessageId) {
    clearFailedSendRecord_(draftId);
    Logger.log("Cleared failed-send record after the draft changed. id=%s", draftId);
    return null;
  }
  let freshDraft;
  try {
    freshDraft = GmailApp.getDraft(draftId);
  } catch (error) {
    if (isMissingDraftError_(error)) {
      clearFailedSendRecord_(draftId);
      Logger.log(DRAFT_DELETED_BEFORE_SEND_LOG_TEMPLATE, draftId);
      return { outcome: "canceled" };
    }
    if (isRetryLaterQuotaError_(error)) {
      throw error;
    }
    logDraftProblem_("Delayed send will retry this draft. id=%s error=%s", draftId, error);
    return { outcome: "retry" };
  }
  if (freshDraft.getMessageId() !== recordedMessageId) {
    clearFailedSendRecord_(draftId);
    Logger.log("Cleared failed-send record after the draft changed. id=%s", draftId);
    return null;
  }
  Logger.log("Not sending again after a failed send. id=%s", draftId);
  return { outcome: "failed" };
}

function clearInFlightIfDraft_(draftId) {
  const inFlight = readInFlight_();
  if (inFlight && inFlight.draftId === draftId) {
    clearInFlight_();
  }
}

function writeInFlight_(draftId, messageId) {
  try {
    PropertiesService.getScriptProperties().setProperty(
      IN_FLIGHT_SEND_PROPERTY,
      JSON.stringify({
        draftId: draftId,
        messageId: messageId,
        startedAt: Date.now(),
      })
    );
    return true;
  } catch (error) {
    Logger.log(
      "Could not store the in-flight send record. id=%s error=%s",
      draftId,
      formatError_(error)
    );
    return false;
  }
}

function clearInFlight_() {
  try {
    const properties = PropertiesService.getScriptProperties();
    if (properties.getProperty(IN_FLIGHT_SEND_PROPERTY) === null) {
      return;
    }
    properties.deleteProperty(IN_FLIGHT_SEND_PROPERTY);
  } catch (error) {
    Logger.log("Could not clear the in-flight send record. error=%s", formatError_(error));
  }
}

function readInFlight_() {
  try {
    const parsed = readStoredJson_(IN_FLIGHT_SEND_PROPERTY);
    if (!parsed || typeof parsed.draftId !== "string" || typeof parsed.messageId !== "string") {
      return null;
    }
    if (typeof parsed.startedAt !== "number" || !isFinite(parsed.startedAt)) {
      return null;
    }
    return parsed;
  } catch (error) {
    Logger.log("Could not read the in-flight send record. error=%s", formatError_(error));
    return null;
  }
}

function recordedFailedSendMessageId_(draftId) {
  try {
    const failedSendsByDraftId = readFailedSendMap_();
    if (!Object.prototype.hasOwnProperty.call(failedSendsByDraftId, draftId)) {
      return null;
    }
    const messageId = failedSendsByDraftId[draftId];
    if (typeof messageId !== "string" || messageId === "") {
      return null;
    }
    return messageId;
  } catch (error) {
    Logger.log("Could not read the failed-send record. id=%s error=%s", draftId, formatError_(error));
    return null;
  }
}

function recordFailedSend_(draftId, messageId) {
  try {
    const failedSendsByDraftId = readFailedSendMap_();
    failedSendsByDraftId[draftId] = messageId;
    writeFailedSendMap_(failedSendsByDraftId);
  } catch (error) {
    Logger.log("Could not record the failed send. id=%s error=%s", draftId, formatError_(error));
  }
}

function clearFailedSendRecord_(draftId) {
  try {
    const failedSendsByDraftId = readFailedSendMap_();
    if (!Object.prototype.hasOwnProperty.call(failedSendsByDraftId, draftId)) {
      return;
    }
    delete failedSendsByDraftId[draftId];
    writeFailedSendMap_(failedSendsByDraftId);
  } catch (error) {
    Logger.log("Could not clear the failed-send record. id=%s error=%s", draftId, formatError_(error));
  }
}

function readFailedSendMap_() {
  const parsed = readStoredJson_(FAILED_SEND_BY_DRAFT_ID_PROPERTY);
  if (!parsed || typeof parsed !== "object" || typeof parsed.length === "number") {
    return {};
  }
  return parsed;
}

function writeFailedSendMap_(failedSendsByDraftId) {
  const properties = PropertiesService.getScriptProperties();
  if (!mapHasAnyKey_(failedSendsByDraftId)) {
    if (properties.getProperty(FAILED_SEND_BY_DRAFT_ID_PROPERTY) !== null) {
      properties.deleteProperty(FAILED_SEND_BY_DRAFT_ID_PROPERTY);
    }
    return;
  }
  properties.setProperty(FAILED_SEND_BY_DRAFT_ID_PROPERTY, JSON.stringify(failedSendsByDraftId));
}

function mapHasAnyKey_(map) {
  for (const key in map) {
    if (Object.prototype.hasOwnProperty.call(map, key)) {
      return true;
    }
  }
  return false;
}

function readStoredJson_(propertyName) {
  const raw = PropertiesService.getScriptProperties().getProperty(propertyName);
  if (raw === null || raw === "") {
    return null;
  }
  try {
    return JSON.parse(raw);
  } catch (error) {
    Logger.log("Could not parse script property %s. error=%s", propertyName, formatError_(error));
    return null;
  }
}

function logSendFailedSkipsOnce_(draftIds) {
  if (draftIds.length === 0) {
    return;
  }
  const currentIds = [];
  const seen = {};
  for (let index = 0; index < draftIds.length; index++) {
    const draftId = draftIds[index];
    if (seen[draftId]) {
      continue;
    }
    seen[draftId] = true;
    currentIds.push(draftId);
  }
  let stored = {};
  let canRead = true;
  try {
    const parsed = readStoredJson_(SEND_FAILED_SKIP_LOGGED_PROPERTY);
    if (parsed && typeof parsed.length === "number") {
      for (let index = 0; index < parsed.length; index++) {
        stored[parsed[index]] = true;
      }
    }
  } catch (error) {
    canRead = false;
    Logger.log("Could not record the Send failed skip log. error=%s", formatError_(error));
  }
  for (let index = 0; index < currentIds.length; index++) {
    if (!canRead || !stored[currentIds[index]]) {
      Logger.log("Skipping draft on Send failed. id=%s", currentIds[index]);
    }
  }
  if (!canRead) {
    return;
  }
  try {
    PropertiesService.getScriptProperties().setProperty(
      SEND_FAILED_SKIP_LOGGED_PROPERTY,
      JSON.stringify(currentIds)
    );
  } catch (error) {
    Logger.log("Could not record the Send failed skip log. error=%s", formatError_(error));
  }
}

function applyStickyHoldForPass_(views, sticky, labelIds, nowMilliseconds, passFlags) {
  if (!sticky.readable) {
    forceHoldAllDraftViews_(views);
    return;
  }
  const viewsByThreadId = {};
  const threadIds = [];
  for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
    const threadId = views[viewIndex].threadId;
    if (!viewsByThreadId[threadId]) {
      viewsByThreadId[threadId] = [];
      threadIds.push(threadId);
    }
    viewsByThreadId[threadId].push(views[viewIndex]);
  }
  for (let threadIndex = 0; threadIndex < threadIds.length; threadIndex++) {
    applyStickyHoldForThread_(
      viewsByThreadId[threadIds[threadIndex]],
      sticky,
      labelIds,
      nowMilliseconds,
      passFlags
    );
  }
}

function threadScanIsIncomplete_(views, passFlags) {
  if (!passFlags) {
    return false;
  }
  if (passFlags.blockAllReleases || passFlags.quota) {
    return true;
  }
  const threadId = views[0].threadId;
  return Boolean(passFlags.incompleteThreadIds && passFlags.incompleteThreadIds[threadId]);
}

function holdEntireThread_(views) {
  for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
    views[viewIndex].decision = "hold";
    views[viewIndex].confirmedRelease = false;
  }
}

function anyViewDecisionHold_(views) {
  for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
    if (views[viewIndex].decision === "hold") {
      return true;
    }
  }
  return false;
}

function applyStickyHoldForThread_(views, sticky, labelIds, nowMilliseconds, passFlags) {
  const labelState = views[0].labelState;
  if (threadScanIsIncomplete_(views, passFlags)) {
    holdThreadBecauseScanIsIncomplete_(views, sticky, labelState, passFlags);
    if (labelState.release) {
      markReleaseClockKept_(sticky, views);
    }
    return;
  }
  if (labelState.release) {
    armReleaseForViews_(views, sticky, nowMilliseconds);
    markReleaseClockKept_(sticky, views);
    for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
      views[viewIndex].labelAction = "clear-release";
      views[viewIndex].decision = "release-pending";
      Logger.log("Release label wins. id=%s", views[viewIndex].draftId);
    }
    return;
  }
  if (labelState.hold) {
    for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
      rememberHold_(sticky, views[viewIndex]);
    }
    return;
  }
  let editDroppedHold = false;
  for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
    const draftId = views[viewIndex].draftId;
    if (!Object.prototype.hasOwnProperty.call(sticky.held, draftId)) {
      continue;
    }
    if (sticky.held[draftId] !== views[viewIndex].messageId) {
      editDroppedHold = true;
    }
  }
  if (editDroppedHold) {
    for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
      views[viewIndex].decision = "hold";
      views[viewIndex].labelAction = "restore-hold";
    }
    return;
  }
  let blockRelease = false;
  for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
    const view = views[viewIndex];
    if (!Object.prototype.hasOwnProperty.call(sticky.held, view.draftId)) {
      view.decision = "open";
      continue;
    }
    const fresh = freshDraftObservation_(view.draftId, labelIds);
    if (fresh.quota) {
      passFlags.quota = true;
      view.decision = "hold";
      blockRelease = true;
      continue;
    }
    if (!fresh.ok) {
      if (!fresh.quota) {
        passFlags.incompleteThreadIds[view.threadId] = true;
        noteFreshReadFailure_(sticky, view.draftId, passFlags);
      }
      view.decision = "hold";
      blockRelease = true;
      continue;
    }
    delete sticky.unreadPasses[freshReadFailureKey_(view.draftId)];
    if (fresh.labelState.release) {
      if (threadScanIsIncomplete_(views, passFlags)) {
        holdEntireThread_(views);
        markReleaseClockKept_(sticky, views);
        return;
      }
      armReleaseForViews_(views, sticky, nowMilliseconds);
      markReleaseClockKept_(sticky, views);
      for (let releaseIndex = 0; releaseIndex < views.length; releaseIndex++) {
        views[releaseIndex].labelAction = "clear-release";
        views[releaseIndex].decision = "release-pending";
        Logger.log("Release label wins. id=%s", views[releaseIndex].draftId);
      }
      return;
    }
    if (fresh.labelState.hold) {
      for (let holdIndex = 0; holdIndex < views.length; holdIndex++) {
        if (views[holdIndex].draftId === view.draftId) {
          views[holdIndex].restoreMessageId = fresh.messageId;
        }
        rememberHold_(sticky, views[holdIndex]);
      }
      return;
    }
    if (fresh.messageId !== view.messageId) {
      view.restoreMessageId = fresh.messageId;
      view.decision = "hold";
      view.labelAction = "restore-hold";
      blockRelease = true;
      continue;
    }
    view.confirmedRelease = true;
    view.confirmedMessageId = fresh.messageId;
  }
  if (passFlags.quota || blockRelease || anyViewDecisionHold_(views)) {
    holdEntireThread_(views);
    return;
  }
  let anyConfirmedRelease = false;
  for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
    const view = views[viewIndex];
    if (!view.confirmedRelease) {
      continue;
    }
    const messageId = view.confirmedMessageId;
    if (sticky.releaseSeenOnce[view.draftId] === messageId) {
      anyConfirmedRelease = true;
    } else {
      sticky.releaseSeenOnce[view.draftId] = messageId;
      view.decision = "hold";
      Logger.log(
        "Hold removal seen once. Waiting for another pass. id=%s",
        view.draftId
      );
    }
  }
  if (anyViewDecisionHold_(views) || !anyConfirmedRelease) {
    if (anyViewDecisionHold_(views)) {
      holdEntireThread_(views);
    }
    return;
  }
  armReleaseForViews_(views, sticky, nowMilliseconds);
  for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
    const view = views[viewIndex];
    delete sticky.releaseSeenOnce[view.draftId];
    view.decision = "release";
    Logger.log("Hold removed. Release clock started. id=%s", view.draftId);
  }
}

function markReleaseClockKept_(sticky, views) {
  if (!sticky.keepReleasedAt) {
    sticky.keepReleasedAt = {};
  }
  for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
    sticky.keepReleasedAt[views[viewIndex].draftId] = true;
  }
}

function clearReleaseClockKept_(sticky, views) {
  if (!sticky.keepReleasedAt) {
    return;
  }
  for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
    delete sticky.keepReleasedAt[views[viewIndex].draftId];
  }
}

function holdThreadBecauseScanIsIncomplete_(views, sticky, labelState, passFlags) {
  let editDroppedHold = false;
  if (!labelState.hold && !labelState.release) {
    for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
      const draftId = views[viewIndex].draftId;
      if (!Object.prototype.hasOwnProperty.call(sticky.held, draftId)) {
        continue;
      }
      if (sticky.held[draftId] !== views[viewIndex].messageId) {
        editDroppedHold = true;
      }
    }
  }
  for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
    const view = views[viewIndex];
    const tracked = Object.prototype.hasOwnProperty.call(sticky.held, view.draftId);
    if (labelState.hold) {
      rememberHold_(sticky, view);
      continue;
    }
    if (labelState.release || tracked || editDroppedHold) {
      view.decision = "hold";
    }
    if (editDroppedHold && !passFlags.quota && !labelState.release) {
      view.labelAction = "restore-hold";
    }
  }
}

function rememberHold_(sticky, view) {
  sticky.held[view.draftId] = view.restoreMessageId || view.messageId;
  delete sticky.releasedAt[view.draftId];
  delete sticky.releaseSeenOnce[view.draftId];
  view.decision = "hold";
}

function armReleaseForViews_(views, sticky, nowMilliseconds) {
  for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
    armReleaseClock_(sticky, views[viewIndex].draftId, nowMilliseconds);
  }
}

function armReleaseClock_(sticky, draftId, nowMilliseconds) {
  const existing = sticky.releasedAt[draftId];
  if (typeof existing !== "number" || !isFinite(existing) || existing > nowMilliseconds) {
    sticky.releasedAt[draftId] = nowMilliseconds;
  }
  delete sticky.held[draftId];
  delete sticky.releaseSeenOnce[draftId];
}

function freshDraftObservation_(draftId, labelIds) {
  try {
    const freshDraft = GmailApp.getDraft(draftId);
    const messageId = freshDraft.getMessageId();
    const thread = freshDraft.getMessage().getThread();
    return {
      ok: true,
      messageId: messageId,
      labelState: readThreadLabelState_(thread, labelIds),
    };
  } catch (error) {
    if (isRetryLaterQuotaError_(error)) {
      return { ok: false, quota: true, error: error };
    }
    return { ok: false, missing: isMissingDraftError_(error), error: error };
  }
}

function applyStickyLabelMutations_(views, sticky, labelIds, passFlags) {
  if (passFlags.skipLabelWrites || passFlags.quota) {
    return;
  }
  const viewsByThreadId = {};
  const threadIds = [];
  for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
    const threadId = views[viewIndex].threadId;
    if (!viewsByThreadId[threadId]) {
      viewsByThreadId[threadId] = [];
      threadIds.push(threadId);
    }
    viewsByThreadId[threadId].push(views[viewIndex]);
  }
  for (let threadIndex = 0; threadIndex < threadIds.length; threadIndex++) {
    if (passFlags.quota) {
      return;
    }
    const group = viewsByThreadId[threadIds[threadIndex]];
    let action = null;
    for (let viewIndex = 0; viewIndex < group.length; viewIndex++) {
      if (group[viewIndex].labelAction === "clear-release") {
        action = "clear-release";
      }
    }
    if (!action) {
      for (let viewIndex = 0; viewIndex < group.length; viewIndex++) {
        if (group[viewIndex].labelAction === "restore-hold") {
          action = "restore-hold";
        }
      }
    }
    if (action === "clear-release") {
      const removed = removeReleaseAndHoldLabels_(group[0].thread, labelIds);
      if (removed.quota) {
        passFlags.quota = true;
        return;
      }
      if (!removed.releaseCleared) {
        passFlags.releaseStuck = true;
        markReleaseClockKept_(sticky, group);
        for (let viewIndex = 0; viewIndex < group.length; viewIndex++) {
          group[viewIndex].decision = "hold";
        }
      } else {
        clearReleaseClockKept_(sticky, group);
        for (let viewIndex = 0; viewIndex < group.length; viewIndex++) {
          group[viewIndex].decision = "release";
          group[viewIndex].labelState.hold = false;
          group[viewIndex].labelState.release = false;
        }
      }
    } else if (action === "restore-hold") {
      const restored = restoreHoldLabel_(group[0].thread, labelIds, passFlags);
      if (restored === "quota") {
        passFlags.quota = true;
        return;
      }
      noteHoldRestoreResult_(group, sticky, restored === "restored", passFlags);
    }
  }
}

function noteHoldRestoreResult_(views, sticky, restored, passFlags) {
  for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
    const view = views[viewIndex];
    view.decision = "hold";
    delete sticky.releasedAt[view.draftId];
    delete sticky.releaseSeenOnce[view.draftId];
    const tracked = Object.prototype.hasOwnProperty.call(sticky.held, view.draftId);
    const remembered = tracked ? sticky.held[view.draftId] : null;
    const targetMessageId = view.restoreMessageId || view.messageId;
    const messageChanged =
      tracked &&
      remembered !== targetMessageId &&
      remembered !== STICKY_HOLD_PENDING_MESSAGE_ID;
    if (restored) {
      sticky.held[view.draftId] = targetMessageId;
      if (messageChanged) {
        Logger.log("Re-applied Hold after an edit dropped it. id=%s", view.draftId);
      }
      continue;
    }
    if (messageChanged) {
      Logger.log("Could not re-apply Hold. Staying held. id=%s", view.draftId);
      passFlags.restoreFailed = true;
      continue;
    }
    sticky.held[view.draftId] = STICKY_HOLD_PENDING_MESSAGE_ID;
    Logger.log("Could not re-apply Hold. Staying held. id=%s", view.draftId);
    passFlags.restoreFailed = true;
  }
}

function preSendStickySaysHold_(
  sticky,
  draftId,
  freshMessageId,
  freshState,
  thread,
  labelIds,
  nowMilliseconds,
  passFlags,
  views,
  delayMilliseconds
) {
  if (!sticky || !sticky.readable) {
    Logger.log("Could not read sticky Hold state. Holding draft. id=%s", draftId);
    return true;
  }
  if (passFlags && (passFlags.persistFailed || passFlags.quota)) {
    return true;
  }
  if (freshState.release) {
    const threadId = thread.getId();
    if (
      passFlags &&
      (passFlags.blockAllReleases ||
        (passFlags.incompleteThreadIds && passFlags.incompleteThreadIds[threadId]))
    ) {
      return true;
    }
    const draftIds = draftIdsOnThread_(views, thread.getId(), draftId);
    for (let idIndex = 0; idIndex < draftIds.length; idIndex++) {
      if (!sticky.keepReleasedAt) {
        sticky.keepReleasedAt = {};
      }
      sticky.keepReleasedAt[draftIds[idIndex]] = true;
    }
    for (let idIndex = 0; idIndex < draftIds.length; idIndex++) {
      armReleaseClock_(sticky, draftIds[idIndex], nowMilliseconds);
      Logger.log("Release label wins. id=%s", draftIds[idIndex]);
    }
    const persisted = persistStickyHoldState_(sticky, nowMilliseconds, delayMilliseconds);
    if (!persisted.ok) {
      if (passFlags) {
        passFlags.persistFailed = true;
      }
      return true;
    }
    const removed = removeReleaseAndHoldLabels_(thread, labelIds);
    if (removed.quota) {
      if (passFlags) {
        passFlags.quota = true;
      }
      return true;
    }
    if (!removed.releaseCleared) {
      if (passFlags) {
        passFlags.releaseStuck = true;
      }
      Logger.log("Could not remove Release. Staying held. id=%s", draftId);
      return true;
    }
    for (let idIndex = 0; idIndex < draftIds.length; idIndex++) {
      if (sticky.keepReleasedAt) {
        delete sticky.keepReleasedAt[draftIds[idIndex]];
      }
    }
    freshState.hold = false;
    freshState.release = false;
    return false;
  }
  if (freshState.hold) {
    sticky.held[draftId] = freshMessageId;
    delete sticky.releasedAt[draftId];
    delete sticky.releaseSeenOnce[draftId];
    const persisted = persistStickyHoldState_(sticky, nowMilliseconds, delayMilliseconds);
    if (!persisted.ok && passFlags) {
      passFlags.persistFailed = true;
    }
    Logger.log("Draft gained Hold before send. id=%s", draftId);
    return true;
  }
  return false;
}

function draftIdsOnThread_(views, threadId, currentDraftId) {
  const ids = [];
  const seen = {};
  if (views) {
    for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
      const draftId = views[viewIndex].draftId;
      if (views[viewIndex].threadId === threadId && !seen[draftId]) {
        seen[draftId] = true;
        ids.push(draftId);
      }
    }
  }
  if (!seen[currentDraftId]) {
    ids.push(currentDraftId);
  }
  return ids;
}

function restoreHoldLabel_(thread, labelIds, passFlags) {
  try {
    let holdLabel = null;
    const storedId = labelIds && labelIds.holdId;
    if (storedId) {
      const labels = userLabelsForPass_(passFlags);
      for (let labelIndex = 0; labelIndex < labels.length; labelIndex++) {
        if (labels[labelIndex].getId() === storedId) {
          holdLabel = labels[labelIndex];
          break;
        }
      }
    }
    if (!holdLabel) {
      holdLabel = getOrCreateLabel_(HOLD_LABEL_NAME);
    }
    thread.addLabel(holdLabel);
    return "restored";
  } catch (error) {
    if (isRetryLaterQuotaError_(error)) {
      return "quota";
    }
    Logger.log("Could not re-apply Hold. error=%s", formatError_(error));
    return "failed";
  }
}

function userLabelsForPass_(passFlags) {
  if (passFlags && passFlags.userLabelsLoaded) {
    return passFlags.userLabels;
  }
  const labels = GmailApp.getUserLabels();
  if (passFlags) {
    passFlags.userLabels = labels;
    passFlags.userLabelsLoaded = true;
  }
  return labels;
}

function removeReleaseAndHoldLabels_(thread, labelIds) {
  let labelsOnThread;
  try {
    labelsOnThread = thread.getLabels();
  } catch (error) {
    if (isRetryLaterQuotaError_(error)) {
      return { quota: true, holdCleared: false, releaseCleared: false };
    }
    Logger.log("Could not read labels to clear Release. error=%s", formatError_(error));
    return { quota: false, holdCleared: false, releaseCleared: false };
  }
  const resolvedLabelIds = labelIds || { holdId: null, releaseId: null };
  let holdFailed = false;
  for (let labelIndex = 0; labelIndex < labelsOnThread.length; labelIndex++) {
    const label = labelsOnThread[labelIndex];
    if (
      !labelMatches_(
        label.getName(),
        label.getId(),
        HOLD_LABEL_NAME,
        resolvedLabelIds.holdId,
        true
      )
    ) {
      continue;
    }
    try {
      thread.removeLabel(label);
    } catch (error) {
      if (isRetryLaterQuotaError_(error)) {
        return { quota: true, holdCleared: false, releaseCleared: false };
      }
      holdFailed = true;
      Logger.log("Could not remove %s. error=%s", label.getName(), formatError_(error));
    }
  }
  if (holdFailed) {
    return { quota: false, holdCleared: false, releaseCleared: false };
  }
  let releaseFailed = false;
  for (let labelIndex = 0; labelIndex < labelsOnThread.length; labelIndex++) {
    const label = labelsOnThread[labelIndex];
    if (
      !labelMatches_(
        label.getName(),
        label.getId(),
        RELEASE_LABEL_NAME,
        resolvedLabelIds.releaseId,
        false
      )
    ) {
      continue;
    }
    try {
      thread.removeLabel(label);
    } catch (error) {
      if (isRetryLaterQuotaError_(error)) {
        return { quota: true, holdCleared: true, releaseCleared: false };
      }
      releaseFailed = true;
      Logger.log("Could not remove %s. error=%s", label.getName(), formatError_(error));
    }
  }
  return { quota: false, holdCleared: true, releaseCleared: !releaseFailed };
}

function draftClocksAllowSend_(
  sticky,
  draftId,
  ageMilliseconds,
  delayMilliseconds,
  nowMilliseconds
) {
  return (
    isOldEnoughToSend_(ageMilliseconds, delayMilliseconds) &&
    releaseDelayElapsed_(sticky, draftId, nowMilliseconds, delayMilliseconds)
  );
}

function listedAgeWaitsOnReleaseClock_(
  sticky,
  draftId,
  ageMilliseconds,
  delayMilliseconds,
  nowMilliseconds
) {
  return (
    isOldEnoughToSend_(ageMilliseconds, delayMilliseconds) &&
    !releaseDelayElapsed_(sticky, draftId, nowMilliseconds, delayMilliseconds)
  );
}

function releaseDelayElapsed_(sticky, draftId, nowMilliseconds, delayMilliseconds) {
  if (!sticky || !sticky.readable || sticky.overflowLatch) {
    return false;
  }
  if (!Object.prototype.hasOwnProperty.call(sticky.releasedAt, draftId)) {
    return true;
  }
  let releasedAt = sticky.releasedAt[draftId];
  if (typeof releasedAt !== "number" || !isFinite(releasedAt)) {
    return false;
  }
  if (releasedAt > nowMilliseconds) {
    releasedAt = nowMilliseconds;
  }
  return nowMilliseconds - releasedAt >= delayMilliseconds;
}

function unreadableStickyHoldState_() {
  return {
    held: {},
    releasedAt: {},
    releaseSeenOnce: {},
    absentPasses: {},
    unlistedFound: {},
    unreadPasses: {},
    keepReleasedAt: {},
    readable: false,
    overflowLatch: false,
    shardGeneration: "",
    originalSignature: null,
    needsRewrite: false,
    orphanShardKeys: [],
    shardKeys: {
      held: [],
      releasedAt: [],
      releaseSeenOnce: [],
      absentPasses: [],
      unlistedFound: [],
      unreadPasses: [],
    },
  };
}

function readStickyHoldState_(snapshot, nowMilliseconds) {
  const state = unreadableStickyHoldState_();
  state.readable = true;
  if (!snapshot) {
    state.readable = false;
    return state;
  }
  state.overflowLatch = snapshot[STICKY_OVERFLOW_PROPERTY] === "1";
  state.shardGeneration = snapshot[STICKY_SHARD_GENERATION_PROPERTY] || "";
  state.orphanShardKeys = collectOrphanShardKeys_(snapshot);
  const held = readShardedStickyMap_(snapshot, HELD_DRAFTS_PROPERTY, "hold");
  const releasedAt = readShardedStickyMap_(snapshot, RELEASED_AT_PROPERTY, "release");
  const releaseSeenOnce = readShardedStickyMap_(
    snapshot,
    RELEASE_SEEN_ONCE_PROPERTY,
    "seen"
  );
  const absentPasses = readShardedStickyMap_(snapshot, STICKY_ABSENT_PASSES_PROPERTY, "absent");
  const unlistedFound = readShardedStickyMap_(snapshot, STICKY_UNLISTED_FOUND_PROPERTY, "absent");
  const unreadPasses = readShardedStickyMap_(snapshot, STICKY_UNREAD_PASSES_PROPERTY, "absent");
  if (!held || !releasedAt || !releaseSeenOnce || !absentPasses || !unlistedFound || !unreadPasses) {
    state.readable = false;
    state.held = {};
    state.releasedAt = {};
    state.releaseSeenOnce = {};
    state.absentPasses = {};
    state.unlistedFound = {};
    state.unreadPasses = {};
    return state;
  }
  state.held = held.map;
  state.releasedAt = releasedAt.map;
  state.releaseSeenOnce = releaseSeenOnce.map;
  state.absentPasses = absentPasses.map;
  state.unlistedFound = unlistedFound.map;
  state.unreadPasses = unreadPasses.map;
  state.shardKeys = {
    held: held.keys,
    releasedAt: releasedAt.keys,
    releaseSeenOnce: releaseSeenOnce.keys,
    absentPasses: absentPasses.keys,
    unlistedFound: unlistedFound.keys,
    unreadPasses: unreadPasses.keys,
  };
  state.originalSignature = stickyCanonicalSignature_(state);
  state.needsRewrite = shardValuesExceedCap_(snapshot, state.shardKeys);
  normalizeReleasedAt_(state, nowMilliseconds);
  return state;
}

function shardValuesExceedCap_(snapshot, shardKeys) {
  const groups = [
    "held",
    "releasedAt",
    "releaseSeenOnce",
    "absentPasses",
    "unlistedFound",
    "unreadPasses",
  ];
  for (let groupIndex = 0; groupIndex < groups.length; groupIndex++) {
    const keys = shardKeys[groups[groupIndex]] || [];
    for (let keyIndex = 0; keyIndex < keys.length; keyIndex++) {
      const raw = snapshot[keys[keyIndex]];
      if (typeof raw === "string" && raw.length > STICKY_PROPERTY_CHAR_CAP) {
        return true;
      }
    }
  }
  return false;
}

function readShardedStickyMap_(snapshot, baseName, valueKind) {
  const keys = previousShardKeys_(snapshot, baseName);
  if (!keys) {
    Logger.log(
      "Could not parse sticky Hold state. Holding every draft this pass. property=%s",
      baseName
    );
    return null;
  }
  const map = {};
  for (let keyIndex = 0; keyIndex < keys.length; keyIndex++) {
    const parsed = parseStickyObject_(snapshot[keys[keyIndex]], keys[keyIndex]);
    if (!parsed) {
      return null;
    }
    for (const draftId in parsed) {
      if (!Object.prototype.hasOwnProperty.call(parsed, draftId)) {
        continue;
      }
      if (!stickyValueOk_(parsed[draftId], valueKind)) {
        Logger.log(
          "Could not parse sticky Hold state. Holding every draft this pass. property=%s",
          keys[keyIndex]
        );
        return null;
      }
      if (Object.prototype.hasOwnProperty.call(map, draftId)) {
        Logger.log(
          "Could not parse sticky Hold state. Holding every draft this pass. property=%s",
          keys[keyIndex]
        );
        return null;
      }
      map[draftId] = parsed[draftId];
    }
  }
  return { map: map, keys: keys };
}

function stickyValueOk_(value, valueKind) {
  if (valueKind === "release" || valueKind === "absent") {
    return typeof value === "number" && isFinite(value);
  }
  return typeof value === "string";
}

function collectOrphanShardKeys_(snapshot) {
  const bases = [
    HELD_DRAFTS_PROPERTY,
    RELEASED_AT_PROPERTY,
    RELEASE_SEEN_ONCE_PROPERTY,
    STICKY_ABSENT_PASSES_PROPERTY,
    STICKY_UNLISTED_FOUND_PROPERTY,
    STICKY_UNREAD_PASSES_PROPERTY,
  ];
  const generation = snapshot[STICKY_SHARD_GENERATION_PROPERTY] || "";
  const orphans = [];
  const seen = {};
  for (const key in snapshot) {
    if (!Object.prototype.hasOwnProperty.call(snapshot, key)) {
      continue;
    }
    for (let baseIndex = 0; baseIndex < bases.length; baseIndex++) {
      const parsed = parseStickyShardKey_(bases[baseIndex], key);
      if (!parsed || parsed.shardNumber === 1) {
        continue;
      }
      const active = generation ? parsed.generation === generation : parsed.generation === "";
      if (!active && !seen[key]) {
        seen[key] = true;
        orphans.push(key);
      }
    }
  }
  return orphans;
}

function deleteRememberedOrphanShards_(sticky) {
  const orphanKeys = sticky.orphanShardKeys || [];
  if (orphanKeys.length === 0) {
    return;
  }
  const ordered = orphanKeys.slice();
  ordered.sort(function sortDescending(left, right) {
    return stickyShardSortNumber_(right) - stickyShardSortNumber_(left);
  });
  try {
    const properties = PropertiesService.getScriptProperties();
    for (let keyIndex = 0; keyIndex < ordered.length; keyIndex++) {
      properties.deleteProperty(ordered[keyIndex]);
    }
    sticky.orphanShardKeys = [];
  } catch (error) {
    Logger.log("Could not delete an old sticky shard. error=%s", formatError_(error));
  }
}

function parseStickyShardKey_(baseName, key) {
  if (key === baseName) {
    return { shardNumber: 1, generation: "" };
  }
  const prefix = baseName + "Shard";
  if (key.indexOf(prefix) !== 0) {
    return null;
  }
  const rest = key.substring(prefix.length);
  const genMarker = rest.indexOf("Gen");
  const numberText = genMarker === -1 ? rest : rest.substring(0, genMarker);
  const generation = genMarker === -1 ? "" : rest.substring(genMarker + 3);
  const shardNumber = Number(numberText);
  if (!isFinite(shardNumber) || shardNumber < 2 || String(shardNumber) !== numberText) {
    return null;
  }
  if (generation !== "" && !/^[0-9]+$/.test(generation)) {
    return null;
  }
  return { shardNumber: shardNumber, generation: generation };
}

function previousShardKeys_(snapshot, baseName) {
  if (!snapshot) {
    return [];
  }
  const generation = snapshot[STICKY_SHARD_GENERATION_PROPERTY] || "";
  const found = [];
  for (const key in snapshot) {
    if (!Object.prototype.hasOwnProperty.call(snapshot, key)) {
      continue;
    }
    const parsed = parseStickyShardKey_(baseName, key);
    if (!parsed) {
      continue;
    }
    if (generation) {
      if (parsed.shardNumber !== 1 && parsed.generation !== generation) {
        continue;
      }
    } else if (parsed.generation) {
      continue;
    }
    found.push({ key: key, shardNumber: parsed.shardNumber });
  }
  found.sort(function sortShards(left, right) {
    return left.shardNumber - right.shardNumber;
  });
  if (found.length > STICKY_MAX_SHARDS) {
    return null;
  }
  let expected = 1;
  for (let index = 0; index < found.length; index++) {
    if (found[index].shardNumber !== expected) {
      return null;
    }
    expected += 1;
  }
  const keys = [];
  for (let index = 0; index < found.length; index++) {
    keys.push(found[index].key);
  }
  return keys;
}

// Empty and missing values are an empty map. A bad value is null, which
// means do not send and do not overwrite the stored property.
function parseStickyObject_(raw, propertyName) {
  if (raw === null || raw === undefined || raw === "") {
    return {};
  }
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || typeof parsed.length === "number") {
      Logger.log(
        "Could not parse sticky Hold state. Holding every draft this pass. property=%s",
        propertyName
      );
      return null;
    }
    return parsed;
  } catch (error) {
    Logger.log(
      "Could not parse sticky Hold state. Holding every draft this pass. property=%s error=%s",
      propertyName,
      formatError_(error)
    );
    return null;
  }
}

function normalizeReleasedAt_(sticky, nowMilliseconds) {
  for (const draftId in sticky.releasedAt) {
    if (!Object.prototype.hasOwnProperty.call(sticky.releasedAt, draftId)) {
      continue;
    }
    if (sticky.releasedAt[draftId] > nowMilliseconds) {
      sticky.releasedAt[draftId] = nowMilliseconds;
    }
  }
}

function pruneElapsedReleases_(sticky, nowMilliseconds, delayMilliseconds) {
  const staleIds = [];
  for (const draftId in sticky.releasedAt) {
    if (!Object.prototype.hasOwnProperty.call(sticky.releasedAt, draftId)) {
      continue;
    }
    const releasedAt = sticky.releasedAt[draftId];
    if (typeof releasedAt !== "number" || !isFinite(releasedAt)) {
      continue;
    }
    if (sticky.keepReleasedAt && sticky.keepReleasedAt[draftId]) {
      continue;
    }
    if (
      nowMilliseconds - releasedAt >=
      delayMilliseconds + RELEASED_AT_PRUNE_MARGIN_MILLISECONDS
    ) {
      staleIds.push(draftId);
    }
  }
  for (let staleIndex = 0; staleIndex < staleIds.length; staleIndex++) {
    delete sticky.releasedAt[staleIds[staleIndex]];
  }
}

function pruneStickyDrafts_(sticky, liveIds, listComplete, passFlags, nowMilliseconds) {
  if (!sticky.readable || !listComplete || (passFlags && passFlags.quota)) {
    return;
  }
  const candidateIds = [];
  collectMissingIds_(sticky.held, liveIds, candidateIds);
  collectMissingIds_(sticky.releasedAt, liveIds, candidateIds);
  collectMissingIds_(sticky.releaseSeenOnce, liveIds, candidateIds);
  collectMissingIds_(sticky.absentPasses, liveIds, candidateIds);
  collectMissingIds_(sticky.unlistedFound, liveIds, candidateIds);
  for (let candidateIndex = 0; candidateIndex < candidateIds.length; candidateIndex++) {
    if (passFlags && passFlags.quota) {
      return;
    }
    const draftId = candidateIds[candidateIndex];
    const cooldownUntil = sticky.unlistedFound[draftId];
    if (
      typeof cooldownUntil === "number" &&
      cooldownUntil >= UNLISTED_COOLDOWN_SENTINEL &&
      nowMilliseconds < cooldownUntil
    ) {
      continue;
    }
    let found = false;
    let missing = false;
    try {
      GmailApp.getDraft(draftId);
      found = true;
    } catch (error) {
      if (isRetryLaterQuotaError_(error)) {
        if (passFlags) {
          passFlags.quota = true;
        }
        return;
      }
      if (isMissingDraftError_(error)) {
        missing = true;
      }
    }
    if (missing) {
      sticky.absentPasses[draftId] = (sticky.absentPasses[draftId] || 0) + 1;
      delete sticky.unlistedFound[draftId];
      if (sticky.absentPasses[draftId] >= MISSING_DRAFT_CONFIRMS_BEFORE_PRUNE) {
        delete sticky.held[draftId];
        delete sticky.releasedAt[draftId];
        delete sticky.releaseSeenOnce[draftId];
        delete sticky.absentPasses[draftId];
        delete sticky.unlistedFound[draftId];
        delete sticky.unreadPasses[draftId];
      }
      continue;
    }
    delete sticky.absentPasses[draftId];
    if (!found) {
      continue;
    }
    const previous = sticky.unlistedFound[draftId];
    const alreadyCooling = typeof previous === "number" && previous >= UNLISTED_COOLDOWN_SENTINEL;
    const seenCount = alreadyCooling ? UNLISTED_FOUND_PASSES_BEFORE_COOLDOWN : previous || 0;
    if (seenCount + 1 >= UNLISTED_FOUND_PASSES_BEFORE_COOLDOWN) {
      sticky.unlistedFound[draftId] = nowMilliseconds + UNLISTED_RECHECK_MILLISECONDS;
      if (!alreadyCooling && passFlags) {
        passFlags.alertUnlisted = true;
      }
    } else {
      sticky.unlistedFound[draftId] = seenCount + 1;
    }
  }
  const livePresent = [];
  for (const draftId in sticky.absentPasses) {
    if (Object.prototype.hasOwnProperty.call(sticky.absentPasses, draftId) && liveIds[draftId]) {
      livePresent.push(draftId);
    }
  }
  for (let liveIndex = 0; liveIndex < livePresent.length; liveIndex++) {
    delete sticky.absentPasses[livePresent[liveIndex]];
    delete sticky.unlistedFound[livePresent[liveIndex]];
  }
  const listedAgain = [];
  for (const draftId in sticky.unlistedFound) {
    if (Object.prototype.hasOwnProperty.call(sticky.unlistedFound, draftId) && liveIds[draftId]) {
      listedAgain.push(draftId);
    }
  }
  for (let listedIndex = 0; listedIndex < listedAgain.length; listedIndex++) {
    delete sticky.unlistedFound[listedAgain[listedIndex]];
  }
}

function collectMissingIds_(map, liveIds, candidateIds) {
  for (const draftId in map) {
    if (!Object.prototype.hasOwnProperty.call(map, draftId)) {
      continue;
    }
    if (!liveIds[draftId] && candidateIds.indexOf(draftId) === -1) {
      candidateIds.push(draftId);
    }
  }
}

function persistStickyHoldState_(sticky, nowMilliseconds, delayMilliseconds) {
  if (!sticky || !sticky.readable) {
    return { ok: false, skipped: true };
  }
  pruneElapsedReleases_(sticky, nowMilliseconds, delayMilliseconds);
  normalizeReleasedAt_(sticky, nowMilliseconds);
  const heldChunks = chunkStickyMap_(sticky.held);
  const releasedChunks = chunkStickyMap_(sticky.releasedAt);
  const seenChunks = chunkStickyMap_(sticky.releaseSeenOnce);
  const absentChunks = chunkStickyMap_(sticky.absentPasses);
  const unlistedChunks = chunkStickyMap_(sticky.unlistedFound);
  const unreadChunks = chunkStickyMap_(sticky.unreadPasses);
  if (
    !heldChunks ||
    !releasedChunks ||
    !seenChunks ||
    !absentChunks ||
    !unlistedChunks ||
    !unreadChunks
  ) {
    return markStickyOverflow_(sticky);
  }
  const nextGeneration = String((Number(sticky.shardGeneration) || 0) + 1);
  const batch = {};
  const usedKeys = {};
  const totalChars =
    assignStickyChunks_(
      batch,
      usedKeys,
      HELD_DRAFTS_PROPERTY,
      heldChunks,
      nextGeneration,
      sticky.shardKeys.held
    ) +
    assignStickyChunks_(
      batch,
      usedKeys,
      RELEASED_AT_PROPERTY,
      releasedChunks,
      nextGeneration,
      sticky.shardKeys.releasedAt
    ) +
    assignStickyChunks_(
      batch,
      usedKeys,
      RELEASE_SEEN_ONCE_PROPERTY,
      seenChunks,
      nextGeneration,
      sticky.shardKeys.releaseSeenOnce
    ) +
    assignStickyChunks_(
      batch,
      usedKeys,
      STICKY_ABSENT_PASSES_PROPERTY,
      absentChunks,
      nextGeneration,
      sticky.shardKeys.absentPasses
    ) +
    assignStickyChunks_(
      batch,
      usedKeys,
      STICKY_UNLISTED_FOUND_PROPERTY,
      unlistedChunks,
      nextGeneration,
      sticky.shardKeys.unlistedFound
    ) +
    assignStickyChunks_(
      batch,
      usedKeys,
      STICKY_UNREAD_PASSES_PROPERTY,
      unreadChunks,
      nextGeneration,
      sticky.shardKeys.unreadPasses
    );
  if (mapHasAnyKey_(batch) || sticky.shardGeneration) {
    batch[STICKY_SHARD_GENERATION_PROPERTY] = nextGeneration;
  }
  if (totalChars > STICKY_TOTAL_CHAR_CAP) {
    return markStickyOverflow_(sticky);
  }
  const signature = stickyCanonicalSignature_(sticky);
  if (
    signature === sticky.originalSignature &&
    !sticky.overflowLatch &&
    !sticky.needsRewrite
  ) {
    deleteRememberedOrphanShards_(sticky);
    return { ok: true, unchanged: true };
  }
  try {
    const properties = PropertiesService.getScriptProperties();
    if (mapHasAnyKey_(batch)) {
      properties.setProperties(batch, false);
    }
    deleteUnusedStickyKeys_(properties, sticky.shardKeys, usedKeys);
    deleteRememberedOrphanShards_(sticky);
    if (sticky.overflowLatch) {
      properties.deleteProperty(STICKY_OVERFLOW_PROPERTY);
    }
    sticky.originalSignature = signature;
    sticky.overflowLatch = false;
    sticky.needsRewrite = false;
    sticky.shardGeneration = batch[STICKY_SHARD_GENERATION_PROPERTY] || sticky.shardGeneration;
    sticky.shardKeys = shardKeysFromUsed_(usedKeys);
    return { ok: true };
  } catch (error) {
    Logger.log("Could not store sticky Hold state. error=%s", formatError_(error));
    return { ok: false, error: error };
  }
}

function markStickyOverflow_(sticky) {
  try {
    PropertiesService.getScriptProperties().setProperty(STICKY_OVERFLOW_PROPERTY, "1");
    sticky.overflowLatch = true;
  } catch (error) {
    Logger.log("Could not store sticky Hold overflow latch. error=%s", formatError_(error));
    return { ok: false, overflow: true, error: error };
  }
  return { ok: false, overflow: true };
}

function assignStickyChunks_(batch, usedKeys, baseName, chunks, generation, previousKeys) {
  if (!chunks || chunks.length === 0) {
    const keys = previousKeys || [];
    let hadBase = false;
    for (let keyIndex = 0; keyIndex < keys.length; keyIndex++) {
      if (keys[keyIndex] === baseName) {
        hadBase = true;
      }
    }
    if (!hadBase) {
      return 0;
    }
    batch[baseName] = "{}";
    usedKeys[baseName] = baseName;
    return 2;
  }
  let totalChars = 0;
  for (let chunkIndex = 0; chunkIndex < chunks.length; chunkIndex++) {
    const key =
      chunkIndex === 0
        ? baseName
        : baseName + "Shard" + String(chunkIndex + 1) + "Gen" + generation;
    const encoded = JSON.stringify(chunks[chunkIndex]);
    batch[key] = encoded;
    usedKeys[key] = baseName;
    totalChars += encoded.length;
  }
  return totalChars;
}

function deleteUnusedStickyKeys_(properties, previousKeys, usedKeys) {
  const groups = [
    "held",
    "releasedAt",
    "releaseSeenOnce",
    "absentPasses",
    "unlistedFound",
    "unreadPasses",
  ];
  const doomed = [];
  for (let groupIndex = 0; groupIndex < groups.length; groupIndex++) {
    const keys = previousKeys[groups[groupIndex]] || [];
    for (let keyIndex = 0; keyIndex < keys.length; keyIndex++) {
      if (!Object.prototype.hasOwnProperty.call(usedKeys, keys[keyIndex])) {
        doomed.push(keys[keyIndex]);
      }
    }
  }
  doomed.sort(function sortDescending(left, right) {
    const leftShard = stickyShardSortNumber_(left);
    const rightShard = stickyShardSortNumber_(right);
    return rightShard - leftShard;
  });
  for (let doomedIndex = 0; doomedIndex < doomed.length; doomedIndex++) {
    properties.deleteProperty(doomed[doomedIndex]);
  }
}

function stickyShardSortNumber_(key) {
  const marker = key.indexOf("Shard");
  if (marker === -1) {
    return 1;
  }
  const rest = key.substring(marker + 5);
  const genMarker = rest.indexOf("Gen");
  const numberText = genMarker === -1 ? rest : rest.substring(0, genMarker);
  const shardNumber = Number(numberText);
  return isFinite(shardNumber) ? shardNumber : 0;
}

function shardKeysFromUsed_(usedKeys) {
  const shardKeys = {
    held: [],
    releasedAt: [],
    releaseSeenOnce: [],
    absentPasses: [],
    unlistedFound: [],
    unreadPasses: [],
  };
  const baseToGroup = {};
  baseToGroup[HELD_DRAFTS_PROPERTY] = "held";
  baseToGroup[RELEASED_AT_PROPERTY] = "releasedAt";
  baseToGroup[RELEASE_SEEN_ONCE_PROPERTY] = "releaseSeenOnce";
  baseToGroup[STICKY_ABSENT_PASSES_PROPERTY] = "absentPasses";
  baseToGroup[STICKY_UNLISTED_FOUND_PROPERTY] = "unlistedFound";
  baseToGroup[STICKY_UNREAD_PASSES_PROPERTY] = "unreadPasses";
  for (const key in usedKeys) {
    if (!Object.prototype.hasOwnProperty.call(usedKeys, key)) {
      continue;
    }
    const group = baseToGroup[usedKeys[key]];
    if (group) {
      shardKeys[group].push(key);
    }
  }
  return shardKeys;
}

function chunkStickyMap_(map) {
  const keys = sortedMapKeys_(map);
  const chunks = [];
  let current = {};
  for (let keyIndex = 0; keyIndex < keys.length; keyIndex++) {
    current[keys[keyIndex]] = map[keys[keyIndex]];
    if (JSON.stringify(current).length <= STICKY_PROPERTY_CHAR_CAP) {
      continue;
    }
    delete current[keys[keyIndex]];
    if (!mapHasAnyKey_(current)) {
      return null;
    }
    chunks.push(current);
    current = {};
    current[keys[keyIndex]] = map[keys[keyIndex]];
    if (JSON.stringify(current).length > STICKY_PROPERTY_CHAR_CAP) {
      return null;
    }
  }
  if (mapHasAnyKey_(current)) {
    chunks.push(current);
  }
  if (chunks.length > STICKY_MAX_SHARDS) {
    return null;
  }
  return chunks;
}

function stickyCanonicalSignature_(sticky) {
  return [
    canonicalStickyJson_(sticky.held),
    canonicalStickyJson_(sticky.releasedAt),
    canonicalStickyJson_(sticky.releaseSeenOnce),
    canonicalStickyJson_(sticky.absentPasses),
    canonicalStickyJson_(sticky.unlistedFound),
    canonicalStickyJson_(sticky.unreadPasses),
  ].join("\n");
}

function canonicalStickyJson_(map) {
  if (!map || !mapHasAnyKey_(map)) {
    return "";
  }
  const keys = sortedMapKeys_(map);
  const ordered = {};
  for (let keyIndex = 0; keyIndex < keys.length; keyIndex++) {
    ordered[keys[keyIndex]] = map[keys[keyIndex]];
  }
  return JSON.stringify(ordered);
}

function sortedMapKeys_(map) {
  const keys = [];
  for (const key in map) {
    if (Object.prototype.hasOwnProperty.call(map, key)) {
      keys.push(key);
    }
  }
  keys.sort();
  return keys;
}

function clearStickyDraft_(sticky, draftId) {
  if (!sticky || !sticky.readable || draftId === "unavailable") {
    return;
  }
  delete sticky.held[draftId];
  delete sticky.releasedAt[draftId];
  delete sticky.releaseSeenOnce[draftId];
  delete sticky.absentPasses[draftId];
  delete sticky.unlistedFound[draftId];
  delete sticky.unreadPasses[draftId];
}

// The send error is the failure to log. A subject read must not replace it.
function subjectForLog_(snapshot) {
  if (typeof snapshot.subject === "string") {
    return snapshot.subject;
  }
  try {
    return snapshot.message.getSubject();
  } catch (error) {
    return "";
  }
}

function formatError_(error) {
  if (!error) {
    return "unknown error";
  }
  if (error.stack) {
    return String(error.stack);
  }
  return String(error);
}
