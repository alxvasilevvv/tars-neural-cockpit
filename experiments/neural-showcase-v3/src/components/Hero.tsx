import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { useEffect, useState, lazy, Suspense } from "react";

import { DownloadStrip } from "@/components/DownloadStrip";
import { useT } from "@/lib/i18n";

/**
 * Hero — pattern: AI-Driven Dynamic Landing (skill #30) + a shader-lines
 * background (port of `aliimam/shader-lines` from 21st.dev) standing in
 * for the previous WebGL orb.
 *
 * Section order (top → bottom):
 *   1. Eyebrow status (live dot + brand quanta)
 *   2. Three-beat sovereignty headline (Your AI. / Your machine. / Your terms.)
 *   3. Subline — the council-of-agents promise
 *   4. DownloadStrip (primary CTA — OS-detected button + all-installers row)
 *   5. Live demo (input + result preview cycling through real TARS prompts)
 *   6. Cockpit / Domains CTAs
 *
 * The shader is mounted as an absolute background sculpture per
 * `design-system/tars/MASTER.md` §6 — it never competes with the
 * headline. A radial mask keeps the centre legible. Lazy-loaded so the
 * route still paints without waiting on `three`. Honors
 * `prefers-reduced-motion` internally (frame loop renders one calm
 * frame, time uniform stops advancing).
 */

// Keep the WebGL background out of the critical bundle. The route
// still paints text + downloads while three.js streams in.
const ShaderAnimation = lazy(() =>
  import("@/components/ui/shader-lines").then((m) => ({
    default: m.ShaderAnimation,
  })),
);

const PROMPTS_DEMO: { input: string; label: string; body: string }[] = [
  {
    input: "Brief me on my morning",
    label: "MORNING BRIEF · drafted in 1.8s",
    body:
      "10:00 — Sync с командой (3 уч.). Phase 9 review. " +
      "2 deals waiting on a response · 1 PR ждёт review · " +
      "Council voted: ship the Friday demo.",
  },
  {
    input: "Send 0.05 SOL from my Phantom wallet to alice.sol",
    label: "WALLET · proposed · awaiting confirm",
    body:
      "from: 7XJk…3Hgk · to: alice.sol (resolved) · 0.05 SOL · " +
      "fee ≈ 0.000005 · blockhash refreshed 2s ago. " +
      "Confirm token minted. Hit Approve to broadcast.",
  },
  {
    input: "Score these inbound leads from this morning's CSV",
    label: "ENTREPRENEUR · 12 leads scored",
    body:
      "Top 3 by signal: " +
      "M. Park (LinkedIn, 91) · A. Voss (referral, 88) · " +
      "T. Imai (cold-mail, 84). Drafted 3 follow-ups in your voice.",
  },
  {
    input: "Summarize research.pdf and pull citations",
    label: "FILE SUMMARY · 18 pages, 4 sources",
    body:
      "Главный тезис: дискриминатор обучается в edge-режиме при " +
      "батчах ≤ 256. 4 эксперимента подтверждают, метрики " +
      "стабильны 92%+. Citations: [chunk_3], [chunk_7], [chunk_11].",
  },
  {
    input: "Read this whiteboard photo and turn it into a checklist",
    label: "VISION · OCR · 9 items detected",
    body:
      "1. Refactor council orchestrator. 2. Wire entrepreneur pack. " +
      "3. Vault-rotation drill. 4. Mobile pairing demo… " +
      "(image: 1920×1080, OCR confidence 0.94)",
  },
];

export function Hero() {
  const t = useT();
  const [idx, setIdx] = useState(0);
  const [paused, setPaused] = useState(false);

  // 1 motion at a time per Master §7; cycle every 4.2s.
  // - Pauses on hover / focus inside the demo (operator wants to read).
  // - Honors `prefers-reduced-motion`: shows the first prompt only,
  //   no auto-advance.
  useEffect(() => {
    if (paused) return;
    if (typeof window !== "undefined") {
      const mql = window.matchMedia?.("(prefers-reduced-motion: reduce)");
      if (mql?.matches) return;
    }
    const tm = window.setInterval(() => {
      setIdx((i) => (i + 1) % PROMPTS_DEMO.length);
    }, 4200);
    return () => window.clearInterval(tm);
  }, [paused]);

  const turn = PROMPTS_DEMO[idx];

  return (
    <section className="relative z-20 overflow-hidden pb-24 pt-20 md:pt-28">
      {/* Shader-lines background — absolute, pointer-events: none.
          Master §6: "background sculpture, not the focal point."
          The radial mask keeps the centre dimmed so the headline
          and DownloadStrip card always read clean over it. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 z-0"
        style={{ contain: "strict" }}
      >
        <Suspense fallback={null}>
          <ShaderAnimation />
        </Suspense>
        {/* Centre veil — pulls foreground contrast back without
            killing the rim where the lines look best. */}
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 70% 55% at 50% 42%, rgba(7,7,10,0.78) 0%, rgba(7,7,10,0.55) 38%, rgba(7,7,10,0.0) 78%)",
          }}
        />
        {/* Bottom fade — hands off cleanly to the next section. */}
        <div
          className="absolute inset-x-0 bottom-0 h-40"
          style={{
            background:
              "linear-gradient(to bottom, rgba(7,7,10,0) 0%, rgba(7,7,10,0.92) 85%, var(--color-bg-0) 100%)",
          }}
        />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-30 mx-auto max-w-[1180px] px-6 md:px-12"
      >
        {/* Eyebrow status */}
        <div className="mx-auto mb-9 inline-flex w-full justify-center">
          <div className="inline-flex items-center gap-2.5 rounded-full border border-line bg-white/[0.02] px-3.5 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[3.4px] text-ink-2 backdrop-blur-sm">
            <span
              className="h-1.5 w-1.5 rounded-full bg-alert"
              style={{
                boxShadow: "0 0 10px var(--color-alert-soft)",
                animation: "pulseDot 1.6s ease-in-out infinite",
              }}
            />
            {t("hero.eyebrow")}
          </div>
        </div>

        {/* Three-beat sovereignty headline. Each line is a single claim;
            the rhythm reads as a technical incantation. Last line is
            the gold accent (Master §3 — single primary accent only).
            text-shadow boosts legibility over the 3D scene without
            adding chrome. */}
        <h1
          className="text-center font-display text-[clamp(2.8rem,7.5vw,7.6rem)] font-medium leading-[0.94] tracking-[-0.02em] text-ink"
          style={{ textShadow: "0 2px 24px rgba(0,0,0,0.65)" }}
        >
          <span className="block">{t("hero.title.line1")}</span>
          <span className="block">{t("hero.title.line2")}</span>
          <span
            className="block text-accent"
            style={{ textShadow: "0 0 24px var(--color-accent-soft), 0 2px 24px rgba(0,0,0,0.65)" }}
          >
            {t("hero.title.line3")}
          </span>
        </h1>

        {/* Subline — the council-of-agents promise. Wider than before
            so the new capabilities (vision, on-chain, council) get
            named explicitly. */}
        <p className="mx-auto mt-7 max-w-[640px] text-center text-[14.5px] leading-[1.6] text-ink-2">
          {t("hero.subline")}
        </p>

        {/* DownloadStrip — moved ABOVE the demo per the operator brief.
            The OS-detected primary button + all-installers chip row is
            the very first action surface a visitor reaches. */}
        <div className="mt-9 flex justify-center">
          <div className="w-full max-w-[720px] rounded-md border border-line bg-bg-1/50 p-5 backdrop-blur-sm md:p-6">
            <DownloadStrip variant="hero" />
          </div>
        </div>

        {/* Live demo — input + result preview, cycles every 4.2s.
            Aria-hidden because it is purely decorative motion: every
            capability shown here is already named in plain text in
            the subline above. Cycle pauses on hover/focus so an
            operator can read mid-rotation; reduced-motion freezes on
            the first prompt. */}
        <div
          aria-hidden
          className="mx-auto mt-10 max-w-[720px]"
          onMouseEnter={() => setPaused(true)}
          onMouseLeave={() => setPaused(false)}
          onFocusCapture={() => setPaused(true)}
          onBlurCapture={() => setPaused(false)}
        >
          <div className="mb-2 flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            <span
              aria-hidden
              className="h-1 w-1 rounded-full bg-accent"
              style={{ boxShadow: "0 0 8px var(--color-accent-soft)" }}
            />
            {t("hero.demo.label")}
          </div>

          <div className="group relative">
            {/* HUD corner brackets — 1px hairlines per Master §1.4 */}
            <div
              aria-hidden
              className="pointer-events-none absolute -inset-1.5"
            >
              <span className="absolute left-0 top-0 h-3 w-3 border-l border-t border-line-hot" />
              <span className="absolute right-0 top-0 h-3 w-3 border-r border-t border-line-hot" />
              <span className="absolute bottom-0 left-0 h-3 w-3 border-b border-l border-line-hot" />
              <span className="absolute bottom-0 right-0 h-3 w-3 border-b border-r border-line-hot" />
            </div>

            <div className="relative flex items-center gap-3 rounded-md border border-line bg-bg-1/80 px-5 py-4 backdrop-blur-sm">
              <span className="font-mono-tech text-[13px] text-accent">$</span>
              <div className="relative flex-1 overflow-hidden">
                <AnimatePresence mode="wait">
                  <motion.span
                    key={`p-${idx}`}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{
                      duration: 0.32,
                      ease: [0.22, 1, 0.36, 1],
                    }}
                    className="block truncate font-mono-tech text-[14.5px] text-ink-2"
                  >
                    {turn.input}
                  </motion.span>
                </AnimatePresence>
              </div>
              <span
                aria-hidden
                className="ml-1 inline-block h-[18px] w-[2px] bg-ink"
                style={{ animation: "pulseDot 1.05s steps(2) infinite" }}
              />
            </div>
          </div>

          {/* Result preview */}
          <div className="relative mt-3">
            <AnimatePresence mode="wait">
              <motion.div
                key={`r-${idx}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
                className="rounded-md border border-line bg-bg-1/60 px-5 py-4 text-left backdrop-blur-sm"
              >
                <div className="mb-2 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-accent">
                  {turn.label}
                </div>
                <div className="whitespace-pre-line font-mono-tech text-[12.5px] leading-[1.65] text-ink/95">
                  {turn.body}
                </div>
              </motion.div>
            </AnimatePresence>
          </div>
        </div>

        {/* CTA row */}
        <div className="mt-12 flex flex-wrap items-center justify-center gap-3">
          <a
            href="/cockpit"
            className="group inline-flex cursor-pointer items-center gap-2.5 rounded-md border border-line-hot bg-gradient-to-b from-accent-deep to-accent-deep/40 px-5 py-3.5 font-display text-[12.5px] uppercase tracking-[0.18em] text-accent transition-all duration-200 hover:-translate-y-0.5 hover:border-accent hover:from-accent/20 hover:shadow-[0_0_0_1px_var(--color-accent-soft),0_12px_32px_-10px_var(--color-accent-soft)]"
          >
            <span>{t("hero.cta.cockpit")}</span>
            <ArrowRight
              size={16}
              className="transition-transform duration-200 group-hover:translate-x-0.5"
              strokeWidth={1.6}
            />
          </a>
          <a
            href="#domains"
            className="inline-flex cursor-pointer items-center gap-2.5 rounded-md border border-line bg-white/[0.02] px-5 py-3.5 font-display text-[12.5px] uppercase tracking-[0.18em] text-ink transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:bg-white/[0.04]"
          >
            {t("hero.cta.domains")}
          </a>
        </div>
      </motion.div>
    </section>
  );
}
