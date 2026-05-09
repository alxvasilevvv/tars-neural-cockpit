import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { useT } from "@/lib/i18n";

/**
 * CouncilDemo — two-voice deliberation visual.
 *
 * Mirrors the shape of @/lib/council.ts → Deliberation:
 *   { voices: Proposal[], chosen: string, agreement: number, rationale }
 *
 * Cycles through 3 mock deliberations every 6 seconds. Two model tiles
 * animate in side-by-side, then an agreement bar fills, then the chosen
 * voice gets a Check overlay.
 *
 * This is the unique TARS feature competitors don't have visible —
 * worth a section on the landing.
 */

interface MockProposal {
  model: string;
  brand: string;
  stance: string;
  summary: string;
  confidence: number;
  latency: string;
  tokens: string;
}

interface MockDeliberation {
  prompt: string;
  voices: [MockProposal, MockProposal];
  chosenIdx: 0 | 1;
  agreement: number;       // 0-1
  rationale: string;
}

export function CouncilDemo() {
  const t = useT();
  const deliberations: MockDeliberation[] = [
    {
      prompt: t("council.d1.prompt"),
      voices: [
        {
          model: "claude-sonnet-4.5",
          brand: "#CB7E5A",
          stance: t("council.d1.v0.stance"),
          summary: t("council.d1.v0.summary"),
          confidence: 0.78,
          latency: "412ms",
          tokens: "1.4k / 380",
        },
        {
          model: "gpt-5",
          brand: "#34D399",
          stance: t("council.d1.v1.stance"),
          summary: t("council.d1.v1.summary"),
          confidence: 0.62,
          latency: "538ms",
          tokens: "1.6k / 410",
        },
      ],
      chosenIdx: 0,
      agreement: 0.62,
      rationale: t("council.d1.rationale"),
    },
    {
      prompt: t("council.d2.prompt"),
      voices: [
        {
          model: "claude-sonnet-4.5",
          brand: "#CB7E5A",
          stance: t("council.d2.v0.stance"),
          summary: t("council.d2.v0.summary"),
          confidence: 0.91,
          latency: "298ms",
          tokens: "0.9k / 220",
        },
        {
          model: "gpt-5",
          brand: "#34D399",
          stance: t("council.d2.v1.stance"),
          summary: t("council.d2.v1.summary"),
          confidence: 0.88,
          latency: "356ms",
          tokens: "1.1k / 245",
        },
      ],
      chosenIdx: 1,
      agreement: 0.97,
      rationale: t("council.d2.rationale"),
    },
    {
      prompt: t("council.d3.prompt"),
      voices: [
        {
          model: "claude-sonnet-4.5",
          brand: "#CB7E5A",
          stance: t("council.d3.v0.stance"),
          summary: t("council.d3.v0.summary"),
          confidence: 0.94,
          latency: "421ms",
          tokens: "2.1k / 380",
        },
        {
          model: "gpt-5",
          brand: "#34D399",
          stance: t("council.d3.v1.stance"),
          summary: t("council.d3.v1.summary"),
          confidence: 0.9,
          latency: "510ms",
          tokens: "2.3k / 410",
        },
      ],
      chosenIdx: 0,
      agreement: 0.92,
      rationale: t("council.d3.rationale"),
    },
  ];

  const [idx, setIdx] = useState(0);

  useEffect(() => {
    const tick = setInterval(
      () => setIdx((i) => (i + 1) % deliberations.length),
      6200,
    );
    return () => clearInterval(tick);
  }, [deliberations.length]);

  const d = deliberations[idx];

  return (
    <section
      id="council"
      className="relative z-20 mx-auto max-w-[1280px] overflow-hidden px-6 py-24 md:px-12 md:py-32"
    >
      <motion.div
        // Wave 69 — was whileInView, switched to plain animate (same root
        // cause as Steps/MeeetSection — IntersectionObserver mis-fires
        // after long pinned ScrollStory section above).
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        className="mb-12"
      >
        <div className="mb-3 inline-flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
          <span
            className="h-1 w-1 rounded-full"
            style={{
              background: "var(--color-meeet-cyan)",
              boxShadow: "0 0 8px var(--color-meeet-cyan-soft)",
            }}
          />
          {t("councilDemo.eyebrow")}
        </div>
        <h2
          className="font-display font-medium leading-[0.94] tracking-[-0.02em] text-ink"
          style={{ fontSize: "clamp(2rem, 4.4vw, 3.6rem)" }}
        >
          {t("council.title.before")}
          <span
            className="bg-clip-text text-transparent"
            style={{
              backgroundImage:
                "linear-gradient(95deg, #6366F1 0%, #8B5CF6 50%, #06B6D4 100%)",
            }}
          >
            {t("council.title.grad")}
          </span>
          .
        </h2>
        <p className="mt-5 max-w-[640px] text-[14.5px] leading-[1.6] text-ink-2">
          {t("councilDemo.subtitle")}
        </p>
      </motion.div>

      {/* Demo card */}
      <div className="rounded-[14px] border border-line bg-bg-1/70 backdrop-blur-sm">
        {/* Top hairline accent */}
        <div
          aria-hidden
          className="h-px"
          style={{
            background:
              "linear-gradient(90deg, transparent 0%, #6366F1 30%, #8B5CF6 50%, #06B6D4 70%, transparent 100%)",
          }}
        />

        {/* Prompt header */}
        <div className="flex items-center justify-between gap-3 border-b border-line px-6 py-4">
          <AnimatePresence mode="wait">
            <motion.div
              key={`p-${idx}`}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.35 }}
              className="flex min-w-0 items-center gap-3"
            >
              <span
                className="font-mono-tech text-[13px]"
                style={{ color: "var(--color-meeet-indigo)" }}
              >
                $
              </span>
              <span className="truncate font-mono-tech text-[13.5px] text-ink">
                {d.prompt}
              </span>
            </motion.div>
          </AnimatePresence>
          <span
            className="flex-shrink-0 font-mono-tech text-[10px] uppercase tracking-[1.6px]"
            style={{ color: "var(--color-meeet-cyan)" }}
          >
            {t("council.dualVote")}
          </span>
        </div>

        {/* Two-voice grid */}
        <div className="grid grid-cols-1 gap-px bg-line md:grid-cols-2">
          {d.voices.map((v, vi) => (
            <AnimatePresence key={`v-${idx}-${vi}`} mode="wait">
              <motion.div
                key={`vc-${idx}-${vi}`}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{
                  duration: 0.5,
                  delay: 0.1 + vi * 0.08,
                  ease: [0.22, 1, 0.36, 1],
                }}
                className="relative bg-bg-1 p-6"
              >
                {/* Chosen check overlay */}
                {d.chosenIdx === vi && (
                  <motion.div
                    initial={{ scale: 0, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: 0.85, type: "spring", stiffness: 220 }}
                    className="absolute right-5 top-5 grid h-7 w-7 place-items-center rounded-full"
                    style={{
                      background: "rgba(52,211,153,0.18)",
                      color: "var(--color-success)",
                      boxShadow: "inset 0 0 0 1px rgba(52,211,153,0.5), 0 0 16px rgba(52,211,153,0.45)",
                    }}
                  >
                    <Check size={14} strokeWidth={2.4} />
                  </motion.div>
                )}

                {/* Model tag */}
                <div className="mb-3 flex items-center gap-2.5">
                  <span
                    className="grid h-6 w-6 place-items-center rounded-md font-mono-tech text-[10px] font-bold text-white"
                    style={{ background: v.brand }}
                  >
                    {v.model[0].toUpperCase()}
                  </span>
                  <span className="font-mono-tech text-[11px] uppercase tracking-[1.6px] text-ink">
                    {v.model}
                  </span>
                  <span
                    className="ml-auto font-mono-tech text-[10px] uppercase tracking-[1.6px]"
                    style={{ color: v.brand }}
                  >
                    {v.stance}
                  </span>
                </div>

                {/* Summary */}
                <p className="mb-5 text-[13px] leading-[1.55] text-ink/95">
                  {v.summary}
                </p>

                {/* Bottom stats: confidence bar + latency + tokens */}
                <div className="grid gap-2.5 border-t border-line pt-4 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3">
                  <div className="flex items-center gap-3">
                    <span className="w-[68px] text-ink-2">{t("council.confidence")}</span>
                    <div className="flex-1 overflow-hidden rounded-full bg-bg-0">
                      <motion.div
                        key={`c-${idx}-${vi}`}
                        initial={{ width: 0 }}
                        animate={{ width: `${v.confidence * 100}%` }}
                        transition={{ duration: 1.0, delay: 0.4, ease: [0.22, 1, 0.36, 1] }}
                        className="h-1"
                        style={{ background: v.brand, boxShadow: `0 0 6px ${v.brand}80` }}
                      />
                    </div>
                    <span className="w-10 text-right tabular-nums text-ink">
                      {Math.round(v.confidence * 100)}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-ink-2">
                    <span>{v.latency}</span>
                    <span>
                      {v.tokens} {t("council.tok")}
                    </span>
                  </div>
                </div>
              </motion.div>
            </AnimatePresence>
          ))}
        </div>

        {/* Footer — agreement + rationale */}
        <div className="grid gap-4 border-t border-line px-6 py-5 md:grid-cols-[180px_1fr] md:items-center">
          <div>
            <div className="mb-1.5 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
              {t("council.agreement")}
            </div>
            <div className="flex items-center gap-2.5">
              <div className="flex-1 overflow-hidden rounded-full bg-bg-0">
                <motion.div
                  key={`a-${idx}`}
                  initial={{ width: 0 }}
                  animate={{ width: `${d.agreement * 100}%` }}
                  transition={{ duration: 1.2, delay: 0.6, ease: [0.22, 1, 0.36, 1] }}
                  className="h-1.5 rounded-full"
                  style={{
                    background:
                      "linear-gradient(90deg, #6366F1 0%, #8B5CF6 50%, #06B6D4 100%)",
                    boxShadow: "0 0 12px rgba(139,92,246,0.5)",
                  }}
                />
              </div>
              <span className="w-12 text-right font-mono-tech text-[11px] tabular-nums text-ink">
                {Math.round(d.agreement * 100)}%
              </span>
            </div>
          </div>
          <AnimatePresence mode="wait">
            <motion.p
              key={`r-${idx}`}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4, delay: 0.9 }}
              className="font-mono-tech text-[11.5px] leading-[1.55] text-ink-2"
            >
              <span className="text-success">▸</span> {d.rationale}
            </motion.p>
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
}
