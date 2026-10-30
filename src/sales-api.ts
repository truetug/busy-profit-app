import { timestamp, type Point } from "./model/sales.ts";

const HISTORY_URL = "https://profit.busy.truetug.info/history.csv";
const REQUEST_TIMEOUT_MS = 20_000;

/** Downloads the public rolling CSV and validates every usable snapshot. */
export async function fetchHistory(): Promise<Point[]> {
  const startedAt = Date.now();
  let timeout: ReturnType<typeof setTimeout> | undefined;
  let csv: string;
  try {
    console.info(`busy-profit: GET ${HISTORY_URL}`);
    const request = (async () => {
      const response = await fetch(HISTORY_URL, {
        headers: { Accept: "text/csv" },
      });
      console.info(`busy-profit: response status=${response.status} after ${Date.now() - startedAt}ms`);
      if (!response.ok) throw new Error(`Sales history returned HTTP ${response.status}`);
      const body = await response.text();
      console.info(`busy-profit: body chars=${body.length} after ${Date.now() - startedAt}ms`);
      return body;
    })();
    const deadline = new Promise<never>((_resolve, reject) => {
      timeout = setTimeout(
        () => reject(new Error("Sales history request timed out after 20 seconds")),
        REQUEST_TIMEOUT_MS,
      );
    });
    csv = await Promise.race([request, deadline]);
  } finally {
    clearTimeout(timeout);
  }
  const rows = csv.trim().split(/\r?\n/);
  if (rows.length < 2 || rows[0] !== "observed_at,bars_sold,source_updated_at") {
    throw new Error("Sales history has an invalid CSV header or no observations");
  }

  const points: Point[] = [];
  for (let index = 1; index < rows.length; index++) {
    const columns = rows[index]!.split(",");
    if (columns.length !== 3) continue;
    const at = columns[0]!;
    const count = Number(columns[1]);
    const atMs = timestamp(at);
    if (Number.isFinite(atMs) && Number.isSafeInteger(count) && count >= 0) {
      points.push({ at, count, atMs });
    }
  }
  if (points.length === 0) throw new Error("Sales history contains no valid observations");
  return points;
}
