export type HomePhase = "summary" | "recent-days";
export const INITIAL_HOME_PHASE: HomePhase = "summary";

/** Switches the home headline between lifetime totals and the four recent daily counts. */
export function nextHomePhase(phase: HomePhase): HomePhase {
  return phase === "summary" ? "recent-days" : "summary";
}

/** Moves a day cursor by one or more positions without allowing it past the graph edges. */
export function moveDayCursor(current: number, delta: number, dayCount: number): number {
  if (dayCount <= 0) return 0;
  return Math.min(Math.max(current + delta, 0), dayCount - 1);
}
