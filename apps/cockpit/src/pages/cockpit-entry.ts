/*
 * Entry script for cockpit.html — operator shell ported from the W307
 * reference. No imperative behaviour yet: the markup is hand-authored
 * (so Claude's visual contract stays auditable diff-wise), and this
 * file only pulls the shared design tokens in.
 *
 * When the cockpit grows real behaviour (phase bar updates, policy
 * gate stream, mic toggle, …) it lives next to this entry as small
 * vanilla modules; no framework is required for the visual contract.
 */

import "../styles/global.css";
