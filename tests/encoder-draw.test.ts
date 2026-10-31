import assert from "node:assert/strict";
import test from "node:test";
import { createEncoderDrawScheduler } from "../src/encoder-draw.ts";

test("shows the latest selection during continuous rotation without restarting the timer", () => {
  let nextId = 0;
  let calls = 0;
  let selected = 0;
  const rendered: number[] = [];
  const pending = new Map<number, () => void>();
  const canceled: number[] = [];
  const scheduler = createEncoderDrawScheduler(
    () => { calls++; rendered.push(selected); },
    ((callback: () => void, delay: number) => {
      assert.equal(delay, 60);
      const id = ++nextId;
      pending.set(id, callback);
      return id;
    }) as typeof setTimeout,
    ((id: number) => {
      assert.ok(pending.delete(id), `timer ${id} must still be active`);
      canceled.push(id);
    }) as typeof clearTimeout,
  );
  scheduler.request();
  selected = 7;
  scheduler.request();
  assert.deepEqual(canceled, []);
  assert.equal(pending.size, 1);
  const fire = pending.get(1)!;
  pending.delete(1);
  fire();
  assert.equal(calls, 1);
  assert.deepEqual(rendered, [7]);
  selected = 9;
  scheduler.request();
  scheduler.request();
  assert.equal(pending.size, 1);
  const nextFire = pending.get(2)!;
  pending.delete(2);
  nextFire();
  assert.equal(calls, 2);
  assert.deepEqual(rendered, [7, 9]);
  scheduler.request();
  scheduler.stop();
  scheduler.stop();
  assert.deepEqual(canceled, [3]);
});
