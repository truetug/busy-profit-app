import { sellingDays } from "../model/sales.ts";

/** Splits the headline into a prominent sales count and a compact elapsed-days suffix. */
export function salesHeadline(count: number, now: Date): { count: string; days: string } {
  return { count: String(count), days: `/ ${sellingDays(now)}d` };
}
