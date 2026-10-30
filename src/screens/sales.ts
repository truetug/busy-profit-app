import { column, row, SCREEN, stack, type Node } from "@busy-app/busy-lib";
import { dailySales, increments, type Point, type SalesView } from "../model/sales.ts";
import type { HomePhase } from "../model/navigation.ts";
import { formatDateTime } from "../../shared/datetime.ts";
import { dailySalesIcon, dailySalesIconFromHeights, historicalSalesIcon, SALES_ERROR_COLOR } from "./sales-chart.ts";
import { salesHeadline } from "./sales-format.ts";
import { SALES_CHART_ICON_ID, SALES_LOADING_ICON_ID } from "./sales-ids.ts";

const WHITE = "#FFFFFFFF";
const MUTED = "#A0A0A0FF";
const DIM = "#AAAAAAFF";
const GAP = 3;
const SUB_DY = -1;
const TEXT_W = SCREEN.width - 16 - GAP;
type Screen = SalesView;

/** Renders the complete 28-day chart and the selected day's highlighted sales column. */
function renderDailyGraph(points: Point[], now: Date, selectedDay: number): Node {
  const days = dailySales(points, now);
  const selected = days[Math.min(Math.max(selectedDay, 0), days.length - 1)]!;
  const selectedDate = new Date(selected.atMs);
  return column({ justify: "between", height: SCREEN.height }, [
    row({ justify: "between", align: "center", width: SCREEN.width }, [
      {
        type: "text", id: "sales-selected-day",
        text: `${String(selectedDate.getDate()).padStart(2, "0")}.${String(selectedDate.getMonth() + 1).padStart(2, "0")}  ${selected.count}`,
        font: "small", color: WHITE,
      },
      { type: "text", id: "sales-history-label", text: "28D", font: "small", color: MUTED },
    ]),
    stack({ width: SCREEN.width, height: 9 }, [
      { type: "xpmbitmap", id: "sales-chart", data: historicalSalesIcon(days.map((day) => day.count), SCREEN.width, 9, selectedDay), width: SCREEN.width, height: 9, opacity: 100 },
    ]),
  ]);
}

/** Renders the four-day sales overview or the selected day in the full history chart. */
export function renderSalesScreen(args: {
  screen: Screen;
  homePhase: HomePhase;
  now: Date;
  count?: number;
  points: Point[];
  selectedDay: number;
  stale: boolean;
  iconHeights?: number[];
  error?: string;
}): Node {
  const { screen, homePhase, now, count, points, selectedDay, stale, iconHeights, error } = args;
  if (screen === "days") return renderDailyGraph(points, now, selectedDay);

  if (screen === "home") {
    const date = formatDateTime(now);
    const isLoading = count === undefined && !error;
    const days = dailySales(points, now, 4);
    const headline = count === undefined ? undefined : salesHeadline(count, now);
    const mark: Node = isLoading
      ? {
          type: "animation",
          id: SALES_LOADING_ICON_ID,
          path: "animations/sales_loading.anim",
          loop: true,
          await_previous_end: false,
          opacity: 100,
          width: 16,
          height: 16,
        }
      : {
          type: "xpmbitmap",
          id: SALES_CHART_ICON_ID,
          data: iconHeights
            ? dailySalesIconFromHeights(iconHeights, 16, 16)
            : dailySalesIcon(increments(points, "day", now, 4), 16, 16),
          width: 16,
          height: 16,
          opacity: 100,
        };
    return row({ align: "center", gap: GAP, width: SCREEN.width, height: SCREEN.height }, [
        mark,
        column({ justify: "between", height: SCREEN.height }, [
          homePhase === "recent-days" && count !== undefined
            ? row({ align: "center", justify: "between", width: TEXT_W }, days.map((day, index) => ({
                type: "text" as const,
                id: `sales-recent-count-${index}`,
                text: String(day.count),
                font: "small",
                color: WHITE,
              })))
            : headline
              ? row({ align: "center", gap: 1 }, [
                  {
                    type: "text", id: "sales-count", text: headline.count,
                    font: "bold", color: WHITE, dy: 1,
                  },
                  {
                    type: "text", id: "sales-days", text: headline.days,
                    font: "small", color: DIM,
                  },
                ])
            : {
                type: "text",
                id: "sales-count",
                text: error ? "NO DATA" : "LOADING",
                font: "bold",
                color: WHITE,
                dy: 1,
              },
          {
            type: "text", id: "sales-info",
            text: count === undefined && error ? `${error} · retrying` : date,
            font: "small", color: error || stale ? SALES_ERROR_COLOR : DIM, width: TEXT_W, dy: SUB_DY,
            scroll_rate: 600, scroll_start_delay: 400, scroll_repeat_delay: 800,
          },
        ]),
      ]);
  }

  return renderDailyGraph(points, now, selectedDay);
}
