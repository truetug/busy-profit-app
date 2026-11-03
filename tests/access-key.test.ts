import assert from "node:assert/strict";
import test from "node:test";
import { AccessKeyRequired, fetchHistory } from "../src/sales-api.ts";

test("includes an untrusted hardware UID only when valid and present", async () => {
  for (const uid of ["203638485431500400abcdef", "", "bad\r\nInjected: value", "x".repeat(255)]) {
    await fetchHistory("current", async (url, options) => {
      const headers = new Headers(options?.headers);
      assert.equal(headers.get("X-Busy-Hardware-ID"), uid.length === 24 ? uid.toUpperCase() : null);
      assert.equal(headers.get("X-Busy-Account-Email"), null);
      assert.equal(headers.get("Authorization"), "Bearer key");
      assert.equal(String(url).includes(uid || "@"), false);
      return new Response("observed_at,bars_sold\n2026-11-02T00:00:00Z,123\n");
    }, "key", uid);
  }
});

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
