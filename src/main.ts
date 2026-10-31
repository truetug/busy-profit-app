import type { Point, SalesView } from "./model/sales.ts";
import { addr, device } from "@shared/device";
import { render } from "@busy-app/busy-lib";
import manifest from "./appmeta/manifest.json";
import { fetchHistory } from "./sales-api.ts";
import { renderSalesScreen } from "./screens/sales.ts";
import { increments, timestamp } from "./model/sales.ts";
import { actionForInput } from "./input.ts";
import { startMinuteClock } from "./minute-clock.ts";
import { dailySalesHeights, interpolateBarHeights } from "./screens/sales-chart.ts";
import { SALES_LOADING_ICON_ID } from "./screens/sales-ids.ts";
import { clampNegativeY, clearDisplay, fetchWithTimeout, mergeDrawnElementIds, staleElementIds } from "./display-api.ts";
import { INITIAL_HOME_PHASE, moveDayCursor, nextHomePhase, type HomePhase } from "./model/navigation.ts";
import { SALES_HISTORY_DAYS } from "./model/sales.ts";
import { createTaskScope } from "./task-scope.ts";

const APP = manifest.id;
const REFRESH_MS = 5 * 60 * 1000;
const CHART_TRANSITION_STEPS = 6;
const CHART_TRANSITION_DELAY_MS = 500;
const DISPLAY_REQUEST_TIMEOUT_MS = 8_000;
const apiOrigin = /^https?:\/\//i.test(addr) ? addr : `http://${addr}`;
const DISPLAY_DRAW_URL = `${apiOrigin.replace(/\/$/, "")}/api/display/draw`;
const tasks = createTaskScope();

type Screen = SalesView;

let count: number | undefined;
let points: Point[] = [];
let screen: Screen = "home";
let homePhase: HomePhase = INITIAL_HOME_PHASE;
let selectedDay = SALES_HISTORY_DAYS - 1;
let busy = false;
let loadError: string | undefined;
let exiting = false;
let unbindInput: BusyUnbind | undefined;
let refreshTimer: ReturnType<typeof setInterval> | undefined;
let stopClock: (() => void) | undefined;
let activeRefresh: Promise<void> | undefined;
let drawInFlight: Promise<void> | undefined;
let pendingDraw = false;
let lastDrawError: string | undefined;
let activeElementIds: string[] = [];
let iconHeights: number[] | undefined;

async function draw(): Promise<void> {
  if (exiting) return;
  if (drawInFlight) {
    pendingDraw = true;
    await drawInFlight;
    return;
  }
  let finishDrawing = () => {};
  drawInFlight = new Promise((resolve) => { finishDrawing = resolve; });
  try {
    do {
      pendingDraw = false;
      const now = new Date();
      const elements = clampNegativeY(render(renderSalesScreen({
        screen,
        homePhase,
        now,
        count,
        points,
        selectedDay,
        iconHeights,
        error: loadError,
        stale: points.length > 0 && Date.now() - timestamp(points[points.length - 1]!.at) > REFRESH_MS * 2,
      })));
      const nextElementIds = elements.flatMap((element) => element.id ? [element.id] : []);
      const staleIds = staleElementIds(activeElementIds, nextElementIds);
      let drawSucceeded = false;
      try {
        const response = await fetchWithTimeout(DISPLAY_DRAW_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ application_name: APP, priority: 50, elements }),
        }, DISPLAY_REQUEST_TIMEOUT_MS);
        if (!response.ok) {
          const detail = await response.text();
          throw new Error(`DisplayDraw HTTP ${response.status}: ${detail}`);
        }
        lastDrawError = undefined;
        drawSucceeded = true;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        if (message !== lastDrawError) console.error(`${APP}: display draw failed: ${message}`);
        lastDrawError = message;
      }
      if (exiting) return;
      if (drawSucceeded && pendingDraw) {
        activeElementIds = mergeDrawnElementIds(activeElementIds, nextElementIds);
        continue;
      }
      if (drawSucceeded && staleIds.length > 0) {
        try {
          await clearDisplay(
            DISPLAY_DRAW_URL,
            APP,
            staleIds,
            (input, init) => fetchWithTimeout(input, init, DISPLAY_REQUEST_TIMEOUT_MS),
          );
          activeElementIds = nextElementIds;
        } catch (error) {
          if (exiting) return;
          console.warn(`${APP}: selected stale-element cleanup failed; clearing and redrawing: ${error instanceof Error ? error.message : String(error)}`);
          try {
            await clearDisplay(
              DISPLAY_DRAW_URL,
              APP,
              undefined,
              (input, init) => fetchWithTimeout(input, init, DISPLAY_REQUEST_TIMEOUT_MS),
            );
            const response = await fetchWithTimeout(DISPLAY_DRAW_URL, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ application_name: APP, priority: 50, elements }),
            }, DISPLAY_REQUEST_TIMEOUT_MS);
            if (!response.ok) throw new Error(`DisplayDraw HTTP ${response.status}: ${await response.text()}`);
            activeElementIds = nextElementIds;
          } catch (fallbackError) {
            activeElementIds = [];
            console.error(`${APP}: display recovery failed: ${fallbackError instanceof Error ? fallbackError.message : String(fallbackError)}`);
          }
        }
      } else if (drawSucceeded) {
        activeElementIds = nextElementIds;
      }
    } while (pendingDraw && !exiting);
  } finally {
    drawInFlight = undefined;
    finishDrawing();
  }
}

/** Keeps the JS runner active while the Bar's native fetch waits for the remote response. */
function startFetchHeartbeat(): () => void {
  let seconds = 0;
  let running = true;
  const timer = setInterval(() => {
    seconds += 1;
    console.info(`${APP}: waiting for sales history (${seconds}s)`);
  }, 1_000);
  const unregister = tasks.register(() => clearInterval(timer));
  return () => {
    if (!running) return;
    running = false;
    clearInterval(timer);
    unregister();
  };
}

/** Animates the four-day icon from the previously displayed sales values to the refreshed values. */
async function animateChartTransition(previous: Point[], next: Point[]): Promise<void> {
  if (screen !== "home") return;
  const now = new Date();
  const target = dailySalesHeights(increments(next, "day", now, 4), 16);
  const start = previous.length === 0
    ? [0, 0, 0, 0]
    : dailySalesHeights(increments(previous, "day", now, 4), 16);
  if (start.every((height, index) => height === target[index])) return;

  iconHeights = start;
  await draw();
  await tasks.sleep(CHART_TRANSITION_DELAY_MS);
  for (const frame of interpolateBarHeights(start, target, CHART_TRANSITION_STEPS)) {
    if (exiting || screen !== "home") break;
    iconHeights = frame;
    await draw();
    await tasks.sleep(CHART_TRANSITION_DELAY_MS);
  }
  iconHeights = undefined;
}

async function refresh(): Promise<void> {
  if (busy) return;
  busy = true;
  const stopHeartbeat = startFetchHeartbeat();
  try {
    const previous = count;
    const previousPoints = points;
    const nextPoints = await fetchHistory();
    if (exiting) return;
    points = nextPoints;
    loadError = undefined;
    count = points[points.length - 1]!.count;
    if (previous === undefined) {
      console.info(`${APP}: history loaded (${points.length} points); clearing loading icon`);
      try {
        await clearDisplay(
          DISPLAY_DRAW_URL,
          APP,
          [SALES_LOADING_ICON_ID],
          (input, init) => fetchWithTimeout(input, init, DISPLAY_REQUEST_TIMEOUT_MS),
        );
        console.info(`${APP}: loading icon cleared`);
        activeElementIds = activeElementIds.filter((id) => id !== SALES_LOADING_ICON_ID);
      } catch (error) {
        if (exiting) return;
        console.warn(`${APP}: selected loading-icon cleanup failed; clearing app display: ${error instanceof Error ? error.message : String(error)}`);
        try {
          await clearDisplay(
            DISPLAY_DRAW_URL,
            APP,
            undefined,
            (input, init) => fetchWithTimeout(input, init, DISPLAY_REQUEST_TIMEOUT_MS),
          );
          activeElementIds = [];
        } catch (fallbackError) {
          console.error(`${APP}: display cleanup failed: ${fallbackError instanceof Error ? fallbackError.message : String(fallbackError)}`);
        }
      }
    }
    if (exiting) return;
    await animateChartTransition(previousPoints, points);
    if (!exiting && previous !== undefined && count > previous) {
      const crossedHundred = Math.floor(count / 100) > Math.floor(previous / 100);
      await device.AudioPlay({
        application_name: APP,
        path: crossedHundred ? "sounds/applause.wav" : "sounds/cha-ching.wav",
      });
    }
  } catch (error) {
    loadError = error instanceof Error ? error.message : String(error);
    console.error(`${APP}: ${loadError}`);
  } finally {
    stopHeartbeat();
    busy = false;
    if (!exiting) {
      iconHeights = undefined;
      await draw();
    }
  }
}

/** Stops background work and detaches input without waiting for network requests. */
function exitApp(): void {
  if (exiting) return;
  exiting = true;
  tasks.stop();
  if (refreshTimer !== undefined) clearInterval(refreshTimer);
  refreshTimer = undefined;
  stopClock?.();
  stopClock = undefined;
  setTimeout(() => {
    unbindInput?.();
    unbindInput = undefined;
  }, 10);
}

export default function run(): void {
  unbindInput = listen("input", (event) => {
    const action = actionForInput(event);
    if (action === "exit") {
      exitApp();
      return;
    }
    if (action === "toggle-screen") {
      if (count === undefined) return;
      if (screen === "home") {
        screen = "days";
        selectedDay = SALES_HISTORY_DAYS - 1;
      } else {
        screen = "home";
      }
      void draw();
      return;
    }
    if (action !== "next-day" && action !== "previous-day") return;
    if (screen === "home") {
      if (count === undefined) return;
      homePhase = nextHomePhase(homePhase);
      void draw();
      return;
    }
    const delta = action === "next-day" ? 1 : -1;
    const nextDay = moveDayCursor(selectedDay, delta, SALES_HISTORY_DAYS);
    if (nextDay === selectedDay) return;
    selectedDay = nextDay;
    void draw();
  });

  void (async () => {
    try {
      await clearDisplay(
        DISPLAY_DRAW_URL,
        APP,
        undefined,
        (input, init) => fetchWithTimeout(input, init, DISPLAY_REQUEST_TIMEOUT_MS),
      );
      activeElementIds = [];
    } catch (error) {
      console.error(`${APP}: stale display cleanup failed: ${error instanceof Error ? error.message : String(error)}`);
    }
    await draw();
    if (exiting) return;
    stopClock = startMinuteClock(() => { void draw(); });
    activeRefresh = refresh();
    await activeRefresh;
    activeRefresh = undefined;
    if (!exiting) refreshTimer = setInterval(() => {
      activeRefresh = refresh();
      void activeRefresh.finally(() => { activeRefresh = undefined; });
    }, REFRESH_MS);
  })();
}
