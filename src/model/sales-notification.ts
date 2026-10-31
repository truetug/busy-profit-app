export type SalesNotification = { count: number; sound: "cash" | "applause" };

/** Selects a single notification only for a genuine increase after initial loading. */
export function salesNotification(previous: number | undefined, current: number): SalesNotification | undefined {
  if (previous === undefined || current <= previous) return undefined;
  return { count: current, sound: Math.floor(current / 100) > Math.floor(previous / 100) ? "applause" : "cash" };
}
