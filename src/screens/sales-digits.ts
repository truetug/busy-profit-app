import { generateXpm2, type render } from "@busy-app/busy-lib";

// Exact six-pixel glyphs from the device's busy_bold_7 font, without its leading.
const DIGITS: Record<string, string[]> = {
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
  if (!/^\d+$/.test(text)) throw new Error("Sales digits must be a non-empty integer");
  return generateXpm2({
    palette: { ".": "None", w: "#FFFFFFFF" },
    grid: Array.from({ length: 7 }, (_, y) => [...text].map((digit) => DIGITS[digit]![y]).join(".")),
  });
}

/** Places lit headline pixels at row one instead of clamping a negative font origin. */
export function positionSalesDigits(elements: ReturnType<typeof render>): ReturnType<typeof render> {
  return elements.map((element) => {
    if (element.id === "sales-notification-background") return { ...element, x: 0, y: 0 };
    if (element.type !== "text" || !/^\d+$/.test(element.text ?? "")) return element;
    if (element.id !== "sales-count" && element.id !== "sales-notification") return element;
    const notification = element.id === "sales-notification";
    const width = element.text!.length * 7 - 1;
    return {
      type: "xpmbitmap", id: element.id, data: salesDigits(element.text!),
      x: notification ? Math.floor((72 - width) / 2) : 19,
      y: notification ? 4 : 1, width, height: 7, opacity: 100, z_index: 2,
    };
  });
}
