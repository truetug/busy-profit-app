import assert from "node:assert/strict";
import test from "node:test";
import { countdownIndicator } from "../src/countdown-indicator.ts";

test("shrinks the right-edge indicator from the top down over one minute", () => {
  const [full] = countdownIndicator(60_000);
  const [half] = countdownIndicator(30_000);
  assert.equal(full?.x, 71);
  assert.equal(full?.y, 0);
  assert.equal(full?.height, 16);
  assert.equal(half?.y, 8);
  assert.equal(half?.height, 8);
  assert.deepEqual(countdownIndicator(0), []);
});
