import assert from "node:assert/strict";
import test from "node:test";
import { dailyChange, dailySales, sellingDays, timestamp } from "../src/model/sales.ts";
import { actionForInput } from "../src/input.ts";
import { increments } from "../src/model/sales.ts";
import { formatDateTime } from "../shared/datetime.ts";
import { salesHeadline } from "../src/screens/sales-format.ts";

test("parses Shopify ISO timestamps with microseconds and timezone offsets", () => {
  assert.equal(timestamp("2026-10-29T22:39:11.114060+00:00"), Date.parse("2026-10-29T22:39:11.114Z"));
});

test("rejects malformed and impossible timestamps", () => {
  assert.ok(Number.isNaN(timestamp("not-a-date")));
  assert.ok(Number.isNaN(timestamp("2026-02-30T10:00:00Z")));
});

test("computes 24-hour sales change against the preceding 24 hours", () => {
  const now = new Date("2026-10-30T12:00:00Z");
  const points = [
    { at: "2026-10-28T12:00:00Z", count: 100 },
    { at: "2026-10-29T12:00:00Z", count: 130 },
    { at: "2026-10-30T12:00:00Z", count: 175 },
  ];
  assert.equal(dailyChange(points, now), 15);
});

test("reports elapsed selling days from the July 14 launch date", () => {
  assert.equal(sellingDays(new Date(2026, 6, 15, 12)), 1);
});

test("formats the sales headline with selling days on the same line", () => {
  assert.deepEqual(salesHeadline(5003, new Date(2026, 9, 30, 12)), { count: "5003", days: "108" });
});

test("formats the lower line with only local date and time", () => {
  assert.equal(formatDateTime(new Date(2026, 9, 30, 11, 5)), "30 Oct, 11:05");
});

test("limits the daily chart series to the requested recent-day window", () => {
  const now = new Date(2026, 9, 30, 12);
  const points = [
    { at: "2026-10-26T12:00:00Z", count: 100 },
    { at: "2026-10-27T12:00:00Z", count: 110 },
    { at: "2026-10-28T12:00:00Z", count: 125 },
    { at: "2026-10-29T12:00:00Z", count: 145 },
    { at: "2026-10-30T12:00:00Z", count: 170 },
  ];
  assert.deepEqual(increments(points, "day", now, 4), [10, 15, 20, 25]);
  assert.deepEqual(dailySales(points, now, 4).map((day) => day.count), [10, 15, 20, 25]);
  assert.equal(new Date(dailySales(points, now, 4)[0]!.atMs).getDate(), 27);
});

test("maps short Back and Start presses to exit and screen changes", () => {
  assert.equal(actionForInput({ key: "back", action: "short" }), "exit");
  assert.equal(actionForInput({ key: "back", action: "press" }), "exit");
  assert.equal(actionForInput({ key: "start", action: "short" }), "toggle-screen");
  assert.equal(actionForInput({ key: "start", action: "press" }), undefined);
  assert.equal(actionForInput({ key: "encoder", action: "clockwise", delta: 1 }), "next-day");
  assert.equal(actionForInput({ key: "encoder", action: "counterclockwise", delta: -1 }), "previous-day");
});
