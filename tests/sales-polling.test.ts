import assert from "node:assert/strict";
import test from "node:test";
import { SALES_POLL_INTERVAL_MS, startSalesPolling } from "../src/sales-polling.ts";

test("polls immediately, repeats every minute, and cancels on exit", () => {
  let tick = () => {};
  let delay = 0;
  let calls = 0;
  let cancelled = false;
  const token = 7 as unknown as ReturnType<typeof setInterval>;
  const stop = startSalesPolling(
    () => { calls++; },
    (callback, interval) => { tick = callback; delay = interval; return token; },
    (timer) => { cancelled = timer === token; },
  );
  assert.equal(calls, 1);
  assert.equal(delay, 60_000);
  assert.equal(delay, SALES_POLL_INTERVAL_MS);
  tick();
  stop();
  assert.equal(calls, 2);
  assert.equal(cancelled, true);
});
