/*
 * Entry script for preview.html — design-system diagnostic surface.
 *
 * Renders every MASTER token (palette, typography, motion, CTAs,
 * glyphs) so token drift between MASTER.md ↔ tokens.css ↔ live
 * preview can be eyeballed in one place.
 */

import "../styles/global.css";
import { mountTokensPreview } from "./tokens-preview";

const root = document.getElementById("preview-root");
if (!root) {
  // Loud failure: the preview page is the only diagnostic surface
  // for token drift, a silent miss would hide regressions.
  throw new Error(
    "[cockpit:preview] #preview-root not found in preview.html — refusing to boot.",
  );
}

mountTokensPreview(root);
