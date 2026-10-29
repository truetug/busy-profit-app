// Temperature → color, anchored every 7.5 °C from -30 to +30. Celsius only; Fahrenheit readings run off the last stop.

type Stop = { temp: number; color: string };

/** Anchors, coldest first. */
const STOPS: Stop[] = [
  { temp: -30, color: "#21028B" },
  { temp: -22.5, color: "#393CB0" },
  { temp: -15, color: "#537AD7" },
  { temp: -7.5, color: "#7BAFED" },
  { temp: 0, color: "#D0CEC7" },
  { temp: 7.5, color: "#F8C81A" },
  { temp: 15, color: "#FE9A12" },
  { temp: 22.5, color: "#FE520F" },
  { temp: 30, color: "#FE0200" },
];

/** "#RRGGBB" → the three channels. */
function channels(color: string): [number, number, number] {
  return [
    parseInt(color.slice(1, 3), 16),
    parseInt(color.slice(3, 5), 16),
    parseInt(color.slice(5, 7), 16),
  ];
}

/** The three channels → "#RRGGBB". */
function hex(r: number, g: number, b: number): string {
  const pair = (v: number) => Math.round(v).toString(16).padStart(2, "0");
  return `#${pair(r)}${pair(g)}${pair(b)}`.toUpperCase();
}

/** The color for `temp`, mixed from the anchors it falls between. */
export function tempColor(temp: number): string {
  const first = STOPS[0];
  const last = STOPS[STOPS.length - 1];
  if (temp <= first.temp) return first.color;
  if (temp >= last.temp) return last.color;

  for (let i = 1; i < STOPS.length; i++) {
    const upper = STOPS[i];
    if (temp > upper.temp) continue;

    const lower = STOPS[i - 1];
    const ratio = (temp - lower.temp) / (upper.temp - lower.temp);

    const [r1, g1, b1] = channels(lower.color);
    const [r2, g2, b2] = channels(upper.color);
    return hex(
      r1 + (r2 - r1) * ratio,
      g1 + (g2 - g1) * ratio,
      b1 + (b2 - b1) * ratio,
    );
  }

  return last.color;
}
