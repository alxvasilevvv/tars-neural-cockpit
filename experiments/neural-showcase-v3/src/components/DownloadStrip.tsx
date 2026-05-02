/**
 * <DownloadStrip /> — Phase L9 hero CTA.
 *
 * Functional contract owned by Cursor (`/api/product/downloads`). This
 * file is the visual treatment per `AGENT_HANDOFF.md → Owned by Claude
 * Code (design)` item 11. Polish goals shipped here:
 *
 *   - real OS-glyph icons in the primary button (Apple / Windows / Tux
 *     / iOS / Android), tinted by the brand triad;
 *   - version pill that pulses "NEW" when the latest release dropped
 *     within the last 7 days, falls back to a quiet pill otherwise;
 *   - "verified · sha256 ✓" affordance once the manifest carries a
 *     checksum (signature_url adds a side link);
 *   - "all installers" row replaced by icon chips (one per artifact),
 *     each carries `title=<filename · sha hint>` for hover preview;
 *   - mobile-friendly stacked layout — primary button goes full-width
 *     on <sm screens, version pill drops to a second line;
 *   - footer variant that's slimmer, single line, no extra chips.
 *
 * Still framework-agnostic — no framer, no R3F. CSS animations only,
 * so the component can be dropped into any page (cockpit, marketing,
 * desktop shell) without ceremony. Loading / error / no-installer
 * paths preserved verbatim from Cursor's reference.
 */

import { useMemo } from "react";
import {
  AppleMark,
  WindowsMark,
  LinuxMark,
  IOSMark,
  AndroidMark,
} from "@/components/BrandLogos";
import {
  useDownloads,
  type ArtifactOS,
  type ReleaseArtifact,
  type ReleaseEntry,
} from "@/lib/downloads";
import { trackClick } from "@/lib/analytics";

const OS_LABELS: Record<ArtifactOS, string> = {
  macos: "Download for macOS",
  windows: "Download for Windows",
  linux: "Download for Linux",
  ios: "Get it on iOS",
  android: "Get it on Android",
};

const OS_ACCENT: Record<ArtifactOS, string> = {
  macos: "#F5F5F0",
  windows: "#06B6D4",
  linux: "#A78BFA",
  ios: "#F5F5F0",
  android: "#34D399",
};

function OSGlyph({ os, size = 16 }: { os: ArtifactOS; size?: number }) {
  switch (os) {
    case "macos":
      return <AppleMark size={size} />;
    case "windows":
      return <WindowsMark size={size} />;
    case "linux":
      return <LinuxMark size={size} />;
    case "ios":
      return <IOSMark size={size} />;
    case "android":
      return <AndroidMark size={size} />;
  }
}

/** Days since `released_at` — used to pulse the NEW badge. */
function daysSince(iso: string | undefined | null): number {
  if (!iso) return 999;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return 999;
  return (Date.now() - t) / 86_400_000;
}

interface Props {
  variant?: "hero" | "footer";
}

export function DownloadStrip({ variant = "hero" }: Props) {
  const { primary, detected, loading, error, artifacts, manifest } = useDownloads();
  const release = manifest?.releases?.[0];
  const isFresh = useMemo(() => daysSince(release?.released_at) < 7, [release]);

  if (loading) {
    return (
      <div
        className={`flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink-3 ${
          variant === "hero" ? "mt-6" : "mt-2"
        }`}
        aria-live="polite"
      >
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink-3" />
        loading installers…
      </div>
    );
  }

  if (error) {
    return (
      <div
        className={`flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-alert ${
          variant === "hero" ? "mt-6" : "mt-2"
        }`}
        role="alert"
      >
        offline · couldn't load installers ({error})
      </div>
    );
  }

  // Footer variant — slim, single line (+ checksum hint when manifest ships sha256).
  if (variant === "footer") {
    if (!primary || !release) return null;
    return (
      <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
        <a
          href={primary.url}
          data-filename={primary.filename}
          data-sha256={primary.sha256 ?? ""}
          onClick={() =>
            trackClick(`download_${primary.os}_${primary.arch}`, {
              version: release.version,
              kind: primary.kind,
              surface: "footer",
            })
          }
          className="group inline-flex items-center gap-2.5 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink-2 transition-colors hover:text-ink"
        >
          <span style={{ color: OS_ACCENT[primary.os] }}>
            <OSGlyph os={primary.os} size={13} />
          </span>
          <span>{OS_LABELS[primary.os]}</span>
          <span className="text-ink-3">v{release.version}</span>
          <span aria-hidden className="transition-transform group-hover:translate-x-0.5">→</span>
        </a>
        {primary.sha256 ? (
          <span
            className="inline-flex items-center gap-1 font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-3"
            title={primary.sha256}
          >
            <span
              className="grid h-3 w-3 place-items-center rounded-full text-[8px]"
              style={{
                background: "color-mix(in srgb, var(--color-success) 18%, transparent)",
                color: "var(--color-success)",
              }}
              aria-hidden
            >
              ✓
            </span>
            <span className="text-ink-3">sha256</span>
          </span>
        ) : null}
      </span>
    );
  }

  // Hero variant — full polish.
  return (
    <div className="mt-7 flex w-full flex-col items-start gap-4">
      {primary && release ? (
        <div className="flex w-full flex-col items-start gap-3 sm:flex-row sm:items-center">
          <PrimaryButton
            artifact={primary}
            label={OS_LABELS[primary.os] ?? `Download for ${detected.label}`}
            version={release.version}
          />
          <VersionPill release={release} fresh={isFresh} />
        </div>
      ) : (
        <span className="font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink-3">
          no installer for {detected.label} yet · check back soon
        </span>
      )}

      {/* Verified affordance — only when the manifest carries a checksum */}
      {primary?.sha256 && (
        <div className="flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
          <span
            className="grid h-4 w-4 place-items-center rounded-full"
            style={{
              background: "color-mix(in srgb, var(--color-success) 18%, transparent)",
              color: "var(--color-success)",
              boxShadow: "inset 0 0 0 1px color-mix(in srgb, var(--color-success) 45%, transparent)",
            }}
            aria-hidden
          >
            ✓
          </span>
          <span className="text-ink-2">verified</span>
          <span>·</span>
          <span title={primary.sha256}>sha256 {primary.sha256.slice(0, 12)}…</span>
          {primary.signature_url && (
            <>
              <span>·</span>
              <a
                href={primary.signature_url}
                className="text-ink-2 underline-offset-2 hover:text-ink hover:underline"
                title="Detached signature"
              >
                signature
              </a>
            </>
          )}
        </div>
      )}

      {/* All installers — icon chips */}
      {artifacts.length > 1 && (
        <div className="flex flex-wrap items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[1.8px]">
          <span className="text-ink-3">all installers</span>
          {artifacts.map(art => (
            <a
              key={`${art.os}-${art.arch}-${art.kind}`}
              href={art.url}
              title={`${art.filename}${art.sha256 ? ` · ${art.sha256.slice(0, 16)}…` : ""}`}
              data-os={art.os}
              data-arch={art.arch}
              data-kind={art.kind}
              data-sha256={art.sha256 ?? ""}
              onClick={() =>
                trackClick(`download_${art.os}_${art.arch}`, {
                  version: release?.version ?? "",
                  kind: art.kind,
                  surface: "all_installers",
                })
              }
              className="group inline-flex items-center gap-1.5 rounded-full border border-line bg-bg-1/60 px-2.5 py-1 text-ink-2 backdrop-blur-sm transition-all hover:border-line-strong hover:bg-bg-2/60 hover:text-ink"
            >
              <span
                style={{ color: OS_ACCENT[art.os] }}
                className="opacity-80 transition-opacity group-hover:opacity-100"
              >
                <OSGlyph os={art.os} size={11} />
              </span>
              <span className="tracking-[1.6px]">{art.arch}</span>
              <span className="text-ink-3">· {art.kind}</span>
            </a>
          ))}
        </div>
      )}

      {/* Local CSS for the NEW pulse — keeps the file dependency-free */}
      <style>{`
        @keyframes dlNewPulse {
          0%, 100% { transform: scale(1); opacity: 0.92; }
          50%      { transform: scale(1.06); opacity: 1; }
        }
        .dl-new-pulse {
          animation: dlNewPulse 2.6s ease-in-out infinite;
        }
        @media (prefers-reduced-motion: reduce) {
          .dl-new-pulse { animation: none; }
        }
      `}</style>
    </div>
  );
}

function PrimaryButton({
  artifact,
  label,
  version,
}: {
  artifact: ReleaseArtifact;
  label: string;
  version?: string;
}) {
  return (
    <a
      href={artifact.url}
      data-filename={artifact.filename}
      data-sha256={artifact.sha256 ?? ""}
      data-size-bytes={artifact.size_bytes ?? ""}
      onClick={() =>
        trackClick(`download_${artifact.os}_${artifact.arch}`, {
          version: version ?? "",
          kind: artifact.kind,
          surface: "hero",
        })
      }
      className="group inline-flex w-full items-center justify-center gap-2.5 rounded-md px-6 py-3.5 font-display text-[13px] uppercase tracking-[0.16em] text-white transition-all duration-200 hover:-translate-y-0.5 sm:w-auto"
      style={{
        background: "linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)",
        boxShadow:
          "0 0 0 1px rgba(99,102,241,0.45), 0 14px 38px -10px rgba(99,102,241,0.6)",
      }}
    >
      <span aria-hidden className="opacity-95">
        <OSGlyph os={artifact.os} size={16} />
      </span>
      <span>{label}</span>
      <span
        aria-hidden
        className="font-mono-tech text-[10px] uppercase tracking-[2px] opacity-80"
      >
        {artifact.kind}
      </span>
      <span aria-hidden className="transition-transform duration-200 group-hover:translate-x-0.5">
        →
      </span>
    </a>
  );
}

function VersionPill({ release, fresh }: { release: ReleaseEntry; fresh: boolean }) {
  const beta = release.channel !== "stable";
  const borderColor = beta
    ? "rgba(245, 158, 11, 0.4)"
    : fresh
      ? "rgba(52, 211, 153, 0.4)"
      : "var(--color-line-strong)";
  const fg = beta ? "#F59E0B" : fresh ? "var(--color-success)" : "var(--color-ink-2)";
  return (
    <div
      className="inline-flex items-center gap-2 rounded-full border bg-bg-1/60 px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2.2px] backdrop-blur-sm"
      style={{ borderColor, color: fg }}
    >
      {fresh && (
        <span
          aria-hidden
          className="dl-new-pulse h-1.5 w-1.5 rounded-full"
          style={{
            background: "var(--color-success)",
            boxShadow: "0 0 8px var(--color-success)",
          }}
        />
      )}
      <span>v{release.version}</span>
      {beta && <span>· {release.channel}</span>}
      {fresh && !beta && <span className="text-ink-2">· new</span>}
    </div>
  );
}
