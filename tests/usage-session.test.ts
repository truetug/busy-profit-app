import assert from "node:assert/strict";
import test from "node:test";
import { createUsageSession } from "../src/usage-session.ts";
import { fetchHistory } from "../src/sales-api.ts";

test("session snapshots retain cumulative time and detail opens across polls", () => {
  let time = 100000;
  const session = createUsageSession(() => time, () => 0.25);
  const first = session.snapshot();
  session.enterDetails(); session.enterDetails(); time += 61500;
  assert.deepEqual(session.snapshot(), { id: first.id, uptimeSeconds: 61, detailsCount: 2 });
  assert.deepEqual(session.snapshot(), session.snapshot());
});

test("sends cumulative session metadata with the existing request only", async () => {
  await fetchHistory("current", async (_url, options) => {
    const h = new Headers(options?.headers);
    assert.equal(h.get("X-Busy-Session-ID"), "session-123");
    assert.equal(h.get("X-Busy-Uptime-Seconds"), "60");
    assert.equal(h.get("X-Busy-Details-Count"), "2");
    return new Response("observed_at,bars_sold\n2026-11-03T00:00:00Z,1\n");
  }, "key", "203638485431500400ABCDEF", { id: "session-123", uptimeSeconds: 60, detailsCount: 2 });
});
