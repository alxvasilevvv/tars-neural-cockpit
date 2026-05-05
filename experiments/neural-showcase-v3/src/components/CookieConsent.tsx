import { motion, AnimatePresence } from "framer-motion";
import { Link } from "react-router-dom";
import { Cookie, X } from "lucide-react";
import { useEffect, useState } from "react";
import { BrandHairline } from "@/components/BrandHairline";
import { BrandButton } from "@/components/BrandButton";
import { useT } from "@/lib/i18n";

/**
 * CookieConsent — dismissible banner that confirms our functional-
 * cookies-only policy. Per `docs/PRIVACY_POLICY.md` § 9, we use four
 * functional cookies (session, theme, lang, Cloudflare BM) and no
 * tracking/advertising cookies.
 *
 * The banner exists for compliance UX — operators in EU/EEA expect
 * to see *something*. We don't actually have any cookies that
 * require consent under GDPR Article 7 (functional cookies are
 * exempt), so this is informational + ack rather than a real opt-in
 * gate.
 *
 * Persistence: localStorage flag `tars-cookie-ack`. Once acked, the
 * banner stays gone for the session lifetime.
 */

const KEY = "tars-cookie-ack";

export function CookieConsent() {
  const t = useT();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (typeof localStorage === "undefined") return;
    try {
      if (localStorage.getItem(KEY) !== "1") {
        // Delay 1.2s so the banner doesn't fight with the hero
        // entrance animation.
        const t = setTimeout(() => setVisible(true), 1200);
        return () => clearTimeout(t);
      }
    } catch {
      /* private mode — show once per session */
      setVisible(true);
    }
  }, []);

  const dismiss = () => {
    try {
      localStorage.setItem(KEY, "1");
    } catch {
      /* ignore */
    }
    setVisible(false);
  };

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          role="region"
          aria-label="cookie notice"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
          className="fixed bottom-4 left-1/2 z-40 flex w-full max-w-[820px] -translate-x-1/2 flex-col items-stretch gap-3 rounded-[12px] border border-line bg-bg-1/90 px-4 py-3 backdrop-blur-md sm:flex-row sm:items-center sm:gap-4 sm:px-5 md:bottom-6"
          style={{ width: "calc(100% - 1.5rem)" }}
        >
          <BrandHairline />

          <div className="flex items-start gap-3 sm:flex-1 sm:items-center sm:gap-4">
            <span
              className="grid h-9 w-9 shrink-0 place-items-center rounded-md text-accent"
              style={{
                background: "color-mix(in srgb, var(--color-accent) 14%, transparent)",
                boxShadow: "inset 0 0 0 1px rgba(99,102,241,0.32)",
              }}
              aria-hidden
            >
              <Cookie size={15} strokeWidth={1.7} />
            </span>

            <div className="flex-1 min-w-0">
              <div className="font-display text-[13.5px] tracking-[0.01em] text-ink">
                {t("cookie.title")}
              </div>
              <div className="mt-0.5 text-[11.5px] leading-[1.5] text-ink-2">
                {t("cookie.body")}{" "}
                <Link to="/privacy" className="text-ink-2 underline-offset-2 hover:text-ink hover:underline">
                  {t("cookie.privacy_link")}
                </Link>
                .
              </div>
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 sm:gap-3">
            <BrandButton onClick={dismiss}>{t("cookie.accept")}</BrandButton>

            <button
              type="button"
              onClick={dismiss}
              aria-label={t("cookie.dismiss")}
              className="relative grid h-9 w-9 shrink-0 place-items-center rounded-full text-ink-3 transition-colors hover:bg-white/[0.05] hover:text-ink sm:h-7 sm:w-7 sm:before:absolute sm:before:inset-[-10px] sm:before:content-['']"
            >
              <X size={14} strokeWidth={2} aria-hidden />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
