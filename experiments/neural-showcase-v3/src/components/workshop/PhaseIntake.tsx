// SYNC: claude-w80-fe-only
/**
 * PhaseIntake — first phase of the B2B workshop.
 *
 * Operator describes their existing process (a few sentences); we
 * synthesize a starter playbook + render the composer for review.
 * Marking complete writes to localStorage so WorkshopRail picks up
 * the ✓.
 */

import { motion } from "framer-motion";
import { Workflow } from "lucide-react";
import { PlaybookComposer } from "@/components/workshop/PlaybookComposer";

interface PhaseIntakeProps {
  onComplete: () => void;
}

export function PhaseIntake({ onComplete }: PhaseIntakeProps) {
  return (
    <motion.section
      initial={{ opacity: 1 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="grid gap-6"
    >
      <header className="grid gap-2">
        <div className="inline-flex items-center gap-2 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
          <Workflow
            size={12}
            strokeWidth={1.7}
            aria-hidden
            style={{ color: "var(--brand-indigo)" }}
          />
          <span>phase 01 · intake</span>
        </div>
        <h2 className="font-display text-[28px] leading-[1.05] tracking-[-0.01em] text-ink md:text-[34px]">
          Describe your process — TARS scaffolds the playbook.
        </h2>
        <p className="max-w-[60ch] font-mono-tech text-[12px] leading-[1.6] text-ink-2">
          Three sentences are enough. We'll synthesize a draft you can edit
          before saving. Skip ahead by composing the playbook by hand.
        </p>
      </header>

      <PlaybookComposer onSaved={() => onComplete()} />
    </motion.section>
  );
}
