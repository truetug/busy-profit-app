import { column, generateXpm2, row, SCREEN, type Node } from "@busy-app/busy-lib";
import { increments, lifetimeAverage, type Point, type SalesView } from "../model/sales.ts";

const WHITE = "#FFFFFFFF";
const MUTED = "#A0A0A0FF";
const RED = "#FF3838";
type Screen = SalesView;

/** Maps a volume to red for high sales and green for low sales. */
function color(value: number, max: number): string {
  const strength = max === 0 ? 0 : Math.min(1, value / max);
  const red = Math.round(51 + strength * 204);
  const green = Math.round(204 - strength * 168);
  return `#${red.toString(16).padStart(2, "0")}${green.toString(16).padStart(2, "0")}44`;
}

/** Builds a full-width bar bitmap, tallest at the maximum and with an empty-slot baseline. */
function chart(values: number[], width: number, height: number): string {
  const max = Math.max(1, ...values);
  const grid = Array.from({ length: height }, () => Array<string>(width).fill("."));
  const palette: Record<string, string> = { ".": "None" };
  const symbols = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const barWidth = Math.max(1, Math.floor(width / values.length));
  values.forEach((value, index) => {
    const symbol = symbols[index % symbols.length]!;
    palette[symbol] = color(value, max);
    const barHeight = Math.round((value / max) * height);
    const xStart = index * barWidth;
    for (let y = height - barHeight; y < height; y++) {
      if (y < 0) continue;
      for (let x = xStart; x < Math.min(width, xStart + barWidth); x++) grid[y]![x] = symbol;
    }
  });
  return generateXpm2({ palette, grid: grid.map((line) => line.join("")) });
}

/** Renders the selected sales view: headline metrics, hourly activity, or the last 28 days. */
export function renderSalesScreen(args: {
  screen: Screen;
  now: Date;
  count?: number;
  points: Point[];
  stale: boolean;
}): Node {
  const { screen, now, count, points, stale } = args;
  const label = screen === "current" ? "SALES" : screen === "hours" ? "BY HOUR · 24H" : "BY DAY · 28D";
  const chartValues = screen === "hours" ? increments(points, "hour", now) : increments(points, "day", now);
  const bitmap = chart(chartValues, SCREEN.width, 9);
  const timestamp = `${String(now.getDate()).padStart(2, "0")}.${String(now.getMonth() + 1).padStart(2, "0")} ${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  const info: Node = column({ justify: "between", height: 6 }, [
    row({ justify: "between", width: SCREEN.width }, [
      { type: "text", id: "sales-label", text: label, font: "small", color: MUTED },
      { type: "text", id: "sales-time", text: stale ? "STALE" : timestamp, font: "small", color: stale ? RED : MUTED },
    ]),
    row({ justify: "between", width: SCREEN.width, align: "center" }, [
      { type: "text", id: "sales-count", text: count === undefined ? "NO DATA" : `${count.toLocaleString()} BARS`, font: "global", color: WHITE },
      { type: "text", id: "sales-average", text: count === undefined ? "" : lifetimeAverage(count, now), font: "small", color: WHITE },
    ]),
  ]);
  return column({ justify: "between", height: SCREEN.height }, [
    info,
    { type: "xpmbitmap", id: "sales-chart", data: bitmap, width: SCREEN.width, height: 9, opacity: 100 },
  ]);
}
