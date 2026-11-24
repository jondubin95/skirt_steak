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
  if (settings.leaveUnarmed !== true) {
    properties.delayedSendArmedVersion = "2";
  }
  const cacheStore = {};
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
        const names = thread.perMessage ? unionMessageLabels_(thread) : thread.labelNames;
        return names.map((name) => ensureLabel(name, thread.labelIdsByName[name]));
      },
      addLabel(label) {
        labelOps.push("add:" + label.getName());
        if (thread.addLabelError) {
          throw new Error(thread.addLabelError);
        }
        if (thread.perMessage) {
          Object.keys(thread.messageLabels).forEach((messageId) => {
            if (thread.messageLabels[messageId].indexOf(label.getName()) === -1) {
              thread.messageLabels[messageId].push(label.getName());
            }
          });
          syncUnionLabelNames_(thread);
          return;
        }
        if (thread.labelNames.indexOf(label.getName()) === -1) {
          thread.labelNames.push(label.getName());
        }
      },
      removeLabel(label) {
        labelOps.push("remove:" + label.getName());
        const namedError =
          thread.removeLabelErrorsByName && thread.removeLabelErrorsByName[label.getName()];
        if (namedError) {
          throw new Error(namedError);
        }
        if (thread.removeLabelError) {
          throw new Error(thread.removeLabelError);
        }
        if (thread.perMessage) {
          Object.keys(thread.messageLabels).forEach((messageId) => {
            thread.messageLabels[messageId] = thread.messageLabels[messageId].filter(
              (name) => name !== label.getName()
            );
          });
          syncUnionLabelNames_(thread);
          return;
        }
        thread.labelNames = thread.labelNames.filter((name) => name !== label.getName());
      },
      labelNames: [],
      labelIdsByName: {},
      messageLabels: {},
      perMessage: false,
      getLabelsError: null,
      addLabelError: null,
      removeLabelError: null,
      removeLabelErrorsByName: null,
    };
    threads[threadId] = thread;
    return thread;
  }

  function threadFor(threadId) {
    return threads[threadId] || makeThread(threadId);
  }

  function unionMessageLabels_(thread) {
    const names = [];
    Object.keys(thread.messageLabels).forEach((messageId) => {
      thread.messageLabels[messageId].forEach((name) => {
        if (names.indexOf(name) === -1) {
          names.push(name);
        }
      });
    });
    return names;
  }

  function syncUnionLabelNames_(thread) {
    thread.labelNames = unionMessageLabels_(thread);
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

  function makeDraft(spec, useListedSnapshot) {
    let consumed = false;
    let message = null;
    function viewMessageId() {
      if (useListedSnapshot && spec.listedMessageId) {
        return spec.listedMessageId;
      }
      return spec.messageId;
    }
    function viewDateMilliseconds() {
      if (useListedSnapshot && spec.listedDateMilliseconds !== undefined) {
        return spec.listedDateMilliseconds;
      }
      return spec.dateMilliseconds;
    }
    return {
      getId() {
        if (spec.getIdError) {
          throw new Error(spec.getIdError);
        }
        return spec.id;
      },
      getMessageId() {
        return viewMessageId();
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
          message = makeMessage(
            Object.assign({}, spec, {
              messageId: viewMessageId(),
              dateMilliseconds: viewDateMilliseconds(),
            }),
            false
          );
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
    if (spec.removeLabelErrorsByName) {
      thread.removeLabelErrorsByName = Object.assign(
        {},
        thread.removeLabelErrorsByName,
        spec.removeLabelErrorsByName
      );
    }
    if (spec.messageLabels) {
      thread.perMessage = true;
      thread.messageLabels[spec.messageId] = spec.messageLabels.slice();
      spec.messageLabels.forEach((name) => {
        ensureLabel(name, thread.labelIdsByName[name]);
      });
      syncUnionLabelNames_(thread);
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
            if (settings.failSetPropertyKeys && settings.failSetPropertyKeys[key]) {
              throw new Error("set failed " + key);
            }
            properties[key] = String(value);
          },
          setProperties(values) {
            if (settings.propertiesSetError) {
              throw new Error(settings.propertiesSetError);
            }
            Object.keys(values).forEach((key) => {
              properties[key] = String(values[key]);
            });
          },
          getProperties() {
            if (settings.propertiesGetError) {
              throw new Error(settings.propertiesGetError);
            }
            const copy = {};
            Object.keys(properties).forEach((key) => {
              copy[key] = properties[key];
            });
            return copy;
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
    CacheService: {
      getScriptCache() {
        if (settings.cacheDisabled) {
          throw new Error("cache down");
        }
        return {
          get(key) {
            const entry = cacheStore[key];
            if (!entry) {
              return null;
            }
            if (entry.expiresAt <= nowHolder.milliseconds) {
              delete cacheStore[key];
              return null;
            }
            return entry.value;
          },
          put(key, value, expirationSeconds) {
            const seconds = expirationSeconds || 600;
            cacheStore[key] = {
              value: String(value),
              expiresAt: nowHolder.milliseconds + seconds * 1000,
            };
          },
          remove(key) {
            delete cacheStore[key];
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
      getUserLabels() {
        serviceCalls.push("getUserLabels");
        if (settings.getUserLabelsError) {
          throw new Error(settings.getUserLabelsError);
        }
        return Object.keys(labelsById).map((id) => labelsById[id]);
      },
      getDrafts() {
        serviceCalls.push("getDrafts");
        if (settings.getDraftsError) {
          throw new Error(settings.getDraftsError);
        }
        return Object.keys(draftSpecs)
          .filter((id) => !draftSpecs[id].gone && !draftSpecs[id].hiddenFromList)
          .map((id) => makeDraft(draftSpecs[id], true));
      },
      getDraft(id) {
        serviceCalls.push("getDraft:" + id);
        const spec = draftSpecs[id];
        if (settings.confirmMissingError && (!spec || spec.gone)) {
          throw new Error(settings.confirmMissingError);
        }
        if (!spec || spec.gone || spec.missingOnReread) {
          throw new Error("No draft with the given ID can be found");
        }
        if (spec.rereadError) {
          throw new Error(spec.rereadError);
        }
        if (spec.dropLabelOnReread) {
          const droppedLabelName =
            spec.dropLabelOnReread === true ? "Send in 5" : spec.dropLabelOnReread;
          const thread = threadFor(spec.threadId);
          if (thread.perMessage) {
            Object.keys(thread.messageLabels).forEach((messageId) => {
              thread.messageLabels[messageId] = thread.messageLabels[messageId].filter(
                (name) => name !== droppedLabelName
              );
            });
            syncUnionLabelNames_(thread);
          } else {
            thread.labelNames = thread.labelNames.filter((name) => name !== droppedLabelName);
          }
        }
        if (spec.gainLabelOnReread) {
          const thread = threadFor(spec.threadId);
          if (thread.perMessage) {
            Object.keys(thread.messageLabels).forEach((messageId) => {
              if (thread.messageLabels[messageId].indexOf(spec.gainLabelOnReread) === -1) {
                thread.messageLabels[messageId].push(spec.gainLabelOnReread);
              }
            });
            syncUnionLabelNames_(thread);
          } else if (thread.labelNames.indexOf(spec.gainLabelOnReread) === -1) {
            thread.labelNames.push(spec.gainLabelOnReread);
          }
        }
        if (spec.rereadDateMilliseconds !== undefined) {
          const reread = Object.assign({}, spec, { dateMilliseconds: spec.rereadDateMilliseconds });
          return makeDraft(reread, false);
        }
        return makeDraft(spec, false);
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
    labelsById,
    draftSpecs,
    ensureLabel,
    addDraft,
    settings,
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
  assert.ok(world.labelsByName["Release now"]);
  assert.ok(world.labelsByName["Send failed"]);
  assert.equal(world.labelsByName["Send in 5"], undefined);
  assert.equal(world.triggers.length, 1);
  assert.equal(world.triggers[0].handlerName, "sendDraftsAfterDelay");
  assert.equal(world.triggers[0].intervalMinutes, 1);
  world.context.installDelayedGmailSend();
  assert.equal(world.triggers.length, 1);
  assert.equal(world.serviceCalls.filter((call) => call === "createLabel:Hold").length, 1);
  assert.equal(world.serviceCalls.filter((call) => call === "createLabel:Release now").length, 1);
  assert.equal(world.serviceCalls.filter((call) => call === "createLabel:Send failed").length, 1);
  assert.equal(world.serviceCalls.filter((call) => call === "createLabel:Send in 5").length, 0);
  assert.equal(world.properties.delayedSendHoldLabelId, "id:Hold");
  assert.equal(world.properties.delayedSendReleaseNowLabelId, "id:Release now");
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

test("a properties failure before send does not call send", () => {
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
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.ok(world.logs.some((line) => line.indexOf("in-flight record was not stored") !== -1));
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
  assert.equal(JSON.parse(oldEnough.properties.delayedSendHeldDrafts)["draft-1"], "message-1");
  assert.equal(oldEnough.properties.delayedSendReleasedAt, undefined);
  assert.equal(
    JSON.parse(oldEnough.properties.delayedSendReleaseSeenOnce)["draft-1"],
    "message-1"
  );
  assert.ok(
    oldEnough.logs.some(
      (line) => line === "Hold removal seen once. Waiting for another pass. id=draft-1"
    )
  );
  oldEnough.context.sendDraftsAfterDelay();
  assert.deepEqual(oldEnough.sendCalls, []);
  assert.equal(oldEnough.properties.delayedSendHeldDrafts, "{}");
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
  assert.equal(oldEnough.properties.delayedSendReleasedAt, "{}");
  assert.equal(oldEnough.properties.delayedSendHeldDrafts, "{}");

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
        labels: ["Hold", "Release now"],
        labelIdsByName: { "Release now": "id:Release now" },
      }),
    ],
  });
  world.properties.delayedSendHeldDrafts = JSON.stringify({ "draft-1": "message-old" });
  world.properties.delayedSendReleaseNowLabelId = "id:Release now";
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.deepEqual(labelNames(world, "thread-1"), []);
  assert.equal(world.properties.delayedSendHeldDrafts, "{}");
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
  assert.equal(world.properties.delayedSendReleasedAt, "{}");
});

test("Release added before send starts the release clock", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        gainLabelOnReread: "Release now",
        labelIdsByName: { "Release now": "id:Release now" },
      }),
    ],
  });
  world.properties.delayedSendReleaseNowLabelId = "id:Release now";
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(labelNames(world, "thread-1").indexOf("Release now"), -1);
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
  assert.equal(JSON.parse(world.properties.delayedSendHeldDrafts)["draft-gone"], "message-gone");
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(JSON.parse(world.properties.delayedSendHeldDrafts), {
    "draft-1": "message-1",
  });
  assert.equal(world.properties.delayedSendReleasedAt, "{}");
  assert.deepEqual(world.sendCalls, []);

  const empty = createWorld({ drafts: [] });
  empty.properties.delayedSendHeldDrafts = JSON.stringify({ "draft-gone": "message-gone" });
  empty.properties.delayedSendReleasedAt = JSON.stringify({ "draft-gone": now });
  empty.context.sendDraftsAfterDelay();
  assert.equal(JSON.parse(empty.properties.delayedSendHeldDrafts)["draft-gone"], "message-gone");
  empty.context.sendDraftsAfterDelay();
  assert.equal(empty.properties.delayedSendHeldDrafts, "{}");
  assert.equal(empty.properties.delayedSendReleasedAt, "{}");
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
  assert.equal(world.properties.delayedSendReleasedAt, "{}");
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
  assertThrows(
    () => world.context.sendDraftsAfterDelay(),
    /Could not re-apply Hold/
  );
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

test("pre-send recheck holds a draft that gains Hold and retries a read error", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        messageId: "message-1",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        gainLabelOnReread: "Hold",
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(JSON.parse(world.properties.delayedSendHeldDrafts)["draft-1"], "message-1");
  assert.ok(world.logs.some((line) => line.indexOf("Draft gained Hold before send") !== -1));
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);

  const retry = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        messageId: "message-1",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        rereadError: "Service error: Gmail",
      }),
    ],
  });
  retry.context.sendDraftsAfterDelay();
  assert.deepEqual(retry.sendCalls, []);
  assert.equal(retry.labelOps.indexOf("add:Send failed"), -1);
  assert.equal(retry.properties.delayedSendHeldDrafts, undefined);
  assert.ok(retry.logs.some((line) => line.indexOf("will retry") !== -1));
});

test("a sticky map over one property shards instead of dropping a live hold", () => {
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
  assert.equal(
    world.logs.some((line) => line.indexOf("Dropped sticky Hold entry") !== -1),
    false
  );
  const storedHeld = {};
  Object.keys(world.properties).forEach((key) => {
    if (key === "delayedSendHeldDrafts" || key.indexOf("delayedSendHeldDraftsShard") === 0) {
      Object.assign(storedHeld, JSON.parse(world.properties[key]));
    }
  });
  assert.equal(Object.keys(storedHeld).length, 200);
  assert.equal(storedHeld["draft-199"], held["draft-199"]);
  world.draftSpecs["draft-199"].messageId = "message-edited";
  world.threads["thread-draft-199"].labelNames = [];
  world.nowHolder.milliseconds = now + 60_000;
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  const afterEdit = {};
  Object.keys(world.properties).forEach((key) => {
    if (key === "delayedSendHeldDrafts" || key.indexOf("delayedSendHeldDraftsShard") === 0) {
      Object.assign(afterEdit, JSON.parse(world.properties[key]));
    }
  });
  assert.equal(afterEdit["draft-199"], "message-edited");
});

function storedHeldMap(world) {
  const storedHeld = {};
  Object.keys(world.properties).forEach((key) => {
    if (key === "delayedSendHeldDrafts" || key.indexOf("delayedSendHeldDraftsShard") === 0) {
      Object.assign(storedHeld, JSON.parse(world.properties[key]));
    }
  });
  return storedHeld;
}

test("a stale draft list does not treat an edit as a Hold removal", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        messageId: "message-2",
        listedMessageId: "message-1",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: [],
      }),
    ],
  });
  world.properties.delayedSendHeldDrafts = JSON.stringify({ "draft-1": "message-1" });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.deepEqual(labelNames(world, "thread-1"), ["Hold"]);
  assert.equal(storedHeldMap(world)["draft-1"], "message-2");
  assert.equal(world.properties.delayedSendReleasedAt, undefined);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
});

test("a missing-draft error during the scan does not forget a held draft", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-held",
        threadId: "thread-shared",
        messageId: "message-held",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: [],
        messageError: "Requested entity was not found.",
      }),
      draft({
        id: "draft-sibling",
        threadId: "thread-shared",
        messageId: "message-sibling",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: [],
      }),
    ],
  });
  world.properties.delayedSendHeldDrafts = JSON.stringify({
    "draft-held": "message-held",
    "draft-sibling": "message-sibling",
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(storedHeldMap(world)["draft-held"], "message-held");
  assert.equal(storedHeldMap(world)["draft-sibling"], "message-sibling");
  assert.equal(world.properties.delayedSendReleasedAt, undefined);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
});

test("a partial scan does not start a release clock", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-kept",
        threadId: "thread-shared",
        messageId: "message-kept",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: [],
      }),
      draft({
        id: "draft-quota",
        threadId: "thread-other",
        messageId: "message-quota",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        messageError: "Service invoked too many times for one day: gmail",
      }),
    ],
  });
  world.properties.delayedSendHeldDrafts = JSON.stringify({
    "draft-kept": "message-kept",
  });
  assertThrows(() => world.context.sendDraftsAfterDelay(), /Gmail quota reached/);
  assert.deepEqual(world.sendCalls, []);
  assert.equal(storedHeldMap(world)["draft-kept"], "message-kept");
  assert.equal(world.properties.delayedSendReleasedAt, undefined);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.equal(world.labelOps.indexOf("add:Hold"), -1);
});

test("a kill after Hold is seen keeps the held entry", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-held",
        threadId: "thread-held",
        messageId: "message-held",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Hold"],
      }),
      draft({
        id: "draft-open",
        threadId: "thread-open",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
    ],
  });
  const originalLog = world.context.Logger.log;
  world.context.Logger.log = function logUntilHold(template, ...values) {
    originalLog(template, ...values);
    const line = values.length === 0 ? String(template) : formatLog(template, values);
    if (line.indexOf("Holding draft. id=draft-held") !== -1) {
      assert.equal(storedHeldMap(world)["draft-held"], "message-held");
      throw new Error("execution killed");
    }
  };
  assertThrows(() => world.context.sendDraftsAfterDelay(), /execution killed/);
  assert.equal(storedHeldMap(world)["draft-held"], "message-held");
  world.context.Logger.log = originalLog;
  world.draftSpecs["draft-held"].messageId = "message-held-2";
  world.threads["thread-held"].labelNames = [];
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-open"]);
  assert.equal(storedHeldMap(world)["draft-held"], "message-held-2");
  assert.deepEqual(labelNames(world, "thread-held"), ["Hold"]);
});

test("a failed sticky write does not send and leaves Hold in place", () => {
  const now = 1_700_000_000_000;
  const options = {
    nowMilliseconds: now,
    propertiesSetError: "properties down",
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Hold"],
      }),
    ],
  };
  const world = createWorld(options);
  assertThrows(() => world.context.sendDraftsAfterDelay(), /Could not store sticky Hold state/);
  assert.deepEqual(world.sendCalls, []);
  assert.deepEqual(labelNames(world, "thread-1"), ["Hold"]);
  assert.equal(world.properties.delayedSendHeldDrafts, undefined);
  options.propertiesSetError = null;
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(storedHeldMap(world)["draft-1"], "message-1");
});

test("sticky overflow holds every draft and an edit does not send", () => {
  const now = 1_700_000_000_000;
  const drafts = [
    draft({
      id: "draft-open",
      threadId: "thread-open",
      messageId: "message-open",
      dateMilliseconds: now - FIVE_MINUTES_MS,
      labels: [],
    }),
  ];
  for (let index = 0; index < 260; index += 1) {
    const draftId = "d" + String(index).padStart(4, "0");
    drafts.push(
      draft({
        id: draftId,
        threadId: "thread-" + draftId,
        messageId: "m" + "x".repeat(900),
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Hold"],
      })
    );
  }
  const world = createWorld({ nowMilliseconds: now, drafts: drafts });
  assertThrows(
    () => world.context.sendDraftsAfterDelay(),
    /Sticky Hold state does not fit/
  );
  assert.deepEqual(world.sendCalls, []);
  assert.equal(world.properties.delayedSendStickyOverflow, "1");
  world.draftSpecs["d0000"].messageId = "m-edited";
  world.threads["thread-d0000"].labelNames = [];
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
});

test("Release on a multi-draft thread starts the clock for every draft", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-a",
        threadId: "thread-shared",
        messageId: "message-a",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Hold", "Release now"],
        labelIdsByName: { "Release now": "id:Release now" },
      }),
      draft({
        id: "draft-b",
        threadId: "thread-shared",
        messageId: "message-b",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
    ],
  });
  world.properties.delayedSendReleaseNowLabelId = "id:Release now";
  world.properties.delayedSendHeldDrafts = JSON.stringify({
    "draft-a": "message-old-a",
    "draft-b": "message-old-b",
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  const releasedAt = JSON.parse(world.properties.delayedSendReleasedAt);
  assert.equal(releasedAt["draft-a"], now);
  assert.equal(releasedAt["draft-b"], now);
  assert.equal(world.properties.delayedSendHeldDrafts, "{}");
  world.nowHolder.milliseconds = now + FIVE_MINUTES_MS;
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-a", "draft-b"]);
});

test("Release added before send on a multi-draft thread does not send the sibling", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-a",
        threadId: "thread-shared",
        messageId: "message-a",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        gainLabelOnReread: "Release now",
        labelIdsByName: { "Release now": "id:Release now" },
      }),
      draft({
        id: "draft-b",
        threadId: "thread-shared",
        messageId: "message-b",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
    ],
  });
  world.properties.delayedSendReleaseNowLabelId = "id:Release now";
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  const releasedAt = JSON.parse(world.properties.delayedSendReleasedAt);
  assert.equal(releasedAt["draft-a"], now);
  assert.equal(releasedAt["draft-b"], now);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
});

test("install after a rename keeps the stored label ids", () => {
  const world = createWorld({ sendLabelExists: false });
  world.ensureLabel("Kept", "Label_1");
  world.ensureLabel("Parked", "Label_failed");
  world.ensureLabel("Go", "Label_release");
  world.properties.delayedSendHoldLabelId = "Label_1";
  world.properties.delayedSendSendFailedLabelId = "Label_failed";
  world.properties.delayedSendReleaseNowLabelId = "Label_release";
  world.context.installDelayedGmailSend();
  assert.equal(world.properties.delayedSendHoldLabelId, "Label_1");
  assert.equal(world.properties.delayedSendSendFailedLabelId, "Label_failed");
  assert.equal(world.properties.delayedSendReleaseNowLabelId, "id:Release now");
  assert.equal(world.labelsByName["Hold"], undefined);
  assert.ok(world.labelsByName["Release now"]);
  assert.notEqual(world.properties.delayedSendReleaseNowLabelId, "Label_release");
});

test("re-applying Hold after a rename uses the stored label", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        messageId: "message-1",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Kept"],
        labelIdsByName: { Kept: "Label_1" },
      }),
    ],
  });
  world.ensureLabel("Kept", "Label_1");
  world.properties.delayedSendHoldLabelId = "Label_1";
  world.context.sendDraftsAfterDelay();
  world.draftSpecs["draft-1"].messageId = "message-2";
  world.threads["thread-1"].labelNames = [];
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.deepEqual(labelNames(world, "thread-1"), ["Kept"]);
  assert.equal(world.labelsByName["Hold"], undefined);
  assert.equal(storedHeldMap(world)["draft-1"], "message-2");
  assert.equal(world.serviceCalls.filter((call) => call === "createLabel:Hold").length, 0);
});

test("install does not adopt a pre-existing Release now label", () => {
  const world = createWorld({ sendLabelExists: false });
  world.ensureLabel("Release now", "user-release");
  world.context.installDelayedGmailSend();
  assert.notEqual(world.properties.delayedSendReleaseNowLabelId, "user-release");
  assert.equal(
    world.properties.delayedSendReleaseNowLabelId,
    "id:Release now (delayed send)"
  );
  assert.equal(world.labelsById["user-release"].getName(), "Release now");
  assert.ok(world.labelsByName["Release now (delayed send)"]);
});

test("corrupt sticky state throws and does not send", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now - FIVE_MINUTES_MS })],
  });
  world.properties.delayedSendHeldDrafts = "{not json";
  assertThrows(() => world.context.sendDraftsAfterDelay(), /Could not read sticky Hold state/);
  assert.deepEqual(world.sendCalls, []);
  assert.equal(world.properties.delayedSendHeldDrafts, "{not json");
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.ok(world.logs.some((line) => line.indexOf("Not throwing again this hour") !== -1));
  assert.equal(world.properties.delayedSendHeldDrafts, "{not json");
});

test("a Release label that cannot be removed does not send or reset the clock", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - HOUR_MS,
        labels: ["Hold", "Release now"],
        labelIdsByName: { "Release now": "id:Release now" },
        removeLabelErrorsByName: { "Release now": "cannot remove release" },
      }),
    ],
  });
  world.properties.delayedSendReleaseNowLabelId = "id:Release now";
  assertThrows(() => world.context.sendDraftsAfterDelay(), /Could not remove Release now/);
  assert.deepEqual(world.sendCalls, []);
  assert.equal(JSON.parse(world.properties.delayedSendReleasedAt)["draft-1"], now);
  assert.ok(labelNames(world, "thread-1").indexOf("Release now") !== -1);
  assert.equal(labelNames(world, "thread-1").indexOf("Hold"), -1);
  world.nowHolder.milliseconds = now + 60_000;
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(JSON.parse(world.properties.delayedSendReleasedAt)["draft-1"], now);
  assert.ok(world.logs.some((line) => line.indexOf("Not throwing again this hour") !== -1));
});

test("a quota error while putting Hold back stops the pass", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-held",
        threadId: "thread-held",
        messageId: "message-1",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Hold"],
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  world.draftSpecs["draft-held"].messageId = "message-2";
  world.threads["thread-held"].labelNames = [];
  world.threads["thread-held"].addLabelError =
    "Service invoked too many times for one day: gmail";
  assertThrows(() => world.context.sendDraftsAfterDelay(), /Gmail quota reached/);
  assert.deepEqual(world.sendCalls, []);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.equal(storedHeldMap(world)["draft-held"], "message-1");
});

test("a missing Hold label is looked up once per hour", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now + HOUR_MS })],
  });
  world.context.sendDraftsAfterDelay();
  world.context.sendDraftsAfterDelay();
  assert.equal(
    world.serviceCalls.filter((call) => call === "getUserLabelByName:Hold").length,
    1
  );
  assert.equal(
    world.serviceCalls.filter((call) => call === "getUserLabelByName:Release now").length,
    0
  );
  world.nowHolder.milliseconds = now + HOUR_MS;
  world.context.sendDraftsAfterDelay();
  assert.equal(
    world.serviceCalls.filter((call) => call === "getUserLabelByName:Hold").length,
    2
  );
  assert.deepEqual(world.sendCalls, []);
});

test("a future release time is clamped to the pass", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now - HOUR_MS })],
  });
  world.properties.delayedSendReleasedAt = JSON.stringify({ "draft-1": now + HOUR_MS });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(JSON.parse(world.properties.delayedSendReleasedAt)["draft-1"], now);
  world.nowHolder.milliseconds = now + FIVE_MINUTES_MS;
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
});

test("a reply draft stays held while an older message still has Hold", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-reply",
        threadId: "thread-existing",
        messageId: "message-reply",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        messageLabels: [],
        labelIdsByName: { Hold: "id:Hold" },
      }),
    ],
  });
  world.ensureLabel("Hold", "id:Hold");
  world.threads["thread-existing"].messageLabels["message-old"] = ["Hold"];
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(storedHeldMap(world)["draft-reply"], "message-reply");
  world.draftSpecs["draft-reply"].messageId = "message-reply-2";
  world.threads["thread-existing"].messageLabels["message-reply-2"] = [];
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(storedHeldMap(world)["draft-reply"], "message-reply-2");
  assert.ok(world.threads["thread-existing"].messageLabels["message-old"].indexOf("Hold") !== -1);
});

test("a failed Hold restore marks an unchanged sibling pending", () => {
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
  world.threads["thread-shared"].addLabelError = "label backend down";
  assertThrows(() => world.context.sendDraftsAfterDelay(), /Could not re-apply Hold/);
  assert.equal(storedHeldMap(world)["draft-edited"], "message-edited");
  assert.equal(storedHeldMap(world)["draft-sibling"], "pending-hold-restore");
  assert.deepEqual(world.sendCalls, []);
  world.draftSpecs["draft-edited"].gone = true;
  world.threads["thread-shared"].addLabelError = null;
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(storedHeldMap(world)["draft-sibling"], "message-sibling");
  assert.deepEqual(labelNames(world, "thread-shared"), ["Hold"]);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
});

test("a draft missing from the list but still in getDraft is not pruned", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-live",
        threadId: "thread-live",
        messageId: "message-live",
        dateMilliseconds: now - 1000,
        labels: ["Hold"],
      }),
      draft({
        id: "draft-hidden",
        threadId: "thread-hidden",
        messageId: "message-hidden",
        dateMilliseconds: now - 1000,
        labels: ["Hold"],
        hiddenFromList: true,
      }),
    ],
  });
  world.properties.delayedSendHeldDrafts = JSON.stringify({
    "draft-live": "message-live",
    "draft-hidden": "message-hidden",
  });
  world.context.sendDraftsAfterDelay();
  assert.equal(storedHeldMap(world)["draft-hidden"], "message-hidden");
  assert.equal(storedHeldMap(world)["draft-live"], "message-live");
  assert.deepEqual(world.sendCalls, []);
});

test("transient getDraft errors do not prune a held draft", () => {
  const now = 1_700_000_000_000;
  const options = {
    nowMilliseconds: now,
    confirmMissingError: "Service error: Gmail",
    drafts: [draft({ id: "draft-live", dateMilliseconds: now - 1000, labels: ["Hold"] })],
  };
  const world = createWorld(options);
  world.properties.delayedSendHeldDrafts = JSON.stringify({
    "draft-live": "message-1",
    "draft-blip": "message-blip",
  });
  for (let pass = 0; pass < 5; pass += 1) {
    world.context.sendDraftsAfterDelay();
  }
  assert.equal(storedHeldMap(world)["draft-blip"], "message-blip");
  assert.equal(storedHeldMap(world)["draft-live"], "message-1");
  assert.deepEqual(world.sendCalls, []);
});

test("a draft getDraft keeps finding is not looked up forever", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-live",
        dateMilliseconds: now - 1000,
        labels: ["Hold"],
      }),
      draft({
        id: "draft-hidden",
        threadId: "thread-hidden",
        messageId: "message-hidden",
        dateMilliseconds: now - 1000,
        labels: ["Hold"],
        hiddenFromList: true,
      }),
    ],
  });
  world.properties.delayedSendHeldDrafts = JSON.stringify({
    "draft-live": "message-1",
    "draft-hidden": "message-hidden",
  });
  for (let pass = 0; pass < 59; pass += 1) {
    world.context.sendDraftsAfterDelay();
  }
  assertThrows(() => world.context.sendDraftsAfterDelay(), /getDraft still finds it/);
  const lookups = world.serviceCalls.filter((call) => call === "getDraft:draft-hidden").length;
  world.context.sendDraftsAfterDelay();
  assert.equal(
    world.serviceCalls.filter((call) => call === "getDraft:draft-hidden").length,
    lookups
  );
  assert.equal(storedHeldMap(world)["draft-hidden"], "message-hidden");
  assert.deepEqual(world.sendCalls, []);
});

test("one unreadable draft does not block another thread", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-bad",
        threadId: "thread-bad",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        getLabelsError: "Invalid argument: draft",
      }),
      draft({
        id: "draft-release",
        threadId: "thread-ok",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Release now"],
        labelIdsByName: { "Release now": "id:Release now" },
      }),
    ],
  });
  world.properties.delayedSendReleaseNowLabelId = "id:Release now";
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(JSON.parse(world.properties.delayedSendReleasedAt)["draft-release"], now);
  assert.equal(labelNames(world, "thread-ok").indexOf("Release now"), -1);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
});

test("an unread sibling keeps Release now on that thread", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-release",
        threadId: "thread-shared",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Release now"],
        labelIdsByName: { "Release now": "id:Release now" },
      }),
      draft({
        id: "draft-unread",
        threadId: "thread-shared",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        messageError: "Invalid argument: draft",
      }),
    ],
  });
  world.properties.delayedSendReleaseNowLabelId = "id:Release now";
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(world.properties.delayedSendReleasedAt, undefined);
  assert.ok(labelNames(world, "thread-shared").indexOf("Release now") !== -1);
});

test("an unreadable draft stops blocking other threads after repeated failures", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-bad",
        threadId: "thread-bad",
        messageError: "Invalid argument: draft",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
      draft({
        id: "draft-release",
        threadId: "thread-ok",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Release now"],
        labelIdsByName: { "Release now": "id:Release now" },
      }),
    ],
  });
  world.properties.delayedSendReleaseNowLabelId = "id:Release now";
  world.context.sendDraftsAfterDelay();
  world.context.sendDraftsAfterDelay();
  world.context.sendDraftsAfterDelay();
  assert.equal(world.properties.delayedSendReleasedAt, undefined);
  assert.ok(labelNames(world, "thread-ok").indexOf("Release now") !== -1);
  assertThrows(() => world.context.sendDraftsAfterDelay(), /stayed unreadable/);
  assert.equal(JSON.parse(world.properties.delayedSendReleasedAt)["draft-release"], now);
  world.context.sendDraftsAfterDelay();
  assert.ok(world.logs.some((line) => line.indexOf("Not throwing again this hour") !== -1));
});

test("Hold on one fresh read keeps every draft on the thread", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-a",
        threadId: "thread-shared",
        messageId: "message-a",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: [],
      }),
      draft({
        id: "draft-b",
        threadId: "thread-shared",
        messageId: "message-b",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: [],
      }),
    ],
  });
  world.properties.delayedSendHeldDrafts = JSON.stringify({
    "draft-a": "message-a",
    "draft-b": "message-b",
  });
  world.draftSpecs["draft-b"].listedMessageId = "message-b";
  const realGetDraft = world.context.GmailApp.getDraft;
  world.context.GmailApp.getDraft = function getDraft(id) {
    const draft = realGetDraft(id);
    if (id === "draft-b") {
      const thread = world.threads["thread-shared"];
      if (thread.labelNames.indexOf("Hold") === -1) {
        thread.labelNames.push("Hold");
      }
    }
    return draft;
  };
  world.context.sendDraftsAfterDelay();
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(world.properties.delayedSendReleasedAt, undefined);
  assert.ok(storedHeldMap(world)["draft-a"]);
  assert.ok(storedHeldMap(world)["draft-b"]);
});

test("the first removal pass holds an untracked sibling", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-tracked",
        threadId: "thread-shared",
        messageId: "message-tracked",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
      draft({
        id: "draft-new",
        threadId: "thread-shared",
        messageId: "message-new",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
    ],
  });
  world.properties.delayedSendHeldDrafts = JSON.stringify({
    "draft-tracked": "message-tracked",
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(world.properties.delayedSendReleasedAt, undefined);
  assert.ok(world.logs.some((line) => line.indexOf("Holding draft. id=draft-new") !== -1));
});

test("Send failed skips a draft even when Release now is also present", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - HOUR_MS,
        labels: ["Send failed", "Release now"],
        labelIdsByName: { "Release now": "id:Release now" },
      }),
    ],
  });
  world.properties.delayedSendReleaseNowLabelId = "id:Release now";
  world.properties.delayedSendReleasedAt = JSON.stringify({
    "draft-1": now - HOUR_MS,
  });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.ok(world.logs.some((line) => line.indexOf("Skipping draft on Send failed") !== -1));
});

test("the in-flight record is written only after the last label read", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now - FIVE_MINUTES_MS })],
  });
  const thread = world.threads["thread-1"];
  const originalGetLabels = thread.getLabels.bind(thread);
  let calls = 0;
  thread.getLabels = function getLabels() {
    calls += 1;
    if (calls > 2) {
      throw new Error("Service error: Gmail");
    }
    return originalGetLabels();
  };
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(world.properties.delayedSendInFlightSend, undefined);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.ok(world.logs.some((line) => line.indexOf("will retry") !== -1));
});

test("a stuck Release now keeps its original clock past the prune margin", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - HOUR_MS,
        labels: ["Release now"],
        labelIdsByName: { "Release now": "id:Release now" },
        removeLabelErrorsByName: { "Release now": "cannot remove release" },
      }),
    ],
  });
  world.properties.delayedSendReleaseNowLabelId = "id:Release now";
  world.properties.delayedSendReleasedAt = JSON.stringify({
    "draft-1": now - (6 * 60 * 1000),
  });
  assertThrows(() => world.context.sendDraftsAfterDelay(), /Could not remove Release now/);
  assert.equal(JSON.parse(world.properties.delayedSendReleasedAt)["draft-1"], now - 6 * 60 * 1000);
  assert.deepEqual(world.sendCalls, []);
  world.nowHolder.milliseconds = now + 60_000;
  world.context.sendDraftsAfterDelay();
  assert.equal(JSON.parse(world.properties.delayedSendReleasedAt)["draft-1"], now - 6 * 60 * 1000);
});

test("getUserLabels quota while restoring Hold does not apply Send failed", () => {
  const now = 1_700_000_000_000;
  const options = {
    nowMilliseconds: now,
    drafts: [
      draft({
        messageId: "message-1",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Hold"],
      }),
    ],
  };
  const world = createWorld(options);
  world.properties.delayedSendHoldLabelId = "id:Hold";
  world.context.sendDraftsAfterDelay();
  world.draftSpecs["draft-1"].messageId = "message-2";
  world.threads["thread-1"].labelNames = [];
  options.getUserLabelsError = "Service invoked too many times for one day: gmail";
  assertThrows(() => world.context.sendDraftsAfterDelay(), /Gmail quota reached/);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.equal(storedHeldMap(world)["draft-1"], "message-1");
});

test("a legacy Release id is not reused", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    sendLabelExists: false,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Hold", "Release"],
        labelIdsByName: { Release: "old-release" },
      }),
    ],
  });
  world.ensureLabel("Release", "old-release");
  world.properties.delayedSendReleaseLabelId = "old-release";
  world.properties.delayedSendHeldDrafts = JSON.stringify({ "draft-1": "message-old" });
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(world.properties.delayedSendReleasedAt, undefined);
  assert.ok(labelNames(world, "thread-1").indexOf("Hold") !== -1);
  world.context.installDelayedGmailSend();
  assert.equal(world.properties.delayedSendReleaseNowLabelId, "id:Release now");
  assert.notEqual(world.properties.delayedSendReleaseNowLabelId, "old-release");
});

test("Send failed is applied with the stored label id", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        sendError: "smtp down",
      }),
    ],
  });
  world.ensureLabel("Parked", "Label_failed");
  world.properties.delayedSendSendFailedLabelId = "Label_failed";
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
  assert.ok(labelNames(world, "thread-1").indexOf("Parked") !== -1);
  assert.equal(world.labelsByName["Send failed"], undefined);
});

test("a shard gap is unreadable and does not send", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now - FIVE_MINUTES_MS })],
  });
  world.properties.delayedSendStickyShardGeneration = "1";
  world.properties.delayedSendHeldDrafts = JSON.stringify({ "draft-a": "message-a" });
  world.properties.delayedSendHeldDraftsShard3Gen1 = JSON.stringify({ "draft-b": "message-b" });
  assertThrows(() => world.context.sendDraftsAfterDelay(), /Could not read sticky Hold state/);
  assert.deepEqual(world.sendCalls, []);
});

test("more shards than the maximum fail closed", () => {
  const now = 1_700_000_000_000;
  const drafts = [];
  for (let index = 0; index < 41; index += 1) {
    const draftId = "d" + String(index).padStart(2, "0");
    drafts.push(
      draft({
        id: draftId,
        threadId: "thread-" + draftId,
        messageId: "m" + "x".repeat(4000),
        dateMilliseconds: now - FIVE_MINUTES_MS,
        labels: ["Hold"],
      })
    );
  }
  const world = createWorld({ nowMilliseconds: now, drafts: drafts });
  assertThrows(
    () => world.context.sendDraftsAfterDelay(),
    /does not fit in script properties/
  );
  assert.deepEqual(world.sendCalls, []);
});

test("nothing sends until install arms this version", () => {
  const now = 1_700_000_000_000;
  const unarmed = createWorld({
    leaveUnarmed: true,
    nowMilliseconds: now,
    triggers: [{ id: "old", handlerName: "sendLabeledDraftsAfterDelay" }],
    drafts: [draft({ dateMilliseconds: now - FIVE_MINUTES_MS })],
  });
  unarmed.context.sendDraftsAfterDelay();
  unarmed.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(unarmed.sendCalls, []);
  assert.ok(unarmed.logs.some((line) => line.indexOf("not armed") !== -1));
  assert.equal(unarmed.serviceCalls.indexOf("getDrafts"), -1);

  const stale = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now - FIVE_MINUTES_MS })],
  });
  stale.properties.delayedSendArmedVersion = "1";
  stale.context.sendDraftsAfterDelay();
  assert.deepEqual(stale.sendCalls, []);

  const upgrading = createWorld({
    leaveUnarmed: true,
    sendLabelExists: false,
    triggers: [
      { id: "legacy", handlerName: "sendLabeledDraftsAfterDelay" },
      { id: "current", handlerName: "sendDraftsAfterDelay" },
    ],
  });
  upgrading.context.installDelayedGmailSend();
  assert.equal(upgrading.properties.delayedSendArmedVersion, "2");
  assert.equal(upgrading.triggers.length, 1);
  assert.equal(upgrading.triggers[0].handlerName, "sendDraftsAfterDelay");
  upgrading.context.installDelayedGmailSend();
  assert.equal(upgrading.triggers.length, 1);
});

test("a persistent fresh read failure alerts and keeps the thread held", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-tracked",
        threadId: "thread-shared",
        messageId: "message-tracked",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        rereadError: "Service error: Gmail",
      }),
      draft({
        id: "draft-sibling",
        threadId: "thread-shared",
        messageId: "message-sibling",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
    ],
  });
  world.properties.delayedSendHeldDrafts = JSON.stringify({
    "draft-tracked": "message-tracked",
  });
  world.context.sendDraftsAfterDelay();
  world.context.sendDraftsAfterDelay();
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assertThrows(() => world.context.sendDraftsAfterDelay(), /stayed unreadable/);
  assert.deepEqual(world.sendCalls, []);
  assert.ok(JSON.parse(world.properties.delayedSendStickyUnreadPasses)["fresh:draft-tracked"] > 3);
});

test("an empty sticky map is stored as an empty object", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now - 1000, labels: ["Hold"] })],
  });
  world.properties.delayedSendReleasedAt = JSON.stringify({ "draft-ghost": now - 1000 });
  world.context.sendDraftsAfterDelay();
  world.context.sendDraftsAfterDelay();
  assert.equal(world.properties.delayedSendReleasedAt, "{}");
  assert.equal(JSON.parse(world.properties.delayedSendHeldDrafts)["draft-1"], "message-1");
});

test("an old-generation shard is deleted", () => {
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
  world.properties.delayedSendStickyShardGeneration = "2";
  world.properties.delayedSendHeldDrafts = JSON.stringify({ "draft-1": "message-1" });
  world.properties.delayedSendHeldDraftsShard2Gen1 = JSON.stringify({
    "draft-old": "message-old",
  });
  world.context.sendDraftsAfterDelay();
  assert.equal(world.properties.delayedSendHeldDraftsShard2Gen1, undefined);
  assert.equal(storedHeldMap(world)["draft-old"], undefined);
  assert.equal(storedHeldMap(world)["draft-1"], "message-1");
  assert.deepEqual(world.sendCalls, []);
});

test("a failed in-flight write does not send", () => {
  const now = 1_700_000_000_000;
  const options = {
    nowMilliseconds: now,
    failSetPropertyKeys: { delayedSendInFlightSend: true },
    drafts: [draft({ dateMilliseconds: now - FIVE_MINUTES_MS })],
  };
  const world = createWorld(options);
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.ok(world.logs.some((line) => line.indexOf("in-flight record was not stored") !== -1));
  options.failSetPropertyKeys = null;
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
});

test("a successful scan resets the unavailable-draft counter", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-bad",
        threadId: "thread-bad",
        dateMilliseconds: now - 1000,
        getIdError: "Invalid argument: id",
      }),
      draft({
        id: "draft-open",
        threadId: "thread-open",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
    ],
  });
  world.context.sendDraftsAfterDelay();
  world.context.sendDraftsAfterDelay();
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  world.draftSpecs["draft-bad"].getIdError = null;
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-open"]);
  assert.equal(JSON.parse(world.properties.delayedSendStickyUnreadPasses || "{}")["unavailable-draft"], undefined);
  world.draftSpecs["draft-bad"].getIdError = "Invalid argument: id";
  world.context.sendDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-open"]);
  assert.equal(JSON.parse(world.properties.delayedSendStickyUnreadPasses)["unavailable-draft"], 1);
});

test("a listed draft clears its unlisted cooldown", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now - 1000, labels: ["Hold"] })],
  });
  world.properties.delayedSendStickyUnlistedFound = JSON.stringify({
    "draft-1": now + HOUR_MS,
  });
  world.context.sendDraftsAfterDelay();
  assert.equal(world.properties.delayedSendStickyUnlistedFound, "{}");
});

test("the cache-down alert window covers a longer trigger", () => {
  assert.equal(worldMinuteWindow(0, 1), true);
  assert.equal(worldMinuteWindow(2, 1), false);
  assert.equal(worldMinuteWindow(2, 5), true);
  assert.equal(worldMinuteWindow(7, 5), false);
  assert.equal(worldMinuteWindow(29, 30), true);
  assert.equal(worldMinuteWindow(40, 30), false);

  const minuteMs = 60 * 1000;
  const base = 1_700_000_000_000;
  const minuteOfHour = Math.floor(base / minuteMs) % 60;
  const minuteZero = base - minuteOfHour * minuteMs;
  const inside = createWorld({
    cacheDisabled: true,
    nowMilliseconds: minuteZero,
    getDraftsError: "Service invoked too many times for one day: gmail",
    drafts: [draft()],
  });
  assertThrows(() => inside.context.sendDraftsAfterDelay(), /Gmail quota reached/);
  const outside = createWorld({
    cacheDisabled: true,
    nowMilliseconds: minuteZero + 2 * minuteMs,
    getDraftsError: "Service invoked too many times for one day: gmail",
    drafts: [draft()],
  });
  outside.context.sendDraftsAfterDelay();
  assert.ok(outside.logs.some((line) => line.indexOf("Not throwing again this hour") !== -1));
  assert.deepEqual(outside.sendCalls, []);
});

function worldMinuteWindow(minuteOfHour, intervalMinutes) {
  const now = minuteOfHour * 60 * 1000;
  const world = createWorld({ leaveUnarmed: true, nowMilliseconds: now });
  return world.context.minuteFallsInPersistentFailureWindow_(now, intervalMinutes);
}

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
