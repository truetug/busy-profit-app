import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("ships native catalog frames and enlarged documentation frames for all three screens", () => {
  for (const name of ["lifetime-summary", "daily-chart", "new-sales"]) {
    for (const [folder, width, height] of [["catalog/", 72, 16], ["", 1152, 256]] as const) {
      const png = readFileSync(new URL(`../screenshots/${folder}${name}.png`, import.meta.url));
      assert.equal(png.readUInt32BE(16), width);
      assert.equal(png.readUInt32BE(20), height);
    }
  }
});
