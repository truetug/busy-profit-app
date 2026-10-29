// WMO weather codes → the assets that depict them. Several codes share one condition: the list is finer than what ships in animations/ and images/.

/** A weather condition, as far as this app draws it. */
export type Condition =
  | "clear"
  | "mclear"
  | "pcloudy"
  | "cloudy"
  | "fog"
  | "drizzle"
  | "rain"
  | "heavy_rain"
  | "sun_showers"
  | "flurries"
  | "snow"
  | "heavy_snow"
  | "blizzard"
  | "thunderstorms"
  | "windy";

/** Conditions that look different by day and by night; their assets carry a `_day`/`_night` suffix. */
const DIURNAL = new Set<Condition>(["clear", "mclear", "pcloudy"]);

/** WMO code → condition. Anything unlisted is drawn as cloudy. */
const CONDITIONS = new Map<number, Condition>([
  [0, "clear"],
  [1, "mclear"],
  [2, "pcloudy"],
  [3, "cloudy"],
  [45, "fog"],
  [48, "fog"],
  // Drizzle, freezing drizzle.
  [51, "drizzle"],
  [53, "drizzle"],
  [55, "drizzle"],
  [56, "drizzle"],
  [57, "drizzle"],
  // Rain, freezing rain.
  [61, "rain"],
  [63, "rain"],
  [65, "heavy_rain"],
  [66, "rain"],
  [67, "heavy_rain"],
  // Snowfall, snow grains.
  [71, "flurries"],
  [73, "snow"],
  [75, "heavy_snow"],
  [77, "flurries"],
  // Rain showers.
  [80, "sun_showers"],
  [81, "rain"],
  [82, "heavy_rain"],
  // Snow showers.
  [85, "snow"],
  [86, "blizzard"],
  // Thunderstorms, with and without hail.
  [95, "thunderstorms"],
  [96, "thunderstorms"],
  [99, "thunderstorms"],
]);

/** The condition a code stands for. */
export function conditionOf(wmo: number): Condition {
  return CONDITIONS.get(wmo) ?? "cloudy";
}

/** Base name of the assets for a code, without an extension. */
function assetFor(wmo: number, daylight: boolean): string {
  const condition = conditionOf(wmo);
  return DIURNAL.has(condition) ? `${condition}_${daylight ? "day" : "night"}` : condition;
}

/** Every condition has an icon of its own. */
export function iconFor(wmo: number, daylight: boolean): string {
  return `${assetFor(wmo, daylight)}.png`;
}

/** Every icon has an animation under the same name. */
export function animationFor(wmo: number, daylight: boolean): string {
  return `${assetFor(wmo, daylight)}.anim`;
}
