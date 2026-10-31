import type { Point, SalesView } from "./model/sales.ts";
import { addr, device } from "@shared/device";
import { render } from "@busy-app/busy-lib";
import manifest from "./appmeta/manifest.json";
import { fetchHistory } from "./sales-api.ts";
import { dailyGraphElements, renderSalesScreen } from "./screens/sales.ts";
import { increments, mergeHistory, timestamp } from "./model/sales.ts";
import { actionForInput, encoderMovement } from "./input.ts";
import { startMinuteClock } from "./minute-clock.ts";
import { dailySalesHeights, interpolateBarHeights } from "./screens/sales-chart.ts";
import { SALES_LOADING_ICON_ID } from "./screens/sales-ids.ts";
import { changedElements, clampNegativeY, clearDisplay, fetchWithTimeout, mergeDrawnElementIds, staleElementIds } from "./display-api.ts";
import { moveDayCursor } from "./model/navigation.ts";
import { HOME_HISTORY_DAYS, SALES_HISTORY_DAYS } from "./model/sales.ts";
import { createTaskScope } from "./task-scope.ts";
import { createOlderFeedLoader } from "./older-feed.ts";
import { SALES_POLL_INTERVAL_MS, startSalesPolling } from "./sales-polling.ts";
import { salesNotification } from "./model/sales-notification.ts";
import { countdownIndicator } from "./countdown-indicator.ts";
import { createEncoderDrawScheduler } from "./encoder-draw.ts";

const APP = manifest.id;
const CHART_TRANSITION_STEPS = 6;
const CHART_TRANSITION_DELAY_MS = 500;
const DISPLAY_REQUEST_TIMEOUT_MS = 8_000;
const apiOrigin = /^https?:\/\//i.test(addr) ? addr : `http://${addr}`;
const DISPLAY_DRAW_URL = `${apiOrigin.replace(/\/$/, "")}/api/display/draw`;
const tasks = createTaskScope();

type Screen = SalesView;

let count: number | undefined;
let points: Point[] = [];
let olderPoints: Point[] = [];
let combinedPoints: Point[] = [];
let olderLoadedDay: string | undefined;
let olderError = false;
let screen: Screen = "home";
let selectedDay = SALES_HISTORY_DAYS - 1;
let busy = false;
let loadError: string | undefined;
let exiting = false;
let unbindInput: BusyUnbind | undefined;
let stopPolling: (() => void) | undefined;
let stopClock: (() => void) | undefined;
let stopCountdown: (() => void) | undefined;
let nextPollAt = 0;
let countdownHeight = -1;
let drawInFlight: Promise<void> | undefined;
let pendingDraw = false;
let lastDrawError: string | undefined;
let activeElementIds: string[] = [];
let drawnElements = new Map<string, string>();
let iconHeights: number[] | undefined;
let notificationCount: number | undefined;
let notificationGeneration = 0;
const encoderDraw = createEncoderDrawScheduler(() => { void draw(); });

const olderFeed = createOlderFeedLoader(
  async () => {
    const stopHeartbeat = startFetchHeartbeat("older");
    try {
      return await fetchHistory("older");
    } finally {
      stopHeartbeat();
    }
  },
  (state) => {
    olderPoints = state.points;
    combinedPoints = mergeHistory(olderPoints, points);
    olderLoadedDay = state.loadedDay;
    olderError = state.failed;
    if (!exiting && screen === "days") void draw();
  },
  (error) => {
    console.error(`${APP}: older sales history failed: ${error instanceof Error ? error.message : String(error)}`);
  },
);

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
      const dailyReady = screen === "days" && olderLoadedDay && notificationCount === undefined;
      const screenElements = dailyReady ? dailyGraphElements(combinedPoints, now, selectedDay) : render(renderSalesScreen({
        screen,
        now,
        count,
        points: screen === "days" ? combinedPoints : points,
        historyState: olderLoadedDay ? "ready" : olderError ? "error" : "loading",
        selectedDay,
        iconHeights,
        notificationCount,
        error: loadError,
        stale: points.length > 0 && Date.now() - timestamp(points[points.length - 1]!.at) > SALES_POLL_INTERVAL_MS * 2,
      }));
      const elements = clampNegativeY([...screenElements, ...(screen === "home" && notificationCount === undefined && nextPollAt
        ? countdownIndicator(nextPollAt - Date.now()) : [])]);
      const nextElementIds = elements.flatMap((element) => element.id ? [element.id] : []);
      const staleIds = staleElementIds(activeElementIds, nextElementIds);
      const changed = changedElements(elements, drawnElements);
      let drawSucceeded = false;
      try {
        if (changed.length) {
          const response = await fetchWithTimeout(DISPLAY_DRAW_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ application_name: APP, priority: 50, elements: changed }),
          }, DISPLAY_REQUEST_TIMEOUT_MS);
          if (!response.ok) {
            const detail = await response.text();
            throw new Error(`DisplayDraw HTTP ${response.status}: ${detail}`);
          }
        }
        lastDrawError = undefined;
        drawSucceeded = true;
        for (const element of changed) if (element.id) drawnElements.set(element.id, JSON.stringify(element));
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
          for (const id of staleIds) drawnElements.delete(id);
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
            drawnElements = new Map(elements.flatMap((element) => element.id ? [[element.id, JSON.stringify(element)]] : []));
          } catch (fallbackError) {
            activeElementIds = [];
            drawnElements.clear();
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

/** Shows one updated total for ten seconds and plays the appropriate sales sound. */
async function showSalesNotification(previous: number | undefined, current: number): Promise<void> {
  const notification = salesNotification(previous, current);
  if (!notification || exiting) return;
  const generation = ++notificationGeneration;
  notificationCount = notification.count;
  void draw();
  void device.AudioPlay({
    application_name: APP,
    path: notification.sound === "applause" ? "sounds/applause.snd" : "sounds/cha-ching.snd",
  }).catch((error: unknown) => console.error(`${APP}: notification audio failed: ${String(error)}`));
  await tasks.sleep(10_000);
  if (exiting || generation !== notificationGeneration) return;
  notificationCount = undefined;
  void draw();
}

/** Updates the progress line only when its visible pixel height changes. */
function updateCountdown(): void {
  const height = Math.max(0, Math.min(16, Math.ceil((nextPollAt - Date.now()) / SALES_POLL_INTERVAL_MS * 16)));
  if (height === countdownHeight) return;
  countdownHeight = height;
  if (!exiting && screen === "home" && notificationCount === undefined) void draw();
}

/** Keeps the JS runner active while the Bar's native fetch waits for the remote response. */
function startFetchHeartbeat(feed: "current" | "older"): () => void {
  let seconds = 0;
  let running = true;
  const timer = setInterval(() => {
    seconds += 1;
    console.info(`${APP}: waiting for ${feed} sales history (${seconds}s)`);
  }, 1_000);
  const unregister = tasks.register(() => clearInterval(timer));
  return () => {
    if (!running) return;
    running = false;
    clearInterval(timer);
    unregister();
  };
}

/** Animates the eight-day icon from the previous values to the refreshed values. */
async function animateChartTransition(previous: Point[], next: Point[]): Promise<void> {
  if (screen !== "home") return;
  const now = new Date();
  const target = dailySalesHeights(increments(next, "day", now, HOME_HISTORY_DAYS), 16);
  const start = previous.length === 0
    ? Array<number>(HOME_HISTORY_DAYS).fill(0)
    : dailySalesHeights(increments(previous, "day", now, HOME_HISTORY_DAYS), 16);
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

/** Loads older history against the latest observed day and its current-feed anchor. */
function refreshOlder(): Promise<void> {
  const latest = points[points.length - 1]!;
  const now = new Date(latest.atMs ?? timestamp(latest.at));
  const day = `${now.getFullYear()}-${now.getMonth()}-${now.getDate()}`;
  return olderFeed.refresh(day, points[0]?.at);
}

async function refresh(): Promise<void> {
  if (busy) return;
  busy = true;
  const stopHeartbeat = startFetchHeartbeat("current");
  try {
    const previous = count;
    const previousPoints = points;
    const nextPoints = await fetchHistory("current");
    if (exiting) return;
    points = nextPoints;
    combinedPoints = mergeHistory(olderPoints, points);
    loadError = undefined;
    count = points[points.length - 1]!.count;
    void showSalesNotification(previous, count);
    void refreshOlder();
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
        drawnElements.delete(SALES_LOADING_ICON_ID);
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
          drawnElements.clear();
        } catch (fallbackError) {
          console.error(`${APP}: display cleanup failed: ${fallbackError instanceof Error ? fallbackError.message : String(fallbackError)}`);
        }
      }
    }
    if (exiting) return;
    await animateChartTransition(previousPoints, points);
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
  olderFeed.stop();
  tasks.stop();
  stopPolling?.();
  stopPolling = undefined;
  stopClock?.();
  stopClock = undefined;
  stopCountdown?.();
  stopCountdown = undefined;
  encoderDraw.stop();
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
    if (screen === "home") return;
    const delta = encoderMovement(event);
    const nextDay = moveDayCursor(selectedDay, delta, SALES_HISTORY_DAYS);
    if (nextDay === selectedDay) return;
    selectedDay = nextDay;
    encoderDraw.request();
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
    stopPolling = startSalesPolling(() => {
      nextPollAt = Date.now() + SALES_POLL_INTERVAL_MS;
      updateCountdown();
      void refresh();
    });
    const countdownTimer = setInterval(updateCountdown, 1_000);
    stopCountdown = () => clearInterval(countdownTimer);
  })();
}
