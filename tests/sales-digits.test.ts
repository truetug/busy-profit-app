import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { render, registerFontMaps } from "@busy-app/busy-lib";
import { bold, small, tiny } from "@busy-app/busy-lib/fonts";
import { renderSalesScreen } from "../src/screens/sales.ts";
import { positionSalesDigits, salesDigits } from "../src/screens/sales-digits.ts";
import { staleElementIds } from "../src/display-api.ts";

[bold, small, tiny].forEach(registerFontMaps);

test("uses identical native-bold pixel origins for LOADING and sales, with two empty rows before the date", () => {
  for (const count of [undefined, 5020]) {
    const elements = positionSalesDigits(render(renderSalesScreen({ screen: "home", now: new Date(2026, 10, 2), count, points: [], selectedDay: 35, stale: false })));
    const headline = elements.find((element) => element.id === "sales-count-digits");
    assert.equal(headline?.type, "xpmbitmap");
    assert.equal(headline?.x, 19);
    assert.equal(headline?.y, 1);
    assert.equal(headline?.height, 7);
    // The small font's first lit row is two pixels below its origin.
    assert.equal(elements.find((element) => element.id === "sales-info")?.y, 8);
    assert.equal(8 + 2 - (1 + 7), 2);
  }
  assert.match(salesDigits("LOADING"), /46 7 2 1/);
});

test("renders the real home layout with digits at row one and the date origin at row eight", () => {
  const elements = positionSalesDigits(render(renderSalesScreen({ screen: "home", now: new Date(2026, 10, 2), count: 5015, points: [], selectedDay: 35, stale: false })));
  assert.equal(elements.find((element) => element.id === "sales-count-digits")?.y, 1);
  assert.equal(elements.find((element) => element.id === "sales-info")?.y, 8);
});

test("places exact bold sales glyphs one pixel below the top edge", () => {
  const [number] = positionSalesDigits([{ type: "text", id: "sales-count", text: "5015", font: "bold", x: 19, y: -3 }]);
  assert.equal(number?.type, "xpmbitmap");
  assert.equal(number?.y, 1);
  assert.equal(number?.x, 19);
  assert.equal(number?.height, 7);
  assert.equal(number?.id, "sales-count-digits");
  assert.deepEqual(staleElementIds(["sales-count"], [number!.id!]), ["sales-count"]);
  assert.match(salesDigits("5015"), /27 7 2 1/);
  assert.match(salesDigits("5015"), /#FFFFFF/);
});

test("keeps the date unchanged and leaves two blank rows after the digits", () => {
  const date = { type: "text" as const, id: "sales-info", text: "2 Nov, 01:50", x: 19, y: 10, font: "small" as const };
  assert.deepEqual(positionSalesDigits([date]), [date]);
  assert.equal(10 - (1 + 7), 2);
});

test("centers notification digits above the animation and cleans both up on return", () => {
  const [number] = positionSalesDigits([{ type: "text", id: "sales-notification", text: "5016", font: "bold" }]);
  assert.equal(number?.x, 22);
  assert.equal(number?.y, 4);
  assert.equal(number?.z_index, 2);
  assert.deepEqual(staleElementIds(["sales-notification", "sales-notification-background"], ["sales-count", "sales-info"]), ["sales-notification", "sales-notification-background"]);
});

test("ships a slow native 72x16 notification animation", () => {
  const animation = readFileSync(new URL("../src/animations/sales_notification.anim", import.meta.url));
  assert.equal(animation.subarray(0, 8).toString(), "bicycle1");
  assert.deepEqual([...animation.subarray(9, 12)], [72, 16, 2]);
  assert.equal(animation[16], 4);
});

test("adds a black one-pixel shadow beneath notification digits only", () => {
  const elements = positionSalesDigits([{ type: "text", id: "sales-notification", text: "5021", font: "bold" }]);
  const number = elements.find((element) => element.id === "sales-notification")!;
  const shadow = elements.find((element) => element.id === "sales-notification-shadow")!;
  assert.equal(shadow.x, number.x! + 1);
  assert.equal(shadow.y, number.y! + 1);
  assert.ok(shadow.z_index! < number.z_index!);
  assert.equal(shadow.type === "xpmbitmap" && shadow.data, salesDigits("5021").replace("#FFFFFFFF", "#000000FF"));
});
