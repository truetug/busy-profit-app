// The forecast screen: the day ahead, one hour at a time.
//
//   ┌────────────────────────┐
//   │ ☀ +23°          12:00  │
//   │ ▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆▇  │
//   └────────────────────────┘
//
// Everything on it describes the hour the marker stands on, not the present one.

import { column, row, stack, type Node } from "@busy-app/busy-lib";
import type { ForecastHour } from "../api.ts";
import { BAR_W, GRAPH_H, GRAPH_W, renderMarker, type Graph } from "../graph.ts";
import { formatTemp } from "../temp.ts";
import { iconFor } from "../wmo.ts";

const ICON = { width: 7, height: 7 };

/** Space between the icon and the temperature. */
const GAP = 2;

const WHITE = "#FFFFFFFF";
/** The clock is dimmed: it labels the hour rather than telling the time. */
const DIM = "#AAAAAAFF";

/** "12:00" for the hour the marker sits on. */
function formatHour(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`;
}

/**
 * The frame.
 *
 * @param hours every hour the graph draws
 * @param at index into `hours` of the one the marker sits on
 */
export function forecastScreen(hours: ForecastHour[], graph: Graph, at: number): Node {
  const current = hours[at];
  const box = graph.markers[at];

  // Apart, so a step redraws the marker and leaves the graph alone.
  const bars: Node[] = [
    {
      type: "xpmbitmap",
      id: "xpm-graph",
      data: graph.bitmap,
      opacity: 100,
      width: GRAPH_W,
      height: GRAPH_H,
    },
    {
      type: "xpmbitmap",
      id: "xpm-marker",
      data: renderMarker(box.height),
      opacity: 100,
      width: BAR_W,
      height: box.height,
      // Graph coordinates: the stack pins both to its top-left.
      dx: box.x,
      dy: box.y,
      z_index: 60,
    },
  ];

  return column({ justify: "between" }, [
    row({ justify: "between", align: "center", width: GRAPH_W }, [
      row({ align: "center", gap: GAP }, [
        {
          type: "image",
          id: "image-icon",
          path: `images/${iconFor(current.code, current.daylight)}`,
          opacity: 100,
          ...ICON,
        },
        {
          type: "text",
          id: "text-temp",
          text: formatTemp(current.temp, "degree"),
          font: "small",
          color: WHITE,
        },
      ]),
      {
        type: "text",
        id: "text-sub",
        text: formatHour(current.hour),
        font: "small",
        color: DIM,
      },
    ]),
    stack({ width: GRAPH_W, height: GRAPH_H }, bars),
  ]);
}
