export const SALES_POLL_INTERVAL_MS = 60_000;

/** Starts current-sales polling immediately and repeats until the app exits. */
export function startSalesPolling(
  onPoll: () => void,
  schedule: typeof setInterval = setInterval,
  cancel: typeof clearInterval = clearInterval,
): () => void {
  const timer = schedule(onPoll, SALES_POLL_INTERVAL_MS);
  onPoll();
  return () => cancel(timer);
}
