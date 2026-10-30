import assert from "node:assert/strict";
import test from "node:test";
import { MINUTE_MS, startMinuteClock } from "../src/minute-clock.ts";

test("redraws on a minute interval and cancels it when stopped", () => {
  let tick = () => {};
  let delay = 0;
  let cancelled = false;
  let calls = 0;
  const token = 7 as unknown as ReturnType<typeof setInterval>;
  const stop = startMinuteClock(
    () => { calls += 1; },
    (callback, interval) => {
      tick = callback;
      delay = interval;
      return token;
    },
    (timer) => { cancelled = timer === token; },
  );

  tick();
  stop();

  assert.equal(delay, MINUTE_MS);
  assert.equal(calls, 1);
  assert.equal(cancelled, true);
});
