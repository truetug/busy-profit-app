import { generateXpm2 } from "@busy-app/busy-lib";

const EMPTY = ".";
const BACKGROUND = "#2c2c2c";
const COLORS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
const SALES_COLOR_LEVELS = 30;
export const SALES_ERROR_COLOR = "#FF3838FF";

/** Maps vertical position from a light-green baseline to a red chart ceiling. */
function colorForRow(y: number, height: number): string {
  const ratio = height <= 1 ? 0 : (height - 1 - y) / (height - 1);
  const strength = Math.round(ratio * (SALES_COLOR_LEVELS - 1)) / (SALES_COLOR_LEVELS - 1);
  const channels = [144 + strength * 111, 232 - strength * 187, 154 - strength * 119];
  return `#${channels.map((channel) => Math.round(channel).toString(16).padStart(2, "0")).join("")}`;
}

/** Scales day values into icon heights while preserving a one-pixel zero baseline. */
export function dailySalesHeights(values: number[], height: number): number[] {
  if (values.length === 0 || height < 1) return [];
  const maximum = Math.max(...values);
  const minimum = Math.min(...values);
  const span = maximum - minimum;
  if (span === 0) return values.map(() => maximum === 0 ? 1 : height);
  return values.map((value) => 1 + Math.round(((value - minimum) / span) * (height - 1)));
}

/** Interpolates a fixed number of frames from one set of column heights to another. */
export function interpolateBarHeights(from: number[], to: number[], steps: number): number[][] {
  return Array.from({ length: steps }, (_, frame) =>
    to.map((height, index) => {
      const start = from[index] ?? 0;
      return Math.round(start + ((height - start) * (frame + 1)) / steps);
    }),
  );
}

/** Builds a subtly backed bar-chart bitmap from raw sales values. */
export function dailySalesIcon(values: number[], width: number, height: number): string {
  return dailySalesIconFromHeights(dailySalesHeights(values, height), width, height);
}

/** Builds the icon bitmap from pre-scaled heights, used for frame-by-frame transitions. */
export function dailySalesIconFromHeights(heights: number[], width: number, height: number): string {
  return gradientChart(heights, width, height);
}

/** Builds an edge-to-edge historical bitmap, highlighting the selected day's complete bar in white. */
export function historicalSalesIcon(values: number[], width: number, height: number, selectedIndex = -1): string {
  const max = Math.max(1, ...values);
  const heights = values.map((value, index) => Math.max(
    index === selectedIndex ? 1 : 0,
    Math.round((value / max) * height),
  ));
  return gradientChart(heights, width, height, selectedIndex, "None");
}

/** Shares a row-based gradient palette across all bars without adding UI elements. */
function gradientChart(heights: number[], width: number, height: number, selectedIndex = -1, background = BACKGROUND): string {
  const grid = Array.from({ length: height }, () => Array<string>(width).fill(EMPTY));
  const palette: Record<string, string> = { [EMPTY]: background };
  const symbols = new Map<string, string>();
  for (let y = 0; y < height; y++) {
    const color = colorForRow(y, height);
    let symbol = symbols.get(color);
    if (!symbol) {
      symbol = COLORS[symbols.size]!;
      symbols.set(color, symbol);
      palette[symbol] = color;
    }
    heights.forEach((barHeight, index) => {
      if (height - y > barHeight) return;
      const start = Math.floor((index * width) / heights.length);
      const end = Math.floor(((index + 1) * width) / heights.length);
      const pixel = index === selectedIndex ? "_" : symbol;
      if (index === selectedIndex) palette._ = "#FFFFFF";
      for (let x = start; x < end; x++) grid[y]![x] = pixel;
    });
  }

  return generateXpm2({ palette, grid: grid.map((line) => line.join("")) });
}
