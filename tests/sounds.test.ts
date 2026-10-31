import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("ships headerless 16-bit mono PCM at 44.1 kHz for both notification sounds", () => {
  for (const [name, duration] of [["cha-ching", 1.036], ["applause", 3.389]] as const) {
    const audio = readFileSync(new URL(`../src/sounds/${name}.snd`, import.meta.url));
    assert.notEqual(audio.subarray(0, 4).toString(), "RIFF");
    assert.equal(audio.length % 2, 0);
    assert.ok(Math.abs(audio.length / 2 / 44_100 - duration) < 0.02);
    assert.ok(audio.some((byte) => byte !== 0));
  }
});
