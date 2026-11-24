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

/**
 * Creates the label when missing and installs one every-minute trigger.
 * Running this again deletes duplicate triggers for the handler first.
 */
function installDelayedGmailSend() {
  assertDelayedSendConfigured_();
  const label = getOrCreateSendLabel_();
  const removedTriggerCount = deleteDelayedSendTriggers_();
  ScriptApp.newTrigger(sendLabeledDraftsAfterDelay.name)
    .timeBased()
    .everyMinutes(1)
    .create();
  Logger.log(
    "Installed delayed send. label=%s removedTriggers=%s minuteTrigger=1 handler=%s",
    label.getName(),
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
 * Time-driven entry point. Lists drafts, keeps those whose thread has
 * the send label, and sends each one that is old enough. One draft's
 * error is logged and does not stop the rest. Returns immediately when
 * there are no drafts.
 */
function sendLabeledDraftsAfterDelay() {
  assertDelayedSendConfigured_();
  const delayMilliseconds = delayMilliseconds_();
  const label = GmailApp.getUserLabelByName(SEND_LABEL_NAME);
  if (!label) {
    throw new Error(
      "Delayed send label not found: " +
        SEND_LABEL_NAME +
        ". Run installDelayedGmailSend."
    );
  }

  const drafts = GmailApp.getDrafts();
  if (drafts.length === 0) {
    return;
  }

  let labeledCount = 0;
  let sentCount = 0;
  let waitingCount = 0;
  let failedCount = 0;

  for (let draftIndex = 0; draftIndex < drafts.length; draftIndex++) {
    const draft = drafts[draftIndex];
    let draftId = "unavailable";
    try {
      draftId = draft.getId();
      const outcome = sendLabeledDraftIfOldEnough_(draft, label, delayMilliseconds);
      if (outcome === "not-labeled") {
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
      failedCount++;
      Logger.log(
        "Delayed send failed for one draft. id=%s error=%s",
        draftId,
        formatError_(error)
      );
    }
  }

  if (labeledCount === 0 && failedCount === 0) {
    return;
  }
  Logger.log(
    "Delayed send pass finished. labeled=%s sent=%s waiting=%s failed=%s",
    labeledCount,
    sentCount,
    waitingCount,
    failedCount
  );
}

function sendLabeledDraftIfOldEnough_(draft, label, delayMilliseconds) {
  if (!draftThreadHasSendLabel_(draft)) {
    return "not-labeled";
  }

  const draftId = draft.getId();
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
  const freshDraft = GmailApp.getDraft(draftId);
  if (!draftThreadHasSendLabel_(freshDraft)) {
    Logger.log("Draft lost the send label before send. id=%s", draftId);
    return "not-labeled";
  }
  const freshMessage = freshDraft.getMessage();
  const freshAgeMilliseconds = messageAgeMilliseconds_(freshMessage.getDate(), Date.now());
  if (!isOldEnoughToSend_(freshAgeMilliseconds, delayMilliseconds)) {
    logWaitingDraft_(draftId, freshMessage.getSubject(), freshAgeMilliseconds, "recheck");
    return "waiting";
  }

  const sentMessage = freshDraft.send();
  if (!sentMessage) {
    throw new Error("GmailDraft.send() returned no message");
  }
  Logger.log("Sent draft. id=%s subject=%s", draftId, freshMessage.getSubject());
  removeSendLabelFromSentThread_(sentMessage, label, draftId);
  return "sent";
}

function getOrCreateSendLabel_() {
  const existingLabel = GmailApp.getUserLabelByName(SEND_LABEL_NAME);
  if (existingLabel) {
    return existingLabel;
  }
  return GmailApp.createLabel(SEND_LABEL_NAME);
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
  const labelsOnThread = draft.getMessage().getThread().getLabels();
  for (let labelIndex = 0; labelIndex < labelsOnThread.length; labelIndex++) {
    if (labelsOnThread[labelIndex].getName() === SEND_LABEL_NAME) {
      return true;
    }
  }
  return false;
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

function formatError_(error) {
  if (!error) {
    return "unknown error";
  }
  if (error.stack) {
    return String(error.stack);
  }
  return String(error);
}
