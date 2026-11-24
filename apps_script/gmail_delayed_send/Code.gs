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
 * sent. Removing the label makes it eligible again. The clock is still
 * the draft's last save, not the moment the label came off.
 *
 * SEND_FAILED_LABEL_NAME on the thread means a previous non-quota
 * failure. Those drafts are skipped so a one-minute trigger does not
 * send them again. Removing the label makes them eligible again.
 *
 * LEGACY_SEND_LABEL_NAME ("Send in 5") is not an eligibility gate.
 * Older versions of this script required it. It is removed after a
 * send, or after Send failed is applied, only when no draft on that
 * thread is still waiting or held back by a quota error. Leaving it
 * in place does not change who sends.
 *
 * A draft message cannot carry a user label. Hold and Send failed are
 * thread labels. Every draft on that thread shares them.
 *
 * A recipient-quota error and a Gmail read/write quota error leave the
 * draft eligible and stop the rest of the pass. Those throw at most
 * once per hour so a one-minute trigger does not fail on every run.
 * Any other send failure applies SEND_FAILED_LABEL_NAME when no other
 * draft on that thread is still waiting or held back by quota.
 * A draft with no To, Cc, or Bcc is that kind of failure: it is logged
 * and parked, and it does not stop the pass. Empty To with a Cc or
 * Bcc is sendable. Reply drafts are ordinary drafts; GmailDraft.send()
 * keeps the thread.
 */

const DELAY_MINUTES = 5;
const HOLD_LABEL_NAME = "Hold";
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
const QUOTA_REMAINING_DRAFTS_LOG_MESSAGE =
  "Gmail quota reached. Remaining drafts stay for a later run.";
const QUOTA_DRAFTS_LEFT_UNSENT_THROW_MESSAGE =
  "Gmail quota reached. Drafts left unsent stay eligible and are tried on a later run.";
const DRAFT_DELETED_BEFORE_SEND_LOG_TEMPLATE = "Draft deleted before send. id=%s";
const LEGACY_DELAYED_SEND_HANDLER_NAME = "sendLabeledDraftsAfterDelay";

/**
 * Creates the Hold and Send failed labels when missing and installs one
 * time trigger. Running this again deletes duplicate triggers for the
 * current handler and for the older opt-in handler first.
 * "Send in 5" is not created.
 */
function installDelayedGmailSend() {
  assertDelayedSendConfigured_();
  const holdLabel = getOrCreateLabel_(HOLD_LABEL_NAME);
  const failedLabel = getOrCreateLabel_(SEND_FAILED_LABEL_NAME);
  const removedTriggerCount = deleteDelayedSendTriggers_();
  ScriptApp.newTrigger(sendDraftsAfterDelay.name)
    .timeBased()
    .everyMinutes(TRIGGER_INTERVAL_MINUTES)
    .create();
  Logger.log(
    "Installed delayed send. holdLabel=%s failedLabel=%s removedTriggers=%s intervalMinutes=%s handler=%s",
    holdLabel.getName(),
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
  if (drafts.length === 0) {
    clearPersistentFailureLatch_();
    return;
  }

  const eligibleDrafts = [];
  const threadLabelStateByThreadId = {};
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
      const snapshot = snapshotEligibleDraft_(draft, draftId, threadLabelStateByThreadId);
      if (!snapshot) {
        continue;
      }
      eligibleDrafts.push(snapshot);
    } catch (error) {
      if (isMissingDraftError_(error)) {
        canceledCount++;
        Logger.log(DRAFT_DELETED_BEFORE_SEND_LOG_TEMPLATE, draftId);
        continue;
      }
      failedCount++;
      logDraftProblem_("Delayed send failed for one draft. id=%s error=%s", draftId, error);
      if (isRetryLaterQuotaError_(error)) {
        retryLaterQuotaReached = true;
        Logger.log(QUOTA_REMAINING_DRAFTS_LOG_MESSAGE);
        break;
      }
      const failedThread = markDraftSendFailed_(draft, draftId);
      if (failedThread) {
        removeLegacySendLabelFromThread_(
          failedThread,
          draftId,
          "Send failed is applied, but removing the legacy label failed. id=%s error=%s"
        );
      }
    }
  }

  for (let eligibleIndex = 0; eligibleIndex < eligibleDrafts.length; eligibleIndex++) {
    if (retryLaterQuotaReached) {
      break;
    }
    const snapshot = eligibleDrafts[eligibleIndex];
    try {
      const result = sendDraftIfOldEnough_(snapshot, delayMilliseconds);
      snapshot.outcome = result.outcome;
      snapshot.sentMessage = result.sentMessage || null;
      if (result.outcome === "held" || result.outcome === "skipped") {
        continue;
      }
      eligibleCount++;
      if (result.outcome === "sent") {
        sentCount++;
      } else if (result.outcome === "waiting") {
        waitingCount++;
      } else if (result.outcome === "canceled") {
        canceledCount++;
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
      logDraftProblem_(
        "Delayed send failed for one draft. id=%s error=%s",
        snapshot.draftId,
        error
      );
      if (isRetryLaterQuotaError_(error)) {
        snapshot.outcome = "quota";
        retryLaterQuotaReached = true;
        Logger.log(QUOTA_REMAINING_DRAFTS_LOG_MESSAGE);
        break;
      }
    }
  }

  settleThreadLabels_(eligibleDrafts);

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

function snapshotEligibleDraft_(draft, draftId, threadLabelStateByThreadId) {
  const message = draft.getMessage();
  const thread = message.getThread();
  const threadId = thread.getId();
  let labelState = threadLabelStateByThreadId[threadId];
  if (labelState === undefined) {
    labelState = readThreadLabelState_(thread);
    threadLabelStateByThreadId[threadId] = labelState;
  }
  if (labelState.sendFailed) {
    return null;
  }
  if (labelState.hold) {
    Logger.log("Holding draft. id=%s subject=%s", draftId, message.getSubject());
    return null;
  }
  return {
    draft: draft,
    draftId: draftId,
    message: message,
    threadId: threadId,
    outcome: "pending",
    sentMessage: null,
  };
}

function readThreadLabelState_(thread) {
  const labelsOnThread = thread.getLabels();
  const state = { hold: false, sendFailed: false };
  for (let labelIndex = 0; labelIndex < labelsOnThread.length; labelIndex++) {
    const name = labelsOnThread[labelIndex].getName();
    if (name === HOLD_LABEL_NAME) {
      state.hold = true;
    } else if (name === SEND_FAILED_LABEL_NAME) {
      state.sendFailed = true;
    }
  }
  return state;
}

function sendDraftIfOldEnough_(snapshot, delayMilliseconds) {
  const draftId = snapshot.draftId;
  const listedMessage = snapshot.message;
  const listedAgeMilliseconds = messageAgeMilliseconds_(listedMessage.getDate(), Date.now());
  if (!isOldEnoughToSend_(listedAgeMilliseconds, delayMilliseconds)) {
    logWaitingDraft_(draftId, listedMessage.getSubject(), listedAgeMilliseconds, "listed");
    return { outcome: "waiting" };
  }

  // Re-read before send so a save, Hold, or Send failed during this run
  // still resets or cancels. GmailApp can serve a stale message from
  // the earlier getDrafts() result.
  let freshDraft;
  try {
    freshDraft = GmailApp.getDraft(draftId);
  } catch (error) {
    if (isMissingDraftError_(error)) {
      Logger.log(DRAFT_DELETED_BEFORE_SEND_LOG_TEMPLATE, draftId);
      return { outcome: "canceled" };
    }
    throw error;
  }
  const freshMessage = freshDraft.getMessage();
  const freshState = readThreadLabelState_(freshMessage.getThread());
  if (freshState.hold) {
    Logger.log("Draft gained Hold before send. id=%s", draftId);
    return { outcome: "held" };
  }
  if (freshState.sendFailed) {
    Logger.log("Draft gained Send failed before send. id=%s", draftId);
    return { outcome: "skipped" };
  }
  const freshAgeMilliseconds = messageAgeMilliseconds_(freshMessage.getDate(), Date.now());
  if (!isOldEnoughToSend_(freshAgeMilliseconds, delayMilliseconds)) {
    logWaitingDraft_(draftId, freshMessage.getSubject(), freshAgeMilliseconds, "recheck");
    return { outcome: "waiting" };
  }
  if (!draftHasRecipient_(freshMessage)) {
    throw new Error("Draft has no recipient");
  }

  const subject = freshMessage.getSubject();
  const sentMessage = freshDraft.send();
  if (!sentMessage) {
    throw new Error("GmailDraft.send() returned no message");
  }
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
    threadHasOutcome_(records, "held");
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

function logWaitingDraft_(draftId, subject, ageMilliseconds, stage) {
  Logger.log(
    "Waiting to send draft. stage=%s id=%s subject=%s ageSeconds=%s",
    stage,
    draftId,
    subject,
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
    text.indexOf("too many times: gmail") !== -1
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

function formatError_(error) {
  if (!error) {
    return "unknown error";
  }
  if (error.stack) {
    return String(error.stack);
  }
  return String(error);
}
