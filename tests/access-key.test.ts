import assert from "node:assert/strict";
import test from "node:test";
import { AccessKeyRequired, fetchHistory } from "../src/sales-api.ts";

test("does not send a request without an access key", async () => {
  await assert.rejects(fetchHistory("current", async () => { assert.fail("unexpected request"); }), AccessKeyRequired);
});

test("sends the key only in the Authorization header", async () => {
  await fetchHistory("current", async (url, options) => {
    assert.equal(String(url).includes("private-key"), false);
    assert.equal(new Headers(options?.headers).get("Authorization"), "Bearer private-key");
    return new Response("observed_at,bars_sold\n2026-11-02T00:00:00Z,123\n");
  }, "private-key");
});

test("distinguishes rejected keys from transient failures", async () => {
  for (const status of [401, 403]) {
    await assert.rejects(fetchHistory("current", async () => new Response("", { status }), "invalid"), AccessKeyRequired);
  }
});
