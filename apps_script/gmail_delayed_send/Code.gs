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
 * Once a pass has seen Hold, the script stores draft id to message id in
 * delayedSendHeldDrafts. The draft id stays across an edit. The message
 * id does not. Gmail API drafts.update replaces the message and the new
 * message carries no user labels, so a standalone draft loses Hold.
 * If Hold is gone and the message id changed, the edit dropped it: put
 * Hold back, remember the new message id, and skip. If Hold is gone and
 * the message id is the same, a person removed it: forget the held entry
 * and start the release clock. A Release label always wins over Hold.
 * The draft sends only when the message is DELAY_MINUTES old and the
 * release clock is unset or also DELAY_MINUTES old. If putting Hold back
 * throws, keep the held entry and try again next pass. Do not mark that
 * Send failed. When the sticky state cannot be read, hold rather than send.
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
 * A draft message cannot carry a user label. Hold, Release, and Send
 * failed are thread labels. Every draft on that thread shares them.
 * If any remembered draft on a thread changed message id while Hold is
 * gone, the other drafts on that thread stay held too. The label is
 * shared, so a removed label and an edit that stripped it look the same.
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
const RELEASE_LABEL_NAME = "Release";
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
const RELEASE_LABEL_ID_PROPERTY = "delayedSendReleaseLabelId";
const SEND_FAILED_LABEL_ID_PROPERTY = "delayedSendSendFailedLabelId";
// Map of draft id to the message id last seen while the thread had Hold.
const HELD_DRAFTS_PROPERTY = "delayedSendHeldDrafts";
// Map of draft id to the epoch ms when Hold came off or Release was seen.
const RELEASED_AT_PROPERTY = "delayedSendReleasedAt";
// Script properties allow 9KB per value. Stay under that for these maps.
const STICKY_PROPERTY_CHAR_CAP = 7000;
// Stored when Hold must be restored and this pass has no prior message id.
// It matches no Gmail message id, so the next pass tries the restore again.
const STICKY_HOLD_PENDING_MESSAGE_ID = "pending-hold-restore";
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
 * Creates the Hold, Release, and Send failed labels when missing and
 * installs one time trigger. Running this again deletes duplicate
 * triggers for the current handler and for the older opt-in handler first.
 * "Send in 5" is not created.
 */
function installDelayedGmailSend() {
  assertDelayedSendConfigured_();
  const holdLabel = getOrCreateLabel_(HOLD_LABEL_NAME);
  const releaseLabel = getOrCreateLabel_(RELEASE_LABEL_NAME);
  const failedLabel = getOrCreateLabel_(SEND_FAILED_LABEL_NAME);
  storeLabelId_(HOLD_LABEL_ID_PROPERTY, holdLabel);
  storeLabelId_(RELEASE_LABEL_ID_PROPERTY, releaseLabel);
  storeLabelId_(SEND_FAILED_LABEL_ID_PROPERTY, failedLabel);
  const removedTriggerCount = deleteDelayedSendTriggers_();
  ScriptApp.newTrigger(sendDraftsAfterDelay.name)
    .timeBased()
    .everyMinutes(TRIGGER_INTERVAL_MINUTES)
    .create();
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
function sendDraftsAfterDelay() {
  assertDelayedSendConfigured_();
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
  const sticky = readStickyHoldState_();

  let drafts;
  try {
    drafts = GmailApp.getDrafts();
  } catch (error) {
    if (isRetryLaterQuotaError_(error)) {
      finishRetryLaterQuota_(error);
      return;
    }
    throw error;
  }
  const liveDraftIds = liveDraftIdsFromList_(drafts);
  if (drafts.length === 0) {
    clearPersistentFailureLatch_();
    finishStickyHoldPass_(sticky, liveDraftIds);
    return;
  }

  const eligibleDrafts = [];
  const draftViews = [];
  const threadLabelStateByThreadId = {};
  const skippedSendFailedDraftIds = [];
  const labelIds = rememberedLabelIds_();
  let eligibleCount = 0;
  let sentCount = 0;
  let waitingCount = 0;
  let failedCount = 0;
  let canceledCount = 0;
  let retryLaterQuotaReached = false;

  for (let draftIndex = 0; draftIndex < drafts.length; draftIndex++) {
    const draft = drafts[draftIndex];
    let draftId = "unavailable";
    try {
      draftId = draft.getId();
      draftViews.push(
        readDraftView_(draft, draftId, threadLabelStateByThreadId, labelIds)
      );
    } catch (error) {
      if (isMissingDraftError_(error)) {
        if (draftId !== "unavailable") {
          clearStickyDraft_(sticky, draftId);
        }
        canceledCount++;
        Logger.log(DRAFT_DELETED_BEFORE_SEND_LOG_TEMPLATE, draftId);
        continue;
      }
      logDraftProblem_("Delayed send will retry this draft. id=%s error=%s", draftId, error);
      if (isRetryLaterQuotaError_(error)) {
        failedCount++;
        retryLaterQuotaReached = true;
        Logger.log(QUOTA_REMAINING_DRAFTS_LOG_MESSAGE);
        break;
      }
    }
  }

  applyStickyHoldForPass_(draftViews, sticky, labelIds, passStartedAtMilliseconds);

  for (let viewIndex = 0; viewIndex < draftViews.length; viewIndex++) {
    const view = draftViews[viewIndex];
    if (view.labelState.sendFailed) {
      skippedSendFailedDraftIds.push(view.draftId);
      continue;
    }
    if (view.decision === "hold") {
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
    if (retryLaterQuotaReached) {
      break;
    }
    const snapshot = eligibleDrafts[eligibleIndex];
    try {
      const result = sendDraftIfOldEnough_(
        snapshot,
        delayMilliseconds,
        passStartedAtMilliseconds,
        labelIds,
        sticky
      );
      snapshot.outcome = result.outcome;
      snapshot.sentMessage = result.sentMessage || null;
      if (result.outcome === "sent" || result.outcome === "canceled") {
        clearStickyDraft_(sticky, snapshot.draftId);
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
        clearStickyDraft_(sticky, snapshot.draftId);
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
        retryLaterQuotaReached = true;
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

  settleThreadLabels_(eligibleDrafts);
  logSendFailedSkipsOnce_(skippedSendFailedDraftIds);
  finishStickyHoldPass_(sticky, liveDraftIds);

  if (eligibleCount === 0 && failedCount === 0 && canceledCount === 0) {
    clearPersistentFailureLatch_();
    return;
  }
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
  if (retryLaterQuotaReached) {
    throwPersistentFailureAtMostOncePerHour_(QUOTA_DRAFTS_LEFT_UNSENT_THROW_MESSAGE);
    return;
  }
  clearPersistentFailureLatch_();
}

function finishRetryLaterQuota_(error) {
  Logger.log("Gmail quota reached before any draft was sent. error=%s", formatError_(error));
  throwPersistentFailureAtMostOncePerHour_(QUOTA_DRAFTS_LEFT_UNSENT_THROW_MESSAGE);
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
    if (labelMatches_(name, labelId, HOLD_LABEL_NAME, resolvedLabelIds.holdId)) {
      state.hold = true;
    }
    if (labelMatches_(name, labelId, RELEASE_LABEL_NAME, resolvedLabelIds.releaseId)) {
      state.release = true;
    }
    if (labelMatches_(name, labelId, SEND_FAILED_LABEL_NAME, resolvedLabelIds.sendFailedId)) {
      state.sendFailed = true;
    }
  }
  return state;
}

function labelMatches_(name, labelId, expectedName, storedId) {
  if (name === expectedName) {
    return true;
  }
  return Boolean(storedId) && labelId === storedId;
}

function sendDraftIfOldEnough_(
  snapshot,
  delayMilliseconds,
  passStartedAtMilliseconds,
  labelIds,
  sticky
) {
  const draftId = snapshot.draftId;
  const listedMessage = snapshot.message;
  const listedMessageId = listedMessage.getId();
  const interruptedResult = handleInterruptedSend_(draftId, listedMessageId, passStartedAtMilliseconds);
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

  // Re-read before send so a save, Hold, Release, or Send failed during
  // this run still resets or cancels. GmailApp can serve a stale message
  // from the earlier getDrafts() result. A sticky Hold entry also blocks
  // the send when the fresh thread no longer shows Hold.
  let freshDraft;
  try {
    freshDraft = GmailApp.getDraft(draftId);
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
  const freshMessage = freshDraft.getMessage();
  let freshState;
  try {
    freshState = readThreadLabelState_(freshMessage.getThread(), labelIds);
  } catch (error) {
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
  const freshMessageId = freshDraft.getMessageId();
  if (freshMessageId !== listedMessageId) {
    clearFailedSendRecord_(draftId);
    clearInFlightIfDraft_(draftId);
  }
  const freshThread = freshMessage.getThread();
  if (
    preSendStickySaysHold_(
      sticky,
      draftId,
      freshMessageId,
      freshState,
      freshThread,
      labelIds,
      passStartedAtMilliseconds
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
  writeInFlight_(draftId, freshMessageId);
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

function settleThreadLabels_(eligibleDrafts) {
  const threadIds = [];
  for (let draftIndex = 0; draftIndex < eligibleDrafts.length; draftIndex++) {
    const threadId = eligibleDrafts[draftIndex].threadId;
    if (threadIds.indexOf(threadId) === -1) {
      threadIds.push(threadId);
    }
  }
  for (let threadIndex = 0; threadIndex < threadIds.length; threadIndex++) {
    settleOneThread_(eligibleDrafts, threadIds[threadIndex]);
  }
}

function settleOneThread_(eligibleDrafts, threadId) {
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
      failedThread = markDraftSendFailed_(failedRecord.draft, failedRecord.draftId);
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

/**
 * Applies Send failed. Returns the thread when the label is on the thread
 * after this call, including when it was already there. Returns null when
 * the thread could not be read or the label could not be applied. A null
 * return leaves the draft eligible, so a later run tries again.
 */
function markDraftSendFailed_(draft, draftId) {
  let thread;
  try {
    thread = draft.getMessage().getThread();
  } catch (error) {
    logDraftProblem_("Could not mark draft send failed. id=%s error=%s", draftId, error);
    return null;
  }
  if (threadHasLabelName_(thread, SEND_FAILED_LABEL_NAME)) {
    return thread;
  }
  try {
    const failedLabel = getOrCreateLabel_(SEND_FAILED_LABEL_NAME);
    thread.addLabel(failedLabel);
    Logger.log(
      "Marked draft send failed. id=%s appliedLabel=%s",
      draftId,
      SEND_FAILED_LABEL_NAME
    );
  } catch (error) {
    logDraftProblem_("Could not apply the failure label. id=%s error=%s", draftId, error);
    return null;
  }
  return thread;
}

function threadHasLabelName_(thread, labelName) {
  const labelsOnThread = thread.getLabels();
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

function throwPersistentFailureAtMostOncePerHour_(message) {
  let alreadyLatchedThisHour = false;
  try {
    const properties = PropertiesService.getScriptProperties();
    const stored = properties.getProperty(PERSISTENT_FAILURE_LATCH_PROPERTY);
    const latchedAtMilliseconds = stored === null ? NaN : Number(stored);
    const nowMilliseconds = Date.now();
    if (
      isFinite(latchedAtMilliseconds) &&
      nowMilliseconds - latchedAtMilliseconds < PERSISTENT_FAILURE_THROW_INTERVAL_MILLISECONDS
    ) {
      alreadyLatchedThisHour = true;
    } else {
      properties.setProperty(PERSISTENT_FAILURE_LATCH_PROPERTY, String(nowMilliseconds));
    }
  } catch (error) {
    logPersistentFailureLatchProblem_("update", error);
  }
  if (alreadyLatchedThisHour) {
    Logger.log("Persistent delayed-send failure. Not throwing again this hour. %s", message);
    return;
  }
  throw new Error(message);
}

function clearPersistentFailureLatch_() {
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

function rememberedLabelIds_() {
  const labelIds = { holdId: null, sendFailedId: null, releaseId: null };
  let properties;
  try {
    properties = PropertiesService.getScriptProperties();
    labelIds.holdId = properties.getProperty(HOLD_LABEL_ID_PROPERTY);
    labelIds.releaseId = properties.getProperty(RELEASE_LABEL_ID_PROPERTY);
    labelIds.sendFailedId = properties.getProperty(SEND_FAILED_LABEL_ID_PROPERTY);
  } catch (error) {
    Logger.log(
      "Could not read stored label ids. Matching by name only. error=%s",
      formatError_(error)
    );
    return labelIds;
  }
  if (!labelIds.holdId) {
    labelIds.holdId = lookupAndStoreLabelId_(properties, HOLD_LABEL_NAME, HOLD_LABEL_ID_PROPERTY);
  }
  if (!labelIds.releaseId) {
    labelIds.releaseId = lookupAndStoreLabelId_(
      properties,
      RELEASE_LABEL_NAME,
      RELEASE_LABEL_ID_PROPERTY
    );
  }
  if (!labelIds.sendFailedId) {
    labelIds.sendFailedId = lookupAndStoreLabelId_(
      properties,
      SEND_FAILED_LABEL_NAME,
      SEND_FAILED_LABEL_ID_PROPERTY
    );
  }
  return labelIds;
}

function lookupAndStoreLabelId_(properties, labelName, propertyName) {
  try {
    const label = GmailApp.getUserLabelByName(labelName);
    if (!label) {
      return null;
    }
    const labelId = label.getId();
    if (typeof labelId !== "string" || labelId === "") {
      return null;
    }
    try {
      properties.setProperty(propertyName, labelId);
    } catch (error) {
      Logger.log("Could not store label id. label=%s error=%s", labelName, formatError_(error));
    }
    return labelId;
  } catch (error) {
    Logger.log(
      "Could not look up label id. Matching by name only. label=%s error=%s",
      labelName,
      formatError_(error)
    );
    return null;
  }
}

function handleInterruptedSend_(draftId, listedMessageId, passStartedAtMilliseconds) {
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
  const failedThread = markDraftSendFailed_(freshDraft, draftId);
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
  } catch (error) {
    Logger.log(
      "Could not store the in-flight send record. id=%s error=%s",
      draftId,
      formatError_(error)
    );
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

function applyStickyHoldForPass_(views, sticky, labelIds, nowMilliseconds) {
  if (!sticky.readable) {
    Logger.log("Could not read sticky Hold state. Holding every draft this pass.");
    for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
      views[viewIndex].decision = "hold";
    }
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
      nowMilliseconds
    );
  }
}

function applyStickyHoldForThread_(views, sticky, labelIds, nowMilliseconds) {
  const labelState = views[0].labelState;
  const thread = views[0].thread;
  if (labelState.release) {
    for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
      delete sticky.held[views[viewIndex].draftId];
      sticky.releasedAt[views[viewIndex].draftId] = nowMilliseconds;
      views[viewIndex].decision = "release";
      Logger.log("Release label wins. id=%s", views[viewIndex].draftId);
    }
    removeReleaseAndHoldLabels_(thread, labelIds);
    labelState.hold = false;
    labelState.release = false;
    return;
  }
  if (labelState.hold) {
    for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
      sticky.held[views[viewIndex].draftId] = views[viewIndex].messageId;
      delete sticky.releasedAt[views[viewIndex].draftId];
      views[viewIndex].decision = "hold";
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
      break;
    }
  }
  if (editDroppedHold) {
    const restored = restoreHoldLabel_(thread);
    for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
      keepThreadHeldAfterEdit_(views[viewIndex], sticky, restored);
    }
    if (restored) {
      labelState.hold = true;
    }
    return;
  }
  for (let viewIndex = 0; viewIndex < views.length; viewIndex++) {
    const view = views[viewIndex];
    if (!Object.prototype.hasOwnProperty.call(sticky.held, view.draftId)) {
      view.decision = "open";
      continue;
    }
    delete sticky.held[view.draftId];
    sticky.releasedAt[view.draftId] = nowMilliseconds;
    view.decision = "release";
    Logger.log("Hold removed. Release clock started. id=%s", view.draftId);
  }
}

function keepThreadHeldAfterEdit_(view, sticky, restored) {
  view.decision = "hold";
  delete sticky.releasedAt[view.draftId];
  const tracked = Object.prototype.hasOwnProperty.call(sticky.held, view.draftId);
  const messageChanged = tracked && sticky.held[view.draftId] !== view.messageId;
  if (restored) {
    sticky.held[view.draftId] = view.messageId;
    if (messageChanged) {
      Logger.log("Re-applied Hold after an edit dropped it. id=%s", view.draftId);
    }
    return;
  }
  if (messageChanged) {
    Logger.log("Could not re-apply Hold. Staying held. id=%s", view.draftId);
    return;
  }
  if (!tracked) {
    sticky.held[view.draftId] = STICKY_HOLD_PENDING_MESSAGE_ID;
    Logger.log("Could not re-apply Hold. Staying held. id=%s", view.draftId);
  }
}

function preSendStickySaysHold_(
  sticky,
  draftId,
  freshMessageId,
  freshState,
  thread,
  labelIds,
  nowMilliseconds
) {
  if (!sticky || !sticky.readable) {
    Logger.log("Could not read sticky Hold state. Holding draft. id=%s", draftId);
    return true;
  }
  if (freshState.release) {
    delete sticky.held[draftId];
    sticky.releasedAt[draftId] = nowMilliseconds;
    removeReleaseAndHoldLabels_(thread, labelIds);
    freshState.hold = false;
    freshState.release = false;
    Logger.log("Release label wins. id=%s", draftId);
    return false;
  }
  const tracked = Object.prototype.hasOwnProperty.call(sticky.held, draftId);
  if (!freshState.hold && !tracked) {
    return false;
  }
  if (!freshState.hold) {
    const restored = restoreHoldLabel_(thread);
    if (restored) {
      sticky.held[draftId] = freshMessageId;
      Logger.log("Re-applied Hold after an edit dropped it. id=%s", draftId);
    } else {
      Logger.log("Could not re-apply Hold. Staying held. id=%s", draftId);
    }
    delete sticky.releasedAt[draftId];
    return true;
  }
  sticky.held[draftId] = freshMessageId;
  delete sticky.releasedAt[draftId];
  if (!tracked) {
    Logger.log("Draft gained Hold before send. id=%s", draftId);
  } else {
    Logger.log("Holding draft. id=%s", draftId);
  }
  return true;
}

function restoreHoldLabel_(thread) {
  try {
    const holdLabel = getOrCreateLabel_(HOLD_LABEL_NAME);
    thread.addLabel(holdLabel);
    return true;
  } catch (error) {
    Logger.log("Could not re-apply Hold. error=%s", formatError_(error));
    return false;
  }
}

function removeReleaseAndHoldLabels_(thread, labelIds) {
  let labelsOnThread;
  try {
    labelsOnThread = thread.getLabels();
  } catch (error) {
    Logger.log("Could not read labels to clear Release. error=%s", formatError_(error));
    return;
  }
  const resolvedLabelIds = labelIds || { holdId: null, releaseId: null };
  for (let labelIndex = 0; labelIndex < labelsOnThread.length; labelIndex++) {
    const label = labelsOnThread[labelIndex];
    const name = label.getName();
    const labelId = label.getId();
    const shouldRemove =
      labelMatches_(name, labelId, RELEASE_LABEL_NAME, resolvedLabelIds.releaseId) ||
      labelMatches_(name, labelId, HOLD_LABEL_NAME, resolvedLabelIds.holdId);
    if (!shouldRemove) {
      continue;
    }
    try {
      thread.removeLabel(label);
    } catch (error) {
      Logger.log("Could not remove %s. error=%s", name, formatError_(error));
    }
  }
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
  if (!sticky || !sticky.readable) {
    return false;
  }
  if (!Object.prototype.hasOwnProperty.call(sticky.releasedAt, draftId)) {
    return true;
  }
  const releasedAt = sticky.releasedAt[draftId];
  if (typeof releasedAt !== "number" || !isFinite(releasedAt)) {
    return false;
  }
  return nowMilliseconds - releasedAt >= delayMilliseconds;
}

function readStickyHoldState_() {
  const state = {
    held: {},
    releasedAt: {},
    readable: true,
    originalHeldJson: null,
    originalReleasedJson: null,
  };
  try {
    const properties = PropertiesService.getScriptProperties();
    state.originalHeldJson = properties.getProperty(HELD_DRAFTS_PROPERTY);
    state.originalReleasedJson = properties.getProperty(RELEASED_AT_PROPERTY);
  } catch (error) {
    state.readable = false;
    Logger.log(
      "Could not read sticky Hold state. Holding every draft this pass. error=%s",
      formatError_(error)
    );
    return state;
  }
  const held = parseStickyHoldMap_(state.originalHeldJson, HELD_DRAFTS_PROPERTY);
  const releasedAt = parseStickyReleaseMap_(state.originalReleasedJson, RELEASED_AT_PROPERTY);
  if (!held || !releasedAt) {
    state.readable = false;
    state.held = {};
    state.releasedAt = {};
    return state;
  }
  state.held = held;
  state.releasedAt = releasedAt;
  return state;
}

function parseStickyHoldMap_(raw, propertyName) {
  const parsed = parseStickyObject_(raw, propertyName);
  if (!parsed) {
    return parsed;
  }
  const held = {};
  for (const draftId in parsed) {
    if (!Object.prototype.hasOwnProperty.call(parsed, draftId)) {
      continue;
    }
    if (typeof parsed[draftId] !== "string") {
      Logger.log(
        "Could not parse sticky Hold state. Holding every draft this pass. property=%s",
        propertyName
      );
      return null;
    }
    held[draftId] = parsed[draftId];
  }
  return held;
}

function parseStickyReleaseMap_(raw, propertyName) {
  const parsed = parseStickyObject_(raw, propertyName);
  if (!parsed) {
    return parsed;
  }
  const releasedAt = {};
  for (const draftId in parsed) {
    if (!Object.prototype.hasOwnProperty.call(parsed, draftId)) {
      continue;
    }
    const timestamp = parsed[draftId];
    if (typeof timestamp !== "number" || !isFinite(timestamp)) {
      Logger.log(
        "Could not parse sticky Hold state. Holding every draft this pass. property=%s",
        propertyName
      );
      return null;
    }
    releasedAt[draftId] = timestamp;
  }
  return releasedAt;
}

// Empty and missing values are an empty map. A bad value is null, which
// means do not send and do not overwrite the stored property.
function parseStickyObject_(raw, propertyName) {
  if (raw === null || raw === "") {
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

function liveDraftIdsFromList_(drafts) {
  const ids = {};
  let complete = true;
  for (let draftIndex = 0; draftIndex < drafts.length; draftIndex++) {
    try {
      ids[drafts[draftIndex].getId()] = true;
    } catch (error) {
      if (isMissingDraftError_(error)) {
        continue;
      }
      complete = false;
      Logger.log(
        "Could not read a draft id. Sticky Hold entries were not pruned. error=%s",
        formatError_(error)
      );
      break;
    }
  }
  return { ids: ids, complete: complete };
}

function finishStickyHoldPass_(sticky, liveDraftIds) {
  if (!sticky.readable) {
    return;
  }
  if (liveDraftIds.complete) {
    pruneStickyMap_(sticky.held, liveDraftIds.ids);
    pruneStickyMap_(sticky.releasedAt, liveDraftIds.ids);
  }
  capStickyMap_(sticky.releasedAt, RELEASED_AT_PROPERTY);
  capStickyMap_(sticky.held, HELD_DRAFTS_PROPERTY);
  writeStickyMapIfChanged_(HELD_DRAFTS_PROPERTY, sticky.held, sticky.originalHeldJson);
  writeStickyMapIfChanged_(RELEASED_AT_PROPERTY, sticky.releasedAt, sticky.originalReleasedJson);
}

function pruneStickyMap_(map, liveIds) {
  const staleIds = [];
  for (const draftId in map) {
    if (!Object.prototype.hasOwnProperty.call(map, draftId)) {
      continue;
    }
    if (!liveIds[draftId]) {
      staleIds.push(draftId);
    }
  }
  for (let staleIndex = 0; staleIndex < staleIds.length; staleIndex++) {
    delete map[staleIds[staleIndex]];
  }
}

function capStickyMap_(map, propertyName) {
  let encoded = canonicalStickyJson_(map);
  while (encoded !== null && encoded.length > STICKY_PROPERTY_CHAR_CAP) {
    const keys = sortedMapKeys_(map);
    if (keys.length === 0) {
      return;
    }
    const droppedId = keys[keys.length - 1];
    delete map[droppedId];
    Logger.log(
      "Dropped sticky Hold entry over the property cap. property=%s id=%s",
      propertyName,
      droppedId
    );
    encoded = canonicalStickyJson_(map);
  }
}

function writeStickyMapIfChanged_(propertyName, map, originalJson) {
  const canonical = canonicalStickyJson_(map);
  if (sameStickyJson_(originalJson, canonical)) {
    return;
  }
  try {
    const properties = PropertiesService.getScriptProperties();
    if (canonical === null) {
      if (properties.getProperty(propertyName) !== null) {
        properties.deleteProperty(propertyName);
      }
      return;
    }
    properties.setProperty(propertyName, canonical);
  } catch (error) {
    Logger.log(
      "Could not store sticky Hold state. property=%s error=%s",
      propertyName,
      formatError_(error)
    );
  }
}

function sameStickyJson_(originalJson, canonical) {
  if (canonical === null) {
    return originalJson === null || originalJson === "" || originalJson === "{}";
  }
  if (originalJson === null || originalJson === "") {
    return false;
  }
  try {
    return canonicalStickyJson_(JSON.parse(originalJson)) === canonical;
  } catch (error) {
    return false;
  }
}

function canonicalStickyJson_(map) {
  if (!map || !mapHasAnyKey_(map)) {
    return null;
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
