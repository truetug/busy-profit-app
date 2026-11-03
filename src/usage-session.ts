/** Tracks cumulative counters so repeated requests cannot duplicate session usage. */
export function createUsageSession(now = Date.now, random = Math.random) {
  const startedAt = now();
  const id = `${startedAt.toString(36)}-${random().toString(36).slice(2, 12)}`;
  let detailsCount = 0;
  return {
    enterDetails() { detailsCount++; },
    snapshot() {
      return { id, uptimeSeconds: Math.max(0, Math.floor((now() - startedAt) / 1000)), detailsCount };
    },
  };
}

export type UsageSnapshot = ReturnType<ReturnType<typeof createUsageSession>["snapshot"]>;
