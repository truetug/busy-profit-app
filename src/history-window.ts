import type { Point } from "./model/sales.ts";
import { mergeHistory, SALES_HISTORY_DAYS, timestamp } from "./model/sales.ts";

/** Measure closes at local midnights; missing or corrected days stay unknown. */
export function archivedDays(points: Point[], end: Date): (number | null)[] {
  const boundary = new Date(end);
  boundary.setHours(0, 0, 0, 0);
  boundary.setDate(boundary.getDate() - SALES_HISTORY_DAYS + 1);
  let index = 0;
  let last: Point | undefined;
  const close = (): number | undefined => {
    while (index < points.length && timestamp(points[index]!.at) < boundary.getTime()) last = points[index++];
    return last && boundary.getTime() - timestamp(last.at) <= 7_200_000 ? last.count : undefined;
  };
  let before = close();
  return Array.from({ length: SALES_HISTORY_DAYS }, () => {
    boundary.setDate(boundary.getDate() + 1);
    const after = close();
    const value = before !== undefined && after !== undefined && after >= before ? after - before : null;
    before = after;
    return value;
  });
}

/** Loads only UTC months intersecting the local window plus its baseline. */
export function createHistoryWindow(load: (month: string) => Promise<Point[]>) {
  const cache = new Map<string, Point[]>();
  let cacheDay = "";
  return async (end: Date): Promise<Point[]> => {
    const today = new Date().toISOString().slice(0, 10);
    if (cacheDay && cacheDay !== today) cache.delete(cacheDay.slice(0, 7));
    cacheDay = today;
    const start = new Date(end);
    start.setHours(0, 0, 0, 0);
    start.setDate(start.getDate() - SALES_HISTORY_DAYS);
    const cursor = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), 1));
    let points: Point[] = [];
    while (cursor <= end) {
      const month = cursor.toISOString().slice(0, 7);
      let rows = cache.get(month);
      if (!rows) rows = await load(month);
      cache.delete(month);
      cache.set(month, rows);
      if (cache.size > 4) cache.delete(cache.keys().next().value!);
      points = mergeHistory(points, rows);
      cursor.setUTCMonth(cursor.getUTCMonth() + 1);
    }
    return points;
  };
}
