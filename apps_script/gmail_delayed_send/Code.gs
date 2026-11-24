/**
 * Consumer Gmail delayed send.
 *
 * Gmail Undo Send holds a message for at most 30 seconds. This script
 * sends a draft only after its current message is DELAY_MINUTES old.
 *
 * GmailDraft has no last-updated getter. A save does not edit the
 * message in place: Gmail replaces it. The draft id stays; the message
 * id and message date change. draft.getMessage().getDate() is the
 * timestamp of that replacement message, so an edit resets the wait.
 * This script does not read the RFC 2822 Date header. The date is also
 * not the time the label was applied. Labeling a draft that was last
 * saved more than DELAY_MINUTES ago makes it eligible on the next run.
 *
 * A draft message cannot carry a user label. The Gmail UI puts
 * SEND_LABEL_NAME on the thread. Match the thread, then remove the
 * label from the sent thread after GmailDraft.send() only when no
 * other labeled draft on that thread still needs it.
 *
 * A recipient-quota error and a Gmail read/write quota error keep the
 * label and stop the rest of the pass. Those, and a missing send
 * label, throw at most once per hour so a one-minute trigger does not
 * fail on every run. Any other send failure removes the label and
 * applies SEND_FAILED_LABEL_NAME when this draft is the only one on
 * the thread that still needs the label.
 */

const DELAY_MINUTES = 5;
const SEND_LABEL_NAME = "Send in 5";
const SEND_FAILED_LABEL_NAME = "Send failed";
// ClockTriggerBuilder.everyMinutes allows only these values. 2 is rejected.
const ALLOWED_TRIGGER_INTERVAL_MINUTES = [1, 5, 10, 15, 30];
// 1 keeps an already-old labeled draft about a minute from the next look.
// 5 would cut the daily Gmail read count by about five and add up to
// about four minutes of wait. See the README quotas section.
const TRIGGER_INTERVAL_MINUTES = 1;
// Do not wait. A queued run would sit on the consumer trigger-time quota.
const LOCK_WAIT_MILLISECONDS = 0;
// Timestamp of the last thrown persistent failure. Not a draft id.
const PERSISTENT_FAILURE_LATCH_PROPERTY = "delayedSendPersistentFailureLatchedAt";
const PERSISTENT_FAILURE_THROW_INTERVAL_MILLISECONDS = 60 * 60 * 1000;

/**
 * Creates the send and failure labels when missing and installs one
 * time trigger. Running this again deletes duplicate triggers for the
 * handler first.
 */
function installDelayedGmailSend() {
  assertDelayedSendConfigured_();
  const sendLabel = getOrCreateLabel_(SEND_LABEL_NAME);
  const failedLabel = getOrCreateLabel_(SEND_FAILED_LABEL_NAME);
  const removedTriggerCount = deleteDelayedSendTriggers_();
  ScriptApp.newTrigger(sendLabeledDraftsAfterDelay.name)
    .timeBased()
    .everyMinutes(TRIGGER_INTERVAL_MINUTES)
    .create();
  Logger.log(
    "Installed delayed send. sendLabel=%s failedLabel=%s removedTriggers=%s intervalMinutes=%s handler=%s",
    sendLabel.getName(),
    failedLabel.getName(),
    removedTriggerCount,
    TRIGGER_INTERVAL_MINUTES,
    sendLabeledDraftsAfterDelay.name
  );
}

/**
 * Removes every trigger in this project whose handler is the delayed send.
 * Does not delete the Gmail label.
 */
function uninstallDelayedGmailSend() {
  const removedTriggerCount = deleteDelayedSendTriggers_();
  Logger.log("Removed delayed-send triggers. count=%s", removedTriggerCount);
}

/**
 * Time-driven entry point. One run at a time. Lists drafts, keeps those
 * whose thread has the send label, and sends each one that is old enough.
 * One draft's error is logged and does not stop the rest, except a Gmail
 * quota error, which leaves the remaining drafts for a later run.
 * Returns immediately when there are no drafts, or when another run holds
 * the script lock.
 */
function sendLabeledDraftsAfterDelay() {
  assertDelayedSendConfigured_();
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(LOCK_WAIT_MILLISECONDS)) {
    Logger.log("Delayed send skipped. Another run holds the script lock.");
    return;
  }
  try {
    sendLabeledDraftsWithLockHeld_();
  } finally {
    lock.releaseLock();
  }
}

function sendLabeledDraftsWithLockHeld_() {
  const passStartedAtMilliseconds = Date.now();
  const delayMilliseconds = delayMilliseconds_();
  let label;
  try {
    label = GmailApp.getUserLabelByName(SEND_LABEL_NAME);
  } catch (error) {
    if (isRetryLaterQuotaError_(error)) {
      finishRetryLaterQuota_(error);
      return;
    }
    throw error;
  }
  if (!label) {
    throwPersistentFailureAtMostOncePerHour_(
      "Delayed send label not found: " + SEND_LABEL_NAME + ". Run installDelayedGmailSend."
    );
    return;
  }

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

  const labeledDrafts = [];
  const threadHasSendLabelByThreadId = {};
  let labeledCount = 0;
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
      const snapshot = snapshotLabeledDraft_(draft, threadHasSendLabelByThreadId);
      if (!snapshot) {
        continue;
      }
      labeledDrafts.push(snapshot);
    } catch (error) {
      if (isMissingDraftError_(error)) {
        canceledCount++;
        Logger.log("Draft deleted before send. id=%s", draftId);
        continue;
      }
      failedCount++;
      Logger.log(
        "Delayed send failed for one draft. id=%s error=%s",
        draftId,
        formatError_(error)
      );
      if (isRetryLaterQuotaError_(error)) {
        retryLaterQuotaReached = true;
        Logger.log(
          "Gmail quota reached. Remaining labeled drafts stay labeled for a later run."
        );
        break;
      }
      markDraftSendFailed_(draft, label, draftId);
    }
  }

  for (let labeledIndex = 0; labeledIndex < labeledDrafts.length; labeledIndex++) {
    if (retryLaterQuotaReached) {
      break;
    }
    const snapshot = labeledDrafts[labeledIndex];
    try {
      const result = sendLabeledDraftIfOldEnough_(snapshot, delayMilliseconds);
      snapshot.outcome = result.outcome;
      snapshot.sentMessage = result.sentMessage || null;
      if (result.outcome === "not-labeled") {
        continue;
      }
      labeledCount++;
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
        labeledCount++;
        canceledCount++;
        Logger.log("Draft deleted before send. id=%s", snapshot.draftId);
        continue;
      }
      snapshot.outcome = "failed";
      labeledCount++;
      failedCount++;
      Logger.log(
        "Delayed send failed for one draft. id=%s error=%s",
        snapshot.draftId,
        formatError_(error)
      );
      if (isRetryLaterQuotaError_(error)) {
        snapshot.outcome = "quota";
        retryLaterQuotaReached = true;
        Logger.log(
          "Gmail quota reached. Remaining labeled drafts stay labeled for a later run."
        );
        break;
      }
    }
  }

  settleThreadLabels_(labeledDrafts, label);

  if (labeledCount === 0 && failedCount === 0 && canceledCount === 0) {
    clearPersistentFailureLatch_();
    return;
  }
  Logger.log(
    "Delayed send pass finished. drafts=%s labeled=%s sent=%s waiting=%s failed=%s canceled=%s elapsedMs=%s",
    drafts.length,
    labeledCount,
    sentCount,
    waitingCount,
    failedCount,
    canceledCount,
    Date.now() - passStartedAtMilliseconds
  );
  if (retryLaterQuotaReached) {
    throwPersistentFailureAtMostOncePerHour_(
      "Gmail quota reached. Labeled drafts left unsent stay labeled and are tried on a later run."
    );
    return;
  }
  clearPersistentFailureLatch_();
}

function finishRetryLaterQuota_(error) {
  Logger.log("Gmail quota reached before any draft was sent. error=%s", formatError_(error));
  throwPersistentFailureAtMostOncePerHour_(
    "Gmail quota reached. Labeled drafts left unsent stay labeled and are tried on a later run."
  );
}

function snapshotLabeledDraft_(draft, threadHasSendLabelByThreadId) {
  const draftId = draft.getId();
  const message = draft.getMessage();
  const thread = message.getThread();
  const threadId = thread.getId();
  let hasSendLabel = threadHasSendLabelByThreadId[threadId];
  if (hasSendLabel === undefined) {
    hasSendLabel = threadHasLabelName_(thread, SEND_LABEL_NAME);
    threadHasSendLabelByThreadId[threadId] = hasSendLabel;
  }
  if (!hasSendLabel) {
    return null;
  }
  return {
    draft: draft,
    draftId: draftId,
    message: message,
    thread: thread,
    threadId: threadId,
    outcome: "pending",
    sentMessage: null,
  };
}

function sendLabeledDraftIfOldEnough_(snapshot, delayMilliseconds) {
  const draftId = snapshot.draftId;
  const listedMessage = snapshot.message;
  const listedAgeMilliseconds = messageAgeMilliseconds_(listedMessage.getDate(), Date.now());
  if (!isOldEnoughToSend_(listedAgeMilliseconds, delayMilliseconds)) {
    logWaitingDraft_(draftId, listedMessage.getSubject(), listedAgeMilliseconds, "listed");
    return { outcome: "waiting" };
  }

  // Re-read before send so a save or a label removal during this run
  // still resets or cancels. GmailApp can serve a stale message from
  // the earlier getDrafts() result.
  let freshDraft;
  try {
    freshDraft = GmailApp.getDraft(draftId);
  } catch (error) {
    if (isMissingDraftError_(error)) {
      Logger.log("Draft deleted before send. id=%s", draftId);
      return { outcome: "canceled" };
    }
    throw error;
  }
  const freshMessage = freshDraft.getMessage();
  if (!threadHasLabelName_(freshMessage.getThread(), SEND_LABEL_NAME)) {
    Logger.log("Draft lost the send label before send. id=%s", draftId);
    return { outcome: "not-labeled" };
  }
  const freshAgeMilliseconds = messageAgeMilliseconds_(freshMessage.getDate(), Date.now());
  if (!isOldEnoughToSend_(freshAgeMilliseconds, delayMilliseconds)) {
    logWaitingDraft_(draftId, freshMessage.getSubject(), freshAgeMilliseconds, "recheck");
    return { outcome: "waiting" };
  }

  const subject = freshMessage.getSubject();
  const sentMessage = freshDraft.send();
  if (!sentMessage) {
    throw new Error("GmailDraft.send() returned no message");
  }
  Logger.log("Sent draft. id=%s subject=%s", draftId, subject);
  return { outcome: "sent", sentMessage: sentMessage };
}

function settleThreadLabels_(labeledDrafts, label) {
  const threadIds = [];
  for (let draftIndex = 0; draftIndex < labeledDrafts.length; draftIndex++) {
    const threadId = labeledDrafts[draftIndex].threadId;
    if (threadIds.indexOf(threadId) === -1) {
      threadIds.push(threadId);
    }
  }
  for (let threadIndex = 0; threadIndex < threadIds.length; threadIndex++) {
    settleOneThreadLabel_(labeledDrafts, threadIds[threadIndex], label);
  }
}

function settleOneThreadLabel_(labeledDrafts, threadId, label) {
  const records = [];
  for (let draftIndex = 0; draftIndex < labeledDrafts.length; draftIndex++) {
    if (labeledDrafts[draftIndex].threadId === threadId) {
      records.push(labeledDrafts[draftIndex]);
    }
  }
  const keepsSendLabel =
    threadHasOutcome_(records, "waiting") ||
    threadHasOutcome_(records, "pending") ||
    threadHasOutcome_(records, "quota");
  if (keepsSendLabel) {
    if (threadHasOutcome_(records, "sent") || threadHasOutcome_(records, "failed")) {
      Logger.log(
        "Left Send in 5 on the thread. Another labeled draft still needs it. threadId=%s",
        threadId
      );
    }
    return;
  }
  if (threadHasOutcome_(records, "failed")) {
    const failedRecord = firstRecordWithOutcome_(records, "failed");
    markDraftSendFailed_(failedRecord.draft, label, failedRecord.draftId);
    return;
  }
  if (threadHasOutcome_(records, "sent")) {
    const sentRecord = firstRecordWithOutcome_(records, "sent");
    removeSendLabelFromSentThread_(sentRecord.sentMessage, label, sentRecord.draftId);
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

function markDraftSendFailed_(draft, sendLabel, draftId) {
  let thread;
  try {
    thread = draft.getMessage().getThread();
  } catch (error) {
    Logger.log(
      "Could not mark draft send failed. id=%s error=%s",
      draftId,
      formatError_(error)
    );
    return;
  }
  if (!threadHasLabelName_(thread, SEND_LABEL_NAME)) {
    return;
  }
  // Remove the send label first. If that fails, the next run retries,
  // which is the same outcome as before this function existed. Adding
  // Send failed first can leave both labels when the remove throws.
  try {
    thread.removeLabel(sendLabel);
  } catch (error) {
    Logger.log(
      "Could not remove the send label after a failed send. id=%s error=%s",
      draftId,
      formatError_(error)
    );
    return;
  }
  try {
    const failedLabel = getOrCreateLabel_(SEND_FAILED_LABEL_NAME);
    thread.addLabel(failedLabel);
    Logger.log(
      "Marked draft send failed. id=%s appliedLabel=%s removedLabel=%s",
      draftId,
      SEND_FAILED_LABEL_NAME,
      SEND_LABEL_NAME
    );
  } catch (error) {
    Logger.log(
      "Removed the send label but could not apply the failure label. id=%s error=%s",
      draftId,
      formatError_(error)
    );
  }
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
  const handlerName = sendLabeledDraftsAfterDelay.name;
  const triggers = ScriptApp.getProjectTriggers();
  let removedTriggerCount = 0;
  for (let triggerIndex = 0; triggerIndex < triggers.length; triggerIndex++) {
    const trigger = triggers[triggerIndex];
    if (trigger.getHandlerFunction() === handlerName) {
      ScriptApp.deleteTrigger(trigger);
      removedTriggerCount++;
    }
  }
  return removedTriggerCount;
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
  for (
    let intervalIndex = 0;
    intervalIndex < ALLOWED_TRIGGER_INTERVAL_MINUTES.length;
    intervalIndex++
  ) {
    if (ALLOWED_TRIGGER_INTERVAL_MINUTES[intervalIndex] === intervalMinutes) {
      return;
    }
  }
  throw new Error(
    "TRIGGER_INTERVAL_MINUTES must be 1, 5, 10, 15, or 30. ClockTriggerBuilder.everyMinutes rejects any other value."
  );
}

function assertDelayedSendConfigured_() {
  delayMilliseconds_();
  assertTriggerIntervalMinutes_(TRIGGER_INTERVAL_MINUTES);
  if (typeof SEND_LABEL_NAME !== "string" || SEND_LABEL_NAME.trim() === "") {
    throw new Error("SEND_LABEL_NAME must be a non-empty string");
  }
  if (typeof SEND_FAILED_LABEL_NAME !== "string" || SEND_FAILED_LABEL_NAME.trim() === "") {
    throw new Error("SEND_FAILED_LABEL_NAME must be a non-empty string");
  }
}

function removeSendLabelFromSentThread_(sentMessage, label, draftId) {
  try {
    sentMessage.getThread().removeLabel(label);
  } catch (error) {
    // The message is already sent. Do not rethrow: a retry would not
    // find the draft, and the log is the signal to remove the label by hand.
    Logger.log(
      "Sent draft, but removing the label failed. id=%s error=%s",
      draftId,
      formatError_(error)
    );
  }
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
    Logger.log(
      "Could not update the persistent-failure latch. error=%s",
      formatError_(error)
    );
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
    Logger.log(
      "Could not clear the persistent-failure latch. error=%s",
      formatError_(error)
    );
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
