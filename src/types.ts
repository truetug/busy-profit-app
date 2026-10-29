import type { render } from "@busy-app/busy-lib";

/** A drawn element, as `render` and `list` return them. `Element` alone is the DOM one. */
export type Drawn = ReturnType<typeof render>[number];
