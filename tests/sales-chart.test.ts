import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dailySalesIcon, dailySalesHeights, historicalSalesIcon, interpolateBarHeights, SALES_ERROR_COLOR } from "../src/screens/sales-chart.ts";
import { SALES_CHART_ICON_ID, SALES_LOADING_ICON_ID } from "../src/screens/sales-ids.ts";

/** Reads the bitmap's declared dimensions and pixel rows for focused rendering assertions. */
function readBitmap(data: string): { width: number; height: number; palette: string[]; rows: string[] } {
  const lines = data.split("\n");
  const [width, height, colors] = lines[1]!.split(" ").map(Number);
  return {
    width: width!,
    height: height!,
    palette: lines.slice(2, 2 + colors!),
    rows: lines.slice(2 + colors!),
  };
}

test("scales four daily sales columns into the 16x16 icon slot", () => {
  const bitmap = readBitmap(dailySalesIcon([10, 20, 30, 40], 16, 16));
  const heights = [1, 5, 9, 13].map((x) => bitmap.rows.filter((row) => row[x] !== ".").length);

  assert.equal(bitmap.width, 16);
  assert.equal(bitmap.height, 16);
  assert.deepEqual(heights, [1, 6, 11, 16]);
});

test("draws adjoining icon bars and uses green-to-red colors", () => {
  const bitmap = readBitmap(dailySalesIcon([5, 10, 15, 20], 16, 16));

  assert.equal(bitmap.rows.at(-1), "aaaabbbbccccdddd");
  assert.ok(bitmap.palette.some((entry) => entry.includes("#23af4b")));
  assert.ok(bitmap.palette.some((entry) => entry.includes("#ff2d23")));
  assert.ok(bitmap.palette.every((entry) => !/#(?:[\da-f]{8}|[\da-f]{12}|[\da-f]{16})$/i.test(entry)));
});

test("scales equal non-zero sales without producing invalid heights", () => {
  assert.deepEqual(dailySalesHeights([7, 7, 7, 7], 16), [16, 16, 16, 16]);
});

test("interpolates a graph from zero to its final heights over generated frames", () => {
  const frames = interpolateBarHeights([0, 0, 0, 0], [16, 12, 8, 4], 4);

  assert.deepEqual(frames[0], [4, 3, 2, 1]);
  assert.deepEqual(frames.at(-1), [16, 12, 8, 4]);
});

test("uses separate element IDs for the loading animation and bitmap chart", () => {
  assert.notEqual(SALES_LOADING_ICON_ID, SALES_CHART_ICON_ID);
});

test("fills historical chart columns edge-to-edge and uses letter-only XPM symbols", () => {
  const bitmap = readBitmap(historicalSalesIcon([5, 10, 15, 20], 16, 9));

  assert.equal(bitmap.rows.at(-1), "aaaabbbbccccdddd");
  assert.ok(bitmap.palette.every((entry) => !/[0-9] c /.test(entry)));
});

test("renders the entire selected historical bar white", () => {
  const bitmap = readBitmap(historicalSalesIcon([9, 6, 3], 15, 9, 1));
  const whiteSymbol = bitmap.palette.find((entry) => entry.includes("#FFFFFF"))?.[0];

  assert.ok(whiteSymbol);
  assert.deepEqual(bitmap.rows.slice(3).map((row) => row.slice(5, 10)), Array(6).fill(whiteSymbol.repeat(5)));
  assert.deepEqual(bitmap.rows.slice(0, 3).map((row) => row.slice(5, 10)), Array(3).fill("....."));
});

test("keeps a white one-pixel baseline for a selected zero-sales day", () => {
  const bitmap = readBitmap(historicalSalesIcon([2, 0, 4], 15, 9, 1));
  const whiteSymbol = bitmap.palette.find((entry) => entry.includes("#FFFFFF"))?.[0];

  assert.ok(whiteSymbol);
  assert.equal(bitmap.rows.at(-1)?.slice(5, 10), whiteSymbol.repeat(5));
});

test("keeps zero-sales icon columns at a one-pixel baseline", () => {
  const bitmap = readBitmap(dailySalesIcon([0, 0, 0, 0], 16, 16));

  assert.deepEqual([1, 5, 9, 13].map((x) => bitmap.rows.filter((row) => row[x] !== ".").length), [1, 1, 1, 1]);
});

test("ships a native transparent 16x16 looping loading icon like Weather", () => {
  const animation = readFileSync(new URL("../src/animations/sales_loading.anim", import.meta.url));

  assert.equal(animation.subarray(0, 8).toString(), "bicycle1");
  assert.deepEqual([...animation.subarray(9, 12)], [16, 16, 2]);
  assert.equal(animation[16], 3);
});

test("uses the Bar API's required RGBA format for error text", () => {
  assert.match(SALES_ERROR_COLOR, /^#[\da-f]{8}$/i);
});
