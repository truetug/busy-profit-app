import { column, generateXpm2, render, row, SCREEN, type Node } from "@busy-app/busy-lib";
import { dailySales, increments, HOME_HISTORY_DAYS, type DaySales, type Point, type SalesView } from "../model/sales.ts";
import { formatDateTime } from "../../shared/datetime.ts";
import { dailySalesIcon, dailySalesIconFromHeights, historicalSalesIcon, SALES_ERROR_COLOR } from "./sales-chart.ts";
import { salesHeadline } from "./sales-format.ts";
import { SALES_CHART_ICON_ID, SALES_LOADING_ICON_ID } from "./sales-ids.ts";

const WHITE = "#FFFFFFFF";
const MUTED = "#A0A0A0FF";
const DIM = "#AAAAAAFF";
const GAP = 3;
const SUB_DY = -2;
const TEXT_W = SCREEN.width - 16 - GAP;
type Screen = SalesView;
let cachedChartKey = "";
let cachedChart = "";
let cachedPoints: Point[] | undefined;
let cachedDay = "";
let cachedDays: DaySales[] = [];
let cachedMaximum = 1;
let cachedWeekends = "";

/** Recalculates calendar buckets only when source history or the local date changes. */
function prepareDailyGraph(points: Point[], now: Date): void {
  const dayKey = `${now.getFullYear()}-${now.getMonth()}-${now.getDate()}`;
  if (cachedPoints === points && cachedDay === dayKey) return;
  cachedPoints = points;
  cachedDay = dayKey;
  cachedDays = dailySales(points, now);
  cachedMaximum = Math.max(1, ...cachedDays.map((day) => day.count));
  const weekends = cachedDays.map((day) => {
    const weekday = new Date(day.atMs).getDay();
    return weekday === 0 || weekday === 6 ? "ww" : "..";
  }).join("");
  cachedWeekends = generateXpm2({ palette: { ".": "None", w: "#808080FF" }, grid: [weekends] });
}

/** Reuses the static chart when only the selected day changes. */
function dailyChart(values: number[]): string {
  const key = values.join(",");
  if (key !== cachedChartKey) {
    cachedChartKey = key;
    cachedChart = historicalSalesIcon(values, SCREEN.width, 9);
  }
  return cachedChart;
}

/** Places daily-chart elements directly, avoiding layout work on every encoder step. */
export function dailyGraphElements(points: Point[], now: Date, selectedDay: number): ReturnType<typeof render> {
  prepareDailyGraph(points, now);
  const index = Math.min(Math.max(selectedDay, 0), cachedDays.length - 1);
  const selected = cachedDays[index]!;
  const date = new Date(selected.atMs);
  const height = Math.max(1, Math.round(selected.count / cachedMaximum * 9));
  return [
    { type: "text", id: "sales-selected-day", x: 0, y: 0, text: `${String(date.getDate()).padStart(2, "0")}.${String(date.getMonth() + 1).padStart(2, "0")}  ${selected.count}`, font: "small", color: WHITE },
    { type: "text", id: "sales-history-label", x: SCREEN.width - 1, y: 0, align: "top_right", text: "36D", font: "small", color: MUTED },
    { type: "xpmbitmap", id: "sales-chart", x: 0, y: 7, data: dailyChart(cachedDays.map((day) => day.count)), opacity: 100, z_index: 0 },
    { type: "rectangle", id: "sales-day-marker", x: index * 2, y: 16 - height, width: 2, height, fill: "solid", fill_colors: [WHITE], border_width: 0, z_index: 5 },
    { type: "xpmbitmap", id: "sales-weekends", x: 0, y: 15, data: cachedWeekends, opacity: 100, z_index: 6 },
  ];
}

/** Renders the sales overview or the selected day in the full history chart. */
export function renderSalesScreen(args: {
  screen: Screen;
  now: Date;
  count?: number;
  points: Point[];
  selectedDay: number;
  stale: boolean;
  historyState?: "loading" | "error" | "ready";
  iconHeights?: number[];
  notificationCount?: number;
  error?: string;
}): Node {
  const { screen, now, count, points, stale, iconHeights, notificationCount, error, historyState } = args;
  if (notificationCount !== undefined) {
    return row({ justify: "center", align: "center", width: SCREEN.width, height: SCREEN.height }, [
      { type: "text", id: "sales-notification", text: String(notificationCount), font: "large", color: WHITE },
    ]);
  }
  if (screen === "days") {
    return { type: "text", id: "sales-history-status", text: historyState === "error" ? "NO DATA" : "LOADING", font: "bold", color: WHITE };
  }

  if (screen === "home") {
    const date = formatDateTime(now);
    const isLoading = count === undefined && !error;
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
            : dailySalesIcon(increments(points, "day", now, HOME_HISTORY_DAYS), 16, 16),
          width: 16,
          height: 16,
          opacity: 100,
        };
    return row({ align: "center", gap: GAP, width: SCREEN.width, height: SCREEN.height }, [
        mark,
        column({ justify: "between", height: SCREEN.height }, [
          headline
              ? row({ align: "center", justify: "between", width: TEXT_W - 1 }, [
                  {
                    type: "text", id: "sales-count", text: headline.count,
                    font: "bold", color: WHITE, dy: 1,
                  },
                  {
                    type: "text", id: "sales-days", text: headline.days,
                    font: "tiny", color: DIM,
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

  throw new Error(`Unsupported sales screen: ${screen}`);
}
