export const MINUTE_MS = 60_000;

/** Schedules a display update every minute and returns a function that stops the clock. */
export function startMinuteClock(
  onMinute: () => void,
  schedule: typeof setInterval = setInterval,
  cancel: typeof clearInterval = clearInterval,
): () => void {
  const timer = schedule(onMinute, MINUTE_MS);
  return () => cancel(timer);
}
