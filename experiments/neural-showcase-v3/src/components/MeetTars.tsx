import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { SplineScene } from "@/components/SplineScene";
import { getHealth } from "@/lib/api";
import { useT } from "@/lib/i18n";

/**
 * MeetTars — robot character showcase.
 *
 * Split layout: TARS persona (Spline 3D) on the left,
 * cycling demo strip on the right (real prompt + result preview).
 *
 * Lives directly under <Hero/> on the Landing page.
 */

const TARS_SCENE =
  "https://prod.spline.design/kZDDjO5HuC9GJUM2/scene.splinecode";

const PROMPTS = [
  "Подготовь заметки для встречи в 10:00",
  "Сделай summary research.pdf",
  "Отсортируй ~/Downloads по типу",
  "Покажи PR'ы которые ждут review",
];

interface Preview {
  label: string;
  body: string;
  ms: string;
}

const PREVIEWS: Preview[] = [
  {
    label: "MEETING NOTES",
    body: "10:00 — Sync. 3 участника, тема: Phase 9 review. Готовы: agenda, blocker list, 2 решения для обсуждения.",
    ms: "4.1s",
  },
  {
    label: "FILE SUMMARY",
    body: "research.pdf · 18 страниц. Дискриминатор обучается в edge при батчах ≤ 256. 4 эксперимента, метрики 92%+.",
    ms: "2.8s",
  },
  {
    label: "DOWNLOADS SORTED",
    body: "47 files · PDF: 12 → /PDF/. Images: 18 → /Images/. Code: 8 → /Code/. Receipt rcp_a91f0c2 anchored.",
    ms: "2.3s",
  },
  {
    label: "PR REVIEW QUEUE",
    body: "tars #87 · awareness sse stream — 2h ago.\nrelayer #142 · escrow batch — 6h ago.\nagent-sdk #23 — 1d ago.",
    ms: "0.9s",
  },
];

export function MeetTars() {
  const [idx, setIdx] = useState(0);
  const [live, setLive] = useState(false);
  const t = useT();

  useEffect(() => {
    const t = setInterval(() => setIdx(i => (i + 1) % PREVIEWS.length), 4200);
    return () => clearInterval(t);
  }, []);

  // Honest live indicator — pings the local TARS daemon every 30s.
  // Online → "LIVE" badge + CTA to interact in /cockpit. Offline → "DEMO".
  useEffect(() => {
    let cancelled = false;
    // Track in-flight timeout handles so we can clear them on unmount and
    // avoid the dangling-setTimeout leak that piles up under route churn.
    const pending = new Set<number>();
    const check = async () => {
      let timeoutId: number | undefined;
      try {
        const h = await Promise.race([
          getHealth(),
          new Promise<never>((_, rej) => {
            timeoutId = window.setTimeout(() => rej(new Error("t")), 1500);
            pending.add(timeoutId);
          }),
        ]);
        if (timeoutId !== undefined) {
          window.clearTimeout(timeoutId);
          pending.delete(timeoutId);
        }
        if (!cancelled) setLive(Boolean(h));
      } catch {
        if (timeoutId !== undefined) {
          pending.delete(timeoutId);
        }
        if (!cancelled) setLive(false);
      }
    };
    void check();
    const t = window.setInterval(check, 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
      for (const id of pending) window.clearTimeout(id);
      pending.clear();
    };
  }, []);

  const preview = PREVIEWS[idx];

  return (
    <section
      id="meet-tars"
      className="relative z-20 mx-auto max-w-[1280px] overflow-hidden px-6 py-24 md:px-12 md:py-32"
    >
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-100px" }}
        transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        className="grid grid-cols-1 items-center gap-10 lg:grid-cols-[1fr_1.05fr] lg:gap-12"
      >
        {/* LEFT — Robot character */}
        <div className="relative h-[420px] sm:h-[500px] lg:h-[560px]">
          {/* HUD corner brackets */}
          <div aria-hidden className="pointer-events-none absolute -inset-2 z-10">
            <span
              className="absolute left-0 top-0 h-4 w-4 border-l border-t"
              style={{ borderColor: "var(--color-meeet-indigo-soft)" }}
            />
            <span
              className="absolute right-0 top-0 h-4 w-4 border-r border-t"
              style={{ borderColor: "var(--color-meeet-indigo-soft)" }}
            />
            <span
              className="absolute bottom-0 left-0 h-4 w-4 border-b border-l"
              style={{ borderColor: "var(--color-meeet-indigo-soft)" }}
            />
            <span
              className="absolute bottom-0 right-0 h-4 w-4 border-b border-r"
              style={{ borderColor: "var(--color-meeet-indigo-soft)" }}
            />
          </div>

          {/* Ambient indigo+violet glow */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 -z-10"
            style={{
              background: `
                radial-gradient(ellipse 70% 60% at 50% 50%, rgba(99,102,241,0.32) 0%, transparent 65%),
                radial-gradient(ellipse 55% 45% at 50% 65%, rgba(139,92,246,0.22) 0%, transparent 65%)
              `,
              filter: "blur(20px)",
            }}
          />

          <div
            role="img"
            aria-label="TARS robot character — your local agent"
            className="absolute inset-0"
          >
            <SplineScene scene={TARS_SCENE} className="h-full w-full" />
          </div>

          {/* TARS status pill — switches to LIVE when local daemon responds */}
          <div
            className="absolute bottom-3 left-3 z-20 inline-flex items-center gap-2 rounded-full border bg-bg-0/70 px-3 py-1 font-mono-tech text-[10px] uppercase tracking-[2.4px] backdrop-blur-sm"
            style={{
              borderColor: live ? "var(--color-success)" : "var(--color-line-strong)",
              color: live ? "var(--color-success)" : "var(--color-ink-2)",
            }}
          >
            <span
              className="h-1 w-1 rounded-full"
              style={{
                background: live ? "var(--color-success)" : "var(--color-meeet-cyan)",
                boxShadow: live
                  ? "0 0 8px rgba(52,211,153,0.6)"
                  : "0 0 6px var(--color-meeet-cyan-soft)",
                animation: live ? "pulseDot 1.6s ease-in-out infinite" : undefined,
              }}
            />
            {live ? t("meetTars.live.label") : t("meetTars.live.demo")}
          </div>
        </div>

        {/* RIGHT — copy + cycling demo */}
        <div>
          <div
            className="mb-5 inline-flex items-center gap-2 rounded-full border bg-white/[0.02] px-3 py-1 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-2"
            style={{ borderColor: "rgba(6,182,212,0.26)" }}
          >
            <span
              className="h-1 w-1 rounded-full"
              style={{
                background: "var(--color-meeet-cyan)",
                boxShadow: "0 0 6px var(--color-meeet-cyan-soft)",
              }}
            />
            {t("meetTars.eyebrow")}
          </div>

          <h2
            className="font-display font-medium leading-[0.94] tracking-[-0.02em] text-ink"
            style={{ fontSize: "clamp(2.2rem, 4.4vw, 3.8rem)" }}
          >
            {t("meetTars.title.lead")}{" "}
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(95deg, #6366F1 0%, #8B5CF6 50%, #06B6D4 100%)",
              }}
            >
              {t("meetTars.title.tail")}
            </span>
            .
          </h2>

          <p className="mt-6 max-w-[520px] text-[15px] leading-[1.65] text-ink-2">
            {t("meetTars.body")}
          </p>

          {/* Cycling demo strip — prompt + preview */}
          <div className="mt-8 grid gap-3">
            <div
              className="flex items-center gap-3 rounded-md border bg-bg-1/80 px-4 py-3 backdrop-blur-sm"
              style={{ borderColor: "rgba(99,102,241,0.22)" }}
            >
              <span
                className="font-mono-tech text-[13px]"
                style={{ color: "var(--color-meeet-indigo)" }}
              >
                $
              </span>
              <div className="flex-1 overflow-hidden">
                <AnimatePresence mode="wait">
                  <motion.span
                    key={idx}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.32 }}
                    className="block truncate font-mono-tech text-[13.5px] text-ink-2"
                  >
                    {PROMPTS[idx]}
                  </motion.span>
                </AnimatePresence>
              </div>
              <span
                aria-hidden
                className="ml-1 inline-block h-[16px] w-[2px] bg-ink"
                style={{ animation: "pulseDot 1.05s steps(2) infinite" }}
              />
            </div>

            <AnimatePresence mode="wait">
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.42 }}
                className="rounded-md border border-line bg-bg-1/60 px-4 py-3.5 backdrop-blur-sm"
              >
                <div className="mb-2 flex items-center justify-between">
                  <div
                    className="font-mono-tech text-[10px] uppercase tracking-[2.4px]"
                    style={{ color: "var(--color-meeet-cyan)" }}
                  >
                    {preview.label}
                  </div>
                  <div
                    className="font-mono-tech text-[10px] tabular-nums"
                    style={{ color: "var(--color-meeet-violet)" }}
                  >
                    {t("meetTars.draftedIn", { ms: preview.ms })}
                  </div>
                </div>
                <div className="whitespace-pre-line font-mono-tech text-[12.5px] leading-[1.6] text-ink/95">
                  {preview.body}
                </div>
              </motion.div>
            </AnimatePresence>

            {/* Live CTA — visible only when daemon is reachable */}
            {live && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
                className="flex items-center justify-between gap-3 rounded-md border px-4 py-2.5 font-mono-tech text-[10.5px] uppercase tracking-[2.4px]"
                style={{
                  borderColor: "var(--color-success)",
                  background: "color-mix(in srgb, var(--color-success) 8%, transparent)",
                  color: "var(--color-success)",
                }}
              >
                <span>{t("meetTars.live.cta")}</span>
                <Link
                  to="/cockpit"
                  className="inline-flex items-center gap-1.5 text-ink transition-colors hover:underline"
                >
                  {t("meetTars.live.openCockpit")}
                  <ArrowUpRight size={12} strokeWidth={2} />
                </Link>
              </motion.div>
            )}
          </div>
        </div>
      </motion.div>
    </section>
  );
}
