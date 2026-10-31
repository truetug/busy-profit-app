import { timestamp, type Point } from "./model/sales.ts";

const FEED_BASE_URL = "https://profit.busy.truetug.info";
const REQUEST_TIMEOUT_MS = 20_000;
export type SalesFeed = "current" | "older";

/** Downloads the public rolling CSV and validates every usable snapshot. */
export async function fetchHistory(feed: SalesFeed, fetcher: typeof fetch = fetch): Promise<Point[]> {
  const url = `${FEED_BASE_URL}/${feed}.csv`;
  const startedAt = Date.now();
  let timeout: ReturnType<typeof setTimeout> | undefined;
  let csv: string;
  try {
    console.info(`busy-profit: GET ${url}`);
    const request = (async () => {
      const response = await fetcher(url, {
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
  const columnCount = rows[0] === "observed_at,bars_sold" ? 2
    : rows[0] === "observed_at,bars_sold,source_updated_at" ? 3 : 0;
  if (columnCount === 0) {
    throw new Error("Sales history has an invalid CSV header");
  }

  const points: Point[] = [];
  for (let index = 1; index < rows.length; index++) {
    const columns = rows[index]!.split(",");
    if (columns.length !== columnCount) continue;
    const at = columns[0]!;
    const count = Number(columns[1]);
    const atMs = timestamp(at);
    if (Number.isFinite(atMs) && Number.isSafeInteger(count) && count >= 0) {
      points.push({ at, count, atMs });
    }
  }
  if (points.length === 0 && !(feed === "older" && rows.length === 1)) {
    throw new Error("Sales history contains no valid observations");
  }
  return points;
}
