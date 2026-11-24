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
 * label from the sent thread after GmailDraft.send().
 */

const DELAY_MINUTES = 5;
const SEND_LABEL_NAME = "Send in 5";
const SEND_FAILED_LABEL_NAME = "Send failed";
// Do not wait. A queued run would sit on the consumer trigger-time quota.
const LOCK_WAIT_MILLISECONDS = 0;
// A missing label or a service quota throws at most once an hour so a
// minute trigger is not a long streak of failed executions.
const PERSISTENT_FAILURE_REPEAT_MILLISECONDS = 60 * 60 * 1000;

/**
 * Creates the send and failure labels when missing and installs one
 * every-minute trigger. Running this again deletes duplicate triggers
 * for the handler first.
 */
function installDelayedGmailSend() {
  assertDelayedSendConfigured_();
  const sendLabel = getOrCreateLabel_(SEND_LABEL_NAME);
  const failedLabel = getOrCreateLabel_(SEND_FAILED_LABEL_NAME);
  const removedTriggerCount = deleteDelayedSendTriggers_();
  ScriptApp.newTrigger(sendLabeledDraftsAfterDelay.name)
    .timeBased()
    .everyMinutes(1)
    .create();
  Logger.log(
    "Installed delayed send. sendLabel=%s failedLabel=%s removedTriggers=%s minuteTrigger=1 handler=%s",
    sendLabel.getName(),
    failedLabel.getName(),
    removedTriggerCount,
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
 * One draft's error is logged and does not stop the rest, except a daily
 * email-quota error, which leaves the remaining drafts for a later run.
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
  const delayMilliseconds = delayMilliseconds_();
  const label = GmailApp.getUserLabelByName(SEND_LABEL_NAME);
  if (!label) {
    throwPersistentFailureOncePerHour_(
      "missing-label",
      new Error(
        "Delayed send label not found: " +
          SEND_LABEL_NAME +
          ". Run installDelayedGmailSend."
      )
    );
    return;
  }

  const drafts = GmailApp.getDrafts();
  if (drafts.length === 0) {
    return;
  }

  const queued = [];
  let failedCount = 0;
  let quotaReason = "";

  for (let draftIndex = 0; draftIndex < drafts.length; draftIndex++) {
    const draft = drafts[draftIndex];
    let draftId = "unavailable";
    try {
      draftId = draft.getId();
      const message = draft.getMessage();
      const thread = message.getThread();
      if (!threadHasLabelName_(thread, SEND_LABEL_NAME)) {
        continue;
      }
      queued.push({
        draft: draft,
        draftId: draftId,
        thread: thread,
        threadId: thread.getId(),
      });
    } catch (error) {
      const handled = handleDraftFailure_(error, draft, label, draftId, true);
      failedCount++;
      if (handled.quotaReason) {
        quotaReason = handled.quotaReason;
        break;
      }
    }
  }

  const remainingByThreadId = {};
  for (let queuedIndex = 0; queuedIndex < queued.length; queuedIndex++) {
    const threadId = queued[queuedIndex].threadId;
    remainingByThreadId[threadId] = (remainingByThreadId[threadId] || 0) + 1;
  }

  let labeledCount = 0;
  let sentCount = 0;
  let waitingCount = 0;

  if (!quotaReason) {
    for (let queuedIndex = 0; queuedIndex < queued.length; queuedIndex++) {
      const queuedDraft = queued[queuedIndex];
      try {
        const outcome = sendQueuedDraftIfOldEnough_(
          queuedDraft,
          label,
          delayMilliseconds,
          remainingByThreadId
        );
        if (outcome === "not-labeled" || outcome === "canceled") {
          continue;
        }
        labeledCount++;
        if (outcome === "sent") {
          sentCount++;
        } else if (outcome === "waiting") {
          waitingCount++;
        } else {
          throw new Error("Unexpected delayed-send outcome: " + outcome);
        }
      } catch (error) {
        const siblingsRemain = remainingByThreadId[queuedDraft.threadId] > 1;
        const handled = handleDraftFailure_(
          error,
          queuedDraft.draft,
          label,
          queuedDraft.draftId,
          !siblingsRemain
        );
        failedCount++;
        if (!handled.quotaReason && !siblingsRemain) {
          remainingByThreadId[queuedDraft.threadId] -= 1;
        }
        if (handled.quotaReason) {
          quotaReason = handled.quotaReason;
          break;
        }
      }
    }
  }

  if (labeledCount === 0 && failedCount === 0 && !quotaReason) {
    return;
  }
  Logger.log(
    "Delayed send pass finished. labeled=%s sent=%s waiting=%s failed=%s",
    labeledCount,
    sentCount,
    waitingCount,
    failedCount
  );
  if (quotaReason) {
    throwPersistentFailureOncePerHour_(
      quotaReason,
      new Error(quotaFailureMessage_(quotaReason))
    );
  }
}

function sendQueuedDraftIfOldEnough_(queuedDraft, label, delayMilliseconds, remainingByThreadId) {
  const draft = queuedDraft.draft;
  const draftId = queuedDraft.draftId;
  const listedMessage = draft.getMessage();
  const listedAgeMilliseconds = messageAgeMilliseconds_(
    listedMessage.getDate(),
    Date.now()
  );
  if (!isOldEnoughToSend_(listedAgeMilliseconds, delayMilliseconds)) {
    logWaitingDraft_(draftId, listedMessage.getSubject(), listedAgeMilliseconds, "listed");
    return "waiting";
  }

  // Re-read before send so a save or a label removal during this run
  // still resets or cancels. GmailApp can serve a stale message from
  // the earlier getDrafts() result.
  let freshDraft;
  try {
    freshDraft = GmailApp.getDraft(draftId);
  } catch (error) {
    if (isMissingDraftError_(error)) {
      Logger.log("Draft gone before send. id=%s", draftId);
      releaseQueuedThread_(queuedDraft, label, remainingByThreadId);
      return "canceled";
    }
    throw error;
  }
  if (!draftThreadHasSendLabel_(freshDraft)) {
    Logger.log("Draft lost the send label before send. id=%s", draftId);
    releaseQueuedThread_(queuedDraft, label, remainingByThreadId);
    return "not-labeled";
  }
  const freshMessage = freshDraft.getMessage();
  const subject = freshMessage.getSubject();
  const freshAgeMilliseconds = messageAgeMilliseconds_(freshMessage.getDate(), Date.now());
  if (!isOldEnoughToSend_(freshAgeMilliseconds, delayMilliseconds)) {
    logWaitingDraft_(draftId, subject, freshAgeMilliseconds, "recheck");
    return "waiting";
  }

  const sentMessage = freshDraft.send();
  if (!sentMessage) {
    throw new Error("GmailDraft.send() returned no message");
  }
  releaseQueuedThread_(queuedDraft, label, remainingByThreadId, sentMessage);
  Logger.log("Sent draft. id=%s subject=%s", draftId, subject);
  return "sent";
}

function releaseQueuedThread_(queuedDraft, label, remainingByThreadId, sentMessage) {
  remainingByThreadId[queuedDraft.threadId] -= 1;
  if (remainingByThreadId[queuedDraft.threadId] > 0) {
    Logger.log(
      "Left the send label. Another draft on the thread is still queued. id=%s",
      queuedDraft.draftId
    );
    return;
  }
  const thread = sentMessage ? sentMessage.getThread() : queuedDraft.thread;
  removeSendLabelFromSentThread_(thread, label, queuedDraft.draftId);
}

function getOrCreateLabel_(labelName) {
  const existingLabel = GmailApp.getUserLabelByName(labelName);
  if (existingLabel) {
    return existingLabel;
  }
  return GmailApp.createLabel(labelName);
}

function handleDraftFailure_(error, draft, sendLabel, draftId, removeSendLabel) {
  Logger.log(
    "Delayed send failed for one draft. id=%s error=%s",
    draftId,
    formatError_(error)
  );
  const quotaReason = serviceQuotaReason_(error);
  if (quotaReason) {
    Logger.log("%s", quotaFailureMessage_(quotaReason));
    return { quotaReason: quotaReason };
  }
  markDraftSendFailed_(draft, sendLabel, draftId, removeSendLabel);
  return { quotaReason: "" };
}

function markDraftSendFailed_(draft, sendLabel, draftId, removeSendLabel) {
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
  if (!removeSendLabel) {
    Logger.log(
      "Left the send label after a failure. Another draft on the thread is still queued. id=%s",
      draftId
    );
  } else {
    try {
      thread.removeLabel(sendLabel);
    } catch (error) {
      Logger.log(
        "Could not remove the send label after a failure. id=%s error=%s",
        draftId,
        formatError_(error)
      );
    }
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
    Logger.log(
      "Could not apply the send-failed label. id=%s error=%s",
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

function draftThreadHasSendLabel_(draft) {
  return threadHasLabelName_(draft.getMessage().getThread(), SEND_LABEL_NAME);
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

function assertDelayedSendConfigured_() {
  delayMilliseconds_();
  if (typeof SEND_LABEL_NAME !== "string" || SEND_LABEL_NAME.trim() === "") {
    throw new Error("SEND_LABEL_NAME must be a non-empty string");
  }
  if (typeof SEND_FAILED_LABEL_NAME !== "string" || SEND_FAILED_LABEL_NAME.trim() === "") {
    throw new Error("SEND_FAILED_LABEL_NAME must be a non-empty string");
  }
}

function removeSendLabelFromSentThread_(thread, label, draftId) {
  try {
    thread.removeLabel(label);
  } catch (error) {
    // Do not rethrow. A sent message must not be sent again, and a draft
    // that is already gone has nothing to park.
    Logger.log(
      "Could not remove the send label. id=%s error=%s",
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

function errorText_(error) {
  const parts = [];
  if (error && error.message) {
    parts.push(String(error.message));
  }
  parts.push(formatError_(error));
  return parts.join("\n").toLowerCase();
}

function serviceQuotaReason_(error) {
  const text = errorText_(error);
  if (
    text.indexOf("email recipients per day") !== -1 ||
    text.indexOf("too many times for one day: email") !== -1 ||
    text.indexOf("too many times in a short time: email") !== -1
  ) {
    return "email-send-quota";
  }
  if (
    text.indexOf("too many times for one day: gmail") !== -1 ||
    text.indexOf("too many times in a short time: gmail") !== -1
  ) {
    return "gmail-read-quota";
  }
  return "";
}

function quotaFailureMessage_(reason) {
  if (reason === "gmail-read-quota") {
    return (
      "Gmail read quota reached. Labeled drafts stay on " +
      SEND_LABEL_NAME +
      " and were not parked on " +
      SEND_FAILED_LABEL_NAME +
      "."
    );
  }
  return "Daily email quota reached. Labeled drafts left unsent stay labeled and are tried on a later run.";
}

function isMissingDraftError_(error) {
  const text = errorText_(error);
  return text.indexOf("not found") !== -1 || text.indexOf("invalid draft") !== -1;
}

function throwPersistentFailureOncePerHour_(reason, error) {
  const propertyKey = "delayedSendPersistentFailure:" + reason;
  const nowMilliseconds = Date.now();
  let lastMilliseconds = 0;
  try {
    const stored = PropertiesService.getScriptProperties().getProperty(propertyKey);
    if (stored) {
      lastMilliseconds = Number(stored);
    }
  } catch (readError) {
    Logger.log(
      "Could not read the persistent-failure latch. error=%s",
      formatError_(readError)
    );
  }
  if (
    isFinite(lastMilliseconds) &&
    nowMilliseconds - lastMilliseconds < PERSISTENT_FAILURE_REPEAT_MILLISECONDS
  ) {
    Logger.log(
      "Persistent failure still present. reason=%s suppressedRepeat=1 error=%s",
      reason,
      formatError_(error)
    );
    return;
  }
  try {
    PropertiesService.getScriptProperties().setProperty(propertyKey, String(nowMilliseconds));
  } catch (writeError) {
    Logger.log(
      "Could not store the persistent-failure latch. error=%s",
      formatError_(writeError)
    );
  }
  throw error;
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
