// SYNC: claude-w80-fe-only
/**
 * WorkshopRail — vertical 4-step progress indicator for the workshop
 * surface. Modelled on the dividers used in <ScrollStory />:
 *   - Sticky on desktop (md+); stacks on mobile.
 *   - Visual states: complete (✓), current (○), locked (░).
 *   - Click a completed/current step to navigate via ?phase=...
 *
 * Phases share an enum with Workshop.tsx; that file owns the
 * authoritative definitions and passes them down so this component
 * stays presentation-only.
 */

import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { Workflow, Wand2, FlaskConical, Rocket, Check, Lock } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type WorkshopPhaseId = "intake" | "design" | "test" | "deploy";

export interface WorkshopPhaseMeta {
  id: WorkshopPhaseId;
  label: string;
  caption: string;
  Icon: LucideIcon;
  accent: string;
}

export const WORKSHOP_PHASES: WorkshopPhaseMeta[] = [
  {
    id: "intake",
    label: "Intake",
    caption: "Describe your process",
    Icon: Workflow,
    accent: "var(--brand-indigo)",
  },
  {
    id: "design",
    label: "Design",
    caption: "Pick a domain · configure agent",
    Icon: Wand2,
    accent: "var(--brand-violet)",
  },
  {
    id: "test",
    label: "Test",
    caption: "Backtest against history",
    Icon: FlaskConical,
    accent: "var(--brand-cyan)",
  },
  {
    id: "deploy",
    label: "Deploy",
    caption: "Autopilot · schedule · run",
    Icon: Rocket,
    accent: "var(--brand-orchid)",
  },
];

interface WorkshopRailProps {
  active: WorkshopPhaseId;
  /** Phases the operator has fully completed (UI-only — persisted to localStorage). */
  completed: Set<WorkshopPhaseId>;
}

export function WorkshopRail({ active, completed }: WorkshopRailProps) {
  const navigate = useNavigate();
  const activeIdx = WORKSHOP_PHASES.findIndex((p) => p.id === active);

  return (
    <nav
      aria-label="workshop phases"
      className="md:sticky md:top-32 md:self-start"
    >
      <ol className="grid gap-3 md:gap-2">
        {WORKSHOP_PHASES.map((phase, idx) => {
          const isComplete = completed.has(phase.id);
          const isCurrent = phase.id === active;
          // Step is locked if it's after the active step AND not yet
          // completed — operators move forward, but can revisit.
          const isLocked = idx > activeIdx && !isComplete;
          const Icon = phase.Icon;

          const marker = isComplete ? (
            <Check size={11} strokeWidth={2.4} aria-hidden />
          ) : isLocked ? (
            <Lock size={10} strokeWidth={2} aria-hidden />
          ) : (
            <span
              className="block h-1.5 w-1.5 rounded-full"
              style={{ background: phase.accent }}
              aria-hidden
            />
          );

          return (
            <li key={phase.id}>
              <motion.button
                type="button"
                disabled={isLocked}
                onClick={() => navigate(`/workshop?phase=${phase.id}`)}
                initial={{ opacity: 1 }}
                animate={{ opacity: isLocked ? 0.5 : 1 }}
                transition={{ duration: 0.25 }}
                className={`group grid w-full grid-cols-[28px_1fr] items-start gap-3 rounded-md border px-3 py-2.5 text-left transition-colors ${
                  isCurrent
                    ? "border-line-strong bg-bg-2/60"
                    : "border-line/40 bg-transparent hover:bg-bg-2/40"
                } ${isLocked ? "cursor-not-allowed" : "cursor-pointer"}`}
                aria-current={isCurrent ? "step" : undefined}
              >
                <span
                  className="mt-0.5 grid h-7 w-7 place-items-center rounded-md border"
                  style={{
                    borderColor: isCurrent || isComplete ? phase.accent : "var(--color-line)",
                    color: isCurrent || isComplete ? phase.accent : "var(--color-ink-3)",
                    background:
                      isCurrent || isComplete
                        ? `color-mix(in srgb, ${phase.accent} 10%, transparent)`
                        : "transparent",
                  }}
                >
                  {isCurrent || isComplete || !isLocked ? (
                    <Icon size={13} strokeWidth={1.7} aria-hidden />
                  ) : (
                    marker
                  )}
                </span>
                <span className="min-w-0">
                  <span className="flex items-center gap-2">
                    <span className="font-mono-tech text-[9.5px] uppercase tracking-[2.2px] text-ink-3">
                      {String(idx + 1).padStart(2, "0")}
                    </span>
                    <span className="font-display text-[13px] text-ink">{phase.label}</span>
                    <span className="ml-auto" aria-hidden>
                      {marker}
                    </span>
                  </span>
                  <span className="mt-0.5 block truncate font-mono-tech text-[10.5px] uppercase tracking-[1.6px] text-ink-3">
                    {phase.caption}
                  </span>
                </span>
              </motion.button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
