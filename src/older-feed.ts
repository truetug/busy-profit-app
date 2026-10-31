import type { Point } from "./model/sales.ts";

export type OlderFeedState = {
  points: Point[];
  loadedDay?: string;
  loadedAnchor?: string;
  loading: boolean;
  failed: boolean;
};

/** Coordinates background history loading without blocking current sales refreshes. */
export function createOlderFeedLoader(
  load: () => Promise<Point[]>,
  onChange: (state: OlderFeedState) => void,
  onError: (error: unknown) => void,
) {
  let state: OlderFeedState = { points: [], loading: false, failed: false };
  let stopped = false;

  async function refresh(day: string, anchor?: string): Promise<void> {
    if (stopped || state.loading || (state.loadedDay === day && state.loadedAnchor === anchor)) return;
    state = { ...state, loading: true, failed: false };
    onChange(state);
    try {
      const points = await load();
      if (stopped) return;
      if (anchor && points.length > 0 && points[points.length - 1]!.at !== anchor) {
        throw new Error("Sales feeds have different boundary observations");
      }
      state = { points, loadedDay: day, loadedAnchor: anchor, loading: false, failed: false };
    } catch (error) {
      if (stopped) return;
      state = { ...state, loading: false, failed: true };
      onError(error);
    }
    if (!stopped) onChange(state);
  }

  function stop(): void {
    stopped = true;
  }

  return { refresh, stop };
}
