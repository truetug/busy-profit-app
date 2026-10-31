import assert from "node:assert/strict";
import test from "node:test";
import { createOlderFeedLoader, type OlderFeedState } from "../src/older-feed.ts";
import type { Point } from "../src/model/sales.ts";

test("loads older data in the background only once per day", async () => {
  let finish: (points: Point[]) => void = () => {};
  let calls = 0;
  const states: OlderFeedState[] = [];
  const loader = createOlderFeedLoader(
    () => { calls++; return new Promise((resolve) => { finish = resolve; }); },
    (state) => states.push(state),
    () => assert.fail("unexpected load error"),
  );
  const pending = loader.refresh("day-1");
  await loader.refresh("day-1");
  assert.equal(calls, 1);
  assert.equal(states.at(-1)?.loading, true);

  finish([{ at: "2026-10-30T12:00:00Z", count: 5 }]);
  await pending;
  await loader.refresh("day-1");
  assert.equal(calls, 1);
  assert.equal(states.at(-1)?.loadedDay, "day-1");
  const nextDay = loader.refresh("day-2");
  assert.equal(calls, 2);
  finish([]);
  await nextDay;
  assert.equal(states.at(-1)?.loadedDay, "day-2");
});

test("retains the previous chart after a failed refresh and retries", async () => {
  let calls = 0;
  const states: OlderFeedState[] = [];
  const errors: unknown[] = [];
  const saved = [{ at: "2026-10-30T12:00:00Z", count: 5 }];
  const loader = createOlderFeedLoader(async () => {
    calls++;
    if (calls === 2) throw new Error("offline");
    return saved;
  }, (state) => states.push(state), (error) => errors.push(error));

  await loader.refresh("day-1");
  await loader.refresh("day-2");
  assert.equal(states.at(-1)?.failed, true);
  assert.equal(states.at(-1)?.loadedDay, "day-1");
  assert.deepEqual(states.at(-1)?.points, saved);
  assert.equal(errors.length, 1);
  await loader.refresh("day-2");
  assert.equal(calls, 3);
  assert.equal(states.at(-1)?.loadedDay, "day-2");
});

test("does not update the display when a pending history load finishes after exit", async () => {
  let finish: (points: Point[]) => void = () => {};
  const states: OlderFeedState[] = [];
  const loader = createOlderFeedLoader(
    () => new Promise((resolve) => { finish = resolve; }),
    (state) => states.push(state),
    () => assert.fail("unexpected load error"),
  );
  const pending = loader.refresh("day-1");
  loader.stop();
  finish([]);
  await pending;
  await loader.refresh("day-2");
  assert.equal(states.length, 1);
  assert.equal(states[0]?.loading, true);
});

test("retries when independently updated feeds have a mismatched boundary", async () => {
  let calls = 0;
  const states: OlderFeedState[] = [];
  const errors: unknown[] = [];
  const loader = createOlderFeedLoader(async () => {
    calls++;
    return [{ at: calls === 1 ? "old-boundary" : "new-boundary", count: 5 }];
  }, (state) => states.push(state), (error) => errors.push(error));

  await loader.refresh("day-2", "new-boundary");
  assert.equal(states.at(-1)?.failed, true);
  assert.equal(states.at(-1)?.loadedDay, undefined);
  await loader.refresh("day-2", "new-boundary");
  assert.equal(calls, 2);
  assert.equal(states.at(-1)?.loadedAnchor, "new-boundary");
  assert.equal(errors.length, 1);
});
