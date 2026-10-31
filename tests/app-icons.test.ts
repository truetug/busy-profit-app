import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { inflateSync } from "node:zlib";

test("ships transparent chart icons in the required sizes and color modes", () => {
  for (const [name, size, grayscale] of [
    ["icon_front_8x8.png", 8, false],
    ["icon_back_11x11.png", 11, true],
  ] as const) {
    const png = readFileSync(new URL(`../src/appmeta/${name}`, import.meta.url));
    assert.equal(png.subarray(0, 8).toString("hex"), "89504e470d0a1a0a");
    assert.equal(png.readUInt32BE(16), size);
    assert.equal(png.readUInt32BE(20), size);
    assert.equal(png[25], 6); // RGBA
    assert.equal(png.subarray(37, 41).toString(), "IDAT");
    const pixels = inflateSync(png.subarray(41, 41 + png.readUInt32BE(33)));
    let visible = 0;
    let transparent = 0;
    const columnHeights = Array<number>(size).fill(0);
    for (let y = 0; y < size; y++) {
      assert.equal(pixels[y * (size * 4 + 1)], 0);
      for (let x = 0; x < size; x++) {
        const offset = y * (size * 4 + 1) + 1 + x * 4;
        if (pixels[offset + 3] === 0) transparent++;
        else {
          visible++;
          columnHeights[x]!++;
          if (grayscale) {
            assert.equal(pixels[offset], pixels[offset + 1]);
            assert.equal(pixels[offset], pixels[offset + 2]);
          }
        }
      }
    }
    assert.ok(visible > 0 && transparent > 0);
    assert.deepEqual(columnHeights.slice(1, size - 1), Array.from({ length: size - 2 }, (_, index) => index + 1));
  }
});
