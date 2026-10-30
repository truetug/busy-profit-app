export type AppAction = "exit" | "toggle-screen" | "previous-day" | "next-day";

/** Maps the firmware's short button event to an app action. */
export function actionForInput(event: BusyInputEvent): AppAction | undefined {
  if (event.key === "back" && (event.action === "press" || event.action === "short")) {
    return "exit";
  }
  if (event.key === "start" && event.action === "short") return "toggle-screen";
  if (event.key === "encoder") return event.delta > 0 ? "next-day" : "previous-day";
  return undefined;
}
