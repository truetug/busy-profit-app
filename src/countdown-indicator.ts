import { render } from "@busy-app/busy-lib";

/** Positions the remaining time as a shrinking right-edge line on the home screen. */
export function countdownIndicator(remainingMs: number) {
  const height = Math.max(0, Math.min(16, Math.ceil(remainingMs / 60_000 * 16)));
  if (height === 0) return [];
  return render({
    type: "rectangle",
    id: "sales-countdown",
    fill: "solid",
    fill_colors: ["#404040FF"],
    border_width: 0,
    width: 1,
    height,
    dx: 71,
    dy: 16 - height,
    z_index: 5,
  });
}
