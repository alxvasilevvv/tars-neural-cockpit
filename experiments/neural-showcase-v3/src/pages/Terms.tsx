import source from "@docs/TERMS_OF_SERVICE.md?raw";
import { LegalLayout } from "@/components/LegalLayout";

/**
 * /terms — renders the canonical Terms of Service markdown.
 * Source-of-truth: docs/TERMS_OF_SERVICE.md.
 */
export function Terms() {
  return (
    <LegalLayout
      eyebrow="02 / terms"
      title="Terms of Service"
      lastReviewed="2026-04-29"
      source={source}
    />
  );
}
