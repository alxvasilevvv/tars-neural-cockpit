import source from "@docs/PRIVACY_POLICY.md?raw";
import { LegalLayout } from "@/components/LegalLayout";

/**
 * /privacy — renders the canonical Privacy Policy markdown.
 * Source-of-truth: docs/PRIVACY_POLICY.md (single document, no duplication).
 */
export function Privacy() {
  return (
    <LegalLayout
      eyebrow="01 / privacy"
      title="Privacy Policy"
      lastReviewed="2026-04-29"
      source={source}
    />
  );
}
