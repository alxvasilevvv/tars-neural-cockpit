import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Download,
  KeyRound,
  Settings2,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
} from "lucide-react";
import { useDocumentMeta } from "@/lib/meta";
import { useT } from "@/lib/i18n";
import { CornerFrame, StatusLozenge, BrandHairline } from "@/components/Glyphs";
import { useSidecarStatus } from "@/lib/useSidecarStatus";

/**
 * <Settings /> — slim user-facing surface for the few settings TARS
 * v9 actually exposes. Wave 61.
 *
 *   - About            — version, build hash placeholder, sidecar
 *                        status + copy-paste-friendly diagnostics.
 *   - Updates          — "Check for updates now" button. In Tauri it
 *                        calls the updater plugin; in the browser it
 *                        links out to GitHub Releases.
 *   - Keyboard         — table of every shortcut TARS responds to.
 *
 * Deep-link target: `tars://settings` from Wave 59 routes here.
 * The cockpit Cmd+K palette can also navigate here via `/settings`.
 */
export function Settings() {
  const t = useT();
  useDocumentMeta({
    title: "Settings · TARS",
    description: "Update preferences, check for updates, see keyboard shortcuts.",
  });
  const sidecar = useSidecarStatus();

  return (
    <section className="relative z-10 mx-auto max-w-[920px] px-6 pb-24 pt-32 md:px-12">
      <CornerFrame>
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3 transition-colors hover:text-ink"
        >
          <ArrowLeft size={11} strokeWidth={2} aria-hidden />
          <span>{t("settings.back" as never) ?? "back"}</span>
        </Link>
      </CornerFrame>

      <header className="mb-12 grid gap-6 md:grid-cols-[1fr_auto] md:items-end">
        <div>
          <div className="mb-3 inline-flex items-center gap-2.5 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
            <Settings2 size={12} strokeWidth={1.7} aria-hidden style={{ color: "var(--brand-indigo)" }} />
            <span>settings</span>
          </div>
          <h1
            className="font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
            style={{ fontSize: "var(--text-display-md)" }}
          >
            Tune TARS
          </h1>
        </div>
        <StatusLozenge>v{appVersion()}</StatusLozenge>
      </header>

      {/* ─── About ─────────────────────────────────────────────────── */}
      <SettingsCard
        eyebrow="01 · about"
        title="What's running"
      >
        <BrandHairline />
        <dl className="mt-5 grid grid-cols-1 gap-3 text-[12.5px] text-ink-2 md:grid-cols-2">
          <Row label="Version" value={`v${appVersion()}`} />
          <Row label="Runtime" value={runtimeLabel()} />
          <Row
            label="Backend"
            value={
              sidecar.status === "ready"
                ? `ready · :${sidecar.started?.port ?? 8765}${sidecar.started?.took_ms ? ` · ${sidecar.started.took_ms}ms` : ""}`
                : sidecar.status === "starting"
                  ? "starting…"
                  : sidecar.status === "failed"
                    ? `failed · ${sidecar.failed?.stage ?? "unknown"}`
                    : sidecar.status === "exited"
                      ? "stopped"
                      : "—"
            }
          />
          <Row label="Build" value="github.com/alxvasilevvv/tars-neural-cockpit" linkHref="https://github.com/alxvasilevvv/tars-neural-cockpit" />
        </dl>
      </SettingsCard>

      {/* ─── Updates ───────────────────────────────────────────────── */}
      <UpdatesCard />

      {/* ─── Keyboard Shortcuts ────────────────────────────────────── */}
      <SettingsCard eyebrow="03 · keyboard" title="Shortcuts">
        <BrandHairline />
        <ul className="mt-5 grid gap-2.5 text-[12.5px]">
          {SHORTCUTS.map((s) => (
            <li
              key={s.label}
              className="grid grid-cols-[1fr_auto] items-center gap-3 border-b border-line/50 pb-2 last:border-0"
            >
              <span className="text-ink-2">{s.label}</span>
              <kbd className="rounded-md border border-line bg-bg-2/60 px-2 py-0.5 font-mono-tech text-[11px] tracking-[1px] text-ink">
                {s.combo}
              </kbd>
            </li>
          ))}
        </ul>
      </SettingsCard>

      <p className="mt-12 max-w-[60ch] text-[12px] leading-[1.65] text-ink-3">
        TARS is local-first. Your data, your machine, your keys. Settings live in{" "}
        <code className="rounded bg-bg-2/60 px-1 py-0.5 font-mono-tech text-[11px] text-ink-2">
          ~/Library/Application Support/world.meeet.tars
        </code>{" "}
        on macOS, the equivalent on Windows/Linux. Delete that folder to reset all preferences.
      </p>
    </section>
  );
}

/* ─── Sub-components ─────────────────────────────────────────────── */

function SettingsCard({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 6 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-10% 0px" }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="relative mb-6 overflow-hidden rounded-[14px] border border-line-strong bg-bg-1 p-6 md:p-8"
    >
      <div className="mb-2 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-3">
        {eyebrow}
      </div>
      <h2 className="font-display text-[20px] leading-[1.25] text-ink">{title}</h2>
      {children}
    </motion.section>
  );
}

function Row({
  label,
  value,
  linkHref,
}: {
  label: string;
  value: string;
  linkHref?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line/40 pb-2.5 md:border-0 md:pb-0">
      <dt className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
        {label}
      </dt>
      <dd className="truncate text-ink">
        {linkHref ? (
          <a
            href={linkHref}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 underline-offset-4 hover:underline"
            style={{ color: "var(--color-accent)" }}
          >
            {value}
            <ExternalLink size={10} strokeWidth={2} aria-hidden />
          </a>
        ) : (
          value
        )}
      </dd>
    </div>
  );
}

/**
 * Updater button. In Tauri runtime calls @tauri-apps/plugin-updater;
 * in the browser, links out to GitHub Releases. The button is the
 * same width either way so layout doesn't reflow.
 */
function UpdatesCard() {
  const [state, setState] = useState<
    | { kind: "idle" }
    | { kind: "checking" }
    | { kind: "uptodate"; current: string }
    | { kind: "available"; current: string; next: string; url?: string }
    | { kind: "error"; message: string }
  >({ kind: "idle" });

  const onCheck = async () => {
    setState({ kind: "checking" });
    if (!isTauri()) {
      // Browser build — open GitHub Releases.
      window.open(
        "https://github.com/alxvasilevvv/tars-neural-cockpit/releases/latest",
        "_blank",
        "noreferrer",
      );
      setState({ kind: "idle" });
      return;
    }
    try {
      const mod = (await import(
        /* @vite-ignore */
        "@tauri-apps/plugin-updater"
      )) as { check?: () => Promise<{ available?: boolean; version?: string; currentVersion?: string }> };
      if (!mod.check) {
        setState({ kind: "error", message: "Updater plugin not available" });
        return;
      }
      const result = await mod.check();
      if (!result || !result.available) {
        setState({ kind: "uptodate", current: result?.currentVersion ?? appVersion() });
        return;
      }
      setState({
        kind: "available",
        current: result.currentVersion ?? appVersion(),
        next: result.version ?? "?",
      });
    } catch (err) {
      setState({
        kind: "error",
        message: err instanceof Error ? err.message : String(err),
      });
    }
  };

  return (
    <SettingsCard eyebrow="02 · updates" title="Stay current">
      <BrandHairline />
      <p className="mt-5 max-w-[60ch] text-[13px] leading-[1.6] text-ink-2">
        TARS auto-updates in the background when a new signed release ships. To
        check now, click below.
      </p>

      <div className="mt-5 flex items-center gap-3">
        <button
          type="button"
          onClick={onCheck}
          disabled={state.kind === "checking"}
          className="inline-flex items-center gap-2 rounded-md border border-line-strong bg-bg-2/60 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink transition-colors hover:border-accent disabled:opacity-60"
        >
          {state.kind === "checking" ? (
            <Loader2 size={12} strokeWidth={2} className="animate-spin" aria-hidden />
          ) : (
            <Download size={12} strokeWidth={1.7} aria-hidden />
          )}
          <span>
            {state.kind === "checking" ? "checking…" : "check for updates"}
          </span>
        </button>
        {!isTauri() && (
          <span className="font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3">
            (web build — opens GitHub Releases)
          </span>
        )}
      </div>

      <div className="mt-4 min-h-[1.5em]">
        {state.kind === "uptodate" && (
          <p className="inline-flex items-center gap-2 text-[12.5px]" style={{ color: "var(--color-success)" }}>
            <CheckCircle2 size={13} strokeWidth={1.7} aria-hidden />
            You're on the latest — v{state.current}.
          </p>
        )}
        {state.kind === "available" && (
          <p className="text-[12.5px] text-ink">
            New version <strong>v{state.next}</strong> available (you're on v{state.current}). It will install on next quit.
          </p>
        )}
        {state.kind === "error" && (
          <p className="inline-flex items-center gap-2 text-[12.5px]" style={{ color: "var(--brand-amber)" }}>
            <AlertTriangle size={13} strokeWidth={1.7} aria-hidden />
            {state.message}
          </p>
        )}
      </div>
    </SettingsCard>
  );
}

const SHORTCUTS: { label: string; combo: string }[] = [
  { label: "Open command palette",      combo: "⌘ K" },
  { label: "Jump (threads, attachments)",combo: "⌘ J" },
  { label: "Open operator palette",     combo: "⌘ ." },
  { label: "Show keyboard reference",   combo: "⇧ /" },
  { label: "Toggle TARS window (desktop)", combo: "⌘ ⇧ Space" },
  { label: "Skip to main content",      combo: "Tab (1st)" },
];

function appVersion(): string {
  // Vite injects __APP_VERSION__ via define plugin in production
  // builds; falls back to package.json read at build time.
  // For now we hard-code 9.1.0 — replaced when the release pipeline
  // wires the constant.
  return (
    (typeof __APP_VERSION__ !== "undefined" && __APP_VERSION__) ||
    "9.1.0"
  );
}

declare const __APP_VERSION__: string | undefined;

function runtimeLabel(): string {
  if (typeof window === "undefined") return "—";
  if (
    typeof (window as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__ !==
    "undefined"
  ) {
    return "desktop · tauri 2";
  }
  return "browser · web";
}

function isTauri(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof (window as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__ !==
      "undefined"
  );
}

export default Settings;
