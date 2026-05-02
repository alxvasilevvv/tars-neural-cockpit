import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchJump } from "./search";

describe("fetchJump", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              ok: true,
              query: "",
              count: 1,
              hits: [
                {
                  kind: "thread",
                  id: "t-1",
                  label: "Alpha",
                  sublabel: "thread · traders",
                  score: 0.9,
                  ref: { thread_id: "t-1" },
                },
              ],
            }),
        }),
      ) as unknown as typeof fetch,
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POSTs /api/search/jump with q and limit", async () => {
    const res = await fetchJump("al", { limit: 10 });
    expect(fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/search\/jump$/),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ q: "al", limit: 10 }),
      }),
    );
    expect(res.count).toBe(1);
    expect(res.hits[0]?.kind).toBe("thread");
    expect(res.hits[0]?.label).toBe("Alpha");
  });
});
