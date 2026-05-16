/*
 * TARS cockpit entry point (W308 step 0).
 *
 * Currently mounts the tokens-preview page. When step 2 ships the
 * actual cockpit surfaces, this file becomes a thin router; pages
 * stay self-contained under src/pages/<name>.ts.
 */

import "./styles/global.css";
import { mountTokensPreview } from "./pages/tokens-preview";

const root = document.getElementById("cockpit-root");
if (!root) {
  // Failing loudly is the contract: the cockpit shell relies on this
  // element existing, and a silent miss would let the desktop ship a
  // blank window.
  throw new Error(
    "[cockpit] #cockpit-root not found in index.html — refusing to boot.",
  );
}

mountTokensPreview(root);
