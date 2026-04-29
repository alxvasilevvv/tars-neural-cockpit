import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Cpu,
  Layers,
  Play,
  Maximize2,
  Mic,
  Keyboard,
  X,
} from "lucide-react";
import { BrandHairline } from "@/components/BrandHairline";
import { BrandButton } from "@/components/BrandButton";
import { RobotAvatar } from "@/components/RobotAvatar";
import { useFocusTrap } from "@/lib/useFocusTrap";

/**
 * <CockpitTour /> — six-step welcome modal shown on the first visit
 * to /cockpit. Persists `tars-tour-seen` in localStorage; if private
 * mode prevents writes, the tour shows once per session and quietly
 * stops there.
 *
 * Each step is a self-contained card with: glyph + eyebrow + title +
 * 1-2 sentences + optional keyboard-shortcut chip. No real cockpit
 * highlight overlays — operators just want a fast read of what's
 * where, not a high-friction product tour.
 *
 * Keyboard:
 *   ←/→  prev/next
 *   Esc  dismiss (sets seen flag)
 *   Tab  cycles focus inside (via useFocusTrap)
 */

const STORAGE_KEY = "tars-tour-seen";

interface Step {
  Icon: typeof Cpu;
  eyebrow: string;
  title: string;
  body: string;
  shortcut?: string[];
  accent: string;
}

const STEPS: Step[] = [
  {
    Icon: Cpu,
    eyebrow: "01 / TARS-9",
    title: "Meet your robot.",
    body:
      "The avatar in the right rail mirrors what your machine is doing — idle, thinking, listening, ok, or error. Glance at it the way you glance at a clock.",
    accent: "var(--brand-indigo)",
  },
  {
    Icon: Layers,
    eyebrow: "02 / DOMAINS",
    title: "Pick a domain · pick an action.",
    body:
      "The two left columns are domains (Traders / Entrepreneur / Researcher / Science / …) and the actions inside each. Click to load the JSON args panel on the right.",
    accent: "var(--brand-violet)",
  },
  {
    Icon: Play,
    eyebrow: "03 / INVOKE",
    title: "Run a domain action.",
    body:
      "Edit the JSON, press Invoke. The trace footer streams events in real time, your TARS-9 starts thinking, and the response card lights up with timings + trace_id.",
    shortcut: ["Enter"],
    accent: "var(--brand-cyan)",
  },
  {
    Icon: Maximize2,
    eyebrow: "04 / WATCH ME WORK",
    title: "Cinematic ops mode.",
    body:
      "When you want to see the agent at full size — robot 300px, streaming timeline, big metrics — hit the shortcut. Esc to exit. Use it for screen-share demos.",
    shortcut: ["⌘", "⇧", "W"],
    accent: "var(--brand-orchid)",
  },
  {
    Icon: Mic,
    eyebrow: "05 / VOICE",
    title: "Optional · listen state.",
    body:
      "Click voice on the robot toolbar to enable the mic. Permission lives only while toggled on; the OS-level mic LED goes dark the moment you toggle off. Synthetic pulse if denied.",
    accent: "var(--color-success)",
  },
  {
    // Final card — collects every shortcut covered above plus the global
    // command palette (⌘K) so an operator can leave the tour with the
    // muscle-memory primitives in one screen.
    Icon: Keyboard,
    eyebrow: "06 / SHORTCUTS",
    title: "Move at the speed of intent.",
    body:
      "⌘K opens the command palette anywhere. ⌘⇧W toggles watch-me-work. Enter submits the JSON args panel. Esc closes any modal. Tab cycles focus everywhere.",
    shortcut: ["⌘", "K"],
    accent: "var(--brand-cyan)",
  },
];

function readSeen(): boolean {
  if (typeof localStorage === "undefined") return false;
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function writeSeen() {
  try {
    localStorage.setItem(STORAGE_KEY, "1");
  } catch {
    /* private mode — fall back to session-only */
  }
}

export function CockpitTour() {
  const [open, setOpen] = useState<boolean>(() => !readSeen());
  const [step, setStep] = useState(0);
  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(dialogRef, open);

  const close = () => {
    writeSeen();
    setOpen(false);
  };
  const prev = () => setStep(s => Math.max(0, s - 1));
  const next = () => {
    if (step >= STEPS.length - 1) close();
    else setStep(s => s + 1);
  };

  // Keyboard navigation
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        close();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        next();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        prev();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, step]);

  if (!open) return null;
  const s = STEPS[step];

  return (
    <AnimatePresence>
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-label="cockpit welcome tour"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.24 }}
        className="fixed inset-0 z-[85] flex items-center justify-center bg-[rgba(2,4,12,0.78)] px-3 backdrop-blur-md sm:px-4"
        onClick={close}
      >
        <motion.div
          ref={dialogRef}
          tabIndex={-1}
          onClick={e => e.stopPropagation()}
          initial={{ opacity: 0, y: 12, scale: 0.985 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 8, scale: 0.99 }}
          transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
          className="relative grid w-full max-w-[560px] grid-rows-[auto_1fr_auto] overflow-hidden rounded-[14px] border border-line-strong bg-bg-1 shadow-[0_40px_140px_rgba(0,0,0,0.7)] focus:outline-none"
        >
          <BrandHairline variant="static" />

          <header className="flex items-center justify-between border-b border-line/60 px-5 py-3.5">
            <span
              className="inline-flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.4px]"
              style={{ color: s.accent }}
            >
              <span aria-hidden>·</span>
              welcome to the cockpit
            </span>
            <button
              type="button"
              onClick={close}
              aria-label="Close tour"
              className="grid h-7 w-7 place-items-center rounded-md text-ink-3 transition-colors hover:bg-white/[0.05] hover:text-ink"
            >
              <X size={11} strokeWidth={2} aria-hidden />
            </button>
          </header>

          {/* Slide body */}
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
              className="grid grid-cols-[88px_1fr] items-center gap-4 px-5 py-6 sm:grid-cols-[120px_1fr] sm:gap-5 sm:px-8 sm:py-9"
            >
              <div className="relative flex justify-center">
                {/* Per-step glyph + ambient halo */}
                <span
                  className="absolute inset-0 -z-10 rounded-full blur-2xl"
                  style={{
                    background: `radial-gradient(60% 60% at 50% 50%, ${s.accent}33, transparent 75%)`,
                  }}
                  aria-hidden
                />
                {step === 0 ? (
                  <RobotAvatar state="idle" width={104} />
                ) : (
                  <span
                    className="grid h-20 w-20 place-items-center rounded-2xl border border-line-strong bg-bg-2/60"
                    style={{
                      color: s.accent,
                      boxShadow: `inset 0 0 0 1px ${s.accent}33`,
                    }}
                  >
                    <s.Icon size={28} strokeWidth={1.7} aria-hidden />
                  </span>
                )}
              </div>

              <div>
                <div
                  className="mb-2 inline-flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[3px]"
                  style={{ color: s.accent }}
                >
                  {s.eyebrow}
                </div>
                <h2 className="mb-3 font-display text-[20px] leading-[1.18] tracking-[-0.005em] text-ink">
                  {s.title}
                </h2>
                <p className="text-[13.5px] leading-[1.6] text-ink-2">
                  {s.body}
                </p>
                {s.shortcut && (
                  <div className="mt-4 inline-flex items-center gap-1.5">
                    {s.shortcut.map((k, i) => (
                      <kbd
                        key={i}
                        className="inline-block min-w-[20px] rounded-[5px] border border-line/80 bg-bg-2/80 px-1.5 py-0.5 text-center font-mono-tech text-[10px] uppercase tracking-[1.4px] text-ink/95"
                      >
                        {k}
                      </kbd>
                    ))}
                  </div>
                )}
              </div>
            </motion.div>
          </AnimatePresence>

          {/* Footer — progress + nav */}
          <footer className="flex items-center justify-between border-t border-line/60 px-5 py-3.5">
            <div
              role="tablist"
              aria-label="tour progress"
              className="inline-flex items-center gap-1.5"
            >
              {STEPS.map((_, i) => (
                <button
                  key={i}
                  type="button"
                  role="tab"
                  aria-selected={i === step}
                  aria-label={`Step ${i + 1} of ${STEPS.length}`}
                  onClick={() => setStep(i)}
                  className="h-1.5 w-1.5 rounded-full transition-all duration-150"
                  style={{
                    background: i === step ? s.accent : "var(--color-line-strong)",
                    transform: i === step ? "scale(1.3)" : "scale(1)",
                  }}
                />
              ))}
              <span className="ml-2 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3 tabular-nums">
                {step + 1} / {STEPS.length}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={close}
                className="inline-flex items-center gap-1.5 rounded-md border border-line bg-transparent px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3 transition-colors hover:border-line-strong hover:text-ink"
              >
                Skip tour
              </button>
              {step > 0 && (
                <button
                  type="button"
                  onClick={prev}
                  className="inline-flex items-center gap-1.5 rounded-md border border-line bg-transparent px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
                >
                  Back
                </button>
              )}
              <BrandButton
                onClick={next}
                size="sm"
                trailingIcon={<ArrowRight size={11} strokeWidth={1.8} aria-hidden />}
              >
                {step === STEPS.length - 1 ? "Finish" : "Next"}
              </BrandButton>
            </div>
          </footer>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
