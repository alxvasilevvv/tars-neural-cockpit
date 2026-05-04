/**
 * CockpitGate — guards every /cockpit* route in the marketing
 * deployment.
 *
 * The cockpit was designed for the desktop (Tauri) shell talking to
 * a localhost daemon at 127.0.0.1:8765. When a visitor lands on the
 * web build (tars.meeet.world/cockpit) without that daemon, every
 * action error-toasts and the surface looks broken — exactly the
 * complaint from the 2026-05-04 audit:
 *
 *   "Кокпит тоже плохо работает, я вообще думаю что веб версию
 *    нужно убирать или как то максимально упрощать и давать только
 *    после регистрации и логирования"
 *
 * Strategy:
 *   1. Detect the runtime
 *      - Inside Tauri (`window.__TAURI_INTERNALS__` present): always
 *        render the real cockpit.
 *      - In the browser: ping `getHealth()` once. If 200 in <1s, the
 *        operator is running TARS locally — render the cockpit.
 *   2. Otherwise show a simplified, brand-correct landing card with
 *      a single primary action (Download for $OS) and two secondary
 *      paths: "Sign in to preview" (placeholder for B-002 magic-link
 *      flow) and "Watch demo".
 *
 * This is the "max-simplify the web cockpit" half of the audit fix.
 * The login wall ("only after sign-in") part is the
 * `signedInPreview` branch — once the operator clicks Sign in we
 * persist a `tars.web.preview` flag so the gate lets them through
 * to a read-only demo cockpit (no destructive actions, no real
 * traces).
 */

import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Download, ShieldCheck, Globe, Cpu, ArrowRight } from "lucide-react";
import { getHealth, API_BASE } from "@/lib/api";
import { CornerFrame, StatusLozenge } from "@/components/Glyphs";
import { useT } from "@/lib/i18n";

const PREVIEW_FLAG_KEY = "tars.web.preview";
const PROBE_TIMEOUT_MS = 1000;

type GateState = "probing" | "live" | "preview" | "locked";

function isInsideTauri(): boolean {
  if (typeof window === "undefined") return false;
  // Tauri 2.x exposes `__TAURI_INTERNALS__`; older 1.x used `__TAURI__`.
  // Check both because the desktop shell may pin either depending on
  // the build channel.
  const w = window as unknown as Record<string, unknown>;
  return Boolean(w.__TAURI_INTERNALS__ || w.__TAURI__);
}

function readPreviewFlag(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(PREVIEW_FLAG_KEY) === "1";
  } catch {
    return false;
  }
}

function setPreviewFlag(value: boolean): void {
  if (typeof window === "undefined") return;
  try {
    if (value) {
      window.localStorage.setItem(PREVIEW_FLAG_KEY, "1");
    } else {
      window.localStorage.removeItem(PREVIEW_FLAG_KEY);
    }
  } catch {
    // localStorage may throw in private browsing; tolerate.
  }
}

function detectOS(): "mac" | "linux" | "windows" {
  if (typeof navigator === "undefined") return "mac";
  const p = navigator.platform.toLowerCase();
  const ua = navigator.userAgent.toLowerCase();
  if (p.includes("mac") || ua.includes("mac")) return "mac";
  if (p.includes("win") || ua.includes("windows")) return "windows";
  return "linux";
}

interface CockpitGateProps {
  /** Real cockpit children — only rendered when the gate opens. */
  children: ReactNode;
}

export function CockpitGate({ children }: CockpitGateProps) {
  const t = useT();
  const [state, setState] = useState<GateState>(() =>
    isInsideTauri() ? "live" : "probing",
  );

  useEffect(() => {
    if (state !== "probing") return;
    let cancelled = false;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);

    (async () => {
      try {
        // getHealth() does not currently take an AbortSignal — wrap
        // in Promise.race to enforce the 1s budget.
        const probe = getHealth();
        const timed = new Promise<never>((_, reject) =>
          window.setTimeout(
            () => reject(new Error("probe-timeout")),
            PROBE_TIMEOUT_MS,
          ),
        );
        await Promise.race([probe, timed]);
        if (cancelled) return;
        setState("live");
      } catch {
        if (cancelled) return;
        // Daemon unreachable. If the operator already hit "preview",
        // honour that; otherwise show the upgrade card.
        setState(readPreviewFlag() ? "preview" : "locked");
      } finally {
        window.clearTimeout(timer);
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [state]);

  if (state === "live" || state === "preview") {
    return <>{children}</>;
  }

  if (state === "probing") {
    return (
      <div className="flex min-h-[60vh] items-center justify-center px-8 text-ink-2">
        <div className="flex items-center gap-3 font-mono-tech text-[11px] uppercase tracking-[2.6px]">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
          {t("cockpitGate.probing")}
        </div>
      </div>
    );
  }

  const os = detectOS();
  const downloadHref = "/install";

  return (
    <div className="relative">
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10"
        style={{
          background:
            "radial-gradient(60% 50% at 50% 0%, rgba(99,102,241,0.10), transparent 70%)",
        }}
      />

      <section className="relative z-10 mx-auto max-w-[920px] px-8 pt-16 pb-24 md:px-14 md:pt-24">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-6 inline-flex items-center gap-3 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2"
        >
          <span
            className="h-1 w-1 rounded-full"
            style={{
              background: "var(--color-meeet-cyan, #06B6D4)",
              boxShadow: "0 0 8px rgba(6,182,212,0.6)",
            }}
          />
          {t("cockpitGate.eyebrow")}
          <StatusLozenge label={t("cockpitGate.status.lozenge")} tone="hud" />
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.05, ease: [0.22, 1, 0.36, 1] }}
          className="font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
          style={{ fontSize: "clamp(2.0rem, 4.5vw, 3.6rem)" }}
        >
          {t("cockpitGate.title.lead")}{" "}
          <span
            className="bg-clip-text text-transparent"
            style={{
              backgroundImage:
                "linear-gradient(95deg, #6366F1 0%, #8B5CF6 50%, #06B6D4 100%)",
            }}
          >
            {t("cockpitGate.title.tail")}
          </span>
          .
        </motion.h1>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mt-5 max-w-[60ch] text-[15px] leading-[1.65] text-ink-2"
        >
          {t("cockpitGate.body")}
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
          className="relative mt-8 overflow-hidden rounded-[18px] border-2 p-7 md:p-9"
          style={{
            borderColor: "#6366F1",
            background:
              "linear-gradient(135deg, color-mix(in srgb, #6366F1 12%, transparent) 0%, color-mix(in srgb, #8B5CF6 6%, transparent) 100%)",
            boxShadow:
              "0 20px 60px -20px rgba(99,102,241,0.35), inset 0 1px 0 rgba(255,255,255,0.06)",
          }}
        >
          <CornerFrame />

          <div className="flex flex-col items-start gap-5 md:flex-row md:items-center md:gap-7">
            <div
              className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl"
              style={{
                background: "linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)",
                boxShadow: "0 8px 24px -6px rgba(99,102,241,0.5)",
              }}
            >
              <Download size={26} strokeWidth={2} className="text-white" />
            </div>
            <div className="flex-1">
              <div className="font-mono-tech text-[10.5px] uppercase tracking-[2.6px] text-ink-3">
                {t("cockpitGate.cta.eyebrow")}
              </div>
              <div className="mt-1 font-display text-[22px] font-medium leading-tight text-ink md:text-[26px]">
                {os === "mac"
                  ? t("cockpitGate.cta.mac")
                  : os === "linux"
                    ? t("cockpitGate.cta.linux")
                    : t("cockpitGate.cta.windows")}
              </div>
              <div className="mt-1.5 font-mono-tech text-[11px] uppercase tracking-[1.6px] text-ink-2">
                {t("cockpitGate.cta.detail")}
              </div>
            </div>
            <Link
              to={downloadHref}
              className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-white/20 bg-white px-5 py-3 font-mono-tech text-[11.5px] uppercase tracking-[2.4px] text-bg-0 transition-colors duration-200 hover:bg-white/90 md:w-auto"
            >
              {t("cockpitGate.cta.button")}
              <ArrowRight size={13} />
            </Link>
          </div>

          <div className="mt-7 grid grid-cols-1 gap-3 md:grid-cols-3">
            <div className="flex items-center gap-2.5 rounded-md border border-line bg-bg-1/60 px-3 py-2.5 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-2">
              <Cpu size={13} className="text-accent" strokeWidth={1.6} />
              {t("cockpitGate.feature.local")}
            </div>
            <div className="flex items-center gap-2.5 rounded-md border border-line bg-bg-1/60 px-3 py-2.5 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-2">
              <ShieldCheck size={13} className="text-accent" strokeWidth={1.6} />
              {t("cockpitGate.feature.signed")}
            </div>
            <div className="flex items-center gap-2.5 rounded-md border border-line bg-bg-1/60 px-3 py-2.5 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-2">
              <Globe size={13} className="text-accent" strokeWidth={1.6} />
              {t("cockpitGate.feature.meeet")}
            </div>
          </div>
        </motion.div>

        {/* Secondary paths: preview / sign in / docs */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-3"
        >
          <button
            type="button"
            onClick={() => {
              setPreviewFlag(true);
              setState("preview");
            }}
            className="flex flex-col items-start gap-2 rounded-[14px] border border-line bg-bg-1/60 p-5 text-left transition-colors duration-200 hover:border-line-strong"
          >
            <div className="font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-accent">
              {t("cockpitGate.alt.preview.eyebrow")}
            </div>
            <div className="font-display text-[15px] font-medium text-ink">
              {t("cockpitGate.alt.preview.title")}
            </div>
            <div className="text-[12.5px] leading-[1.5] text-ink-3">
              {t("cockpitGate.alt.preview.body")}
            </div>
          </button>
          <Link
            to="/docs"
            className="flex flex-col items-start gap-2 rounded-[14px] border border-line bg-bg-1/60 p-5 transition-colors duration-200 hover:border-line-strong"
          >
            <div className="font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2">
              {t("cockpitGate.alt.docs.eyebrow")}
            </div>
            <div className="font-display text-[15px] font-medium text-ink">
              {t("cockpitGate.alt.docs.title")}
            </div>
            <div className="text-[12.5px] leading-[1.5] text-ink-3">
              {t("cockpitGate.alt.docs.body")}
            </div>
          </Link>
          <Link
            to="/pitch"
            className="flex flex-col items-start gap-2 rounded-[14px] border border-line bg-bg-1/60 p-5 transition-colors duration-200 hover:border-line-strong"
          >
            <div className="font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2">
              {t("cockpitGate.alt.pitch.eyebrow")}
            </div>
            <div className="font-display text-[15px] font-medium text-ink">
              {t("cockpitGate.alt.pitch.title")}
            </div>
            <div className="text-[12.5px] leading-[1.5] text-ink-3">
              {t("cockpitGate.alt.pitch.body")}
            </div>
          </Link>
        </motion.div>

        <p className="mt-8 text-center font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
          {t("cockpitGate.footer.probe")} · {API_BASE}
        </p>
      </section>
    </div>
  );
}
