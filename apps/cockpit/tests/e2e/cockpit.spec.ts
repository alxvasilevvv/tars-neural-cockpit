/**
 * cockpit.spec.ts — behavioural smoke for the W309 cockpit runtime.
 *
 * W310-c skeleton. Every assertion is `test.skip()` pending W309
 * step 2 (mediarecorder + STT upload + persona <select>) landing.
 * The step-2 implementer:
 *
 *   1. Drops `.skip` off each scenario as the runtime gets wired.
 *   2. Adds new specs for any UI surfaces step 2 introduces.
 *   3. Runs `pnpm --filter @tars/cockpit test:e2e` from the repo root.
 *
 * Scenarios map 1:1 to `docs/handoff/W309_STEP2_BRIEF.md` §3.1.
 * No PR #187-runtime imports are pulled here — the spec interacts
 * via DOM selectors only, so the scaffold rebases cleanly against
 * any state of `cursor/w309-step1-runtime`.
 */
import { expect, test } from "@playwright/test";
import { mockSidecar } from "./helpers/mock-sidecar";
import { mockChatStream } from "./helpers/mock-sse";
import { mockVoiceWebSocket } from "./helpers/mock-ws";

test.describe("cockpit smoke (W309 step 2 prep)", () => {
  test.beforeEach(async ({ page, context }) => {
    await context.grantPermissions(["microphone"]);
    await mockVoiceWebSocket(page);
    await mockSidecar(page);
    await mockChatStream(page);
  });

  test.skip("boot: loads cockpit.html without console errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await page.goto("/cockpit.html");
    await expect(page.getByRole("main")).toBeVisible();
    expect(errors, "console must be clean on boot").toHaveLength(0);
  });

  test.skip("personas: select renders 4 options + default is jarvis", async ({ page }) => {
    await page.goto("/cockpit.html");
    const picker = page.getByLabel(/voice persona/i);
    await expect(picker).toBeVisible();
    const options = await picker.locator("option").allTextContents();
    expect(options).toEqual(["Jarvis", "Stark", "HAL 9000", "TARS"]);
    await expect(picker).toHaveValue("jarvis");
  });

  test.skip("personas: switching persona persists & updates /voice/personas/effective query", async ({ page }) => {
    await page.goto("/cockpit.html");
    const requests: string[] = [];
    page.on("request", (req) => {
      const u = req.url();
      if (u.includes("/api/voice/personas/effective")) requests.push(u);
    });
    await page.getByLabel(/voice persona/i).selectOption("stark");
    await expect.poll(() => requests.at(-1) ?? "").toContain("persona_id=stark");
    await page.reload();
    await expect(page.getByLabel(/voice persona/i)).toHaveValue("stark");
  });

  test.skip("chat: typed message streams SSE deltas into the transcript", async ({ page }) => {
    await page.goto("/cockpit.html");
    await page.getByRole("textbox", { name: /message/i }).fill("ping");
    await page.getByRole("button", { name: /send/i }).click();
    const transcript = page.locator("[data-testid=chat-transcript]");
    await expect(transcript).toContainText("Hello from the mock sidecar.", {
      timeout: 3_000,
    });
  });

  test.skip("ws: voice runtime opens WS and survives a close+reopen cycle", async ({ page }) => {
    await page.goto("/cockpit.html");
    const wsCount = await page.evaluate(() => (window as any).__stubWs?.instances.length ?? 0);
    expect(wsCount).toBeGreaterThanOrEqual(1);
    await page.evaluate(() => (window as any).__stubWs.instances.at(-1)?.close());
    await page.waitForTimeout(50);
    const reopened = await page.evaluate(() => (window as any).__stubWs?.instances.length ?? 0);
    expect(reopened).toBeGreaterThan(wsCount);
  });

  test.skip("stt: mic stop → POSTs blob to /voice/transcribe → text lands in chat input", async ({ page }) => {
    await page.goto("/cockpit.html");
    const postPromise = page.waitForRequest(
      (req) => req.url().includes("/api/voice/transcribe") && req.method() === "POST",
    );
    await page.getByRole("button", { name: /start mic/i }).click();
    await page.waitForTimeout(150);
    await page.getByRole("button", { name: /stop mic/i }).click();
    const req = await postPromise;
    expect(req.postDataBuffer()?.byteLength ?? 0).toBeGreaterThan(0);
    await expect(page.getByRole("textbox", { name: /message/i })).toHaveValue(
      /hello world this is a test transcription/i,
    );
  });

  test.skip("vault: warns when no provider is configured (vault.status.configured=false)", async ({ page }) => {
    await page.goto("/cockpit.html");
    await expect(
      page.getByText(/add an openai \/ anthropic \/ elevenlabs key/i),
    ).toBeVisible();
  });
});
