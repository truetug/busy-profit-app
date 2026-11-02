import { generateXpm2, type render } from "@busy-app/busy-lib";

// Exact six-pixel glyphs from the device's busy_bold_7 font, without its leading.
const GLYPHS: Record<string, string[]> = {
  L: ["ww...", "ww...", "ww...", "ww...", "ww...", "ww...", "wwwww"],
  O: [".wwww.", "ww..ww", "ww..ww", "ww..ww", "ww..ww", "ww..ww", ".wwww."],
  A: ["..ww..", "..ww..", ".wwww.", ".w.ww.", ".wwww.", "ww..ww", "ww..ww"],
  D: ["wwww..", "ww.ww.", "ww..ww", "ww..ww", "ww..ww", "ww.ww.", "wwww.."],
  I: ["wwww", ".ww.", ".ww.", ".ww.", ".ww.", ".ww.", "wwww"],
  N: ["ww...ww", "www..ww", "wwww.ww", "wwwwwww", "ww.wwww", "ww..www", "ww...ww"],
  G: [".wwww.", "ww..ww", "ww....", "ww.www", "ww..ww", "ww..ww", ".www.w"],
  "0": [".wwww.", "ww..ww", "ww.www", "www.ww", "ww..ww", "ww..ww", ".wwww."],
  "1": ["..ww..", ".www..", "wwww..", "..ww..", "..ww..", "..ww..", "wwwwww"],
  "2": [".wwww.", "ww..ww", "....ww", "..www.", ".ww...", "ww....", "wwwwww"],
  "3": [".wwww.", "ww..ww", "....ww", "..www.", "....ww", "ww..ww", ".wwww."],
  "4": ["..www.", ".wwww.", ".w.ww.", "ww.ww.", "ww.ww.", "wwwwww", "...ww."],
  "5": ["wwwwww", "ww....", "ww....", "wwwww.", "....ww", "....ww", "wwwww."],
  "6": [".wwww.", "ww..ww", "ww....", "wwwww.", "ww..ww", "ww..ww", ".wwww."],
  "7": ["wwwwww", "....ww", "...ww.", "..ww..", "..ww..", ".ww...", ".ww..."],
  "8": [".wwww.", "ww..ww", "ww..ww", ".wwww.", "ww..ww", "ww..ww", ".wwww."],
  "9": [".wwww.", "ww..ww", "ww..ww", ".wwwww", "....ww", "ww..ww", ".wwww."],
};

/** Rasterizes the native bold digits without changing their strokes or spacing. */
export function salesDigits(text: string): string {
  if (!/^\d+$/.test(text) && text !== "LOADING") throw new Error("Unsupported sales headline");
  return generateXpm2({
    palette: { ".": "None", w: "#FFFFFFFF" },
    grid: Array.from({ length: 7 }, (_, y) => [...text].map((glyph) => GLYPHS[glyph]![y]).join(".")),
  });
}

/** Places lit headline pixels at row one instead of clamping a negative font origin. */
export function positionSalesDigits(elements: ReturnType<typeof render>): ReturnType<typeof render> {
  return elements.flatMap((element): ReturnType<typeof render> => {
    if (element.id === "sales-notification-background") return [{ ...element, x: 0, y: 0 }];
    if (element.type !== "text" || (!/^\d+$/.test(element.text ?? "") && element.text !== "LOADING")) return [element];
    if (element.id !== "sales-count" && element.id !== "sales-notification") return [element];
    const notification = element.id === "sales-notification";
    const width = [...element.text!].reduce((sum, glyph) => sum + GLYPHS[glyph]![0]!.length + 1, -1);
    const number = {
      type: "xpmbitmap" as const, id: notification ? element.id : "sales-count-digits", data: salesDigits(element.text!),
      x: notification ? Math.floor((72 - width) / 2) : 19,
      y: notification ? 4 : 1, width, height: 7, opacity: 100, z_index: 2,
    };
    return notification ? [number, { ...number, id: "sales-notification-shadow", x: number.x + 1, y: number.y + 1,
      z_index: 1, data: number.data.replace("#FFFFFFFF", "#C02828FF") }] : [number];
  });
}
