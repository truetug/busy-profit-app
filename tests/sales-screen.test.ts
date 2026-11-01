import assert from "node:assert/strict";
import test from "node:test";
import { dailyGraphElements, renderSalesScreen } from "../src/screens/sales.ts";

type ScreenNode = {
  type?: string;
  id?: string;
  text?: string;
  data?: string;
  dx?: number;
  dy?: number;
  z_index?: number;
  font?: string;
  justify?: string;
  width?: number;
  height?: number;
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

test("renders lifetime sales, selling days, and an eight-column icon", () => {
  const tree = renderSalesScreen({
    screen: "home", now: new Date(2026, 9, 30, 12),
    count: 145, points, selectedDay: 35, stale: false,
  }) as ScreenNode;
  const elements = flatten(tree);

  assert.equal(elements.find((item) => item.id === "sales-count")?.text, "145");
  assert.equal(elements.find((item) => item.id === "sales-days")?.text, "108");
  assert.equal(elements.find((item) => item.id === "sales-days")?.font, "tiny");
  assert.equal(elements.find((item) => item.children?.some((child) => child.id === "sales-days"))?.justify, "between");
  assert.equal(elements.find((item) => item.id === "sales-mark")?.type, "xpmbitmap");
  assert.match(elements.find((item) => item.id === "sales-mark")?.data ?? "", /16 16 9 1/);
  assert.ok(elements.find((item) => item.id === "sales-info")?.text);
  assert.equal(elements.find((item) => item.id === "sales-info")?.dy, -2);
});

test("renders the full-width 36-day chart with selected date and count", () => {
  const elements = dailyGraphElements(points, new Date(2026, 9, 30, 12), 35);

  assert.equal(elements.find((item) => item.id === "sales-selected-day" && item.type === "text")?.text, "30.10  20");
  assert.equal(elements.find((item) => item.id === "sales-history-label" && item.type === "text")?.text, "36D");
  assert.equal(elements.find((item) => item.id === "sales-chart")?.type, "xpmbitmap");
  assert.equal(elements.find((item) => item.id === "sales-day-marker")?.type, "rectangle");
  assert.equal(elements.find((item) => item.id === "sales-day-marker")?.x, 70);
  assert.equal(elements.find((item) => item.id === "sales-day-marker")?.z_index, 5);
  assert.equal(elements.find((item) => item.id === "sales-weekends")?.y, 15);
});

test("marks Saturdays and Sundays in the bottom row", () => {
  const weekend = dailyGraphElements(points, new Date(2026, 9, 30, 12), 35)
    .find((item) => item.id === "sales-weekends" && item.type === "xpmbitmap");
  assert.ok(weekend?.data?.includes("#808080"));
  const row = weekend?.data?.split("\n").at(-1) ?? "";
  assert.equal(row.length, 72);
  assert.equal(row.slice(-14), "wwww..........");
});

test("places the day chart directly and only changes its label and marker on scroll", () => {
  const first = dailyGraphElements(points, new Date(2026, 9, 30, 12), 34);
  const second = dailyGraphElements(points, new Date(2026, 9, 30, 12), 35);
  const changed = second.filter((element, index) => JSON.stringify(element) !== JSON.stringify(first[index]));
  assert.deepEqual(changed.map((element) => element.id), ["sales-selected-day", "sales-day-marker"]);
  assert.equal(second.find((element) => element.id === "sales-weekends")?.y, 15);
  assert.equal(second.find((element) => element.id === "sales-day-marker")?.x, 70);
});

test("shows the large updated total over either screen", () => {
  for (const screen of ["home", "days"] as const) {
    const tree = renderSalesScreen({
      screen, now: new Date(2026, 9, 30, 12), count: 145, points,
      selectedDay: 35, stale: false, notificationCount: 146,
    }) as ScreenNode;
    const elements = flatten(tree);
    assert.equal(elements.find((item) => item.id === "sales-notification")?.text, "146");
    assert.equal(elements.some((item) => item.id === "sales-chart"), false);
  }
});

test("reports background chart loading without hiding the current overview", () => {
  const args = { now: new Date(2026, 9, 30, 12), count: 145, points, selectedDay: 35, stale: false };
  const loading = flatten(renderSalesScreen({ ...args, screen: "days", historyState: "loading" }) as ScreenNode);
  const overview = flatten(renderSalesScreen({ ...args, screen: "home", historyState: "loading" }) as ScreenNode);
  const failed = flatten(renderSalesScreen({ ...args, screen: "days", historyState: "error" }) as ScreenNode);
  assert.equal(loading.find((item) => item.id === "sales-history-status")?.text, "LOADING");
  assert.equal(failed.find((item) => item.id === "sales-history-status")?.text, "NO DATA");
  assert.equal(overview.find((item) => item.id === "sales-count")?.text, "145");
});
