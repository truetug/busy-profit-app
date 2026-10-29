export type Point = { at: string; count: number };
export type SalesView = "current" | "hours" | "days";

const HISTORY_DAYS = 28;

/** Calculates the lifetime hourly sales pace since the configured launch date. */
export function lifetimeAverage(count: number, now: Date): string {
  const launched = new Date("2026-07-14T00:00:00");
  const hours = Math.max(1, (now.getTime() - launched.getTime()) / 3_600_000);
  return `${(count / hours).toFixed(1)}/h`;
}

/** Converts cumulative snapshots into non-negative sales increments by hour or calendar day. */
export function increments(points: Point[], unit: "hour" | "day", now: Date): number[] {
  const slots = unit === "hour" ? 24 : HISTORY_DAYS;
  const duration = unit === "hour" ? 3_600_000 : 86_400_000;
  const start = new Date(now);
  if (unit === "hour") start.setMinutes(0, 0, 0);
  else start.setHours(0, 0, 0, 0);
  start.setTime(start.getTime() - (slots - 1) * duration);

  const sorted = [...points].sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
  const result = Array<number>(slots).fill(0);
  for (let index = 1; index < sorted.length; index++) {
    const before = sorted[index - 1]!;
    const after = sorted[index]!;
    const increase = Math.max(0, after.count - before.count);
    const bucket = Math.floor((Date.parse(after.at) - start.getTime()) / duration);
    if (bucket >= 0 && bucket < slots) result[bucket] = result[bucket]! + increase;
  }
  return result;
}
