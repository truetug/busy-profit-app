/** Moves a day cursor by one or more positions without allowing it past the graph edges. */
export function moveDayCursor(current: number, delta: number, dayCount: number): number {
  if (dayCount <= 0) return 0;
  return Math.min(Math.max(current + delta, 0), dayCount - 1);
}
