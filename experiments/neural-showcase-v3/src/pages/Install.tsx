import { motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import {
  Apple,
  Terminal,
  Check,
  Copy,
  Lock,
  Cpu,
  Zap,
  ShieldCheck,
  Download,
  AlertTriangle,
  ChevronDown,
} from "lucide-react";
import { CornerFrame, StatusLozenge } from "@/components/Glyphs";
import { useDocumentMeta } from "@/lib/meta";
import { trackClick } from "@/lib/analytics";
import { useT } from "@/lib/i18n";
import {
  detectMacArch as detectMacArchHelper,
  detectOS as detectOSHelper,
} from "@/lib/installDetect";

/**
 * Install page — rebuilt for the 2026-05-04 audit:
 *
 * Bug #1: "Кнопка для скачивания отсутствует — нужно на файл нажимать."
 *   → giant primary "Download for macOS" button at the top, OS-detected.
 *     Falls back to /install.sh curl one-liner for advanced users.
 *
 * Bug #2: macOS shows "Приложение TARS повреждено" because builds
 *   aren't notarized with an Apple Developer ID ($99/yr). Two fixes:
 *   1. The CI now ad-hoc codesigns the .app before bundling the DMG
 *      (zero-cost, makes Right-click → Open work).
 *   2. The "/install.sh" one-liner strips the quarantine attribute
 *      automatically AND ad-hoc re-signs.
 *   3. This page surfaces a prominent Gatekeeper notice with the
 *      one-shot xattr command + a copy button so even hand-DMG
 *      installers can clear the warning in 5 seconds.
 */

const REPO = "alxvasilevvv/tars-neural-cockpit";
const RELEASE_VERSION = "v8.4.0";
const RELEASE_BASE = `https://github.com/${REPO}/releases/download/${RELEASE_VERSION}`;
const VERSION_NUMERIC = RELEASE_VERSION.replace(/^v/, "");

const ONE_LINE_CURL = "curl -fsSL https://tars.meeet.world/install.sh | bash";
const QUARANTINE_FIX = "xattr -dr com.apple.quarantine /Applications/TARS.app";
const BREW_CMD = "brew install meeet/tap/tars";

type OS = "mac-arm" | "mac-x64" | "linux-deb" | "linux-appimage" | "windows-msi" | "windows-exe";

interface DownloadOption {
  id: OS;
  os: "mac" | "linux" | "windows";
  arch: string;
  format: string;
  asset: string;
  size: string;
  primary?: boolean;
}

const DOWNLOADS: DownloadOption[] = [
  {
    id: "mac-arm",
    os: "mac",
    arch: "Apple Silicon (M1/M2/M3/M4)",
    format: "DMG",
    asset: `TARS_${VERSION_NUMERIC}_aarch64.dmg`,
    size: "~7 MB",
    primary: true,
  },
  {
    id: "mac-x64",
    os: "mac",
    arch: "Intel x64",
    format: "DMG",
    asset: `TARS_${VERSION_NUMERIC}_x64.dmg`,
    size: "~7 MB",
  },
  {
    id: "linux-appimage",
    os: "linux",
    arch: "x86_64",
    format: "AppImage",
    asset: `TARS_${VERSION_NUMERIC}_amd64.AppImage`,
    size: "~85 MB",
    primary: true,
  },
  {
    id: "linux-deb",
    os: "linux",
    arch: "x86_64",
    format: ".deb",
    asset: `TARS_${VERSION_NUMERIC}_amd64.deb`,
    size: "~9 MB",
  },
  {
    id: "windows-msi",
    os: "windows",
    arch: "x86_64",
    format: "MSI",
    asset: `TARS_${VERSION_NUMERIC}_x64_en-US.msi`,
    size: "~7 MB",
    primary: true,
  },
  {
    id: "windows-exe",
    os: "windows",
    arch: "x86_64",
    format: "NSIS .exe",
    asset: `TARS_${VERSION_NUMERIC}_x64-setup.exe`,
    size: "~6 MB",
  },
];

function detectOS(): "mac" | "linux" | "windows" {
  if (typeof navigator === "undefined") return "mac";
  return detectOSHelper(navigator);
}

function detectMacArch(): "arm" | "x64" {
  if (typeof navigator === "undefined") return "arm";
  return detectMacArchHelper(navigator);
}

function primaryFor(os: "mac" | "linux" | "windows"): DownloadOption {
  if (os === "mac") {
    const arch = detectMacArch();
    return DOWNLOADS.find((d) => d.id === (arch === "arm" ? "mac-arm" : "mac-x64"))!;
  }
  if (os === "linux") return DOWNLOADS.find((d) => d.id === "linux-appimage")!;
  return DOWNLOADS.find((d) => d.id === "windows-msi")!;
}

export function Install() {
  const t = useT();
  useDocumentMeta({
    title: "Install TARS · meeet.world",
    description:
      "One click — download TARS for Mac, Linux or Windows. Ships under meeet.world. Free, MIT, local-first.",
    ogImage: "https://tars.meeet.world/og-install.svg",
  });
  const [os, setOs] = useState<"mac" | "linux" | "windows">("mac");
  const [copied, setCopied] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    setOs(detectOS());
  }, []);

  const primary = useMemo(() => primaryFor(os), [os]);
  const primaryUrl = `${RELEASE_BASE}/${primary.asset}`;

  const copy = (text: string, which: string) => {
    navigator.clipboard?.writeText(text);
    setCopied(which);
    trackClick(`install_copy_${which}`, { os });
    setTimeout(() => setCopied(null), 1600);
  };

  return (
    <div className="relative">
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10"
        style={{
          background:
            "radial-gradient(60% 50% at 50% 0%, rgba(99,102,241,0.10), transparent 70%), radial-gradient(40% 40% at 30% 100%, rgba(139,92,246,0.06), transparent 70%)",
        }}
      />

      <section className="relative z-10 mx-auto max-w-[1080px] px-8 pt-20 pb-12 md:px-14 md:pt-28">
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
          {t("install.eyebrow")}
          <StatusLozenge label={`STABLE · ${RELEASE_VERSION}`} tone="hud" />
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.05, ease: [0.22, 1, 0.36, 1] }}
          className="font-display font-medium leading-[0.94] tracking-[-0.02em] text-ink"
          style={{ fontSize: "clamp(2.4rem, 5.4vw, 4.6rem)" }}
        >
          {t("install.title.lead")}
          <br />
          <span
            className="bg-clip-text text-transparent"
            style={{
              backgroundImage:
                "linear-gradient(95deg, #6366F1 0%, #8B5CF6 50%, #06B6D4 100%)",
            }}
          >
            {t("install.title.tail")}
          </span>
          .
        </motion.h1>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.7, delay: 0.2 }}
          className="mt-6 max-w-[60ch] text-[15px] leading-[1.65] text-ink-2"
        >
          {t("install.body")}
        </motion.p>

        {/* OS picker */}
        <div className="mt-10 flex flex-wrap items-center gap-2">
          {[
            { key: "mac" as const, label: "macOS", icon: Apple },
            { key: "linux" as const, label: "Linux", icon: Terminal },
            { key: "windows" as const, label: "Windows", icon: Cpu },
          ].map(({ key, label, icon: Icon }) => {
            const active = os === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => setOs(key)}
                aria-pressed={active}
                className="inline-flex items-center gap-2 rounded-md border px-3.5 py-2 font-mono-tech text-[11px] uppercase tracking-[2.4px] transition-colors duration-200"
                style={{
                  borderColor: active ? "#6366F1" : "var(--color-line-strong)",
                  background: active
                    ? "color-mix(in srgb, #6366F1 12%, transparent)"
                    : "transparent",
                  color: active ? "var(--color-ink)" : "var(--color-ink-2)",
                }}
              >
                <Icon size={13} strokeWidth={1.8} />
                {label}
              </button>
            );
          })}
        </div>

        {/* PRIMARY DOWNLOAD CTA — the giant button */}
        <motion.a
          key={primary.id}
          href={primaryUrl}
          download
          onClick={() => trackClick("install_download_primary", { os, asset: primary.asset })}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
          className="group mt-6 flex flex-col items-center gap-4 rounded-[18px] border-2 px-8 py-7 text-center transition-all duration-200 md:flex-row md:gap-6 md:px-10 md:py-8 md:text-left"
          style={{
            borderColor: "#6366F1",
            background:
              "linear-gradient(135deg, color-mix(in srgb, #6366F1 16%, transparent) 0%, color-mix(in srgb, #8B5CF6 8%, transparent) 100%)",
            boxShadow:
              "0 20px 60px -20px rgba(99,102,241,0.35), inset 0 1px 0 rgba(255,255,255,0.06)",
          }}
        >
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
              {t("install.primary.label")}
            </div>
            <div className="mt-1 font-display text-[22px] font-medium leading-tight text-ink md:text-[26px]">
              {os === "mac"
                ? `${t("install.primary.mac")} · ${primary.arch}`
                : os === "linux"
                  ? t("install.primary.linux")
                  : t("install.primary.windows")}
            </div>
            <div className="mt-1 font-mono-tech text-[11px] uppercase tracking-[1.6px] text-ink-2">
              {primary.format} · {primary.size} · {RELEASE_VERSION} ·{" "}
              <span className="text-accent">{primary.asset}</span>
            </div>
          </div>
          <div
            className="hidden items-center gap-2 rounded-md border px-4 py-2.5 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-ink transition-colors duration-200 md:inline-flex"
            style={{
              borderColor: "rgba(99,102,241,0.5)",
              background: "rgba(99,102,241,0.10)",
            }}
          >
            {t("install.primary.cta")}
            <Download
              size={13}
              className="transition-transform duration-200 group-hover:translate-y-0.5"
            />
          </div>
        </motion.a>

        {/* Mac-only Gatekeeper notice — the headline operator pain. */}
        {os === "mac" && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.45 }}
            className="mt-5 rounded-[14px] border border-amber-500/30 bg-amber-500/5 p-5"
          >
            <div className="flex items-start gap-3">
              <AlertTriangle
                size={18}
                strokeWidth={1.8}
                className="mt-0.5 shrink-0 text-amber-400"
              />
              <div className="flex-1">
                <div className="font-display text-[14px] font-medium text-ink">
                  {t("install.gatekeeper.title")}
                </div>
                <p className="mt-1.5 text-[13px] leading-[1.55] text-ink-2">
                  {t("install.gatekeeper.body")}
                </p>
                <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
                  <code className="flex-1 overflow-x-auto rounded-md border border-line bg-bg-2 px-3 py-2 font-mono text-[12.5px] text-ink">
                    {QUARANTINE_FIX}
                  </code>
                  <button
                    type="button"
                    onClick={() => copy(QUARANTINE_FIX, "fix")}
                    className="inline-flex items-center justify-center gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3.5 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-amber-300 transition-colors duration-200 hover:bg-amber-500/20"
                  >
                    {copied === "fix" ? <Check size={13} /> : <Copy size={13} />}
                    {copied === "fix" ? t("install.copied") : t("install.copy")}
                  </button>
                </div>
                <p className="mt-3 text-[12px] leading-[1.5] text-ink-3">
                  {t("install.gatekeeper.alt")}{" "}
                  <button
                    type="button"
                    onClick={() => copy(ONE_LINE_CURL, "curl")}
                    className="text-accent underline-offset-2 hover:underline"
                  >
                    {t("install.gatekeeper.alt.cta")}
                  </button>
                  {copied === "curl" && (
                    <span className="ml-2 text-success">✓ {t("install.copied")}</span>
                  )}
                </p>
              </div>
            </div>
          </motion.div>
        )}

        {/* Trust ribbon */}
        <ul className="mt-8 grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            { Icon: Lock, label: t("install.trust.local") },
            { Icon: ShieldCheck, label: t("install.trust.mit") },
            { Icon: Cpu, label: t("install.trust.sandbox") },
            { Icon: Zap, label: t("install.trust.setup") },
          ].map(({ Icon, label }) => (
            <li
              key={label}
              className="flex items-center gap-3 rounded-md border border-line bg-bg-1/60 px-3.5 py-3 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2"
            >
              <Icon size={14} strokeWidth={1.6} className="text-accent" />
              {label}
            </li>
          ))}
        </ul>

        {/* Advanced (collapsed): one-liner curl + brew + alt downloads */}
        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          className="mt-10 inline-flex items-center gap-2 rounded-md border border-line bg-bg-1/60 px-4 py-2.5 font-mono-tech text-[10.5px] uppercase tracking-[2.6px] text-ink-2 transition-colors duration-200 hover:border-line-strong hover:text-ink"
          aria-expanded={showAdvanced}
        >
          <ChevronDown
            size={13}
            className="transition-transform duration-200"
            style={{ transform: showAdvanced ? "rotate(180deg)" : undefined }}
          />
          {showAdvanced ? t("install.advanced.hide") : t("install.advanced.show")}
        </button>

        {showAdvanced && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="mt-5 space-y-4"
          >
            {/* curl one-liner */}
            <div className="overflow-hidden rounded-[14px] border border-line-strong bg-bg-1">
              <CornerFrame />
              <div className="px-5 py-3 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
                {t("install.advanced.curl.label")}
              </div>
              <div className="grid grid-cols-1 items-center gap-3 border-t border-line px-5 py-4 md:grid-cols-[1fr_auto] md:gap-4 md:px-7">
                <code className="overflow-x-auto whitespace-nowrap font-mono text-[14px] tracking-tight text-ink">
                  {ONE_LINE_CURL}
                </code>
                <button
                  type="button"
                  onClick={() => copy(ONE_LINE_CURL, "advcurl")}
                  className="inline-flex items-center justify-center gap-2 rounded-md border border-accent/40 bg-accent/10 px-3.5 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-accent transition-colors duration-200 hover:bg-accent/20"
                >
                  {copied === "advcurl" ? <Check size={13} /> : <Copy size={13} />}
                  {copied === "advcurl" ? t("install.copied") : t("install.copy")}
                </button>
              </div>
            </div>

            {os === "mac" && (
              <div className="overflow-hidden rounded-[14px] border border-line bg-bg-1">
                <div className="px-5 py-3 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
                  {t("install.advanced.brew.label")}
                </div>
                <div className="grid grid-cols-1 items-center gap-3 border-t border-line px-5 py-4 md:grid-cols-[1fr_auto] md:gap-4 md:px-7">
                  <code className="overflow-x-auto whitespace-nowrap font-mono text-[14px] tracking-tight text-ink">
                    {BREW_CMD}
                  </code>
                  <button
                    type="button"
                    onClick={() => copy(BREW_CMD, "brew")}
                    className="inline-flex items-center justify-center gap-2 rounded-md border border-line-strong bg-bg-2 px-3.5 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink transition-colors duration-200 hover:bg-line"
                  >
                    {copied === "brew" ? <Check size={13} /> : <Copy size={13} />}
                    {copied === "brew" ? t("install.copied") : t("install.copy")}
                  </button>
                </div>
              </div>
            )}

            {/* All assets table */}
            <div className="overflow-hidden rounded-[14px] border border-line bg-bg-1">
              <div className="px-5 py-3 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
                {t("install.advanced.assets.label")}
              </div>
              <ul className="divide-y divide-line border-t border-line">
                {DOWNLOADS.filter((d) => d.os === os).map((d) => (
                  <li
                    key={d.id}
                    className="flex flex-col gap-2 px-5 py-3 text-[13px] sm:flex-row sm:items-center sm:justify-between md:px-7"
                  >
                    <div>
                      <div className="font-mono text-ink">{d.asset}</div>
                      <div className="font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
                        {d.arch} · {d.format} · {d.size}
                      </div>
                    </div>
                    <a
                      href={`${RELEASE_BASE}/${d.asset}`}
                      download
                      onClick={() =>
                        trackClick("install_download_alt", { asset: d.asset })
                      }
                      className="inline-flex items-center justify-center gap-2 rounded-md border border-line-strong bg-bg-2 px-3.5 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink transition-colors duration-200 hover:border-accent hover:text-accent"
                    >
                      <Download size={12} />
                      {t("install.advanced.assets.download")}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </motion.div>
        )}
      </section>

      {/* Step-by-step: what happens after install */}
      <section className="relative z-10 mx-auto max-w-[1080px] px-8 pb-24 md:px-14 md:pb-36">
        <header className="mb-10 grid grid-cols-1 items-end gap-6 border-t border-line pt-12 md:grid-cols-[1fr_1.2fr] md:pt-16">
          <div className="flex items-baseline gap-3 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
            <span className="text-[14px] tracking-normal text-accent">10</span>
            <span>{t("install.steps.eyebrow")}</span>
          </div>
          <h2 className="font-display text-[clamp(1.6rem,3.2vw,2.6rem)] font-medium leading-[1.06] tracking-[-0.01em] text-ink">
            {t("install.steps.title")}
          </h2>
        </header>

        <ol className="grid grid-cols-1 gap-px overflow-hidden rounded-[14px] border border-line bg-line md:grid-cols-2">
          {(["s1", "s2", "s3", "s4"] as const).map((stepKey, i) => (
            <motion.li
              key={stepKey}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{
                duration: 0.5,
                delay: 0.08 * i,
                ease: [0.22, 1, 0.36, 1],
              }}
              className="relative bg-bg-1 p-7 md:p-9"
            >
              <CornerFrame />
              <div className="mb-3 flex items-center gap-3 font-mono-tech text-[11px] uppercase tracking-[3px]">
                <span style={{ color: "#6366F1" }}>{`0${i + 1}`}</span>
                <span className="text-ink-2">{t("install.steps.step")}</span>
              </div>
              <h3 className="mb-2 font-display text-[18px] font-medium leading-[1.25] text-ink">
                {t(`install.steps.${stepKey}.title`)}
              </h3>
              <p className="text-[13.5px] leading-[1.6] text-ink-2">
                {t(`install.steps.${stepKey}.body`)}
              </p>
            </motion.li>
          ))}
        </ol>
      </section>
    </div>
  );
}
