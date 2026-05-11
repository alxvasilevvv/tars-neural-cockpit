import { motion, AnimatePresence } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useDocumentMeta } from "@/lib/meta";
import {
  ArrowLeft,
  ChevronUp,
  ChevronDown,
} from "lucide-react";
import { SLIDES, NavBtn } from "@/components/pitch/PitchSlides";

/**
 * /pitch — TARS investor / partner deck rendered as a sequence of 12
 * full-bleed slides. Brand triad (indigo / violet / cyan) on OLED
 * background. Keyboard nav (← / → / ↑ / ↓ / Home / End / Esc).
 *
 * Mirrors the structure pinned in `docs/PRODUCT_PHASE_M.md` § 3 (P2).
 * Same content is generated as a .pptx by `scripts/make-pitch.js`
 * for offline distribution.
 *
 * Wave 124 — slide data + reusable primitives extracted to
 * `@/components/pitch/PitchSlides` to bring this page back under the
 * 500-LOC threshold (was 942 LOC).
 */

export function Pitch() {
  useDocumentMeta({
    title: "Pitch deck",
    description:
      "12 slides on TARS — the local-first AI cockpit. Problem, product, architecture, traction, ask. Keyboard nav (← → ↑ ↓).",
    ogImage: "https://tars.meeet.world/og-pitch.svg",
  });
  const [idx, setIdx] = useState(0);

  const next = useCallback(() => {
    setIdx(i => Math.min(SLIDES.length - 1, i + 1));
  }, []);
  const prev = useCallback(() => {
    setIdx(i => Math.max(0, i - 1));
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === "ArrowDown" || e.key === "PageDown") {
        e.preventDefault();
        next();
      } else if (e.key === "ArrowLeft" || e.key === "ArrowUp" || e.key === "PageUp") {
        e.preventDefault();
        prev();
      } else if (e.key === "Home") {
        e.preventDefault();
        setIdx(0);
      } else if (e.key === "End") {
        e.preventDefault();
        setIdx(SLIDES.length - 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, prev]);

  const slide = SLIDES[idx];

  return (
    <div className="relative h-[calc(100vh-72px)] w-full overflow-hidden bg-bg-0">
      {/* Ambient backdrop */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background: `
            radial-gradient(ellipse 50% 40% at 18% 10%, rgba(99,102,241,0.12) 0%, transparent 60%),
            radial-gradient(ellipse 45% 35% at 82% 88%, rgba(139,92,246,0.10) 0%, transparent 60%),
            radial-gradient(ellipse 30% 25% at 50% 50%, rgba(6,182,212,0.06) 0%, transparent 60%)
          `,
        }}
      />

      {/* Slide */}
      <AnimatePresence mode="wait">
        <motion.section
          key={idx}
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto flex h-full max-w-[1200px] flex-col px-8 py-10 md:px-16 md:py-14"
          aria-label={`slide ${idx + 1} of ${SLIDES.length}`}
        >
          {/* Eyebrow */}
          <header className="mb-8 flex items-baseline gap-3 font-mono-tech text-[11px] uppercase tracking-[3px]">
            <span style={{ color: "#6366F1" }}>{slide.num}</span>
            <span className="text-ink-2">{slide.tag}</span>
          </header>

          {/* Title */}
          <h1
            className="mb-9 max-w-[26ch] font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
            style={{ fontSize: "clamp(2.4rem, 5.4vw, 4.6rem)" }}
          >
            {slide.title}
          </h1>

          {/* Body */}
          <div className="flex-1 overflow-auto">{slide.body}</div>

          {/* Footer */}
          <footer className="mt-8 flex items-center justify-between gap-4 border-t border-line pt-5 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
            <Link
              to="/"
              className="inline-flex items-center gap-2 transition-colors hover:text-ink"
            >
              <ArrowLeft size={11} strokeWidth={1.8} /> back to home
            </Link>
            <span aria-hidden>
              meeet.world · TARS · 2026 Q2
            </span>
            <span className="tabular-nums">
              {String(idx + 1).padStart(2, "0")} / {String(SLIDES.length).padStart(2, "0")}
            </span>
          </footer>
        </motion.section>
      </AnimatePresence>

      {/* Brand-triad hairline */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-x-0 top-[72px] z-10 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, #6366F1 30%, #8B5CF6 50%, #06B6D4 70%, transparent 100%)",
          opacity: 0.55,
        }}
      />

      {/* Nav controls — bottom right */}
      <nav
        aria-label="slide navigation"
        className="fixed bottom-6 right-6 z-20 inline-flex items-center gap-2 rounded-full border border-line bg-bg-1/80 p-1 backdrop-blur-md"
      >
        <NavBtn ariaLabel="previous slide" onClick={prev} disabled={idx === 0}>
          <ChevronUp size={14} strokeWidth={1.8} />
        </NavBtn>
        <NavBtn ariaLabel="next slide" onClick={next} disabled={idx === SLIDES.length - 1}>
          <ChevronDown size={14} strokeWidth={1.8} />
        </NavBtn>
      </nav>

      {/* Slide dots — left rail */}
      <ol
        aria-label="slide rail"
        className="fixed left-6 top-1/2 z-20 hidden -translate-y-1/2 flex-col gap-2 lg:flex"
      >
        {SLIDES.map((s, i) => (
          <li key={i}>
            <button
              type="button"
              onClick={() => setIdx(i)}
              aria-label={`go to slide ${i + 1}: ${s.tag}`}
              aria-current={i === idx ? "step" : undefined}
              className="grid place-items-center rounded-full transition-all duration-200"
              style={{
                width: i === idx ? 18 : 6,
                height: 6,
                background:
                  i === idx
                    ? "linear-gradient(90deg, #6366F1, #8B5CF6)"
                    : "var(--color-line-strong)",
              }}
            />
          </li>
        ))}
      </ol>

      {/* Keyboard hint */}
      <div
        aria-hidden
        className="fixed bottom-6 left-6 z-20 hidden items-center gap-2 font-mono-tech text-[9.5px] uppercase tracking-[2.2px] text-ink-3 lg:flex"
      >
        <kbd className="rounded border border-line bg-bg-1/60 px-1.5 py-0.5">←</kbd>
        <kbd className="rounded border border-line bg-bg-1/60 px-1.5 py-0.5">→</kbd>
        <span>navigate</span>
        <span aria-hidden className="mx-1">·</span>
        <kbd className="rounded border border-line bg-bg-1/60 px-1.5 py-0.5">esc</kbd>
        <Link to="/" className="hover:text-ink">
          home
        </Link>
      </div>
    </div>
  );
}
