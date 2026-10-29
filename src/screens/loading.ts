// The startup screen: a spinner and what the app is waiting for.
//
//   ┌────────────────────────┐
//   │ ◐  Loading weather     │
//   └────────────────────────┘
//
// The spinner is a stock animation, played from the device's own assets rather than the app's.

import { row, SCREEN, type Node } from "@busy-app/busy-lib";

const SPINNER = { width: 8, height: 8 };

/** Space between the spinner and the text beside it. */
const GAP = 3;

const WHITE = "#FFFFFFFF";

/** What is left for the text once the spinner has taken its side. */
const TEXT_W = SCREEN.width - SPINNER.width - GAP;

/** Anything wider than TEXT_W scrolls; these set how. */
const SCROLL_RATE = 600;
const SCROLL_START_DELAY = 400;
const SCROLL_REPEAT_DELAY = 800;

export function loadingScreen(text: string): Node {
  return row({ align: "center", gap: GAP, height: SCREEN.height }, [
    {
      type: "animation",
      id: "load-spinner",
      stock_path: "shared/spinner_front_8x8.anim",
      loop: true,
      await_previous_end: false,
      opacity: 100,
      ...SPINNER,
    },
    {
      type: "text",
      id: "load-text",
      text,
      font: "small",
      color: WHITE,
      width: TEXT_W,
      scroll_rate: SCROLL_RATE,
      scroll_start_delay: SCROLL_START_DELAY,
      scroll_repeat_delay: SCROLL_REPEAT_DELAY,
    },
  ]);
}
