/** Owns timers and cleanup callbacks that must not outlive the application. */
export function createTaskScope() {
  let stopped = false;
  const cleanups = new Set<() => void>();

  function register(cleanup: () => void): () => void {
    if (stopped) {
      cleanup();
      return () => {};
    }
    cleanups.add(cleanup);
    return () => { cleanups.delete(cleanup); };
  }

  function sleep(milliseconds: number): Promise<void> {
    if (stopped) return Promise.resolve();
    return new Promise((resolve) => {
      let unregister = () => {};
      const finish = () => {
        clearTimeout(timer);
        unregister();
        resolve();
      };
      const timer = setTimeout(finish, milliseconds);
      unregister = register(finish);
    });
  }

  function stop(): void {
    if (stopped) return;
    stopped = true;
    for (const cleanup of cleanups) cleanup();
    cleanups.clear();
  }

  return { register, sleep, stop };
}
