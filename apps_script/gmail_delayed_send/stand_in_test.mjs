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
  const threads = {};
  const draftSpecs = {};

  function ensureLabel(name) {
    if (!labelsByName[name]) {
      labelsByName[name] = {
        getName() {
          return name;
        },
      };
    }
    return labelsByName[name];
  }

  function makeThread(threadId) {
    const thread = {
      getId() {
        return threadId;
      },
      getLabels() {
        serviceCalls.push("getLabels:" + threadId);
        return thread.labelNames.map((name) => ensureLabel(name));
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
    if (spec.labels) {
      spec.labels.forEach((name) => {
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
          tryLock() {
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
        if (spec.rereadDateMilliseconds !== undefined) {
          const reread = Object.assign({}, spec, { dateMilliseconds: spec.rereadDateMilliseconds });
          if (spec.dropLabelOnReread) {
            threadFor(spec.threadId).labelNames = threadFor(spec.threadId).labelNames.filter(
              (name) => name !== "Send in 5"
            );
          }
          return makeDraft(reread);
        }
        if (spec.dropLabelOnReread) {
          threadFor(spec.threadId).labelNames = threadFor(spec.threadId).labelNames.filter(
            (name) => name !== "Send in 5"
          );
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
      labels: ["Send in 5"],
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

test("exactly five minutes sends and one millisecond under waits", () => {
  const now = 1_700_000_000_000;
  const ready = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now - FIVE_MINUTES_MS, subject: "ready" })],
  });
  ready.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(ready.sendCalls, ["draft-1"]);
  assert.deepEqual(labelNames(ready, "thread-1"), []);
  assert.ok(ready.logs.some((line) => line.indexOf("Sent draft. id=draft-1 subject=ready") !== -1));

  const young = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ id: "draft-young", dateMilliseconds: now - FIVE_MINUTES_MS + 1 })],
  });
  young.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(young.sendCalls, []);
  assert.deepEqual(labelNames(young, "thread-1"), ["Send in 5"]);
  assert.ok(young.logs.some((line) => line.indexOf("Waiting to send draft") !== -1));
});

test("a future message date waits", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now + 60_000 })],
  });
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.deepEqual(labelNames(world, "thread-1"), ["Send in 5"]);
});

test("a missing or invalid date parks the draft and does not send", () => {
  const world = createWorld({
    nowMilliseconds: 1_700_000_000_000,
    drafts: [
      draft({ id: "draft-bad", missingDate: true, threadId: "thread-bad" }),
      draft({
        id: "draft-next",
        threadId: "thread-next",
        dateMilliseconds: 1_700_000_000_000 - FIVE_MINUTES_MS,
        subject: "next",
      }),
    ],
  });
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-next"]);
  assert.deepEqual(labelNames(world, "thread-bad"), ["Send failed"]);
  assert.deepEqual(labelNames(world, "thread-next"), []);
});

test("label removal failure after send does not send again", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        removeLabelError: "label backend down",
      }),
    ],
  });
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
  assert.equal(world.draftSpecs["draft-1"].gone, true);
  assert.ok(world.logs.some((line) => line.indexOf("removing the label failed") !== -1));
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
});

test("a younger re-read cancels the send", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        rereadDateMilliseconds: now - 1000,
      }),
    ],
  });
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.deepEqual(labelNames(world, "thread-1"), ["Send in 5"]);
  assert.ok(world.logs.some((line) => line.indexOf("stage=recheck") !== -1));
});

test("removing the label before send cancels it", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        dropLabelOnReread: true,
      }),
    ],
  });
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.ok(world.logs.some((line) => line.indexOf("lost the send label") !== -1));
  assert.deepEqual(labelNames(world, "thread-1"), []);
});

test("a missing label does not list drafts", () => {
  const world = createWorld({ sendLabelExists: false, drafts: [draft()] });
  assertThrows(
    () => world.context.sendLabeledDraftsAfterDelay(),
    /Delayed send label not found: Send in 5/
  );
  assert.equal(world.serviceCalls.indexOf("getDrafts"), -1);
});

test("install creates both labels and one one-minute trigger", () => {
  const world = createWorld({ sendLabelExists: false });
  world.context.installDelayedGmailSend();
  assert.ok(world.labelsByName["Send in 5"]);
  assert.ok(world.labelsByName["Send failed"]);
  assert.equal(world.triggers.length, 1);
  assert.equal(world.triggers[0].handlerName, "sendLabeledDraftsAfterDelay");
  assert.equal(world.triggers[0].intervalMinutes, 1);
  world.context.installDelayedGmailSend();
  assert.equal(world.triggers.length, 1);
  assert.equal(
    world.serviceCalls.filter((call) => call === "createLabel:Send in 5").length,
    1
  );
});

test("uninstall removes only the delayed-send handler", () => {
  const world = createWorld({
    sendLabelExists: false,
    triggers: [
      { id: "keep", handlerName: "someOtherHandler" },
      { id: "drop", handlerName: "sendLabeledDraftsAfterDelay" },
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
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(world.serviceCalls.indexOf("getDrafts"), -1);
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
        sendError: "Service invoked too many times for one day: email",
      }),
      draft({
        id: "draft-later",
        threadId: "thread-later",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
    ],
  });
  assertThrows(
    () => world.context.sendLabeledDraftsAfterDelay(),
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
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
  assert.deepEqual(labelNames(world, "thread-1"), []);
});

test("a non-quota send failure removes Send in 5 before applying Send failed", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-bad",
        threadId: "thread-bad",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        sendError: "smtp down",
      }),
      draft({
        id: "draft-next",
        threadId: "thread-next",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
    ],
  });
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-bad", "draft-next"]);
  assert.deepEqual(labelNames(world, "thread-bad"), ["Send failed"]);
  assert.deepEqual(world.labelOps.filter((op) => op.indexOf("thread") === -1).slice(0, 2), [
    "remove:Send in 5",
    "add:Send failed",
  ]);
  assert.deepEqual(labelNames(world, "thread-next"), []);
});

test("gmail daily and short-time quota errors retry later", () => {
  const messages = [
    "Service invoked too many times for one day: gmail",
    "Service invoked too many times in a short time: gmail",
    "Service invoked too many times: gmail.",
    "Service invoked too many times in a short time: email.",
    "Service invoked too many times: email.",
    "Limit exceeded: Email recipients per day.",
  ];
  messages.forEach((message) => {
    const now = 1_700_000_000_000;
    const world = createWorld({
      nowMilliseconds: now,
      drafts: [
        draft({
          dateMilliseconds: now - FIVE_MINUTES_MS,
          sendError: message,
        }),
      ],
    });
    assertThrows(() => world.context.sendLabeledDraftsAfterDelay(), /Gmail quota reached/);
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
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(labelNames(world, "thread-1"), ["Send failed"]);
});

test("a repeated quota or missing label throws at most once per hour", () => {
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
  assertThrows(() => quota.context.sendLabeledDraftsAfterDelay(), /Gmail quota reached/);
  assert.equal(quota.logs.filter((line) => line.indexOf("Not throwing again") !== -1).length, 0);
  quota.context.sendLabeledDraftsAfterDelay();
  assert.ok(quota.logs.some((line) => line.indexOf("Not throwing again this hour") !== -1));
  quota.nowHolder.milliseconds = now + HOUR_MS;
  assertThrows(() => quota.context.sendLabeledDraftsAfterDelay(), /Gmail quota reached/);

  const missing = createWorld({ sendLabelExists: false, nowMilliseconds: now });
  assertThrows(() => missing.context.sendLabeledDraftsAfterDelay(), /label not found/);
  missing.context.sendLabeledDraftsAfterDelay();
  assert.ok(missing.logs.some((line) => line.indexOf("Not throwing again this hour") !== -1));
  assert.equal(missing.serviceCalls.filter((call) => call === "getDrafts").length, 0);

  const recovered = createWorld({ nowMilliseconds: now, drafts: [] });
  recovered.properties.delayedSendPersistentFailureLatchedAt = String(now);
  recovered.context.sendLabeledDraftsAfterDelay();
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
  assertThrows(() => world.context.sendLabeledDraftsAfterDelay(), /Gmail quota reached/);
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
  world.context.sendLabeledDraftsAfterDelay();
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
      }),
      draft({
        id: "draft-young",
        threadId: "thread-shared",
        dateMilliseconds: now - 1000,
      }),
    ],
  });
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-old"]);
  assert.deepEqual(labelNames(world, "thread-shared"), ["Send in 5"]);
  assert.ok(world.logs.some((line) => line.indexOf("Another labeled draft still needs it") !== -1));
});

test("a failed draft is not parked while a sibling still needs the label", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-bad",
        threadId: "thread-shared",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        sendError: "smtp down",
      }),
      draft({
        id: "draft-young",
        threadId: "thread-shared",
        dateMilliseconds: now - 1000,
      }),
    ],
  });
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(labelNames(world, "thread-shared"), ["Send in 5"]);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.ok(world.logs.some((line) => line.indexOf("Another labeled draft still needs it") !== -1));
});

test("remove failure during parking leaves Send in 5 and skips Send failed", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        sendError: "smtp down",
        removeLabelError: "remove failed",
      }),
    ],
  });
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(labelNames(world, "thread-1"), ["Send in 5"]);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  assert.ok(
    world.logs.some((line) => line.indexOf("Could not remove the send label after a failed send") !== -1)
  );
});

test("add failure during parking still leaves Send in 5 removed", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        dateMilliseconds: now - FIVE_MINUTES_MS,
        sendError: "smtp down",
        addLabelError: "add failed",
      }),
    ],
  });
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(labelNames(world, "thread-1"), []);
  assert.ok(
    world.logs.some((line) =>
      line.indexOf("Removed the send label but could not apply the failure label") !== -1
    )
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
        missingOnReread: true,
      }),
      draft({
        id: "draft-next",
        threadId: "thread-next",
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
    ],
  });
  world.context.sendLabeledDraftsAfterDelay();
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
  world.context.sendLabeledDraftsAfterDelay();
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
      }),
      draft({
        id: "draft-quota",
        threadId: "thread-quota",
        dateMilliseconds: now - FIVE_MINUTES_MS,
        sendError: "Service invoked too many times for one day: gmail",
      }),
    ],
  });
  assertThrows(() => world.context.sendLabeledDraftsAfterDelay(), /Gmail quota reached/);
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
        subject: "captured",
      }),
    ],
  });
  world.context.sendLabeledDraftsAfterDelay();
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
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, ["draft-1"]);
});

test("a shared thread reads labels once", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [
      draft({
        id: "draft-a",
        threadId: "thread-shared",
        labels: [],
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
      draft({
        id: "draft-b",
        threadId: "thread-shared",
        labels: [],
        dateMilliseconds: now - FIVE_MINUTES_MS,
      }),
    ],
  });
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(world.sendCalls, []);
  assert.equal(
    world.serviceCalls.filter((call) => call === "getLabels:thread-shared").length,
    1
  );
  assert.equal(world.logs.length, 0);
});

test("a listed labeled draft is not read twice before the age check", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ dateMilliseconds: now - 1000 })],
  });
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(
    world.serviceCalls.filter((call) => call === "getMessage:draft-1"),
    ["getMessage:draft-1"]
  );
});

test("an unlabeled pass writes nothing", () => {
  const now = 1_700_000_000_000;
  const world = createWorld({
    nowMilliseconds: now,
    drafts: [draft({ labels: [], dateMilliseconds: now - FIVE_MINUTES_MS })],
  });
  world.context.sendLabeledDraftsAfterDelay();
  assert.deepEqual(world.logs, []);
  assert.deepEqual(world.sendCalls, []);
});

test("getDrafts quota is retry-later and does not park", () => {
  const world = createWorld({
    getDraftsError: "Service invoked too many times in a short time: gmail",
    drafts: [draft()],
  });
  assertThrows(() => world.context.sendLabeledDraftsAfterDelay(), /Gmail quota reached/);
  assert.equal(world.labelOps.indexOf("add:Send failed"), -1);
  world.context.sendLabeledDraftsAfterDelay();
  assert.ok(world.logs.some((line) => line.indexOf("Not throwing again this hour") !== -1));
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
