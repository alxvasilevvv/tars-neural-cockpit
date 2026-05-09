import { motion, AnimatePresence } from "framer-motion";
import { Link, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { ArrowRight, Mail } from "lucide-react";
import { trackClick } from "@/lib/analytics";
import { BrandHairline } from "@/components/BrandHairline";
import { useT } from "@/lib/i18n";

/**
 * <StickyCTA /> — appears once the operator scrolls past the Hero fold.
 * Two CTAs: primary "Open cockpit", secondary "Join waitlist". Hidden
 * on routes where it would compete with the page's own CTAs.
 *
 *   Desktop: floats centred, ~24px above the bottom edge.
 *   Mobile:  full-width pill pinned to the bottom (above CookieConsent
 *            when both are visible).
 *
 * Hides itself on `/cockpit`, `/onboarding`, `/install`, and any route
 * that already owns the bottom of the viewport.
 *
 * Respects `prefers-reduced-motion` (no slide-in, just opacity).
 */

const HIDE_ON: ReadonlyArray<string> = [
  "/cockpit",
  "/onboarding",
  "/install",
  "/pitch", // pitch is a fullscreen deck
];

const SCROLL_TRIGGER_PX = 720; // a touch past Hero on desktop, mid-Hero on mobile

export function StickyCTA() {
  const t = useT();
  const loc = useLocation();
  const [visible, setVisible] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  // Reset dismissal when route changes
  useEffect(() => {
    setDismissed(false);
  }, [loc.pathname]);

  // Track scroll
  useEffect(() => {
    const onScroll = () => {
      setVisible(window.scrollY > SCROLL_TRIGGER_PX);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const blocked = HIDE_ON.some(p => loc.pathname.startsWith(p));
  if (blocked) return null;

  const show = visible && !dismissed;

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          role="region"
          aria-label="quick actions"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 16 }}
          transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
          className="fixed bottom-3 left-1/2 z-30 w-full max-w-[640px] -translate-x-1/2 px-3 sm:bottom-6 sm:px-0"
        >
          <div className="relative flex items-center gap-2 overflow-hidden rounded-full border border-line bg-bg-1/85 px-2 py-2 backdrop-blur-md shadow-[0_24px_60px_-20px_rgba(0,0,0,0.7)] sm:gap-3 sm:px-3">
            <BrandHairline />

            {/* Live pip + label, hidden on tiny mobile to keep CTAs roomy */}
            <div className="hidden items-center gap-2 pl-2 pr-3 sm:flex">
              <span
                aria-hidden
                className="h-1.5 w-1.5 rounded-full"
                style={{
                  background: "var(--color-success)",
                  boxShadow: "0 0 8px rgba(52,211,153,0.55)",
                  animation: "pulseDot 2.4s ease-in-out infinite",
                }}
              />
              <span className="font-mono-tech text-[9.5px] uppercase tracking-[2.4px] text-ink-3">
                ready
              </span>
            </div>

            <Link
              to="/#waitlist"
              onClick={() => trackClick("sticky_cta_waitlist")}
              className="inline-flex flex-1 shrink-0 items-center justify-center gap-2 rounded-full border border-line bg-white/[0.02] px-4 py-2.5 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink transition-all duration-150 hover:-translate-y-px hover:border-line-strong hover:bg-white/[0.04] sm:flex-initial"
            >
              <Mail size={12} strokeWidth={1.8} aria-hidden />
              <span>{t("stickyCTA.notify")}</span>
            </Link>

            {/* Wave 68 — primary CTA gated by INSTALLERS_READY:
                pre-launch we only ask people to join the waitlist;
                post-launch (signed installers) it'll flip back to
                "Download TARS" → /install. Hides the broken-download
                trap until the dl-proxy + Apple Developer ID + Win
                Authenticode + minisign keys are all populated. */}
            <Link
              to="/#waitlist"
              onClick={() => trackClick("sticky_cta_notify")}
              className="inline-flex flex-1 shrink-0 items-center justify-center gap-2 rounded-full px-4 py-2.5 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-white transition-all duration-150 hover:-translate-y-px sm:flex-initial"
              style={{
                background: "var(--brand-cta-gradient)",
                boxShadow: "var(--shadow-brand-cta)",
              }}
            >
              <span>Notify me at launch</span>
              <ArrowRight size={12} strokeWidth={1.8} aria-hidden />
            </Link>

            <button
              type="button"
              onClick={() => {
                setDismissed(true);
                trackClick("sticky_cta_dismiss");
              }}
              aria-label="Hide quick actions"
              className="relative ml-1 hidden h-8 w-8 shrink-0 items-center justify-center rounded-full text-ink-3 transition-colors hover:bg-white/[0.05] hover:text-ink sm:grid"
            >
              <span aria-hidden className="text-[14px] leading-none">×</span>
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
