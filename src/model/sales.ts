export type Point = { at: string; count: number; atMs?: number };
export type SalesView = "home" | "days";
export type DaySales = { atMs: number; count: number };

export const SALES_HISTORY_DAYS = 36;
export const HOME_HISTORY_DAYS = 8;

/** Combines the older and recent snapshots, keeping the current feed at the overlap. */
export function mergeHistory(older: Point[], current: Point[]): Point[] {
  const byTime = new Map<number, Point>();
  for (const point of [...older, ...current]) {
    const atMs = point.atMs ?? timestamp(point.at);
    if (Number.isFinite(atMs)) byTime.set(atMs, { ...point, atMs });
  }
  return [...byTime.entries()].sort((a, b) => a[0] - b[0]).map((entry) => entry[1]);
}

/** Parses Shopify's ISO timestamps without relying on the Bar's incomplete Date.parse implementation. */
export function timestamp(value: string): number {
  if (value.length < 20 || value[4] !== "-" || value[7] !== "-" || value[10] !== "T" || value[13] !== ":" || value[16] !== ":") return Number.NaN;
  const digits = (start: number, end: number): boolean => {
    for (let index = start; index < end; index++) {
      const code = value.charCodeAt(index);
      if (code < 48 || code > 57) return false;
    }
    return true;
  };
  if (!digits(0, 4) || !digits(5, 7) || !digits(8, 10) || !digits(11, 13) || !digits(14, 16) || !digits(17, 19)) return Number.NaN;

  const year = Number(value.slice(0, 4));
  const month = Number(value.slice(5, 7));
  const day = Number(value.slice(8, 10));
  const hour = Number(value.slice(11, 13));
  const minute = Number(value.slice(14, 16));
  const second = Number(value.slice(17, 19));
  if (month < 1 || month > 12 || hour > 23 || minute > 59 || second > 59) return Number.NaN;
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysInMonth = month === 2 ? (leap ? 29 : 28) : [4, 6, 9, 11].includes(month) ? 30 : 31;
  if (day < 1 || day > daysInMonth) return Number.NaN;

  let index = 19;
  let milliseconds = 0;
  if (value[index] === ".") {
    index++;
    const fractionStart = index;
    while (index < value.length && value.charCodeAt(index) >= 48 && value.charCodeAt(index) <= 57) index++;
    if (index === fractionStart) return Number.NaN;
    const fraction = value.slice(fractionStart, Math.min(index, fractionStart + 3));
    milliseconds = Number((fraction + "000").slice(0, 3));
  }
  const utc = Date.UTC(year, month - 1, day, hour, minute, second, milliseconds);
  const zone = value[index];
  if (zone === "Z" && index === value.length - 1) return utc;
  if ((zone !== "+" && zone !== "-") || index + 6 !== value.length || value[index + 3] !== ":") return Number.NaN;
  if (!digits(index + 1, index + 3) || !digits(index + 4, index + 6)) return Number.NaN;
  const offsetHours = Number(value.slice(index + 1, index + 3));
  const offsetMinutes = Number(value.slice(index + 4, index + 6));
  if (offsetHours > 23 || offsetMinutes > 59) return Number.NaN;
  const shift = (offsetHours * 60 + offsetMinutes) * 60_000 * (zone === "+" ? 1 : -1);
  return utc - shift;
}

/** Returns full selling days elapsed since launch, including day zero. */
export function sellingDays(now: Date): number {
  const start = new Date(2026, 6, 14).getTime();
  return Math.max(0, Math.floor((now.getTime() - start) / 86_400_000));
}

/** Compares sales in the latest 24 hours with the preceding 24-hour window. */
export function dailyChange(points: Point[], now: Date): number | undefined {
  const ordered = points
    .map((point) => ({ point, atMs: point.atMs ?? timestamp(point.at) }))
    .sort((a, b) => a.atMs - b.atMs);
  if (ordered.length < 2) return undefined;
  const current = now.getTime();
  const countAt = (cutoff: number): number | undefined => {
    for (let i = ordered.length - 1; i >= 0; i--) {
      if (ordered[i]!.atMs <= cutoff) return ordered[i]!.point.count;
    }
    return undefined;
  };
  const nowCount = countAt(current);
  const dayCount = countAt(current - 86_400_000);
  const twoDayCount = countAt(current - 172_800_000);
  if (nowCount === undefined || dayCount === undefined || twoDayCount === undefined) return undefined;
  return Math.max(0, nowCount - dayCount) - Math.max(0, dayCount - twoDayCount);
}

/** Calculates the lifetime hourly sales pace since the configured launch date. */
export function lifetimeAverage(count: number, now: Date): string {
  const launched = new Date("2026-07-14T00:00:00");
  const hours = Math.max(1, (now.getTime() - launched.getTime()) / 3_600_000);
  return `${(count / hours).toFixed(1)}/h`;
}

/** Converts cumulative snapshots into non-negative sales increments by hour or calendar day. */
export function increments(
  points: Point[],
  unit: "hour" | "day",
  now: Date,
  slots = unit === "hour" ? 24 : SALES_HISTORY_DAYS,
): number[] {
  const duration = unit === "hour" ? 3_600_000 : 86_400_000;
  const start = new Date(now);
  if (unit === "hour") start.setMinutes(0, 0, 0);
  else start.setHours(0, 0, 0, 0);
  start.setTime(start.getTime() - (slots - 1) * duration);

  const sorted = points
    .map((point) => ({ point, atMs: point.atMs ?? timestamp(point.at) }))
    .sort((a, b) => a.atMs - b.atMs);
  const result = Array<number>(slots).fill(0);
  for (let index = 1; index < sorted.length; index++) {
    const before = sorted[index - 1]!.point;
    const after = sorted[index]!.point;
    const increase = Math.max(0, after.count - before.count);
    const bucket = Math.floor((sorted[index]!.atMs - start.getTime()) / duration);
    if (bucket >= 0 && bucket < slots) result[bucket] = result[bucket]! + increase;
  }
  return result;
}

/** Returns daily sales paired with each local calendar day's midnight timestamp. */
export function dailySales(points: Point[], now: Date, slots = SALES_HISTORY_DAYS): DaySales[] {
  const values = increments(points, "day", now, slots);
  const firstDay = new Date(now);
  firstDay.setHours(0, 0, 0, 0);
  firstDay.setDate(firstDay.getDate() - (slots - 1));

  return values.map((count, index) => {
    const day = new Date(firstDay);
    day.setDate(firstDay.getDate() + index);
    return { atMs: day.getTime(), count };
  });
}
