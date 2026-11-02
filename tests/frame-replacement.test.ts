import assert from "node:assert/strict";
import test from "node:test";
import { clearBeforeFrameChange } from "../src/display-api.ts";

test("waits for the old screen to be cleared before drawing the new screen", async () => {
  const calls: string[] = [];
  let finish = () => {};
  const pending = clearBeforeFrameChange(["home"], ["chart"], async () => {
    calls.push("clear");
    await new Promise<void>((resolve) => { finish = resolve; });
    calls.push("cleared");
  }).then(() => { calls.push("draw"); });
  assert.deepEqual(calls, ["clear"]);
  finish();
  await pending;
  assert.deepEqual(calls, ["clear", "cleared", "draw"]);
});

test("does not clear the chart during selection-only updates", async () => {
  assert.equal(await clearBeforeFrameChange(["chart", "marker"], ["chart", "marker"], async () => { assert.fail("unexpected clear"); }), false);
});

test("never draws a new frame after a failed clear", async () => {
  let drawn = false;
  await assert.rejects(async () => {
    await clearBeforeFrameChange(["old"], ["new"], async () => { throw new Error("offline"); });
    drawn = true;
  }, /offline/);
  assert.equal(drawn, false);
});
