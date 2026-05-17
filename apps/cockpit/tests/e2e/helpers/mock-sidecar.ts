/**
 * mock-sidecar.ts — Playwright route helpers for /api/** endpoints.
 *
 * Wires fixture JSON to network routes so the cockpit talks to a
 * deterministic in-process mock instead of the real Python sidecar.
 *
 * Usage in a spec:
 *   import { mockSidecar } from "./helpers/mock-sidecar";
 *   test.beforeEach(async ({ page }) => { await mockSidecar(page); });
 *
 * The default config covers the smallest set the cockpit boot path
 * touches. Per-test overrides are encouraged via the optional
 * `overrides` argument — e.g. simulating a 503 from /voice/health.
 *
 * W310-c scaffold; W309 step 2 wires per-test routes (transcribe,
 * persona swap) once the runtime hits its endpoints.
 */
import type { Page, Route } from "@playwright/test";
import personas from "../fixtures/voice-personas.json";
import health from "../fixtures/voice-health.json";
import vault from "../fixtures/vault-status.json";
import threads from "../fixtures/chat-threads.json";
import transcribe from "../fixtures/voice-transcribe.json";

export type RouteOverride = {
  url: string | RegExp;
  handler: (route: Route) => Promise<void> | void;
};

const json = (body: unknown, status = 200) => ({
  status,
  contentType: "application/json",
  body: JSON.stringify(body),
});

export async function mockSidecar(page: Page, overrides: RouteOverride[] = []) {
  await page.route("**/api/voice/personas", (route) =>
    route.fulfill(json(personas)),
  );
  await page.route("**/api/voice/personas/effective**", (route) => {
    const url = new URL(route.request().url());
    const id = url.searchParams.get("persona_id") ?? personas.default_persona_id;
    const persona = personas.personas.find((p) => p.id === id) ?? personas.personas[0];
    route.fulfill(
      json({
        ok: true,
        persona_id: persona.id,
        name: persona.name,
        voice: {
          provider: "mac_say",
          voice: persona.provider.mac_say,
        },
        fallbacks: ["mac_say"],
        engines_available: ["mac_say"],
      }),
    );
  });

  await page.route("**/api/voice/health", (route) => route.fulfill(json(health)));

  await page.route("**/api/voice/transcribe", (route) =>
    route.fulfill(json(transcribe)),
  );

  await page.route("**/api/vault/status", (route) => route.fulfill(json(vault)));

  await page.route("**/api/chat/threads", (route) => route.fulfill(json(threads)));

  for (const o of overrides) {
    await page.route(o.url, o.handler);
  }
}
