import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { ArrowUpRight, Loader2 } from "lucide-react";
import { Link } from "react-router-dom";
import { CockpitPreview } from "@/components/CockpitPreview";
import { CornerFrame, StatusLozenge } from "@/components/Glyphs";
import { getHealth } from "@/lib/api";

/**
 * CockpitLive — "real cockpit, embedded" preview.
 *
 * Strategy:
 *   1. Run getHealth() against the configured TARS backend.
 *      If reachable → embed `/cockpit` as an iframe (truly live).
 *      If unreachable → fall back to the static <CockpitPreview /> mockup.
 *
 * Iframe is `pointer-events: none` — users can't accidentally fire actions
 * from the marketing page. A clear "Open the real one →" CTA lives over
 * the chrome. Backend health re-polls every 30s so the embed switches if
 * the user starts the daemon mid-session.
 *
 * This replaces the pure-mockup CockpitPreview in Landing.tsx — see
 * task #161 ("Real Cockpit вместо мокапа"). Honest preview before
 * showing investors / brother / first 100 users.
 */

type Mode = "checking" | "live" | "offline";

export function CockpitLive() {
  const [mode, setMode] = useState<Mode>("checking");
  const [iframeReady, setIframeReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    const check = async () => {
      try {
        const h = await Promise.race([
          getHealth(),
          new Promise<never>((_, rej) => setTimeout(() => rej(new Error("timeout")), 1800)),
        ]);
        if (cancelled) return;
        // Health endpoint exists and responded — backend reachable.
        setMode(h ? "live" : "offline");
      } catch {
        if (!cancelled) setMode("offline");
      }
    };

    check();
    timer = setInterval(check, 30_000);
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, []);

  // OFFLINE → show the polished static mockup. Honest fallback.
  if (mode === "offline") {
    return <CockpitPreview />;
  }

  // CHECKING / LIVE → render the live frame (or skeleton while iframe boots).
  return (
    <section
      id="cockpit-preview"
      className="relative z-20 mx-auto max-w-[1280px] overflow-hidden px-6 py-24 md:px-12 md:py-32"
    >
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-100px" }}
        transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        className="mb-12 flex flex-col items-start gap-3 md:flex-row md:items-end md:justify-between"
      >
        <div>
          <div className="mb-3 inline-flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
            <span
              className="h-1 w-1 rounded-full"
              style={{
                background: "var(--color-success)",
                boxShadow: "0 0 8px rgba(52,211,153,0.55)",
                animation: "pulseDot 1.6s ease-in-out infinite",
              }}
            />
            04 / cockpit · live preview
            <StatusLozenge label="LIVE" tone="success" />
          </div>
          <h2
            className="font-display font-medium leading-[0.94] tracking-[-0.02em] text-ink"
            style={{ fontSize: "clamp(2rem, 4.4vw, 3.6rem)" }}
          >
            What you see after{" "}
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(95deg, #6366F1 0%, #8B5CF6 50%, #06B6D4 100%)",
              }}
            >
              install
            </span>
            .
          </h2>
        </div>
        <Link
          to="/cockpit"
          className="group inline-flex items-center gap-2 rounded-md border border-line bg-white/[0.02] px-4 py-2.5 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-ink transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong"
        >
          Open the real one
          <ArrowUpRight
            size={14}
            strokeWidth={1.8}
            className="transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
          />
        </Link>
      </motion.div>

      {/* Live cockpit chrome — same window styling as the static mock */}
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 1, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
        className="relative overflow-hidden rounded-[16px] border border-line-strong bg-bg-1/80 shadow-[0_32px_120px_-30px_rgba(99,102,241,0.45)] backdrop-blur-sm"
      >
        <CornerFrame />
        <div
          aria-hidden
          className="absolute inset-x-0 top-0 z-10 h-px"
          style={{
            background:
              "linear-gradient(90deg, transparent 0%, #6366F1 30%, #8B5CF6 50%, #06B6D4 70%, transparent 100%)",
          }}
        />

        {/* macOS-style traffic-light row */}
        <div className="flex items-center justify-between border-b border-line bg-bg-1 px-5 py-3">
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-[#FF5F57]" />
            <span className="h-3 w-3 rounded-full bg-[#FEBC2E]" />
            <span className="h-3 w-3 rounded-full bg-[#28C840]" />
          </div>
          <span className="font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
            tars · cockpit · localhost:8765
          </span>
          <span style={{ width: 60 }} />
        </div>

        {/* Iframe live preview — pointer-events:none so the marketing page
            can't accidentally fire destructive actions. */}
        <div
          className="relative bg-bg-0"
          style={{ height: "min(72vh, 720px)" }}
        >
          {!iframeReady && (
            <div className="absolute inset-0 z-10 grid place-items-center">
              <div className="flex flex-col items-center gap-3 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-ink-2">
                <Loader2
                  size={18}
                  strokeWidth={1.6}
                  className="animate-spin"
                  style={{ color: "#6366F1" }}
                />
                booting cockpit…
              </div>
            </div>
          )}
          <iframe
            src="/cockpit?embed=1"
            title="TARS cockpit live preview"
            loading="lazy"
            onLoad={() => setIframeReady(true)}
            // No `sandbox` attribute — the iframe loads the same
            // origin as the host page, so `allow-same-origin
            // allow-scripts` would simultaneously trigger the
            // browser's "iframe can escape its sandbox" warning AND
            // grant zero protection (the cockpit needs DOM access to
            // localStorage anyway). Drop the attribute and trust the
            // origin we already serve.
            referrerPolicy="no-referrer-when-downgrade"
            className="absolute inset-0 h-full w-full border-0"
            style={{
              pointerEvents: "none",
              opacity: iframeReady ? 1 : 0,
              transition: "opacity 0.5s ease",
            }}
          />
          {/* Block-pointer overlay with subtle "click-through" CTA badge */}
          <div className="pointer-events-none absolute inset-0 grid place-items-end justify-items-end p-4">
            <span
              className="rounded-full border px-3 py-1 font-mono-tech text-[9.5px] uppercase tracking-[2.4px]"
              style={{
                borderColor: "var(--color-success)",
                color: "var(--color-success)",
                background: "color-mix(in srgb, var(--color-success) 8%, transparent)",
                backdropFilter: "blur(4px)",
              }}
            >
              LIVE · interaction disabled
            </span>
          </div>
        </div>

        <div className="grid items-center gap-3 border-t border-line px-5 py-3.5 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3 md:grid-cols-[1fr_auto]">
          <span>
            This is the actual cockpit running on your local TARS daemon —
            embedded read-only. Your data, your machine.
          </span>
          <Link
            to="/cockpit"
            className="text-success transition-colors hover:underline"
          >
            interact in full →
          </Link>
        </div>
      </motion.div>
    </section>
  );
}
