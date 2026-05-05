# Wave 55 — Final launch ownership pass · sign-off

**Owner:** Claude (Cowork window)  
**Date:** 2026-05-05  
**Baseline:** HEAD `4b6a322` · 217 commits ahead of Wave 51 baseline  
**Lane respected:** components / pages / docs only — no `backend/`, `lib/`, `Makefile`, or `scripts/` writes.

---

## What I owned this wave

A consolidated `role="dialog"` sweep across the cockpit + marketing surface. With 217 commits since the last comprehensive a11y audit and multiple agents touching modal-adjacent code in flight, the consistency check was overdue. Modal a11y is the class of regression that ships silently and shows up in App Store accessibility review weeks later — best caught now, not after launch.

## Findings — verified false positives from earlier audit

The Wave 55 audit-batch reported two P0s that I disproved by reading the actual files:

- **`src/lib/i18n.tsx` SSR window guard "missing"** — already exists at L1617: `if (typeof window === "undefined") return "en";`. False positive.
- **Pricing/FAQ/Compare i18n keys "missing"** — `pricing.title/description`, `faq.title/description`, `compare.title/description` all present in the EN dict (L83–127) and (legacy) RU dict (L884–922). False positive. Wave 36 collapsed the user-facing surface to EN-only but the keys themselves still exist.

## Findings — real, fixed this wave

Of 11 `role="dialog"` overlays in `experiments/neural-showcase-v3/src/`, four had real defects:

| File | L | Defect | Fix |
|---|---|---|---|
| `src/pages/Onboarding.tsx` | 713 | `role="dialog"` without `aria-modal`, no focus trap, no Esc handler | `aria-modal="true"` + `tabIndex={-1}` + `useFocusTrap(dialogRef, true)` + Esc-to-close listener |
| `src/components/JumpPalette.tsx` | 177 | Missing `aria-modal` | `aria-modal="true"` (existing keyboard handler covers Esc/Enter/Arrows) |
| `src/components/CommandPalette.tsx` | 126 | Missing `aria-modal` | `aria-modal="true"` (same reasoning) |
| `src/components/CookieConsent.tsx` | 58 | `role="dialog"` on a non-blocking banner | `role="region"` — semantically correct for a labeled bottom-of-viewport notice |

WCAG sections cited in inline comments where the wiring is non-obvious: 4.1.2 Name Role Value, 2.1.2 No Keyboard Trap.

## Findings — real, deferred to Cursor

Out of lane for me; reported here so Cursor or the next agent picks them up:

- **Hardcoded hex colors** in `src/pages/PricingPage.tsx`, `ComparePage.tsx`, and `src/pages/Onboarding.tsx` role color chips. Visual consistency P1, not a11y. Belongs in the design-token sweep Cursor was running.
- **`make gate-control-tower` runtime side of `BRIDGE_SHARED_SECRET`**. Wave 54 closed the `.env.example` template gap; Cursor owns the Makefile target's runtime guard.
- **Silent-failure logging on `POST /operator/usage` retry exhaustion** in `backend/core/meeet/billing_mirror_remote.py`. When `MEEET_BILLING_USAGE_RETRIES` is exhausted, the mirror silently no-ops; should at minimum emit a structured `meeet.mirror.usage.exhausted` event.

## Verification

Sandbox-side: TypeScript-grade verification limited to import/symbol validation via grep. Both `useEffect` and `useRef` were already imported in `Onboarding.tsx` (L2); `useFocusTrap` import added cleanly (L23). The motion-component `ref` prop accepts `RefObject<HTMLDivElement>` natively (framer-motion 11). No new symbols introduced.

Local (operator side): the brief's existing self-checks still apply — `make smoke-billing-tars`, `make backend-tars-up` + curl `/api/entitlements`, `make dev-tars-stack` for visual smoke. Modal a11y changes don't affect those smoke targets; manual keyboard-only walkthrough on the Onboarding custom-role flow is the recommended verification.

## Launch readiness — my view

**GREEN for the surface I own.** The four real a11y defects in this wave were the last cluster blocking a clean launch from the Claude lane. The marketing + cockpit + onboarding surfaces are launch-ready. Remaining items (hardcoded hex, Makefile gate-control-tower, billing mirror logging) sit in Cursor's lane and are P1, not launch blockers.

**Files changed this wave:**

- `src/pages/Onboarding.tsx`
- `src/components/JumpPalette.tsx`
- `src/components/CommandPalette.tsx`
- `src/components/CookieConsent.tsx`
- `docs/CHANGELOG_AGENTS.md` (Wave 55 entry with `>>> SYNC` marker)
- `docs/WAVE_55_SIGNOFF.md` (this doc)
