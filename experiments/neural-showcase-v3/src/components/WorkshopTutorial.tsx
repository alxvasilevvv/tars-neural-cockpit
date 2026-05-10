/**
 * <WorkshopTutorial /> — Wave 92
 *
 * First-run interactive walkthrough for the workshop surface. Mounts
 * an anchored tooltip overlay on first visit, advancing through a
 * scripted set of steps and persisting completion to localStorage so
 * the operator only sees it once.
 *
 * Three step decks are baked in, picked by `pageKey`:
 *
 *   - workshop-generic    (8 steps) — the /workshop 4-phase journey
 *   - workshop-cohort     (5 steps) — facilitator dashboard primer
 *   - workshop-enterprise (5 steps) — enterprise marketing landing
 *
 * Anchors are looked up via `data-tutorial-id` on the page's DOM. If
 * an anchor isn't found (lazy mount, A/B variant), the step falls
 * back to a centred card — the tour never breaks because of a
 * missing element.
 *
 * Usage:
 *
 *   <WorkshopTutorial pageKey="workshop-generic" />
 *
 * Place once near the bottom of the page so it overlays everything.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { TutorialTooltip } from "@/components/TutorialTooltip";
import { useTutorial, type TutorialPageKey } from "@/lib/tutorial";

interface TourStep {
  /** `data-tutorial-id` to find the anchor element. Null = centred. */
  anchorId: string | null;
  title: string;
  body: string;
  /** Optional CTA on the final step. */
  primaryHref?: string;
  primaryLabel?: string;
}

const STEPS_GENERIC: TourStep[] = [
  {
    anchorId: null,
    title: "Welcome to the TARS Workshop",
    body:
      "TARS Workshop is a 4-phase journey: describe a process, design an agent, test on history, then deploy with autopilot. We'll walk you through each panel in under a minute.",
  },
  {
    anchorId: "workshop-rail",
    title: "Four phases, one rail",
    body:
      "These 4 phases — intake, design, test, deploy — show your progress at a glance. Click any complete phase to revisit it; later phases unlock as you finish the earlier ones.",
  },
  {
    anchorId: "phase-intake",
    title: "Intake — describe your process",
    body:
      "Start by describing the manual process you want TARS to take over. Two or three sentences is enough — TARS turns it into a structured intent.",
  },
  {
    anchorId: "phase-design",
    title: "Design — pick the agent",
    body:
      "Design an agent for one of those processes. Choose tools, set guardrails, and write a short system prompt. Templates ship for the common cases.",
  },
  {
    anchorId: "phase-test",
    title: "Test — run it on history",
    body:
      "Run a backtest against historical data. You'll see win rate, latency, and which tool calls fired so you can tune before letting it loose on live traffic.",
  },
  {
    anchorId: "phase-deploy",
    title: "Deploy — promote to autopilot",
    body:
      "Promote to autopilot when you're ready. Start in human-in-the-loop mode, then graduate to fully unattended once you trust the metrics.",
  },
  {
    anchorId: "cmdk-hint",
    title: "Press Cmd+K to jump anywhere",
    body:
      "The command palette (Cmd+K / Ctrl+K) jumps between every workshop page, the cohort dashboard, ROI calculator, materials hub, and self-assessment quiz.",
  },
  {
    anchorId: null,
    title: "Ready? Pick a starter playbook",
    body:
      "Jump into Intake to describe your first process, or open a starter playbook from Materials. Either way, you can re-open this tour anytime from Settings.",
    primaryHref: "/workshop?phase=intake",
    primaryLabel: "Start with Intake",
  },
];

const STEPS_COHORT: TourStep[] = [
  {
    anchorId: "cohort-table",
    title: "Live attendee table",
    body:
      "Every attendee in the cohort, their current phase, last action, and idle time. Click a row for the deep-dive panel.",
  },
  {
    anchorId: "cohort-broadcast",
    title: "Broadcast composer",
    body:
      "Send a quick prompt to the entire cohort or a phase-filtered subset — appears as a banner above their workshop view.",
  },
  {
    anchorId: "cohort-detail",
    title: "Attendee detail",
    body:
      "Selected attendee's recent events, current agent draft, and risk flags. Use the Mark-as-needs-help button to flag struggling attendees.",
  },
  {
    anchorId: "cohort-risk",
    title: "Risk alerts",
    body:
      "TARS surfaces idle attendees, repeat-error attendees, and anyone exceeding their configured budget. Triage from here without digging into individual rows.",
  },
  {
    anchorId: "cohort-export",
    title: "CSV export",
    body:
      "Pull the entire cohort snapshot as CSV for post-workshop review or sponsor reports. Includes phase, completion time, and event count per attendee.",
  },
];

const STEPS_ENTERPRISE: TourStep[] = [
  {
    anchorId: null,
    title: "Welcome — Enterprise Workshop",
    body:
      "This page is the marketing landing for fund partners and quant teams. The 4-phase wizard is one click away once you've read the playbooks.",
  },
  {
    anchorId: "enterprise-playbooks",
    title: "Five algotrade playbooks",
    body:
      "Mean reversion, momentum breakout, live paper, backtest pipeline, weekly risk audit. Each one runs end-to-end on TARS in under an hour.",
  },
  {
    anchorId: "enterprise-risk",
    title: "Risk-first posture",
    body:
      "Every playbook ships with a kill-switch, position cap, and daily loss cap by default. Quants can scrutinise the risk policy before any agent goes live.",
  },
  {
    anchorId: "enterprise-cta",
    title: "Book a workshop slot",
    body:
      "Pick a date, share the playbook list with your team, and we'll lead a guided session. Day-1 onboarding usually takes 90 minutes.",
  },
  {
    anchorId: null,
    title: "Ready to dive in?",
    body:
      "Open the generic 4-phase wizard to start now, or wait for your facilitator. Re-open this tour anytime from Settings → Reset workshop tutorials.",
    primaryHref: "/workshop",
    primaryLabel: "Open Workshop",
  },
];

const STEP_DECKS: Record<TutorialPageKey, TourStep[]> = {
  "workshop-generic": STEPS_GENERIC,
  "workshop-cohort": STEPS_COHORT,
  "workshop-enterprise": STEPS_ENTERPRISE,
};

export interface WorkshopTutorialProps {
  pageKey: TutorialPageKey;
  /**
   * Imperative mount switch — when set to true the tour shows even
   * if the user already finished it. Wired by Settings + Cmd+K
   * "Restart workshop tutorial" so the operator can replay any time.
   */
  forceShow?: boolean;
}

/** Find an anchor by `data-tutorial-id`. Returns null if not present. */
function findAnchor(id: string | null): HTMLElement | null {
  if (!id || typeof document === "undefined") return null;
  return document.querySelector<HTMLElement>(`[data-tutorial-id="${id}"]`);
}

export function WorkshopTutorial({ pageKey, forceShow }: WorkshopTutorialProps) {
  const steps = STEP_DECKS[pageKey];
  const tut = useTutorial(pageKey, steps.length);

  // The DOM may take a tick to mount the anchored elements (lazy-load,
  // suspended phases). Re-resolve the anchor on every step change AND
  // on a one-shot 100ms tick after step change so we catch late mounts.
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  const currentStep = steps[tut.step];

  useEffect(() => {
    if (!tut.isVisible && !forceShow) return;
    const tryResolve = () => setAnchorEl(findAnchor(currentStep?.anchorId ?? null));
    tryResolve();
    const t = setTimeout(tryResolve, 100);
    return () => clearTimeout(t);
  }, [currentStep?.anchorId, tut.isVisible, forceShow, tut.step]);

  // Imperative restart — listen for a custom window event so other
  // surfaces (Settings button, GlobalCommandPalette) can poke us
  // without prop-drilling refs.
  useEffect(() => {
    const onRestart = (e: Event) => {
      const detail = (e as CustomEvent<{ pageKey?: TutorialPageKey }>).detail;
      if (!detail || detail.pageKey === pageKey || detail.pageKey === undefined) {
        tut.restart();
      }
    };
    window.addEventListener("tars:restart-workshop-tutorial", onRestart);
    return () => window.removeEventListener("tars:restart-workshop-tutorial", onRestart);
  }, [tut, pageKey]);

  // Honor forceShow prop too.
  const visible = useMemo(
    () => Boolean(forceShow || tut.isVisible),
    [forceShow, tut.isVisible],
  );

  const handleNext = useCallback(() => {
    tut.next();
  }, [tut]);
  const handlePrev = useCallback(() => tut.prev(), [tut]);
  const handleSkip = useCallback(() => tut.skip(), [tut]);

  if (!visible || !currentStep) return null;

  return (
    <AnimatePresence>
      <TutorialTooltip
        key={`${pageKey}-${tut.step}`}
        anchor={anchorEl}
        title={currentStep.title}
        body={currentStep.body}
        step={tut.step + 1}
        total={steps.length}
        onNext={handleNext}
        onPrev={handlePrev}
        onSkip={handleSkip}
        primaryHref={currentStep.primaryHref}
        primaryLabel={currentStep.primaryLabel}
        nextLabel={tut.step === steps.length - 1 ? "Finish" : "Next"}
      />
    </AnimatePresence>
  );
}

/**
 * Helper for outside surfaces (Settings, Cmd+K) to fire the imperative
 * restart event. Optional pageKey filter — omit to restart any
 * mounted instance.
 */
export function dispatchRestartTutorial(pageKey?: TutorialPageKey): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent("tars:restart-workshop-tutorial", { detail: { pageKey } }),
  );
}

export default WorkshopTutorial;
