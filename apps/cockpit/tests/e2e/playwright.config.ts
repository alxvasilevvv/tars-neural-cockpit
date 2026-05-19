/**
 * Playwright config for the TARS cockpit e2e harness.
 *
 * W310-c scaffold; W309 step 2 wires the spec to the real runtime.
 *
 * Design rules (per W309_STEP2_BRIEF §3.1 + §5):
 *  - Single browser (chromium) — WKWebView and WebView2 are tested via
 *    the running desktop app, not Playwright. The harness's job is
 *    behavioural coverage of the JS, not cross-browser parity.
 *  - Fail-on-warning: undefined assertions / unmocked routes blow up.
 *  - No retry. A flaky spec must be diagnosed, not papered over.
 *  - Bounded wall-clock: each test ≤ 5s; full suite ≤ 10s.
 *
 * The cockpit dev server (`pnpm dev`) listens on :5174 per
 * `apps/cockpit/package.json`. The webServer block boots it on
 * demand so `pnpm test:e2e` works from a clean checkout.
 */
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: /.*\.spec\.ts/,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: process.env.CI ? 1 : undefined,
  timeout: 5_000,
  expect: { timeout: 2_000 },
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
  ],
  use: {
    baseURL: "http://127.0.0.1:5174",
    actionTimeout: 2_000,
    navigationTimeout: 5_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 800 },
      },
    },
  ],
  webServer: {
    command: "pnpm dev",
    cwd: "../..",
    url: "http://127.0.0.1:5174/cockpit.html",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});
