// The hourly forecast as an XPM2 bitmap: one hour per 3-pixel bar.

import { generateXpm2 } from "@busy-app/busy-lib";
import { tempColor } from "./tempColor.ts";

export const HOURS = 24;
export const BAR_W = 3;
export const GRAPH_W = HOURS * BAR_W;
export const GRAPH_H = 9;

const MARKER_COLOR = "#FFFFFF";
const EMPTY = ".";

const MIN_H = 2;
const MAX_H = 7;

/** Bar heights in pixels, scaled between the day's coldest and warmest hours. */
function heights(temps: number[]): number[] {
  let min = temps[0];
  let max = temps[0];
  for (const t of temps) {
    if (t < min) min = t;
    if (t > max) max = t;
  }

  const span = max - min;
  return temps.map((t) => {
    if (span === 0) return MAX_H;
    const norm = (t - min) / span;
    return MIN_H + Math.round(norm * (MAX_H - MIN_H));
  });
}

/**
 * The graph as it is drawn: the bitmap of the bars, and where the marker sits on each hour.
 *
 * Neither depends on the hour the marker is on, so both are built once per forecast.
 */
export interface Graph {
  /** The bars as an XPM2 bitmap. */
  readonly bitmap: string
  /** The marker box for each hour, indexed as `temps` is. */
  readonly markers: readonly MarkerBox[]
}

export interface MarkerBox {
  readonly x: number
  readonly y: number
  readonly height: number
}

/** Builds everything the forecast screen draws from the temperatures alone. */
export function buildGraph(temps: number[]): Graph {
  const hours = temps.slice(0, HOURS);
  const bars = heights(hours);

  const markers = bars.map((bar, hour) => {
    // The head straddles the bar's top row.
    const y = Math.max(0, GRAPH_H - bar - 1);
    return { x: hour * BAR_W, y, height: GRAPH_H - y };
  });

  return { bitmap: renderBars(hours, bars), markers };
}

/** The bars alone; the marker is a separate element drawn over them. */
function renderBars(hours: number[], bars: number[]): string {

  // One symbol per distinct color; the palette holds at most 32.
  const symbols = new Map<string, string>();
  const palette: Record<string, string> = { [EMPTY]: "None" };
  const ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz";

  const symbolFor = (color: string): string => {
    const known = symbols.get(color);
    if (known) return known;
    const symbol = ALPHABET.charAt(symbols.size);
    symbols.set(color, symbol);
    palette[symbol] = color;
    return symbol;
  };

  const columns = hours.map((temp, hour) => ({
    symbol: symbolFor(tempColor(temp)),
    height: bars[hour],
  }));

  const grid: string[][] = [];
  for (let y = 0; y < GRAPH_H; y++) {
    // Bars grow from the bottom.
    const depth = GRAPH_H - y;
    const row: string[] = [];
    for (const column of columns) {
      const symbol = column.height >= depth ? column.symbol : EMPTY;
      for (let i = 0; i < BAR_W; i++) row.push(symbol);
    }
    grid.push(row);
  }

  return generateXpm2({ palette, grid: grid.map((row) => row.join("")) });
}

/** The marker bitmaps by height; a bar has only so many. */
const markers = new Map<number, string>();

/** A 3×3 head over the bar, then a single-pixel stem to the foot of the graph. */
export function renderMarker(height: number): string {
  const known = markers.get(height);
  if (known !== undefined) return known;

  const bitmap = buildMarker(height);
  markers.set(height, bitmap);
  return bitmap;
}

function buildMarker(height: number): string {
  const empty = ".";
  const ink = "#";
  const middle = BAR_W >> 1;

  const rows: string[] = [];
  for (let y = 0; y < height; y++) {
    if (y < BAR_W) {
      rows.push(ink.repeat(BAR_W));
      continue;
    }
    rows.push(
      Array.from({ length: BAR_W }, (_, x) => (x === middle ? ink : empty)).join(""),
    );
  }

  return generateXpm2({
    palette: { [empty]: "None", [ink]: MARKER_COLOR },
    grid: rows,
  });
}
