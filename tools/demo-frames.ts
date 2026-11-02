/** Generates demonstration-only display requests without reading any real sales feed. */
import { writeFileSync } from "node:fs";
import { render, registerFontMaps } from "@busy-app/busy-lib";
import { bold, small, tiny } from "@busy-app/busy-lib/fonts";
import { renderSalesScreen, dailyGraphElements } from "../src/screens/sales.ts";
import { positionSalesDigits } from "../src/screens/sales-digits.ts";
import { clampNegativeY } from "../src/display-api.ts";
import manifest from "../src/appmeta/manifest.json" with { type: "json" };

[bold, small, tiny].forEach(registerFontMaps);
const now = new Date(2026, 9, 30, 12, 30);
const values = Array.from({ length: 40 }, (_, index) => 4 + index * 7 % 27);
let count = 1234 - values.reduce((sum, value) => sum + value, 0);
const points = values.map((value, index) => {
  count += value;
  return { at: new Date(now.getTime() - (39 - index) * 86_400_000).toISOString(), count };
});
const args = { screen: "home" as const, now, count: 1234, points, selectedDay: 35, stale: false };
const frames = {
  "lifetime-summary": positionSalesDigits(render(renderSalesScreen(args))),
  "daily-chart": dailyGraphElements(points, now, 35),
  "new-sales": positionSalesDigits(render(renderSalesScreen({ ...args, notificationCount: 1235 }))),
};
for (const [name, elements] of Object.entries(frames)) {
  writeFileSync(`/tmp/profit-demo-${name}.json`, JSON.stringify({ application_name: process.env.DEMO_APP_ID ?? manifest.id, priority: 99, elements: clampNegativeY(elements) }));
}
