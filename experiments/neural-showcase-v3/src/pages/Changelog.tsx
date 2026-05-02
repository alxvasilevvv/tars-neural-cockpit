import source from "@docs/CHANGELOG_PUBLIC.md?raw";
import { LegalLayout } from "@/components/LegalLayout";

/**
 * /changelog — public agent changelog. Renders the trimmed
 * `docs/CHANGELOG_PUBLIC.md` (top 60 entries; ~210 KB instead of
 * the full 550+ KB log). The file is regenerated from
 * `docs/CHANGELOG_AGENTS.md` by
 * `scripts/generate_public_changelog.py` (wired into the cockpit
 * `prebuild` script). Full per-edit log is still on GitHub for
 * operators who want the complete history.
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
