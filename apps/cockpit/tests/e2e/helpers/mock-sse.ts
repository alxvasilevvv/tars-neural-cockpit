/**
 * mock-sse.ts — synthesises a streamed SSE response for /api/chat/stream.
 *
 * Uses Playwright's page.route() with a ReadableStream so the cockpit
 * EventSource / fetch+ReadableStream parser sees real wire-format
 * frames instead of one fulfilled JSON blob.
 *
 * Frames come from fixtures/chat-sse-deltas.json. Step-2 implementer
 * may extend with frame-injection helpers if the runtime needs to
 * test mid-stream errors / cancellation.
 *
 * W310-c scaffold; W309 step 2 wires the call sites once the chat
 * stream route is finalised.
 */
import type { Page, Route } from "@playwright/test";
import frames from "../fixtures/chat-sse-deltas.json";

type Frame = { event: string; data: unknown };

const serialise = (f: Frame): string =>
  `event: ${f.event}\ndata: ${JSON.stringify(f.data)}\n\n`;

export async function mockChatStream(
  page: Page,
  customFrames: Frame[] = frames.frames,
) {
  await page.route("**/api/chat/stream**", async (route: Route) => {
    const body = customFrames.map(serialise).join("");
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body,
      headers: {
        "cache-control": "no-cache",
        connection: "keep-alive",
      },
    });
  });
}
