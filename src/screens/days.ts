// The multi-day screen: one day at a time, split into daylight and night.
//
//   ┌────────────────────────┐
//   │ DAY   ☀ +23   23 May   │
//   │ NIGHT ☾ +20   24 May   │
//   └────────────────────────┘

import { formatDay, formatMonth } from "@shared/datetime";
import { column, list, render, row, SCREEN, stack, type Node } from "@busy-app/busy-lib";
import type { DayForecast } from "../api.ts";
import type { Drawn } from "../types.ts";
import { formatTemp } from "../temp.ts";
import { iconFor } from "../wmo.ts";

const ICON = { width: 7, height: 7 };

/** Space between a label, its icon and its reading. */
const GAP = 1;

/** Width of "NIGHT", so both rows line up. */
const LABEL_W = 21;

const DAY_COLOR = "#F5A623FF";
const NIGHT_COLOR = "#4A90D9FF";

const PANEL_W = 47;
const PANEL_COLOR = "#0A1A4AFF";

/** Redrawing one element alone leaves the panel on top of it unless the order is spelled out. */
const PANEL_Z = 10;
const CONTENT_Z = 50;


const WHITE = "#FFFFFFFF";
const DIM = "#808080FF";

const TOP_DY = 0;
const BOTTOM_DY = 0;

const LIST_W = SCREEN.width - PANEL_W - 1;
const LIST_H = SCREEN.height;

/** Clear space between the dates and the scrollbar. */
const DATE_GAP = 2;

const BAR_W = 1;
const TRACK_COLOR = "#404040FF";
const THUMB_COLOR = "#FFFFFFFF";

/** The dates as they are drawn, by ISO date. */
const dates = new Map<string, string>();

/** "23 May" */
function formatDate(date: string): string {
  const known = dates.get(date);
  if (known !== undefined) return known;

  const at = new Date(`${date}T12:00:00`);
  const text = `${formatDay(at)} ${formatMonth(at)}`;
  dates.set(date, text);
  return text;
}

/**
 * One half of the day: its name, its condition and its mean temperature.
 *
 * @param slot - Which element ids this half draws under. See DAY_SLOT.
 */
function half(
  slot: { label: string; icon: string; temp: string },
  label: string,
  color: string,
  code: number,
  temp: number,
  dy: number,
  daylight: boolean,
): Node {
  return row({ align: "center", gap: GAP }, [
    row({ width: LABEL_W }, [
      {
        type: "text",
        id: slot.label,
        text: label,
        font: "small",
        color,
        dy,
        z_index: CONTENT_Z,
      },
    ]),
    {
      type: "image",
      id: slot.icon,
      path: `images/${iconFor(code, daylight)}`,
      opacity: 100,
      dy,
      z_index: CONTENT_Z,
      ...ICON,
    },
    {
      type: "text",
      id: slot.temp,
      text: formatTemp(temp, "none"),
      font: "small",
      color: WHITE,
      dy,
      z_index: CONTENT_Z,
    },
  ]);
}

/** Ids shared with the other screens, so moving between them redraws an element instead of replacing it. */
const DAY_SLOT = { label: "text-a", icon: "image-icon", temp: "text-temp" };
const NIGHT_SLOT = { label: "text-b", icon: "image-icon2", temp: "text-sub" };

/** The panel beside the dates: the labels, conditions and readings for the day on show. */
function panel(current: DayForecast): Node {
  return stack({}, [
    {
      type: "rectangle",
      id: "rect-panel",
      width: PANEL_W,
      height: SCREEN.height,
      // Without these a rectangle is a white outline and nothing else.
      fill: "solid",
      fill_colors: [PANEL_COLOR],
      border_width: 0,
      z_index: PANEL_Z,
    },
    column({ justify: "between", width: PANEL_W, height: SCREEN.height }, [
      half(DAY_SLOT, "DAY", DAY_COLOR, current.dayCode, current.day, TOP_DY, true),
      half(NIGHT_SLOT, "NIGHT", NIGHT_COLOR, current.nightCode, current.night, BOTTOM_DY, false),
    ]),
  ]);
}

/**
 * The frame. Only the panel goes through the layout engine; `list` places the dates itself.
 *
 * @param days every day of the forecast
 * @param at index of the day on show
 */
export function daysScreen(days: DayForecast[], at: number): Drawn[] {
  const labels = days.map((day) => formatDate(day.date));

  return [
    ...render(panel(days[at])),
    ...list({
      id: "list",
      items: labels,
      selected: at,
      x: PANEL_W + 1,
      y: 0,
      width: LIST_W,
      height: LIST_H,
      font: "small",
      gap: DATE_GAP,
      style: { color: DIM, activeColor: WHITE },
      scrollbar: "right",
      scrollbarStyle: { trackColor: TRACK_COLOR, thumbColor: THUMB_COLOR },
      scrollbarGap: 1,
      scrollbarWidth: BAR_W,
      z_index: CONTENT_Z,
    }),
  ];
}
