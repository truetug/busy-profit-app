import assert from "node:assert/strict";
import test from "node:test";
import { fetchHistory } from "../src/sales-api.ts";
import { mergeHistory } from "../src/model/sales.ts";

const HEADER = "observed_at,bars_sold,source_updated_at";

test("loads the two-column public CSV", async () => {
  const fetcher: typeof fetch = async () => new Response(
    "observed_at,bars_sold\n2026-10-30T12:00:00+00:00,5003\n",
  );
  assert.equal((await fetchHistory("current", fetcher))[0]?.count, 5003);
});

test("loads the compact current CSV from its dedicated URL", async () => {
  let url = "";
  const fetcher: typeof fetch = async (input) => {
    url = String(input);
    return new Response(`${HEADER}\n2026-10-30T12:00:00+00:00,5003,2026-10-30T12:00:00+00:00\n`);
  };
  const points = await fetchHistory("current", fetcher);
  assert.equal(url, "https://profit.busy.truetug.info/current.csv");
  assert.equal(points.length, 1);
  assert.equal(points[0]?.count, 5003);
});

test("accepts an empty older feed but rejects an empty current feed", async () => {
  const fetcher: typeof fetch = async () => new Response(`${HEADER}\n`);
  assert.deepEqual(await fetchHistory("older", fetcher), []);
  await assert.rejects(fetchHistory("current", fetcher), /no valid observations/);
});

test("rejects a malformed feed instead of treating it as empty history", async () => {
  const fetcher: typeof fetch = async () => new Response("invalid,header\n");
  await assert.rejects(fetchHistory("older", fetcher), /invalid CSV header/);
});

test("merges chronological feeds and deduplicates their overlapping boundary", () => {
  const older = [
    { at: "2026-10-22T12:00:00+00:00", count: 100 },
    { at: "2026-10-23T12:00:00+00:00", count: 110 },
  ];
  const current = [
    { at: "2026-10-24T12:00:00+00:00", count: 120 },
    { at: "2026-10-23T15:00:00+03:00", count: 111 },
  ];
  assert.deepEqual(mergeHistory(older, current).map((point) => point.count), [100, 111, 120]);
});
