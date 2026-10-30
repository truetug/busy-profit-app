/** Clears this app's display elements through the Bar API's JSON-body contract. */
export async function clearDisplay(
  apiUrl: string,
  applicationName: string,
  elementIds?: string[],
  fetcher: typeof fetch = fetch,
): Promise<void> {
  const separator = apiUrl.includes("?") ? "&" : "?";
  const url = `${apiUrl}${separator}application_name=${encodeURIComponent(applicationName)}`;
  const body = elementIds ? { element_ids: elementIds } : {};
  const response = await fetcher(url, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`DisplayClear HTTP ${response.status}: ${detail}`);
  }
}

/** Rejects a stalled native Bar API call so the app can keep rendering usable data. */
export async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit | undefined,
  timeoutMs: number,
  fetcher: typeof fetch = fetch,
): Promise<Response> {
  let timeout: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      fetcher(input, init),
      new Promise<never>((_resolve, reject) => {
        timeout = setTimeout(() => reject(new Error(`Display API request timed out after ${timeoutMs}ms`)), timeoutMs);
      }),
    ]);
  } finally {
    clearTimeout(timeout);
  }
}

/** Keeps rendered elements inside the display's top edge, which the Bar API validates strictly. */
export function clampNegativeY<T extends { y?: number }>(elements: T[]): T[] {
  return elements.map((element) =>
    element.y !== undefined && element.y < 0 ? { ...element, y: 0 } : element,
  );
}

/** Returns display element IDs that were visible before but are absent from the next frame. */
export function staleElementIds(previousIds: string[], nextIds: string[]): string[] {
  return previousIds.filter((id) => !nextIds.includes(id));
}
