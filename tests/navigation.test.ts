import assert from "node:assert/strict";
import test from "node:test";
import { moveDayCursor } from "../src/model/navigation.ts";
import { encoderMovement } from "../src/input.ts";

test("moves the daily chart selection and clamps it at both ends", () => {
  assert.equal(moveDayCursor(10, 1, 36), 11);
  assert.equal(moveDayCursor(10, -1, 36), 9);
  assert.equal(moveDayCursor(10, 5, 36), 15);
  assert.equal(moveDayCursor(10, -4, 36), 6);
  assert.equal(moveDayCursor(0, -1, 36), 0);
  assert.equal(moveDayCursor(35, 1, 36), 35);
  assert.equal(moveDayCursor(3, 1, 0), 0);
});

test("preserves the firmware encoder direction", () => {
  assert.equal(encoderMovement({ key: "encoder", delta: 1 } as BusyInputEvent), 1);
  assert.equal(encoderMovement({ key: "encoder", delta: -1 } as BusyInputEvent), -1);
});
