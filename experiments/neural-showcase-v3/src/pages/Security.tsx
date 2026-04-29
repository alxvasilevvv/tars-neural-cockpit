import source from "@docs/SECURITY.md?raw";
import { LegalLayout } from "@/components/LegalLayout";

/**
 * /security — renders the canonical Security model document.
 * Source-of-truth: docs/SECURITY.md.
 */
export function Security() {
  return (
    <LegalLayout
      eyebrow="03 / security"
      title="Security model"
      lastReviewed="2026-04-29"
      source={source}
    />
  );
}
