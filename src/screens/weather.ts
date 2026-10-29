// The weather screen: what it is doing outside, right now.
//
//   ┌────────────────────────┐
//   │ ☀  +15°C               │
//   │    25 Aug, 15:34       │
//   └────────────────────────┘
//
// The animation holds the left edge; everything else is text stacked beside it.

import { formatDay, formatHM, formatMonth } from "@shared/datetime";
import { column, row, SCREEN, type Node } from "@busy-app/busy-lib";
import type { CurrentWeather } from "../api.ts";
import { formatTemp } from "../temp.ts";
import { animationFor } from "../wmo.ts";

const ANIMATION = { width: 16, height: 16 };

/** Space between the animation and the text beside it. */
const GAP = 3;

const WHITE = "#FFFFFFFF";
const DIM = "#AAAAAAFF";

const TEMP_DY = 1;
/** Lifts the descenders of "p" and "," back onto the screen. */
const SUB_DY = -2;

/** What the line under the temperature carries, as the settings ask for it. */
export type SubLine = {
  time: boolean;
  date: boolean;
};

/** The line under the temperature: "25 Aug, 15:34", or either half of it alone. */
function subLine(now: Date, show: SubLine): string {
  const date = show.date ? `${formatDay(now)} ${formatMonth(now)}` : "";
  const time = show.time ? formatHM(now) : "";

  if (date && time) return `${date}, ${time}`;
  return date || time;
}

/** The frame: the condition on the left, the reading and the clock beside it. */
export function weatherScreen(weather: CurrentWeather, now: Date, show: SubLine): Node {
  const sub = subLine(now, show);

  const temp: Node = {
    type: "text",
    id: "text-temp",
    text: formatTemp(weather.temp),
    font: "bold",
    color: WHITE,
    dy: TEMP_DY,
  };

  // Two lines take the full height, one against each edge; the reading left alone centres itself against the animation instead.
  const beside: Node =
    sub === ""
      ? temp
      : column({ justify: "between", height: SCREEN.height }, [
          temp,
          {
            type: "text",
            id: "text-sub",
            text: sub,
            font: "small",
            color: DIM,
            dy: SUB_DY,
          },
        ]);

  return row({ align: "center", gap: GAP, height: SCREEN.height }, [
    {
      type: "animation",
      id: "anim",
      path: `animations/${animationFor(weather.code, weather.daylight)}`,
      loop: true,
      await_previous_end: false,
      opacity: 100,
      ...ANIMATION,
    },
    beside,
  ]);
}
