import { AccessKeyRequired } from "./sales-api.ts";

export type DaysView = { revision: string; timezone: string; start: string; values: (number | null)[]; total: number; more: boolean };
export type HoursView = { revision: string; timezone: string; date: string; starts: string[]; values: (number | null)[] };

/** Read a bounded compact view without accepting malformed sales arrays. */
export async function fetchView<T extends DaysView | HoursView>(path: string, key: string, fetcher: typeof fetch = fetch): Promise<T> {
  if (!key) throw new AccessKeyRequired();
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const request = (async () => {
      const response = await fetcher("https://profit.busy.truetug.info/v1/" + path, {
        headers: { Authorization: "Bearer " + key, Accept: "application/json" },
      });
      if (response.status === 401 || response.status === 403) throw new AccessKeyRequired();
      if (!response.ok) throw new Error("View HTTP " + response.status);
      const text = await response.text();
      if (text.length > 24000) throw new Error("View too large");
      const value = JSON.parse(text) as T;
      if (!Array.isArray(value.values) || value.values.length > 3660 ||
        value.values.some((n) => n !== null && (!Number.isSafeInteger(n) || n < 0)) ||
        typeof value.revision !== "string") throw new Error("Invalid view");
      if ("start" in value && (!/^\d{4}-\d{2}-\d{2}$/.test(value.start) || !Number.isSafeInteger(value.total) || value.total<0)) throw new Error("Invalid daily view");
      if ("starts" in value && (!Array.isArray(value.starts) || value.starts.length!==value.values.length || value.values.length>25 ||
        value.starts.some(at=>typeof at!=="string" || at.length>64))) throw new Error("Invalid hourly view");
      return value;
    })();
    return await Promise.race([request, new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new Error("View timeout")), 20000);
    })]);
  } finally { clearTimeout(timer); }
}

/** Convert a calendar date without relying on the firmware's Date.parse. */
export function calendarDate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year!, month! - 1, day!, 12);
}

/** Format local calendar arithmetic as the API's date-only key. */
export function dateKey(date: Date): string {
  return [date.getFullYear(), String(date.getMonth()+1).padStart(2,"0"), String(date.getDate()).padStart(2,"0")].join("-");
}
