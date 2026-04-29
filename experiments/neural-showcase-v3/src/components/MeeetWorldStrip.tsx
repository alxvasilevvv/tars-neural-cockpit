/**
 * <MeeetWorldStrip /> — visible front-door for the meeet.world spine.
 *
 * Per `AGENT_HANDOFF.md → Owned by Claude Code (design)` item 12 +
 * `Notes from Claude → Cursor` extend #6.
 *
 * meeet.world is the issuer for:
 *   - magic-link sign-in (`meeet.world/auth`)
 *   - $MEEET balance + earn (`meeet.world/account`)
 *   - L5 sync key namespace (when crypto lands)
 *
 * Today none of this surfaces in the marketing site beyond a footer
 * line. This component is a small horizontal strip that gives the
 * integration a visible front door:
 *
 *   - status pill — green when local daemon is reachable, muted otherwise
 *   - sign-in CTA → meeet.world/auth (magic link)
 *   - account CTA → meeet.world/account (wallet, $MEEET balance)
 *   - contract pin badge — surfaces `meeet:contract-version`
 *
 * Reads `getHealth()` from `lib/api.ts` — does NOT invent any new
 * backend contract; degrades gracefully when the daemon is offline.
 *
 * Variants:
 *   - "card"   — standalone framed card for landing-page placement
 *   - "footer" — slim text-only line for Footer slot
 */

import { useEffect, useState } from "react";
import { ArrowUpRight } from "lucide-react";
import { MeeetMark } from "@/components/BrandLogos";
import { getHealth } from "@/lib/api";
import { useDownloads } from "@/lib/downloads";

interface Props {
  variant?: "card" | "footer";
  className?: string;
}

export function MeeetWorldStrip({ variant = "card", className }: Props) {
  const [healthy, setHealthy] = useState<boolean | null>(null);
  // Read contract_version from the live manifest so we don't hard-code
  // a stale "1.0.0" — Cursor's L5 batch bumped it to 1.1.0 (additive
  // sync fields). Falls back to "1.x" placeholder until manifest lands.
  const { manifest } = useDownloads();
  const contractVersion = manifest?.contract_version ?? "1.x";

  useEffect(() => {
    let cancelled = false;
    const probe = async () => {
      try {
        const h = await Promise.race([
          getHealth(),
          new Promise<never>((_, rej) => setTimeout(() => rej(new Error("t")), 1500)),
        ]);
        if (!cancelled) setHealthy(Boolean(h));
      } catch {
        if (!cancelled) setHealthy(false);
      }
    };
    probe();
    const t = setInterval(probe, 30_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  if (variant === "footer") {
    return (
      <div
        className={`flex flex-wrap items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3 ${className ?? ""}`}
      >
        <span style={{ color: "var(--color-meeet-cyan, #06B6D4)" }}>
          <MeeetMark size={12} />
        </span>
        <span className="text-ink-2">issued by</span>
        <a
          href="https://meeet.world"
          className="text-ink transition-colors hover:text-accent"
        >
          meeet.world
        </a>
        <span aria-hidden>·</span>
        <span className="text-ink-3">contract {contractVersion}</span>
      </div>
    );
  }

  // Card variant
  return (
    <div
      className={`relative overflow-hidden rounded-[14px] border border-line bg-bg-1/60 backdrop-blur-sm ${className ?? ""}`}
    >
      {/* Top brand-triad hairline */}
      <div
        aria-hidden
        className="absolute inset-x-0 top-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, #6366F1 30%, #8B5CF6 50%, #06B6D4 70%, transparent 100%)",
        }}
      />

      <div className="grid grid-cols-1 gap-5 p-6 md:grid-cols-[auto_1fr_auto] md:items-center md:p-8">
        {/* Mark + label */}
        <div className="flex items-center gap-3.5">
          <span
            className="grid h-10 w-10 place-items-center rounded-md"
            style={{
              background:
                "linear-gradient(135deg, color-mix(in srgb, #6366F1 18%, transparent) 0%, color-mix(in srgb, #06B6D4 18%, transparent) 100%)",
              color: "var(--color-meeet-cyan, #06B6D4)",
              boxShadow: "inset 0 0 0 1px rgba(6, 182, 212, 0.32)",
            }}
            aria-hidden
          >
            <MeeetMark size={20} />
          </span>
          <div>
            <div className="font-display text-[15px] tracking-[0.02em] text-ink">
              meeet.world
            </div>
            <div className="mt-0.5 font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
              issuer · sync · economy
            </div>
          </div>
        </div>

        {/* Status pill */}
        <div className="md:px-6">
          <div
            className="inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono-tech text-[10px] uppercase tracking-[2.2px]"
            style={{
              borderColor: healthy
                ? "rgba(52, 211, 153, 0.45)"
                : "var(--color-line-strong)",
              color: healthy ? "var(--color-success)" : "var(--color-ink-2)",
              background: healthy
                ? "color-mix(in srgb, var(--color-success) 8%, transparent)"
                : "transparent",
            }}
          >
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{
                background: healthy ? "var(--color-success)" : "var(--color-ink-3)",
                boxShadow: healthy ? "0 0 8px var(--color-success)" : undefined,
                animation: healthy ? "pulseDot 1.6s ease-in-out infinite" : undefined,
              }}
              aria-hidden
            />
            <span>
              {healthy === null
                ? "checking…"
                : healthy
                  ? "daemon online · contract " + contractVersion
                  : "daemon offline · stays local-only"}
            </span>
          </div>
        </div>

        {/* CTAs */}
        <div className="flex flex-wrap items-center gap-2">
          <a
            href="https://meeet.world/auth"
            target="_blank"
            rel="noopener noreferrer"
            className="group inline-flex items-center gap-1.5 rounded-md border px-4 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink transition-colors duration-200 hover:bg-white/[0.04]"
            style={{ borderColor: "rgba(99,102,241,0.45)", background: "rgba(99,102,241,0.08)" }}
          >
            Sign in
            <ArrowUpRight
              size={12}
              strokeWidth={1.8}
              className="transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
            />
          </a>
          <a
            href="https://meeet.world/account"
            target="_blank"
            rel="noopener noreferrer"
            className="group inline-flex items-center gap-1.5 rounded-md border border-line px-4 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-2 backdrop-blur-sm transition-colors duration-200 hover:border-line-strong hover:text-ink"
          >
            Account
            <ArrowUpRight
              size={12}
              strokeWidth={1.8}
              className="transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
            />
          </a>
        </div>
      </div>
    </div>
  );
}
