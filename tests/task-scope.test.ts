import assert from "node:assert/strict";
import test from "node:test";
import { createTaskScope } from "../src/task-scope.ts";

test("stopping a scope releases pending animation waits and runs cleanup once", async () => {
  const scope = createTaskScope();
  let cleaned = 0;
  scope.register(() => { cleaned += 1; });
  const waiting = scope.sleep(60_000);

  scope.stop();
  scope.stop();
  await waiting;
  assert.equal(cleaned, 1);
});

test("a stopped scope immediately cleans up new work and never waits", async () => {
  const scope = createTaskScope();
  scope.stop();
  let cleaned = false;
  scope.register(() => { cleaned = true; });

  await scope.sleep(60_000);
  assert.equal(cleaned, true);
});

test("completed work can unregister its cleanup", () => {
  const scope = createTaskScope();
  let cleaned = false;
  const unregister = scope.register(() => { cleaned = true; });
  unregister();
  scope.stop();

  assert.equal(cleaned, false);
});
