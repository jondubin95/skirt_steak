/**
 * GmailApp stand-in for the delayed-send script. No network and no mailbox.
 * Run: node apps_script/gmail_delayed_send/stand_in_test.mjs
 */

import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const code = fs.readFileSync(new URL("./Code.gs", import.meta.url), "utf8");
const FIVE_MINUTES_MS = 5 * 60 * 1000;
const HOUR_MS = 60 * 60 * 1000;

function formatLog(template, values) {
  let index = 0;
  return String(template).replace(/%s/g, () => {
    const value = values[index];
    index += 1;
    return value === undefined ? "" : String(value);
  });
}

function createWorld(options) {
  const settings = options || {};
  const nowHolder = { milliseconds: settings.nowMilliseconds || 1_700_000_000_000 };
  const logs = [];
  const labelOps = [];
  const sendCalls = [];
  const serviceCalls = [];
  const properties = {};
  const triggers = settings.triggers ? settings.triggers.slice() : [];
  let nextTriggerId = 1;
  const labelsByName = {};
  const labelsById = {};
  const threads = {};
  const draftSpecs = {};

  function ensureLabel(name, id) {
    const labelId = id || "id:" + name;
    if (!labelsById[labelId]) {
      const label = {
        name: name,
        id: labelId,
        getName() {
          return this.name;
        },
        getId() {
          return this.id;
        },
      };
      labelsById[labelId] = label;
      labelsByName[name] = label;
    }
    return labelsById[labelId];
  }

  function makeThread(threadId) {
    const thread = {
      getId() {
        return threadId;
      },
      getLabels() {
        serviceCalls.push("getLabels:" + threadId);
        if (thread.getLabelsError) {
          throw new Error(thread.getLabelsError);
        }
        return thread.labelNames.map((name) => ensureLabel(name, thread.labelIdsByName[name]));
      },
      addLabel(label) {
        labelOps.push("add:" + label.getName());
        if (thread.addLabelError) {
          throw new Error(thread.addLabelError);
        }
        if (thread.labelNames.indexOf(label.getName()) === -1) {
          thread.labelNames.push(label.getName());
        }
      },
      removeLabel(label) {
        labelOps.push("remove:" + label.getName());
        if (thread.removeLabelError) {
          throw new Error(thread.removeLabelError);
        }
        thread.labelNames = thread.labelNames.filter((name) => name !== label.getName());
      },
      labelNames: [],
      labelIdsByName: {},
      getLabelsError: null,
      addLabelError: null,
      removeLabelError: null,
    };
    threads[threadId] = thread;
    return thread;
  }

  function threadFor(threadId) {
    return threads[threadId] || makeThread(threadId);
  }

  const OriginalDate = Date;
  class FixedDate extends OriginalDate {
    constructor(...args) {
      if (args.length === 0) {
        super(nowHolder.milliseconds);
      } else {
        super(...args);
      }
    }
    static now() {
      return nowHolder.milliseconds;
    }
  }

  function makeMessage(spec, sentCopy) {
    let consumed = false;
    const message = {
      getDate() {
        if (spec.invalidDate) {
          return new FixedDate(NaN);
        }
        if (spec.missingDate) {
          return "not-a-date";
        }
        return new FixedDate(spec.dateMilliseconds);
      },
      getSubject() {
        if (consumed) {
          throw new Error("subject read after send");
        }
        return spec.subject;
      },
      getThread() {
        serviceCalls.push("getThread:" + spec.threadId);
        return threadFor(spec.threadId);
      },
      getId() {
        return spec.messageId;
      },
      getTo() {
        return spec.to || "";
      },
      getCc() {
        return spec.cc || "";
      },
      getBcc() {
        return spec.bcc || "";
      },
      markConsumed() {
        consumed = true;
      },
    };
    if (sentCopy) {
      message.markConsumed();
    }
    return message;
  }

  function makeDraft(spec) {
    let consumed = false;
    let message = null;
    return {
      getId() {
        return spec.id;
      },
      getMessageId() {
        return spec.messageId;
      },
      getMessage() {
        serviceCalls.push("getMessage:" + spec.id);
        if (spec.gone || consumed) {
          throw new Error("Requested entity was not found.");
        }
        if (spec.messageError) {
          throw new Error(spec.messageError);
        }
        if (!message) {
          message = makeMessage(spec, false);
        }
        return message;
      },
      send() {
        sendCalls.push(spec.id);
        spec.inFlightAtSend = properties.delayedSendInFlightSend || null;
        if (spec.sendError) {
          throw new Error(spec.sendError);
        }
        if (message) {
          message.markConsumed();
        }
        consumed = true;
        spec.gone = true;
        return makeMessage(spec, true);
      },
    };
  }

  function addDraft(spec) {
    draftSpecs[spec.id] = spec;
    const thread = threadFor(spec.threadId);
    if (spec.labelIdsByName) {
      Object.assign(thread.labelIdsByName, spec.labelIdsByName);
    }
    if (spec.labels) {
      spec.labels.forEach((name) => {
        ensureLabel(name, thread.labelIdsByName[name]);
        if (thread.labelNames.indexOf(name) === -1) {
          thread.labelNames.push(name);
        }
      });
    }
    if (spec.removeLabelError) {
      thread.removeLabelError = spec.removeLabelError;
    }
    if (spec.addLabelError) {
      thread.addLabelError = spec.addLabelError;
    }
    if (spec.getLabelsError) {
      thread.getLabelsError = spec.getLabelsError;
    }
  }

  (settings.drafts || []).forEach(addDraft);
  if (settings.sendLabelExists !== false) {
    ensureLabel("Send in 5");
  }
  if (settings.failedLabelExists) {
    ensureLabel("Send failed");
  }

  const context = {
    Date: FixedDate,
    JSON,
    Object,
    Math,
    Number,
    String,
    Error,
    isFinite,
    isNaN,
    Logger: {
      log(template, ...values) {
        logs.push(values.length === 0 ? String(template) : formatLog(template, values));
      },
    },
    PropertiesService: {
      getScriptProperties() {
        return {
          getProperty(key) {
            if (settings.propertiesGetError) {
              throw new Error(settings.propertiesGetError);
            }
            return Object.prototype.hasOwnProperty.call(properties, key) ? properties[key] : null;
          },
          setProperty(key, value) {
            if (settings.propertiesSetError) {
              throw new Error(settings.propertiesSetError);
            }
            properties[key] = String(value);
          },
          deleteProperty(key) {
            delete properties[key];
          },
        };
      },
    },
    LockService: {
      getScriptLock() {
        return {
          tryLock(waitMilliseconds) {
            serviceCalls.push("tryLock:" + waitMilliseconds);
            if (settings.lockHeld) {
              return false;
            }
            return true;
          },
          releaseLock() {
            serviceCalls.push("releaseLock");
          },
        };
      },
    },
    ScriptApp: {
      newTrigger(handlerName) {
        const built = { handlerName, intervalMinutes: null };
        return {
          timeBased() {
            return {
              everyMinutes(intervalMinutes) {
                built.intervalMinutes = intervalMinutes;
                return {
                  create() {
                    triggers.push({
                      id: "trigger-" + nextTriggerId,
                      handlerName,
                      intervalMinutes,
                    });
                    nextTriggerId += 1;
                    return built;
                  },
                };
              },
            };
          },
        };
      },
      getProjectTriggers() {
        return triggers.map((trigger) => ({
          getHandlerFunction() {
            return trigger.handlerName;
          },
          getUniqueId() {
            return trigger.id;
          },
        }));
      },
      deleteTrigger(trigger) {
        const id = trigger.getUniqueId();
        const index = triggers.findIndex((item) => item.id === id);
        if (index !== -1) {
          triggers.splice(index, 1);
        }
      },
    },
    GmailApp: {
      getUserLabelByName(name) {
        serviceCalls.push("getUserLabelByName:" + name);
        if (settings.labelLookupError) {
          throw new Error(settings.labelLookupError);
        }
        return labelsByName[name] || null;
      },
      createLabel(name) {
        serviceCalls.push("createLabel:" + name);
        return ensureLabel(name);
      },
      getDrafts() {
        serviceCalls.push("getDrafts");
        if (settings.getDraftsError) {
          throw new Error(settings.getDraftsError);
        }
        return Object.keys(draftSpecs)
          .filter((id) => !draftSpecs[id].gone && !draftSpecs[id].hiddenFromList)
          .map((id) => makeDraft(draftSpecs[id]));
      },
      getDraft(id) {
        serviceCalls.push("getDraft:" + id);
        const spec = draftSpecs[id];
        if (!spec || spec.gone || spec.missingOnReread) {
          throw new Error("No draft with the given ID can be found");
        }
        if (spec.dropLabelOnReread) {
          const droppedLabelName =
            spec.dropLabelOnReread === true ? "Send in 5" : spec.dropLabelOnReread;
          threadFor(spec.threadId).labelNames = threadFor(spec.threadId).labelNames.filter(
            (name) => name !== droppedLabelName
          );
        }
        if (spec.gainLabelOnReread) {
          const thread = threadFor(spec.threadId);
          if (thread.labelNames.indexOf(spec.gainLabelOnReread) === -1) {
            thread.labelNames.push(spec.gainLabelOnReread);
          }
        }
        if (spec.rereadDateMilliseconds !== undefined) {
          const reread = Object.assign({}, spec, { dateMilliseconds: spec.rereadDateMilliseconds });
          return makeDraft(reread);
        }
        return makeDraft(spec);
      },
    },
  };

  vm.createContext(context);
  vm.runInContext(code, context, { filename: "Code.gs" });

  return {
    context,
    logs,
    labelOps,
    sendCalls,
    serviceCalls,
    properties,
    triggers,
    threads,
    nowHolder,
    labelsByName,
    draftSpecs,
  };
}

function draft(partial) {
  return Object.assign(
    {
      id: "draft-1",
      threadId: "thread-1",
      messageId: "message-1",
      subject: "hello",
      dateMilliseconds: 0,
      labels: [],
      to: "recipient",
      cc: "",
      bcc: "",
    },
    partial
  );
}

function assertThrows(fn, expectedText) {
  assert.throws(fn, (error) => {
    assert.match(String(error.message), expectedText);
    return true;
  });
}

function labelNames(world, threadId) {
  return world.threads[threadId].labelNames.slice();
}

const tests = [];
function test(name, fn) {
  tests.push({ name, fn });
}

test("an unlabeled draft sends after 5 minutes and a recent edit waits", () => {
  const now = 1_700_000_000_000;
  const ready = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now - FIVE_MINUTES_MS, subject: "ready", labels: [] })],
  });
  ready.context.sendDraftsAfterDelay();
  assert.deepEqual(ready.sendCalls, ["draft-1"]);
  assert.deepEqual(labelNames(ready, "thread-1"), []);
  assert.equal(ready.properties.delayedSendHeldDrafts, undefined);
  assert.equal(ready.properties.delayedSendReleasedAt, undefined);
  assert.ok(ready.logs.some((line) => line.indexOf("Sent draft. id=draft-1 subject=ready") !== -1));

  const young = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ id: "draft-young", dateMilliseconds: now - FIVE_MINUTES_MS + 1, labels: [] })],
  });
  young.context.sendDraftsAfterDelay();
  assert.deepEqual(young.sendCalls, []);
  assert.deepEqual(labelNames(young, "thread-1"), []);
  assert.ok(young.logs.some((line) => line.indexOf("Waiting to send draft") !== -1));
});

test("a future message date waits", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now + 60_000, labels: [] })],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.deepEqual(labelNames(world, "thread-1"), []);
});

test("a missing or invalid date parks the draft and does not send", () => {
  const world = createWorld({
    nowMilliseconds: 1_700_000_000_000,
    drafts: [
      draft({ id: "draft-bad", missingDate: true, threadId: "thread-bad" }),
      draft({ id: "draft-invalid", invalidDate: true, threadId: "thread-invalid" }),
      draft({
        id: "draft-next",
        threadId: "thread-next",
        dateMilliseconds: 1_700_000_000_000 - FIVE_MINUTES_MS,
        subject: "next",
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-next"]);
  assert.deepEqual(labelNames(world, "thread-bad"), ["Send failed"]);
  assert.deepEqual(labelNames(world, "thread-invalid"), ["Send failed"]);
  assert.deepEqual(labelNames(world, "thread-next"), []);
});

test("label removal failure after send does not send again", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Send in 5"],
        removeLabelError: "label backend down",
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
  assert.equal(world.draftSpecs["draft-1"].gone, true);
  assert.ok(world.logs.some((line) => line.indexOf("removing the label failed") !== -1));
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
});

test("a recent edit on re-read waits", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        rereadDateMilliseconds: now - 1000,
        labels: ["Send in 5"],
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.deepEqual(labelNames(world, "thread-1"), ["Send in 5"]);
  assert.ok(world.logs.some((line) => line.indexOf("stage=recheck") !== -1));
});

test("adding Hold before send cancels it", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        gainLabelOnReread: "Hold",
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.ok(world.logs.some((line) => line.indexOf("gained Hold") !== -1));
  assert.deepEqual(labelNames(world, "thread-1"), ["Hold"]);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
});

test("removing Send in 5 before send still sends", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Send in 5"],
        dropLabelOnReread: "Send in 5",
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
  assert.equal(world.logs.some((line) => line.indexOf("lost the send label") !== -1), false);
});

test("a missing Hold label still sends an old draft", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    sendLabelExists: false,
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now - FIVE_MINUTES_MS, labels: [] })],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
  assert.ok(world.serviceCalls.indexOf("getDrafts") !== -1);
});

test("install creates Hold, Release, and Send failed and one one-minute trigger", () => {
  const world = createWorld({
    sendLabelExists: false,
    triggers: [{ id: "old", handlerName: "sendLabeledDraftsAfterDelay" }],
  });
  world.context.installDelayedGmailSend();
  assert.ok(world.labelsByName["Hold"]);
  assert.ok(world.labelsByName["Release"]);
  assert.ok(world.labelsByName["Send failed"]);
  assert.equal(world.labelsByName["Send in 5"], undefined);
  assert.equal(world.triggers.length, 1);
  assert.equal(world.triggers[0].handlerName, "sendDraftsAfterDelay");
  assert.equal(world.triggers[0].intervalMinutes, 1);
  world.context.installDelayedGmailSend();
  assert.equal(world.triggers.length, 1);
  assert.equal(world.serviceCalls.filter((call) => call === "createLabel:Hold").length, 1);
  assert.equal(world.serviceCalls.filter((call) => call === "createLabel:Release").length, 1);
  assert.equal(world.serviceCalls.filter((call) => call === "createLabel:Send failed").length, 1);
  assert.equal(world.serviceCalls.filter((call) => call === "createLabel:Send in 5").length, 0);
  assert.equal(world.properties.delayedSendHoldLabelId, "id:Hold");
  assert.equal(world.properties.delayedSendReleaseLabelId, "id:Release");
  assert.equal(world.properties.delayedSendSendFailedLabelId, "id:Send failed");
});

test("uninstall removes the current and legacy delayed-send handlers", () => {
  const world = createWorld({
    sendLabelExists: false,
    triggers: [
      { id: "keep", handlerName: "someOtherHandler" },
      { id: "drop-new", handlerName: "sendDraftsAfterDelay" },
      { id: "drop-old", handlerName: "sendLabeledDraftsAfterDelay" },
    ],
  });
  world.context.uninstallDelayedGmailSend();
  assert.deepEqual(
    world.triggers.map((trigger) => trigger.handlerName),
    ["someOtherHandler"]
  );
});

test("a held script lock does not list or send", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    lockHeld: true,
    drafts: [draft({ dateMilliseconds: now - FIVE_MINUTES_MS })],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(world.serviceCalls.indexOf("getDrafts"), -1);
  assert.ok(world.serviceCalls.indexOf("tryLock:0") !== -1);
  assert.ok(world.logs.some((line) => line.indexOf("script lock") !== -1));
});

test("a daily recipient-quota error skips later drafts and keeps the label", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-quota",
        threadId: "thread-quota",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Send in 5"],
        sendError: "Service invoked too many times for one day: email",
      }),
      draft({
        id: "draft-later",
        threadId: "thread-later",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Send in 5"],
      }),
    ],
  });
  assertThrows(
    () => world.context.sendDraftsAfterDelay(),
    /Gmail quota reached/
  );
  assert.deepEqual(world.sendCalls, ["draft-quota"]);
  assert.deepEqual(labelNames(world, "thread-quota"), ["Send in 5"]);
  assert.deepEqual(labelNames(world, "thread-later"), ["Send in 5"]);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
});

test("quota text in a subject does not park the draft", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        subject: "too many times for one day: email",
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
  assert.deepEqual(labelNames(world, "thread-1"), []);
});

test("a non-quota send failure applies Send failed and the next draft still sends", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-bad",
        threadId: "thread-bad",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Send in 5"],
        sendError: "smtp down",
      }),
      draft({
        id: "draft-next",
        threadId: "thread-next",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-bad", "draft-next"]);
  assert.deepEqual(labelNames(world, "thread-bad"), ["Send failed"]);
  assert.deepEqual(world.labelOps, ["add:Send failed", "remove:Send in 5"]);
  assert.deepEqual(labelNames(world, "thread-next"), []);
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-bad", "draft-next"]);
});

test("gmail daily and short-time quota errors retry later", () => {
  const messages = [
    "Service invoked too many times for one day: gmail",
    "Service invoked too many times in a short time: gmail",
    "Service invoked too many times: gmail.",
    "Service invoked too many times in a short time: email.",
    "Service invoked too many times: email.",
    "Limit exceeded: Email recipients per day.",
    "Service using too much computer time for one day.",
  ];
  messages.forEach((message) => {
    const now = 1_700_000_000_000;
    const world = createWorld({
      nowMilliseconds: now,
      drafts: [
        draft({
          dateMilliseconds: now - FIVE_MINUTES_MS,
          labels: ["Send in 5"],
          sendError: message,
        }),
      ],
    });
    assertThrows(() => world.context.sendDraftsAfterDelay(), /Gmail quota reached/);
    assert.deepEqual(labelNames(world, "thread-1"), ["Send in 5"]);
    assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  });
});

test("a calendar quota error still parks the draft", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        sendError: "Service invoked too many times: calendar.",
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(labelNames(world, "thread-1"), ["Send failed"]);
});

test("a repeated quota error throws at most once per hour", () => {
  const now = 1_700_000_000_000;
  const quota = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        sendError: "Service invoked too many times for one day: gmail",
      }),
    ],
  });
  assertThrows(() => quota.context.sendDraftsAfterDelay(), /Gmail quota reached/);
  assert.equal(quota.logs.filter((line) => line.indexOf("Not throwing again") !== -1).length, 0);
  quota.context.sendDraftsAfterDelay();
  assert.ok(quota.logs.some((line) => line.indexOf("Not throwing again this hour") !== -1));
  quota.nowHolder.milliseconds = now + HOUR_MS;
  assertThrows(() => quota.context.sendDraftsAfterDelay(), /Gmail quota reached/);

  const recovered = createWorld({ nowMilliseconds: now, drafts: [] });
  recovered.properties.delayedSendPersistentFailureLatchedAt = String(now);
  recovered.context.sendDraftsAfterDelay();
  assert.equal(recovered.properties.delayedSendPersistentFailureLatchedAt, undefined);
});

test("a properties failure still throws the quota error", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    propertiesSetError: "properties down",
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        sendError: "Service invoked too many times for one day: gmail",
      }),
    ],
  });
  assertThrows(() => world.context.sendDraftsAfterDelay(), /Gmail quota reached/);
  assert.ok(world.logs.some((line) => line.indexOf("Could not update the persistent-failure latch") !== -1));
});

test("two old drafts on one thread both send and the label comes off once", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-a",
        threadId: "thread-shared",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Send in 5"],
        subject: "first",
      }),
      draft({
        id: "draft-b",
        threadId: "thread-shared",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        subject: "second",
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-a", "draft-b"]);
  assert.deepEqual(labelNames(world, "thread-shared"), []);
  assert.equal(
    world.labelOps.filter((op) => op === "remove:Send in 5").length,
    1
  );
});

test("a younger draft on the same thread keeps the label after the older one sends", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-old",
        threadId: "thread-shared",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Send in 5"],
      }),
      draft({
        id: "draft-young",
        threadId: "thread-shared",
        dateMilliseconds: now - 1000,
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-old"]);
  assert.deepEqual(labelNames(world, "thread-shared"), ["Send in 5"]);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.equal(world.labelOps.indexOf("remove:Send in 5"), -1);
});

test("a failed draft is not parked while a sibling is still waiting", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-bad",
        threadId: "thread-shared",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Send in 5"],
        sendError: "smtp down",
      }),
      draft({
        id: "draft-young",
        threadId: "thread-shared",
        dateMilliseconds: now - 1000,
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(labelNames(world, "thread-shared"), ["Send in 5"]);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.ok(
    world.logs.some((line) => line.indexOf("Another draft on the thread is still waiting") !== -1)
  );
});

test("legacy label removal failure after parking still leaves Send failed", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Send in 5"],
        sendError: "smtp down",
        removeLabelError: "remove failed",
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(labelNames(world, "thread-1"), ["Send in 5", "Send failed"]);
  assert.ok(
    world.logs.some(
      (line) => line.indexOf("Send failed is applied, but removing the legacy label failed") !== -1
    )
  );
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
});

test("failure to apply Send failed does not resend", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Send in 5"],
        sendError: "smtp down",
        addLabelError: "add failed",
        subject: "error-subject",
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(labelNames(world, "thread-1"), ["Send in 5"]);
  assert.ok(
    world.logs.some((line) => line.indexOf("Could not apply the failure label") !== -1)
  );
  assert.ok(
    world.logs.some(
      (line) =>
        line.indexOf("Delayed send failed for one draft") !== -1 &&
        line.indexOf("subject=error-subject") !== -1
    )
  );
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
  assert.deepEqual(labelNames(world, "thread-1"), ["Send in 5"]);
  assert.ok(
    world.logs.some((line) => line === "Not sending again after a failed send. id=draft-1")
  );
});

test("a deleted draft is canceled and the next draft still sends", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-gone",
        threadId: "thread-gone",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Send in 5"],
        missingOnReread: true,
      }),
      draft({
        id: "draft-next",
        threadId: "thread-next",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-next"]);
  assert.deepEqual(labelNames(world, "thread-gone"), ["Send in 5"]);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.ok(world.logs.some((line) => line === "Draft deleted before send. id=draft-gone"));
  assert.deepEqual(labelNames(world, "thread-next"), []);
});

test("a sent draft and a failed sibling on one thread are parked together", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-sent",
        threadId: "thread-shared",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
      draft({
        id: "draft-bad",
        threadId: "thread-shared",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        sendError: "smtp down",
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-sent", "draft-bad"]);
  assert.deepEqual(labelNames(world, "thread-shared"), ["Send failed"]);
});

test("a quota error on a later thread still clears the label on a thread that already sent", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-sent",
        threadId: "thread-sent",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Send in 5"],
      }),
      draft({
        id: "draft-quota",
        threadId: "thread-quota",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Send in 5"],
        sendError: "Service invoked too many times for one day: gmail",
      }),
    ],
  });
  assertThrows(() => world.context.sendDraftsAfterDelay(), /Gmail quota reached/);
  assert.deepEqual(labelNames(world, "thread-sent"), []);
  assert.deepEqual(labelNames(world, "thread-quota"), ["Send in 5"]);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
});

test("subject is captured before send so a post-send subject read cannot skip label removal", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Send in 5"],
        subject: "captured",
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.ok(world.logs.some((line) => line.indexOf("subject=captured") !== -1));
  assert.deepEqual(labelNames(world, "thread-1"), []);
});

test("everyMinutes 2 is rejected and 1 and 5 are allowed", () => {
  const world = createWorld({ sendLabelExists: false });
  assertThrows(
    () => world.context.assertTriggerIntervalMinutes_(2),
    /1, 5, 10, 15, or 30/
  );
  world.context.assertTriggerIntervalMinutes_(1);
  world.context.assertTriggerIntervalMinutes_(5);
});

test("draft-only threads still send when a label thread list would be empty", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now - FIVE_MINUTES_MS, labels: ["Send in 5"] })],
  });
  world.context.GmailApp.getUserLabelByName = function getUserLabelByName(name) {
    const label = world.labelsByName[name] || null;
    if (!label) {
      return null;
    }
    return {
      getName() {
        return name;
      },
      getThreads() {
        throw new Error("label.getThreads must not be the draft list");
      },
    };
  };
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
});

test("a shared thread reads labels once during the scan", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-a",
        threadId: "thread-shared",
        labels: [],
        dateMilliseconds: now - 1000,
      }),
      draft({
        id: "draft-b",
        threadId: "thread-shared",
        labels: [],
        dateMilliseconds: now - 1000,
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(
    world.serviceCalls.filter((call) => call === "getLabels:thread-shared").length,
    1
  );
  assert.ok(world.logs.some((line) => line.indexOf("Waiting to send draft. stage=listed id=draft-a") !== -1));
  assert.ok(world.logs.some((line) => line.indexOf("Waiting to send draft. stage=listed id=draft-b") !== -1));
});

test("a listed draft is not read twice before the age check", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now - 1000 })],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(
    world.serviceCalls.filter((call) => call === "getMessage:draft-1"),
    ["getMessage:draft-1"]
  );
});

test("an empty draft list writes nothing", () => {
  const world = createWorld({ drafts: [] });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.logs, []);
  assert.deepEqual(world.sendCalls, []);
});

test("getDrafts quota is retry-later and does not park", () => {
  const world = createWorld({
    getDraftsError: "Service invoked too many times in a short time: gmail",
    drafts: [draft()],
  });
  assertThrows(() => world.context.sendDraftsAfterDelay(), /Gmail quota reached/);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  world.context.sendDraftsAfterDelay();
  assert.ok(world.logs.some((line) => line.indexOf("Not throwing again this hour") !== -1));
});

test("a Hold draft never sends", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-held",
        threadId: "thread-held",
        dateMilliseconds: 0,
        labels: ["Hold"],
      }),
      draft({
        id: "draft-same-thread",
        threadId: "thread-held",
        dateMilliseconds: 0,
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.ok(world.logs.some((line) => line.indexOf("Holding draft. id=draft-held") !== -1));
  assert.ok(world.logs.some((line) => line.indexOf("Holding draft. id=draft-same-thread") !== -1));
});

test("removing Hold on an unchanged draft starts a 5 minute release clock", () => {
  const now = 1_700_000_000_000;
  const oldEnough = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now - FIVE_MINUTES_MS, labels: ["Hold"] })],
  });
  oldEnough.context.sendDraftsAfterDelay();
  assert.deepEqual(oldEnough.sendCalls, []);
  assert.equal(
    JSON.parse(oldEnough.properties.delayedSendHeldDrafts)["draft-1"],
    "message-1"
  );
  oldEnough.threads["thread-1"].labelNames = oldEnough.threads["thread-1"].labelNames.filter(
    (name) => name !== "Hold"
  );
  oldEnough.context.sendDraftsAfterDelay();
  assert.deepEqual(oldEnough.sendCalls, []);
  assert.equal(oldEnough.properties.delayedSendHeldDrafts, undefined);
  assert.equal(JSON.parse(oldEnough.properties.delayedSendReleasedAt)["draft-1"], now);
  assert.ok(
    oldEnough.logs.some((line) => line === "Hold removed. Release clock started. id=draft-1")
  );
  assert.equal(oldEnough.labelOps.indexOf("add:Send failed"), -1);
  oldEnough.nowHolder.milliseconds = now + FIVE_MINUTES_MS - 1;
  oldEnough.context.sendDraftsAfterDelay();
  assert.deepEqual(oldEnough.sendCalls, []);
  oldEnough.nowHolder.milliseconds = now + FIVE_MINUTES_MS;
  oldEnough.context.sendDraftsAfterDelay();
  assert.deepEqual(oldEnough.sendCalls, ["draft-1"]);
  assert.equal(oldEnough.properties.delayedSendReleasedAt, undefined);
  assert.equal(oldEnough.properties.delayedSendHeldDrafts, undefined);

  const recent = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ id: "draft-recent", dateMilliseconds: now - 1000, labels: ["Hold"] })],
  });
  recent.threads["thread-1"].labelNames = recent.threads["thread-1"].labelNames.filter(
    (name) => name !== "Hold"
  );
  recent.context.sendDraftsAfterDelay();
  assert.deepEqual(recent.sendCalls, []);
  assert.equal(recent.properties.delayedSendReleasedAt, undefined);
  assert.ok(recent.logs.some((line) => line.indexOf("Waiting to send draft") !== -1));
});

test("a Send failed draft is skipped", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-parked",
        threadId: "thread-parked",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Send failed"],
      }),
      draft({
        id: "draft-sibling",
        threadId: "thread-parked",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.deepEqual(labelNames(world, "thread-parked"), ["Send failed"]);
  assert.ok(world.logs.indexOf("Skipping draft on Send failed. id=draft-parked") !== -1);
  assert.ok(world.logs.indexOf("Skipping draft on Send failed. id=draft-sibling") !== -1);
  const firstRunLength = world.logs.length;
  world.context.sendDraftsAfterDelay();
  assert.equal(world.logs.length, firstRunLength);
  assert.equal(
    world.logs.filter((line) => line.indexOf("Skipping draft on Send failed") !== -1).length,
    2
  );
});

test("removing Send failed lets an old draft send", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Send failed"],
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  world.threads["thread-1"].labelNames = [];
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
});

test("a draft with no recipient is parked and the next draft still sends", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-empty",
        threadId: "thread-empty",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        to: "",
        cc: "",
        bcc: "",
      }),
      draft({
        id: "draft-blank",
        threadId: "thread-blank",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        to: "  ",
        cc: " ",
        bcc: "\t",
      }),
      draft({
        id: "draft-next",
        threadId: "thread-next",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-next"]);
  assert.deepEqual(labelNames(world, "thread-empty"), ["Send failed"]);
  assert.deepEqual(labelNames(world, "thread-blank"), ["Send failed"]);
  assert.ok(world.logs.some((line) => line.indexOf("id=draft-empty") !== -1 && line.indexOf("Draft has no recipient") !== -1));
  assert.ok(world.logs.some((line) => line.indexOf("id=draft-blank") !== -1 && line.indexOf("Draft has no recipient") !== -1));
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-next"]);
});

test("a draft with an empty To and a Cc or Bcc still sends", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-cc",
        threadId: "thread-cc",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        to: "",
        cc: "cc-recipient",
      }),
      draft({
        id: "draft-bcc",
        threadId: "thread-bcc",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        to: "",
        bcc: "bcc-recipient",
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-cc", "draft-bcc"]);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
});

test("a reply draft on an existing thread sends after 5 minutes", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-reply",
        threadId: "thread-existing",
        subject: "Re: hello",
        to: "recipient",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-reply"]);
  assert.ok(world.logs.some((line) => line.indexOf("subject=Re: hello") !== -1));
});

test("Hold matches a nested, recased, or renamed label by stored id", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-nested",
        threadId: "thread-nested",
        messageId: "message-nested",
        subject: "nested-subject",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Parent/Hold"],
        labelIdsByName: { "Parent/Hold": "id:Hold" },
      }),
      draft({
        id: "draft-recase",
        threadId: "thread-recase",
        messageId: "message-recase",
        subject: "recase-subject",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["hold"],
        labelIdsByName: { hold: "id:Hold" },
      }),
      draft({
        id: "draft-renamed",
        threadId: "thread-renamed",
        messageId: "message-renamed",
        subject: "renamed-subject",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Kept"],
        labelIdsByName: { Kept: "id:Hold" },
      }),
      draft({
        id: "draft-parked",
        threadId: "thread-parked",
        messageId: "message-parked",
        subject: "parked-subject",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Parked"],
        labelIdsByName: { Parked: "id:Send failed" },
      }),
      draft({
        id: "draft-open",
        threadId: "thread-open",
        messageId: "message-open",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
    ],
  });
  world.properties.delayedSendHoldLabelId = "id:Hold";
  world.properties.delayedSendSendFailedLabelId = "id:Send failed";
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-open"]);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.equal(
    world.logs.filter((line) => line.indexOf("nested-subject") !== -1).length,
    0
  );
  assert.equal(
    world.logs.filter((line) => line.indexOf("recase-subject") !== -1).length,
    0
  );
  assert.equal(
    world.logs.filter((line) => line.indexOf("renamed-subject") !== -1).length,
    0
  );
  assert.ok(world.logs.indexOf("Skipping draft on Send failed. id=draft-parked") !== -1);
  assert.equal(
    world.logs.filter((line) => line.indexOf("parked-subject") !== -1).length,
    0
  );
});

test("a missing label id is stored from the exact name on the first run", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Hold"],
      }),
    ],
  });
  assert.equal(world.properties.delayedSendHoldLabelId, undefined);
  world.context.sendDraftsAfterDelay();
  assert.equal(world.properties.delayedSendHoldLabelId, "id:Hold");
  assert.deepEqual(world.sendCalls, []);
});

test("a getLabels blip does not park the thread", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        getLabelsError: "Service error: Gmail",
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.ok(world.logs.some((line) => line.indexOf("Service error: Gmail") !== -1));
  assert.ok(world.logs.some((line) => line.indexOf("will retry") !== -1));
  world.threads["thread-1"].getLabelsError = null;
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
});

test("a failed send is not retried while a sibling is still young", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-bad",
        threadId: "thread-shared",
        messageId: "message-bad",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        sendError: "smtp down",
      }),
      draft({
        id: "draft-young",
        threadId: "thread-shared",
        messageId: "message-young",
        dateMilliseconds: now - 1000,
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-bad"]);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.equal(
    world.properties.delayedSendFailedSendByDraftId,
    JSON.stringify({ "draft-bad": "message-bad" })
  );
  world.nowHolder.milliseconds = now + 60_000;
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-bad"]);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.ok(
    world.logs.some((line) => line === "Not sending again after a failed send. id=draft-bad")
  );
  world.nowHolder.milliseconds = now + FIVE_MINUTES_MS;
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-bad", "draft-young"]);
  assert.deepEqual(labelNames(world, "thread-shared"), ["Send failed"]);
  assert.equal(world.properties.delayedSendFailedSendByDraftId, undefined);
  world.threads["thread-shared"].labelNames = [];
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-bad", "draft-young", "draft-bad"]);
});

test("an edited draft clears the failed-send record and uses the normal clock", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-bad",
        threadId: "thread-shared",
        messageId: "message-bad",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        sendError: "smtp down",
      }),
      draft({
        id: "draft-young",
        threadId: "thread-shared",
        messageId: "message-young",
        dateMilliseconds: now - 1000,
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  world.draftSpecs["draft-bad"].messageId = "message-edited";
  world.draftSpecs["draft-bad"].dateMilliseconds = now + 60_000 - 1000;
  world.nowHolder.milliseconds = now + 60_000;
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-bad"]);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.ok(
    world.logs.some(
      (line) => line === "Cleared failed-send record after the draft changed. id=draft-bad"
    )
  );
  world.nowHolder.milliseconds = now + 60_000 + FIVE_MINUTES_MS;
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-bad", "draft-bad", "draft-young"]);
});

test("an interrupted send record blocks a resend", () => {
  const now = 1_700_000_000_000;
  const sent = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        messageId: "message-1",
      }),
    ],
  });
  sent.context.sendDraftsAfterDelay();
  assert.equal(
    sent.draftSpecs["draft-1"].inFlightAtSend,
    JSON.stringify({
      draftId: "draft-1",
      messageId: "message-1",
      startedAt: now,
    })
  );
  assert.equal(sent.properties.delayedSendInFlightSend, undefined);

  const blocked = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        messageId: "message-1",
        labels: ["Send in 5"],
      }),
    ],
  });
  blocked.properties.delayedSendInFlightSend = JSON.stringify({
    draftId: "draft-1",
    messageId: "message-1",
    startedAt: now - 60_000,
  });
  blocked.context.sendDraftsAfterDelay();
  assert.deepEqual(blocked.sendCalls, []);
  assert.deepEqual(labelNames(blocked, "thread-1"), ["Send failed"]);
  assert.ok(
    blocked.logs.some((line) => line === "possible interrupted send, check Sent. id=draft-1")
  );
  assert.equal(blocked.properties.delayedSendInFlightSend, undefined);
  blocked.context.sendDraftsAfterDelay();
  assert.deepEqual(blocked.sendCalls, []);
});

test("held and waiting log lines have no subject", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-held",
        threadId: "thread-held",
        subject: "secret-hold-subject",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Hold"],
      }),
      draft({
        id: "draft-young",
        threadId: "thread-young",
        subject: "secret-wait-subject",
        dateMilliseconds: now - 1000,
      }),
      draft({
        id: "draft-sent",
        threadId: "thread-sent",
        subject: "visible-subject",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  world.context.sendDraftsAfterDelay();
  const repeating = world.logs.filter(
    (line) => line.indexOf("Holding draft") !== -1 || line.indexOf("Waiting to send draft") !== -1
  );
  assert.ok(repeating.length >= 2);
  repeating.forEach((line) => {
    assert.equal(line.indexOf("subject="), -1);
    assert.equal(line.indexOf("secret-hold-subject"), -1);
    assert.equal(line.indexOf("secret-wait-subject"), -1);
  });
  assert.ok(
    world.logs.some((line) => line.indexOf("Sent draft. id=draft-sent subject=visible-subject") !== -1)
  );
});

test("an edit that drops Hold is re-applied and the draft stays held", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        messageId: "message-1",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Hold"],
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.equal(JSON.parse(world.properties.delayedSendHeldDrafts)["draft-1"], "message-1");
  world.draftSpecs["draft-1"].messageId = "message-2";
  world.draftSpecs["draft-1"].dateMilliseconds = now - FIVE_MINUTES_MS;
  world.threads["thread-1"].labelNames = [];
  world.nowHolder.milliseconds = now + 60_000;
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.deepEqual(labelNames(world, "thread-1"), ["Hold"]);
  assert.equal(JSON.parse(world.properties.delayedSendHeldDrafts)["draft-1"], "message-2");
  assert.equal(world.properties.delayedSendReleasedAt, undefined);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.ok(
    world.logs.some(
      (line) => line === "Re-applied Hold after an edit dropped it. id=draft-1"
    )
  );
});

test("removing Hold and editing in the same minute stays held", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        messageId: "message-1",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Hold"],
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  world.draftSpecs["draft-1"].messageId = "message-2";
  world.threads["thread-1"].labelNames = [];
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.deepEqual(labelNames(world, "thread-1"), ["Hold"]);
  assert.equal(JSON.parse(world.properties.delayedSendHeldDrafts)["draft-1"], "message-2");
  assert.equal(world.properties.delayedSendReleasedAt, undefined);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
});

test("a sibling stays held when another draft's edit drops Hold", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-edited",
        threadId: "thread-shared",
        messageId: "message-edited",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Hold"],
      }),
      draft({
        id: "draft-sibling",
        threadId: "thread-shared",
        messageId: "message-sibling",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  world.draftSpecs["draft-edited"].messageId = "message-edited-2";
  world.threads["thread-shared"].labelNames = [];
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.deepEqual(labelNames(world, "thread-shared"), ["Hold"]);
  const held = JSON.parse(world.properties.delayedSendHeldDrafts);
  assert.equal(held["draft-edited"], "message-edited-2");
  assert.equal(held["draft-sibling"], "message-sibling");
  assert.equal(world.properties.delayedSendReleasedAt, undefined);
});

test("a Release label wins over Hold and starts the release clock", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Hold", "Release"],
      }),
    ],
  });
  world.properties.delayedSendHeldDrafts = JSON.stringify({ "draft-1": "message-old" });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.deepEqual(labelNames(world, "thread-1"), []);
  assert.equal(world.properties.delayedSendHeldDrafts, undefined);
  assert.equal(JSON.parse(world.properties.delayedSendReleasedAt)["draft-1"], now);
  assert.ok(world.logs.some((line) => line === "Release label wins. id=draft-1"));
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.equal(world.labelOps.indexOf("add:Hold"), -1);
  world.nowHolder.milliseconds = now + FIVE_MINUTES_MS - 1;
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  world.nowHolder.milliseconds = now + FIVE_MINUTES_MS;
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
  assert.equal(world.properties.delayedSendReleasedAt, undefined);
});

test("Release added before send starts the release clock", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        gainLabelOnReread: "Release",
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(labelNames(world, "thread-1").indexOf("Release"), -1);
  assert.equal(JSON.parse(world.properties.delayedSendReleasedAt)["draft-1"], now);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
});

test("deleted draft ids are pruned from sticky Hold", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        messageId: "message-1",
        dateMilliseconds: now - 1000,
        labels: ["Hold"],
      }),
    ],
  });
  world.properties.delayedSendHeldDrafts = JSON.stringify({
    "draft-1": "message-1",
    "draft-gone": "message-gone",
  });
  world.properties.delayedSendReleasedAt = JSON.stringify({
    "draft-ghost": now - 1000,
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(JSON.parse(world.properties.delayedSendHeldDrafts), {
    "draft-1": "message-1",
  });
  assert.equal(world.properties.delayedSendReleasedAt, undefined);
  assert.deepEqual(world.sendCalls, []);

  const empty = createWorld({ drafts: [] });
  empty.properties.delayedSendHeldDrafts = JSON.stringify({ "draft-gone": "message-gone" });
  empty.properties.delayedSendReleasedAt = JSON.stringify({ "draft-gone": now });
  empty.context.sendDraftsAfterDelay();
  assert.equal(empty.properties.delayedSendHeldDrafts, undefined);
  assert.equal(empty.properties.delayedSendReleasedAt, undefined);
  assert.deepEqual(empty.logs, []);
});

test("the release clock blocks an old draft until 5 minutes after release", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now - HOUR_MS, labels: [] })],
  });
  world.properties.delayedSendReleasedAt = JSON.stringify({
    "draft-1": now - FIVE_MINUTES_MS + 1,
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.ok(world.logs.some((line) => line.indexOf("stage=release") !== -1));
  world.nowHolder.milliseconds = now + 1;
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
  assert.equal(world.properties.delayedSendReleasedAt, undefined);
  assert.equal(world.properties.delayedSendHeldDrafts, undefined);
});

test("a failed Hold re-apply stays held and is retried without Send failed", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        messageId: "message-1",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Hold"],
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  world.draftSpecs["draft-1"].messageId = "message-2";
  world.threads["thread-1"].labelNames = [];
  world.threads["thread-1"].addLabelError = "label backend down";
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.deepEqual(labelNames(world, "thread-1"), []);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.equal(JSON.parse(world.properties.delayedSendHeldDrafts)["draft-1"], "message-1");
  assert.ok(
    world.logs.some((line) => line === "Could not re-apply Hold. Staying held. id=draft-1")
  );
  world.threads["thread-1"].addLabelError = null;
  world.nowHolder.milliseconds = now + FIVE_MINUTES_MS;
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.deepEqual(labelNames(world, "thread-1"), ["Hold"]);
  assert.equal(JSON.parse(world.properties.delayedSendHeldDrafts)["draft-1"], "message-2");
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
});

test("pre-send recheck holds a sticky draft after Hold is gone", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        messageId: "message-2",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: [],
      }),
    ],
  });
  const listed = world.context.GmailApp.getDrafts()[0];
  const sticky = {
    held: { "draft-1": "message-1" },
    releasedAt: {},
    readable: true,
    originalHeldJson: null,
    originalReleasedJson: null,
  };
  const result = world.context.sendDraftIfOldEnough_(
    {
      draft: listed,
      draftId: "draft-1",
      message: listed.getMessage(),
      threadId: "thread-1",
      outcome: "pending",
      sentMessage: null,
    },
    FIVE_MINUTES_MS,
    now,
    { holdId: null, sendFailedId: null, releaseId: null },
    sticky
  );
  assert.equal(result.outcome, "held");
  assert.deepEqual(world.sendCalls, []);
  assert.deepEqual(labelNames(world, "thread-1"), ["Hold"]);
  assert.equal(sticky.held["draft-1"], "message-2");
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);

  const sameMessage = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        messageId: "message-1",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: [],
      }),
    ],
  });
  const sameListed = sameMessage.context.GmailApp.getDrafts()[0];
  const sameSticky = {
    held: { "draft-1": "message-1" },
    releasedAt: {},
    readable: true,
    originalHeldJson: null,
    originalReleasedJson: null,
  };
  const sameResult = sameMessage.context.sendDraftIfOldEnough_(
    {
      draft: sameListed,
      draftId: "draft-1",
      message: sameListed.getMessage(),
      threadId: "thread-1",
      outcome: "pending",
      sentMessage: null,
    },
    FIVE_MINUTES_MS,
    now,
    { holdId: null, sendFailedId: null, releaseId: null },
    sameSticky
  );
  assert.equal(sameResult.outcome, "held");
  assert.deepEqual(sameMessage.sendCalls, []);
  assert.equal(sameSticky.releasedAt["draft-1"], undefined);
  assert.deepEqual(labelNames(sameMessage, "thread-1"), ["Hold"]);
});

test("a sticky map over the property cap drops extras and logs", () => {
  const now = 1_700_000_000_000;
  const held = {};
  const drafts = [];
  for (let index = 0; index < 200; index += 1) {
    const draftId = "draft-" + String(index).padStart(3, "0");
    held[draftId] = "message-" + String(index).padStart(3, "0") + "x".repeat(80);
    drafts.push(
      draft({
        id: draftId,
        threadId: "thread-" + draftId,
        messageId: held[draftId],
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Hold"],
      })
    );
  }
  const world = createWorld({ nowMilliseconds: now, drafts: drafts });
  world.properties.delayedSendHeldDrafts = JSON.stringify(held);
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.ok(world.properties.delayedSendHeldDrafts.length <= 7000);
  assert.ok(
    world.logs.some((line) => line.indexOf("Dropped sticky Hold entry over the property cap") !== -1)
  );
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.ok(world.properties.delayedSendHeldDrafts.indexOf("draft-000") !== -1);
});

test("the old handler name still runs one pass", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now - FIVE_MINUTES_MS, labels: [] })],
  });
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
});

let failed = 0;
for (const entry of tests) {
  try {
    entry.fn();
    process.stdout.write("ok " + entry.name + "\n");
  } catch (error) {
    failed += 1;
    process.stderr.write("FAIL " + entry.name + "\n" + error.stack + "\n");
  }
}
if (failed > 0) {
  process.stderr.write(failed + " failed\n");
  process.exit(1);
}
process.stdout.write("all assertions passed\n");
