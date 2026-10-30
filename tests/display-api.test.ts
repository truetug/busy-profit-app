import assert from "node:assert/strict";
import test from "node:test";
import { clampNegativeY, clearDisplay, fetchWithTimeout, staleElementIds } from "../src/display-api.ts";

test("clamps a negative top coordinate without changing valid elements", () => {
  const elements = [
    { id: "headline", y: -1 },
    { id: "date", y: 8 },
    { id: "unspecified" },
  ];

  assert.deepEqual(clampNegativeY(elements), [
    { id: "headline", y: 0 },
    { id: "date", y: 8 },
    { id: "unspecified" },
  ]);
});

test("clears selected display elements in the DELETE JSON body", async () => {
  let requestUrl = "";
  let requestInit: RequestInit | undefined;
  const fetcher: typeof fetch = async (input, init) => {
    requestUrl = String(input);
    requestInit = init;
    return new Response(JSON.stringify({ result: "OK" }), { status: 200 });
  };

  await clearDisplay("http://bar/api/display/draw", "app.busy.profit", ["sales-loading-icon"], fetcher);

  assert.equal(requestUrl, "http://bar/api/display/draw?application_name=app.busy.profit");
  assert.equal(requestInit?.method, "DELETE");
  assert.deepEqual(requestInit?.headers, { "Content-Type": "application/json" });
  assert.deepEqual(JSON.parse(String(requestInit?.body)), {
    element_ids: ["sales-loading-icon"],
  });
});

test("clears all app elements without sending a stale element list", async () => {
  let requestUrl = "";
  let requestInit: RequestInit | undefined;
  const fetcher: typeof fetch = async (input, init) => {
    requestUrl = String(input);
    requestInit = init;
    return new Response(JSON.stringify({ result: "OK" }), { status: 200 });
  };

  await clearDisplay("http://bar/api/display/draw", "app.busy.profit", undefined, fetcher);

  assert.equal(requestUrl, "http://bar/api/display/draw?application_name=app.busy.profit");
  assert.deepEqual(JSON.parse(String(requestInit?.body)), {});
});

test("bounds a stalled native display request", async () => {
  const fetcher: typeof fetch = () => new Promise(() => {});

  await assert.rejects(
    fetchWithTimeout("http://bar/api/display/draw", {}, 5, fetcher),
    /timed out after 5ms/,
  );
});

test("identifies display elements absent from the next rendered frame", () => {
  assert.deepEqual(staleElementIds(["sales-count", "sales-info", "sales-mark"], ["sales-recent-count-0"]), [
    "sales-count", "sales-info", "sales-mark",
  ]);
});
