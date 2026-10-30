import assert from "node:assert/strict";
import test from "node:test";
import { renderSalesScreen } from "../src/screens/sales.ts";

type ScreenNode = {
  type?: string;
  id?: string;
  text?: string;
  data?: string;
  dx?: number;
  children?: ScreenNode[];
};

const points = [
  { at: "2026-10-27T12:00:00Z", count: 100 },
  { at: "2026-10-28T12:00:00Z", count: 110 },
  { at: "2026-10-29T12:00:00Z", count: 125 },
  { at: "2026-10-30T12:00:00Z", count: 145 },
];

/** Flattens a layout tree so the tests can inspect its visible data by element ID. */
function flatten(node: ScreenNode): ScreenNode[] {
  return [node, ...(node.children ?? []).flatMap(flatten)];
}

test("shows four daily sales figures in the headline while keeping the icon and date line", () => {
  const tree = renderSalesScreen({
    screen: "home", homePhase: "recent-days", now: new Date(2026, 9, 30, 12),
    count: 145, points, selectedDay: 27, stale: false,
  }) as ScreenNode;
  const elements = flatten(tree);

  assert.deepEqual(elements.filter((item) => item.id?.startsWith("sales-recent-count-")).map((item) => item.text), ["0", "10", "15", "20"]);
  assert.equal(elements.find((item) => item.id === "sales-mark")?.type, "xpmbitmap");
  assert.ok(elements.find((item) => item.id === "sales-info")?.text);
  assert.equal(elements.some((item) => item.id === "sales-days" || item.id === "sales-count"), false);
});

test("renders lifetime sales and selling days in the alternate manual home phase", () => {
  const tree = renderSalesScreen({
    screen: "home", homePhase: "summary", now: new Date(2026, 9, 30, 12),
    count: 145, points, selectedDay: 27, stale: false,
  }) as ScreenNode;
  const elements = flatten(tree);

  assert.equal(elements.find((item) => item.id === "sales-count")?.text, "145");
  assert.equal(elements.find((item) => item.id === "sales-days")?.text, "/ 108d");
  assert.equal(elements.find((item) => item.id === "sales-mark")?.type, "xpmbitmap");
  assert.ok(elements.find((item) => item.id === "sales-info")?.text);
});

test("renders the full-width 28-day chart with selected date, count, and cursor", () => {
  const tree = renderSalesScreen({
    screen: "days", homePhase: "recent-days", now: new Date(2026, 9, 30, 12),
    count: 145, points, selectedDay: 27, stale: false,
  }) as ScreenNode;
  const elements = flatten(tree);

  assert.equal(elements.find((item) => item.id === "sales-selected-day")?.text, "30.10  20");
  assert.equal(elements.find((item) => item.id === "sales-history-label")?.text, "28D");
  assert.equal(elements.find((item) => item.id === "sales-chart")?.type, "xpmbitmap");
  assert.equal(elements.some((item) => item.id === "sales-day-marker"), false);
  assert.ok(elements.find((item) => item.id === "sales-chart")?.data?.includes("#FFFFFF"));
});
