import assert from "node:assert/strict";
import test from "node:test";
import { dailyGraphElements, renderSalesScreen } from "../src/screens/sales.ts";

type ScreenNode = {
  type?: string;
  id?: string;
  text?: string;
  data?: string;
  fill_colors?: string[];
  dx?: number;
  dy?: number;
  z_index?: number;
  font?: string;
  color?: string;
  justify?: string;
  gap?: number;
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

test("keeps loading animation and clock after the initial fetch fails", () => {
  const elements = flatten(renderSalesScreen({ screen: "home", now: new Date(2026, 10, 2, 12, 30), points: [], selectedDay: 35, stale: false, error: "HTTP 503" }) as ScreenNode);
  assert.equal(elements.find((item) => item.id === "sales-count")?.text, "LOADING");
  assert.equal(elements.find((item) => item.id === "sales-loading-icon")?.type, "animation");
  assert.equal(elements.find((item) => item.id === "sales-info")?.text, "2 Nov, 12:30");
  assert.equal(elements.find((item) => item.id === "sales-info")?.color, "#FF3838FF");
});

test("shows a Wi-Fi error only for a confirmed disconnection and always keeps the date", () => {
  const elements = flatten(renderSalesScreen({ screen: "home", now: new Date(2026, 10, 2, 12, 30), points: [], selectedDay: 35, stale: false, error: "fetch failed", wifiOffline: true }) as ScreenNode);
  assert.equal(elements.find((item) => item.id === "sales-count")?.text, "NO WIFI");
  assert.equal(elements.find((item) => item.id === "sales-info")?.text, "2 Nov, 12:30");
  assert.equal(elements.find((item) => item.id === "sales-loading-icon")?.type, "animation");
});

test("renders lifetime sales, selling days, and an eight-column icon", () => {
  const tree = renderSalesScreen({
    screen: "home", now: new Date(2026, 9, 30, 12),
    count: 145, points, selectedDay: 35, stale: false,
  }) as ScreenNode;
  const elements = flatten(tree);

  assert.equal(elements.find((item) => item.id === "sales-count")?.text, "145");
  assert.equal(elements.find((item) => item.id === "sales-count")?.font, "bold");
  assert.equal(elements.find((item) => item.id === "sales-count")?.dy, undefined);
  assert.equal(elements.find((item) => item.id === "sales-days")?.text, "108");
  assert.equal(elements.find((item) => item.id === "sales-days")?.font, "tiny");
  assert.equal(elements.find((item) => item.children?.some((child) => child.id === "sales-days"))?.justify, "between");
  assert.equal(elements.find((item) => item.id === "sales-mark")?.type, "xpmbitmap");
  assert.match(elements.find((item) => item.id === "sales-mark")?.data ?? "", /16 16 9 1/);
  assert.ok(elements.find((item) => item.id === "sales-info")?.text);
  assert.equal(elements.find((item) => item.id === "sales-info")?.dy, 0);
  const headlineColumn = elements.find((item) => item.children?.some((child) => child.id === "sales-info"));
  assert.equal(headlineColumn?.gap, 2);
  assert.equal(headlineColumn?.dy, -1);
});

test("renders the full-width 36-day chart with selected date and count", () => {
  const elements = dailyGraphElements(points, new Date(2026, 9, 30, 12), 35);

  assert.equal(elements.find((item) => item.id === "sales-selected-day" && item.type === "text")?.text, "30.10  20");
  assert.equal(elements.find((item) => item.id === "sales-history-label" && item.type === "text")?.text, "36D");
  assert.equal(elements.find((item) => item.id === "sales-chart")?.type, "xpmbitmap");
  assert.equal(elements.find((item) => item.id === "sales-day-marker")?.type, "rectangle");
  assert.equal(elements.find((item) => item.id === "sales-day-marker")?.x, 70);
  assert.equal(elements.find((item) => item.id === "sales-day-marker")?.z_index, 7);
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

test("draws the selected weekend marker above the gray weekend indicator", () => {
  const elements = dailyGraphElements(points, new Date(2026, 10, 1, 12), 35);
  const marker = elements.find((item) => item.id === "sales-day-marker");
  const weekends = elements.find((item) => item.id === "sales-weekends");
  const bottomRow = weekends?.data?.split("\n").at(-1) ?? "";

  assert.equal(bottomRow.slice(70, 72), "ww");
  assert.equal(marker?.fill_colors?.[0], "#FFFFFFFF");
  assert.ok((marker?.z_index ?? 0) > (weekends?.z_index ?? 0));
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
    assert.equal(elements.find((item) => item.id === "sales-notification")?.font, "bold");
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

test("keeps the sales headline as bright and bold as the reference temperature", () => {
  const args = { now: new Date(2026, 10, 2, 1, 50), count: 5015, points, selectedDay: 35, stale: false };
  for (const notificationCount of [undefined, 5016]) {
    const elements = flatten(renderSalesScreen({ ...args, screen: "home", notificationCount }) as ScreenNode);
    const number = elements.find((item) => item.id === (notificationCount === undefined ? "sales-count" : "sales-notification"));
    assert.equal(number?.font, "bold");
    assert.equal(number?.color, "#FFFFFFFF");
  }
});

test("restores the overview and its clock after the new-sales notification ends", () => {
  const args = { screen: "home" as const, now: new Date(2026, 10, 2, 1, 50), count: 5016, points, selectedDay: 35, stale: false };
  const notification = flatten(renderSalesScreen({ ...args, notificationCount: 5016 }) as ScreenNode);
  const restored = flatten(renderSalesScreen(args) as ScreenNode);
  assert.equal(notification.some((item) => item.id === "sales-info"), false);
  assert.equal(restored.some((item) => item.id === "sales-notification"), false);
  assert.equal(restored.find((item) => item.id === "sales-count")?.text, "5016");
  assert.equal(restored.find((item) => item.id === "sales-info")?.text, "2 Nov, 01:50");
  assert.equal(restored.find((item) => item.id === "sales-mark")?.type, "xpmbitmap");
});

test("restores the selected daily chart after a notification over the history screen", () => {
  const now = new Date(2026, 10, 2, 1, 50);
  const before = dailyGraphElements(points, now, 32);
  renderSalesScreen({ screen: "days", now, count: 5016, points, selectedDay: 32, stale: false, notificationCount: 5016 });
  assert.deepEqual(dailyGraphElements(points, now, 32), before);
});
