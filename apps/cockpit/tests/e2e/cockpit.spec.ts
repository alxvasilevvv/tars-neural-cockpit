/**
 * cockpit.spec.ts — behavioural smoke for the W309 cockpit runtime.
 *
 * W310-c scaffold; W309 step 2 partial (2026-05-20): boot / chat /
 * vault / ws / persona picker / STT enabled for W309 step 2.
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

  test("boot: loads cockpit.html without console errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await page.goto("/cockpit.html");
    await expect(page.getByRole("main")).toBeVisible();
    expect(errors, "console must be clean on boot").toHaveLength(0);
  });

  test("personas: select renders 4 options + default is jarvis", async ({ page }) => {
    await page.goto("/cockpit.html");
    const picker = page.getByLabel(/voice persona/i);
    await expect(picker).toBeVisible();
    const options = await picker.locator("option").allTextContents();
    expect(options).toEqual(["Jarvis", "Stark", "HAL 9000", "TARS"]);
    await expect(picker).toHaveValue("jarvis");
  });

  test("personas: switching persona persists & updates /voice/personas/effective query", async ({ page }) => {
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

  test("chat: typed message streams SSE deltas into the strand", async ({ page }) => {
    await page.goto("/cockpit.html");
    const input = page.getByRole("textbox", { name: /command input/i });
    await input.fill("ping");
    await input.press("Enter");
    await expect(page.locator(".strand-body").last()).toContainText(
      "Hello from the mock sidecar.",
      { timeout: 3_000 },
    );
  });

  test("ws: backend WS opens and reconnects after close", async ({ page }) => {
    await page.goto("/cockpit.html");
    const backend = page.locator(".status-bar span").first();
    await expect(backend).toHaveAttribute("data-state", "online", {
      timeout: 3_000,
    });
    const before = await page.evaluate(() => (window as any).__stubWs?.instances.length ?? 0);
    expect(before).toBeGreaterThanOrEqual(1);
    await page.evaluate(() => (window as any).__stubWs.instances.at(-1)?.close());
    await page.waitForFunction(
      (n: number) => ((window as any).__stubWs?.instances.length ?? 0) > n,
      before,
      { timeout: 3_000 },
    );
  });

  test("stt: mic stop → POSTs blob to /voice/transcribe → text lands in chat input", async ({ page }) => {
    await page.goto("/cockpit.html");
    const postPromise = page.waitForRequest(
      (req) => req.url().includes("/api/voice/transcribe") && req.method() === "POST",
    );
    await page.getByRole("button", { name: /start mic/i }).click();
    await expect(page.getByRole("button", { name: /stop mic/i })).toBeVisible({
      timeout: 3_000,
    });
    await page.waitForTimeout(300);
    await page.getByRole("button", { name: /stop mic/i }).click();
    const req = await postPromise;
    expect(req.postDataBuffer()?.byteLength ?? 0).toBeGreaterThan(0);
    await expect(page.getByRole("textbox", { name: /command input/i })).toHaveValue(
      /hello world this is a test transcription/i,
    );
  });

  test("vault: warns when ElevenLabs key is missing", async ({ page }) => {
    await page.goto("/cockpit.html");
    await expect(page.getByText(/elevenlabs key not in vault/i)).toBeVisible({
      timeout: 3_000,
    });
    await expect(page.getByRole("link", { name: /add key/i })).toHaveAttribute(
      "rel",
      "noopener noreferrer",
    );
  });
});
