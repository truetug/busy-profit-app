import type { Point, SalesView } from "./model/sales.ts";
import { device } from "@shared/device";
import { render } from "@busy-app/busy-lib";
import manifest from "./appmeta/manifest.json";
import { fetchHistory } from "./sales-api.ts";
import { renderSalesScreen } from "./screens/sales.ts";

const APP = manifest.id;
const REFRESH_MS = 5 * 60 * 1000;

type Screen = SalesView;

let count: number | undefined;
let points: Point[] = [];
let screen: Screen = "current";
let busy = false;

async function draw(): Promise<void> {
  const now = new Date();
  const elements = render(renderSalesScreen({
    screen,
    now,
    count,
    points,
    stale: points.length > 0 && Date.now() - Date.parse(points[points.length - 1]!.at) > REFRESH_MS * 2,
  }));
  await device.DisplayDraw({ application_name: APP, priority: 50, elements });
}

async function refresh(): Promise<void> {
  if (busy) return;
  busy = true;
  try {
    const previous = count;
    points = await fetchHistory();
    count = points[points.length - 1]!.count;
    if (previous !== undefined && count > previous) {
      const crossedHundred = Math.floor(count / 100) > Math.floor(previous / 100);
      await device.AudioPlay({
        application_name: APP,
        path: crossedHundred ? "sounds/applause.wav" : "sounds/cha-ching.wav",
      });
    }
  } catch (error) {
    console.error(`${APP}: ${error instanceof Error ? error.message : String(error)}`);
  } finally {
    busy = false;
    await draw();
  }
}

export default function run(): void {
  void (async () => {
    await refresh();
    setInterval(() => void refresh(), REFRESH_MS);
  })();

  listen("input", (event) => {
    if (event.key !== "encoder") return;
    const order: Screen[] = ["current", "hours", "days"];
    const index = order.indexOf(screen);
    screen = order[(index + (event.delta > 0 ? 1 : 2)) % order.length]!;
    void draw();
  });
}
