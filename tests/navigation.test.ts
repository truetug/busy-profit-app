import assert from "node:assert/strict";
import test from "node:test";
import { INITIAL_HOME_PHASE, moveDayCursor, nextHomePhase } from "../src/model/navigation.ts";

test("manually cycles the home headline between lifetime and four-day sales", () => {
  assert.equal(INITIAL_HOME_PHASE, "summary");
  assert.equal(nextHomePhase("summary"), "recent-days");
  assert.equal(nextHomePhase("recent-days"), "summary");
});

test("moves the daily chart selection and clamps it at both ends", () => {
  assert.equal(moveDayCursor(10, 1, 28), 11);
  assert.equal(moveDayCursor(10, -1, 28), 9);
  assert.equal(moveDayCursor(0, -1, 28), 0);
  assert.equal(moveDayCursor(27, 1, 28), 27);
  assert.equal(moveDayCursor(3, 1, 0), 0);
});
