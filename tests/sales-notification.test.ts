import assert from "node:assert/strict";
import test from "node:test";
import { salesNotification } from "../src/model/sales-notification.ts";

test("notifies only about increases after the first reading", () => {
  assert.equal(salesNotification(undefined, 100), undefined);
  assert.equal(salesNotification(100, 100), undefined);
  assert.equal(salesNotification(100, 99), undefined);
  assert.deepEqual(salesNotification(101, 102), { count: 102, sound: "cash" });
});

test("plays one applause when one or multiple hundreds are crossed", () => {
  assert.deepEqual(salesNotification(99, 100), { count: 100, sound: "applause" });
  assert.deepEqual(salesNotification(3199, 3401), { count: 3401, sound: "applause" });
});
