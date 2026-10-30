import { generateXpm2 } from "@busy-app/busy-lib";

const EMPTY = ".";
const COLORS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
export const SALES_ERROR_COLOR = "#FF3838FF";

/** Maps low sales to green and high sales to red for the history screens. */
function colorForValue(value: number, max: number): string {
  const strength = max === 0 ? 0 : Math.min(1, value / max);
  const red = Math.round(51 + strength * 204);
  const green = Math.round(204 - strength * 168);
  return `#${red.toString(16).padStart(2, "0")}${green.toString(16).padStart(2, "0")}44`;
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

/** Builds a transparent bar-chart bitmap from raw sales values. */
export function dailySalesIcon(values: number[], width: number, height: number): string {
  return dailySalesIconFromHeights(dailySalesHeights(values, height), width, height);
}

/** Builds the icon bitmap from pre-scaled heights, used for frame-by-frame transitions. */
export function dailySalesIconFromHeights(heights: number[], width: number, height: number): string {
  const grid = Array.from({ length: height }, () => Array<string>(width).fill(EMPTY));
  const palette: Record<string, string> = { [EMPTY]: "None" };

  heights.forEach((barHeight, index) => {
    const symbol = COLORS[index % COLORS.length]!;
    const normalized = barHeight <= 1 ? 0 : (barHeight - 1) / Math.max(1, height - 1);
    const red = Math.round(35 + normalized * 220);
    const green = Math.round(175 - normalized * 130);
    const blue = Math.round(75 - normalized * 40);
    palette[symbol] = `#${red.toString(16).padStart(2, "0")}${green.toString(16).padStart(2, "0")}${blue.toString(16).padStart(2, "0")}`;
    const start = Math.floor((index * width) / heights.length);
    const end = Math.floor(((index + 1) * width) / heights.length);

    for (let y = height - barHeight; y < height; y++) {
      for (let x = start; x < end; x++) grid[y]![x] = symbol;
    }
  });

  return generateXpm2({ palette, grid: grid.map((line) => line.join("")) });
}

/** Builds an edge-to-edge historical bitmap, highlighting the selected day's complete bar in white. */
export function historicalSalesIcon(values: number[], width: number, height: number, selectedIndex = -1): string {
  const grid = Array.from({ length: height }, () => Array<string>(width).fill(EMPTY));
  const palette: Record<string, string> = { [EMPTY]: "None" };
  const max = Math.max(1, ...values);

  values.forEach((value, index) => {
    const symbol = COLORS[index % COLORS.length]!;
    palette[symbol] = index === selectedIndex ? "#FFFFFFFF" : colorForValue(value, max);
    const barHeight = index === selectedIndex
      ? Math.max(1, Math.round((value / max) * height))
      : Math.round((value / max) * height);
    const start = Math.floor((index * width) / values.length);
    const end = Math.floor(((index + 1) * width) / values.length);
    for (let y = height - barHeight; y < height; y++) {
      for (let x = start; x < end; x++) grid[y]![x] = symbol;
    }
  });

  return generateXpm2({ palette, grid: grid.map((line) => line.join("")) });
}
