// SYNC: claude-w80-fe-only
/**
 * <Workshop /> — Wave 80-D
 *
 * Main route for the B2B onboarding surface. The workshop walks an
 * operator through 4 phases (intake → design → test → deploy) and
 * persists per-phase completion in localStorage so refreshing the
 * tab keeps the rail's ✓ marks. Phase is reflected in the URL
 * (`?phase=…`) so deep-links work and Cmd+K can jump straight in.
 *
 * Page chrome mirrors `/settings` and `/cockpit`: a CornerFrame
 * wrapper for the back-link, a small eyebrow, a display-md headline,
 * a status lozenge for the current phase, and a responsive 2-column
 * split (rail | active phase). Brand tokens drive every accent —
 * indigo / violet / cyan / orchid map onto the four phases via
 * <WorkshopRail />.
 *
 * Defensive `initial: opacity: 1` on every motion node (Wave 70
 * pattern — keeps the page renderable even if framer-motion bails on
 * variant resolution mid-render).
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, FlaskRound } from "lucide-react";
import { useDocumentMeta } from "@/lib/meta";
import { CornerFrame, StatusLozenge } from "@/components/Glyphs";
import { BrandHairline } from "@/components/BrandHairline";
import {
  WorkshopRail,
  WORKSHOP_PHASES,
  type WorkshopPhaseId,
} from "@/components/workshop/WorkshopRail";
import { PhaseIntake } from "@/components/workshop/PhaseIntake";
import { PhaseDesign } from "@/components/workshop/PhaseDesign";
import { PhaseTest } from "@/components/workshop/PhaseTest";
import { PhaseDeploy } from "@/components/workshop/PhaseDeploy";
import { WorkshopTutorial } from "@/components/WorkshopTutorial";
import type { Agent } from "@/lib/agents";
import type { BacktestResult } from "@/lib/workshop";

const PHASE_KEY = "tars-workshop-completed-v1";
const AGENT_KEY = "tars-workshop-agent-id-v1";

function loadCompleted(): Set<WorkshopPhaseId> {
  if (typeof localStorage === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(PHASE_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr)) return new Set();
    return new Set(arr.filter((s) => typeof s === "string") as WorkshopPhaseId[]);
  } catch {
    return new Set();
  }
}

function saveCompleted(set: Set<WorkshopPhaseId>) {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(PHASE_KEY, JSON.stringify([...set]));
  } catch {
    /* private mode — silently ignore */
  }
}

function loadAgentId(): string | null {
  if (typeof localStorage === "undefined") return null;
  try {
    return localStorage.getItem(AGENT_KEY);
  } catch {
    return null;
  }
}

function saveAgentId(id: string | null) {
  if (typeof localStorage === "undefined") return;
  try {
    if (id) localStorage.setItem(AGENT_KEY, id);
    else localStorage.removeItem(AGENT_KEY);
  } catch {
    /* ignore */
  }
}

function isPhase(s: string | null): s is WorkshopPhaseId {
  return s === "intake" || s === "design" || s === "test" || s === "deploy";
}

export function Workshop() {
  useDocumentMeta({
    title: "Workshop · TARS",
    description:
      "Build, test, and deploy a custom TARS agent for your team in four phases.",
  });

  const [params, setParams] = useSearchParams();
  const phase: WorkshopPhaseId = isPhase(params.get("phase"))
    ? (params.get("phase") as WorkshopPhaseId)
    : "intake";

  const [completed, setCompleted] = useState<Set<WorkshopPhaseId>>(() =>
    loadCompleted(),
  );
  const [agentId, setAgentId] = useState<string | null>(() => loadAgentId());

  useEffect(() => {
    saveCompleted(completed);
  }, [completed]);

  useEffect(() => {
    saveAgentId(agentId);
  }, [agentId]);

  const markComplete = useCallback(
    (id: WorkshopPhaseId, advance: WorkshopPhaseId | null) => {
      setCompleted((prev) => {
        const next = new Set(prev);
        next.add(id);
        return next;
      });
      if (advance) {
        const sp = new URLSearchParams(params);
        sp.set("phase", advance);
        setParams(sp, { replace: false });
      }
    },
    [params, setParams],
  );

  const meta = useMemo(
    () => WORKSHOP_PHASES.find((p) => p.id === phase) ?? WORKSHOP_PHASES[0],
    [phase],
  );

  return (
    <section className="relative z-10 mx-auto max-w-[1200px] px-6 pb-24 pt-32 md:px-12">
      <div className="relative mb-6">
        <CornerFrame />
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3 transition-colors hover:text-ink"
        >
          <ArrowLeft size={11} strokeWidth={2} aria-hidden />
          <span>back</span>
        </Link>
      </div>

      <header className="mb-10 grid gap-6 md:grid-cols-[1fr_auto] md:items-end">
        <div>
          <div className="mb-3 inline-flex items-center gap-2.5 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
            <FlaskRound
              size={12}
              strokeWidth={1.7}
              aria-hidden
              style={{ color: "var(--brand-indigo)" }}
            />
            <span>workshop</span>
          </div>
          <h1
            className="font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
            style={{ fontSize: "var(--text-display-md)" }}
          >
            Build a TARS agent for your team.
          </h1>
          <p className="mt-3 max-w-[60ch] font-mono-tech text-[12px] leading-[1.6] text-ink-2">
            Four phases. Describe the process, design the agent, test on
            history, then deploy with autopilot. Every phase saves locally so
            you can step away and come back.
          </p>
        </div>
        <StatusLozenge label={`phase · ${meta.label.toLowerCase()}`} />
      </header>

      <BrandHairline variant="static" />

      <motion.div
        initial={{ opacity: 1 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3 }}
        className="mt-8 grid gap-8 md:grid-cols-[260px_1fr]"
      >
        {/* Wave 92 — `data-tutorial-id` anchors for the workshop tour overlay. */}
        <div data-tutorial-id="workshop-rail">
          <WorkshopRail active={phase} completed={completed} />
        </div>

        <div className="min-w-0">
          {phase === "intake" && (
            <div data-tutorial-id="phase-intake">
              <PhaseIntake onComplete={() => markComplete("intake", "design")} />
            </div>
          )}
          {phase === "design" && (
            <div data-tutorial-id="phase-design">
              <PhaseDesign
                onComplete={(agent: Agent) => {
                  setAgentId(agent.id);
                  markComplete("design", "test");
                }}
              />
            </div>
          )}
          {phase === "test" && (
            <div data-tutorial-id="phase-test">
              <PhaseTest
                agentId={agentId}
                onComplete={(_r: BacktestResult) =>
                  markComplete("test", "deploy")
                }
              />
            </div>
          )}
          {phase === "deploy" && (
            <div data-tutorial-id="phase-deploy">
              <PhaseDeploy
                agentId={agentId}
                onComplete={() => markComplete("deploy", null)}
              />
            </div>
          )}
        </div>
      </motion.div>

      {/* Wave 92 — invisible cmd+K hint anchor for the tour. The
          GlobalCommandPalette itself is mounted at the App root; this
          marker just anchors step 7 of the walkthrough. */}
      <span
        data-tutorial-id="cmdk-hint"
        aria-hidden
        className="pointer-events-none absolute right-6 top-32 inline-flex items-center gap-1 rounded-md border border-line/60 bg-bg-2/40 px-2 py-1 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3 opacity-60"
      >
        <kbd className="font-mono-tech">⌘K</kbd>
      </span>

      {/* Wave 92 — first-run interactive tutorial overlay (8 steps). */}
      <WorkshopTutorial pageKey="workshop-generic" />
    </section>
  );
}

export default Workshop;
