/** Limits redraw frequency while continuing to show progress during a long turn. */
export function createEncoderDrawScheduler(
  draw: () => void,
  schedule: typeof setTimeout = setTimeout,
  cancel: typeof clearTimeout = clearTimeout,
) {
  let timer: ReturnType<typeof setTimeout> | undefined;

  function request(): void {
    if (timer !== undefined) return;
    timer = schedule(() => {
      timer = undefined;
      draw();
    }, 60);
  }

  function stop(): void {
    if (timer !== undefined) cancel(timer);
    timer = undefined;
  }

  return { request, stop };
}
