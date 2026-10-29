import type { Point } from "./model/sales.ts";

const HISTORY_URL = "https://profit.busy.truetug.info/history.csv";

/** Downloads the public rolling CSV and validates every usable snapshot. */
export async function fetchHistory(): Promise<Point[]> {
  const response = await fetch(HISTORY_URL, {
    headers: { Accept: "text/csv" },
  });
  if (!response.ok) throw new Error(`Sales history returned HTTP ${response.status}`);

  const rows = (await response.text()).trim().split(/\r?\n/);
  if (rows.length < 2 || rows[0] !== "observed_at,bars_sold,source_updated_at") {
    throw new Error("Sales history has an invalid CSV header or no observations");
  }

  const points: Point[] = [];
  for (let index = 1; index < rows.length; index++) {
    const columns = rows[index]!.split(",");
    if (columns.length !== 3) continue;
    const at = columns[0]!;
    const count = Number(columns[1]);
    if (Number.isFinite(Date.parse(at)) && Number.isSafeInteger(count) && count >= 0) {
      points.push({ at, count });
    }
  }
  if (points.length === 0) throw new Error("Sales history contains no valid observations");
  return points;
}
