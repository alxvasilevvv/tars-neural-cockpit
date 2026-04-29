import phaseM from "@docs/PRODUCT_PHASE_M.md?raw";
import { LegalLayout } from "@/components/LegalLayout";

/**
 * /roadmap — public product roadmap. Renders `docs/PRODUCT_PHASE_M.md`
 * (Phase M: monetization, packaging, polish — the eight P-tasks we
 * sequenced after Cursor closed Phase L). Single source of truth.
 */
export function Roadmap() {
  return (
    <LegalLayout
      eyebrow="07 / roadmap"
      title="Phase M — what's next"
      lastReviewed="2026-04-29"
      source={phaseM}
      showToc
    />
  );
}
