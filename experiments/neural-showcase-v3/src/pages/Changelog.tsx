import source from "@docs/CHANGELOG_AGENTS.md?raw";
import { LegalLayout } from "@/components/LegalLayout";

/**
 * /changelog — public agent changelog. Renders the same
 * `docs/CHANGELOG_AGENTS.md` we keep internally, top-down newest-first.
 * It's already MIT-open on GitHub; surfacing it on the marketing site
 * gives operators an honest "what shipped when" view.
 */
export function Changelog() {
  return (
    <LegalLayout
      eyebrow="08 / changelog"
      title="What shipped, top-down"
      lastReviewed="rolling"
      source={source}
      showToc
    />
  );
}
