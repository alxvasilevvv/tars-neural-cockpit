import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import {
  Apple,
  Terminal,
  Check,
  Copy,
  Lock,
  Cpu,
  Zap,
  ShieldCheck,
  ArrowRight,
} from "lucide-react";
import { CornerFrame, StatusLozenge } from "@/components/Glyphs";
import { useDocumentMeta } from "@/lib/meta";
import { trackClick } from "@/lib/analytics";

const INSTALL_CMD = "curl -fsSL meeet.world/install.sh | bash";
const BREW_CMD = "brew install meeet/tap/tars";

type OS = "mac" | "linux" | "windows";

function detectOS(): OS {
  if (typeof navigator === "undefined") return "mac";
  const p = navigator.platform.toLowerCase();
  const ua = navigator.userAgent.toLowerCase();
  if (p.includes("mac") || ua.includes("mac")) return "mac";
  if (p.includes("win") || ua.includes("windows")) return "windows";
  return "linux";
}

const STEPS: { num: string; title: string; body: string }[] = [
  {
    num: "01",
    title: "Run the install command",
    body: "One curl, no sudo unless absolutely needed. Installs to ~/.tars and registers a launchd / systemd service so the daemon survives reboot.",
  },
  {
    num: "02",
    title: "Sign in with magic-link",
    body: "Open meeet.world/auth in your browser, scan a QR with your wallet (or use email magic-link). The token gets handed back to the local agent over a one-shot localhost callback.",
  },
  {
    num: "03",
    title: "Pick your pack",
    body: "Traders, business, entrepreneur, science. You can switch later. The pack tunes the daily briefing template, the council prompts, and the suggested skills.",
  },
  {
    num: "04",
    title: "First Daily Briefing",
    body: "TARS reads your calendar, mail and starred repos (only the sources you connect), drafts a one-page briefing, and asks two questions to calibrate tone. ~60 seconds.",
  },
];

export function Install() {
  useDocumentMeta({
    title: "Install",
    description: "Install TARS on Mac, Linux, or Windows. One curl, sixty seconds, no signup. Manifest-driven OS auto-detect.",
    ogImage: "https://tars.meeet.world/og-install.svg",
  });
  const [os, setOs] = useState<OS>("mac");
  const [copied, setCopied] = useState<"install" | "brew" | null>(null);

  useEffect(() => {
    setOs(detectOS());
  }, []);

  const copy = (text: string, which: "install" | "brew") => {
    navigator.clipboard?.writeText(text);
    setCopied(which);
    trackClick(`install_copy_${which}`, { os });
    setTimeout(() => setCopied(null), 1600);
  };

  return (
    <div className="relative">
      {/* Ambient bg */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10"
        style={{
          background:
            "radial-gradient(60% 50% at 50% 0%, rgba(99,102,241,0.08), transparent 70%), radial-gradient(40% 40% at 30% 100%, rgba(139,92,246,0.06), transparent 70%)",
        }}
      />

      <section className="relative z-10 mx-auto max-w-[1080px] px-8 pt-20 pb-12 md:px-14 md:pt-28">
        {/* Eyebrow */}
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
          install / 1-click setup
          <StatusLozenge label="STABLE · v9.0" tone="hud" />
        </motion.div>

        {/* Title */}
        <motion.h1
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.05, ease: [0.22, 1, 0.36, 1] }}
          className="font-display font-medium leading-[0.94] tracking-[-0.02em] text-ink"
          style={{ fontSize: "clamp(2.4rem, 5.4vw, 4.6rem)" }}
        >
          Install TARS in
          <br />
          <span
            className="bg-clip-text text-transparent"
            style={{
              backgroundImage:
                "linear-gradient(95deg, #6366F1 0%, #8B5CF6 50%, #06B6D4 100%)",
            }}
          >
            sixty seconds
          </span>
          .
        </motion.h1>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.7, delay: 0.2 }}
          className="mt-6 max-w-[60ch] text-[15px] leading-[1.65] text-ink-2"
        >
          One command. Local install. No telemetry, no required cloud account.
          Add a magic-link login later if you want T2T, $MEEET earn, or council
          voting on frontier APIs.
        </motion.p>

        {/* OS picker */}
        <div className="mt-10 flex items-center gap-2">
          {[
            { key: "mac" as OS, label: "macOS", icon: Apple },
            { key: "linux" as OS, label: "Linux", icon: Terminal },
            { key: "windows" as OS, label: "Windows · WSL", icon: Cpu },
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

        {/* Primary install command */}
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.35, ease: [0.22, 1, 0.36, 1] }}
          className="relative mt-6 overflow-hidden rounded-[14px] border border-line-strong bg-bg-1"
        >
          <CornerFrame />
          <div
            aria-hidden
            className="absolute inset-x-0 top-0 h-px"
            style={{
              background:
                "linear-gradient(90deg, transparent 0%, #6366F1 30%, #8B5CF6 50%, #06B6D4 70%, transparent 100%)",
              boxShadow: "0 0 16px rgba(99,102,241,0.45)",
            }}
          />
          <div className="grid grid-cols-1 items-center gap-3 px-5 py-5 md:grid-cols-[auto_1fr_auto] md:gap-4 md:px-7 md:py-6">
            <span
              className="font-mono-tech text-[14px]"
              style={{ color: "#6366F1" }}
            >
              $
            </span>
            <code className="overflow-x-auto whitespace-nowrap font-mono text-[14px] tracking-tight text-ink md:text-[16px]">
              {INSTALL_CMD}
            </code>
            <button
              type="button"
              onClick={() => copy(INSTALL_CMD, "install")}
              className="inline-flex items-center justify-center gap-2 rounded-md border px-3.5 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink transition-colors duration-200"
              style={{
                borderColor: copied === "install" ? "var(--color-success)" : "#6366F1",
                background:
                  copied === "install"
                    ? "color-mix(in srgb, var(--color-success) 14%, transparent)"
                    : "color-mix(in srgb, #6366F1 12%, transparent)",
                color: copied === "install" ? "var(--color-success)" : undefined,
              }}
              aria-label={copied === "install" ? "Copied" : "Copy install command"}
            >
              {copied === "install" ? <Check size={13} /> : <Copy size={13} />}
              {copied === "install" ? "Copied" : "Copy"}
            </button>
          </div>

          {os === "mac" && (
            <div className="border-t border-line px-5 py-3.5 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2 md:px-7">
              Prefer brew?
              <code className="ml-3 rounded bg-bg-2 px-2 py-1 text-ink">
                {BREW_CMD}
              </code>
              <button
                type="button"
                onClick={() => copy(BREW_CMD, "brew")}
                className="ml-3 inline-flex items-center gap-1.5 text-ink transition-colors hover:text-accent"
                aria-label="Copy brew command"
              >
                {copied === "brew" ? <Check size={11} /> : <Copy size={11} />}
                {copied === "brew" ? "Copied" : "copy"}
              </button>
              <span className="ml-4 text-ink-3">
                · or download the notarized .dmg →
              </span>
              <a
                href="https://meeet.world/dl/tars-latest.dmg"
                className="ml-2 text-accent transition-colors hover:underline"
              >
                tars-latest.dmg
              </a>
            </div>
          )}

          {os === "windows" && (
            <div className="border-t border-line px-5 py-3.5 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2 md:px-7">
              Native Windows arrives in v9.1. For now, run inside WSL2 (Ubuntu)
              — the curl command above works as-is.
            </div>
          )}

          {os === "linux" && (
            <div className="border-t border-line px-5 py-3.5 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2 md:px-7">
              Tested on Ubuntu 22+, Debian 12, Fedora 40, Arch. systemd recommended.
              For non-systemd distros, the installer drops a launcher in
              <code className="mx-1.5 rounded bg-bg-2 px-1.5 py-0.5 text-ink">~/.tars/bin/tars</code>
              — wire to your service manager of choice.
            </div>
          )}
        </motion.div>

        {/* Trust ribbon */}
        <ul className="mt-8 grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            { Icon: Lock, label: "Local-first" },
            { Icon: ShieldCheck, label: "MIT licensed" },
            { Icon: Cpu, label: "Sandboxed" },
            { Icon: Zap, label: "60s setup" },
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
      </section>

      {/* Step-by-step */}
      <section className="relative z-10 mx-auto max-w-[1080px] px-8 pb-24 md:px-14 md:pb-36">
        <header className="mb-10 grid grid-cols-1 items-end gap-6 border-t border-line pt-12 md:grid-cols-[1fr_1.2fr] md:pt-16">
          <div className="flex items-baseline gap-3 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
            <span className="text-[14px] tracking-normal text-accent">10</span>
            <span>WHAT HAPPENS</span>
          </div>
          <h2 className="font-display text-[clamp(1.6rem,3.2vw,2.6rem)] font-medium leading-[1.06] tracking-[-0.01em] text-ink">
            Four steps from `bash` to your first briefing.
          </h2>
        </header>

        <ol className="grid grid-cols-1 gap-px overflow-hidden rounded-[14px] border border-line bg-line md:grid-cols-2">
          {STEPS.map((s, i) => (
            <motion.li
              key={s.num}
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
                <span style={{ color: "#6366F1" }}>{s.num}</span>
                <span className="text-ink-2">step</span>
              </div>
              <h3 className="mb-2 font-display text-[18px] font-medium leading-[1.25] text-ink">
                {s.title}
              </h3>
              <p className="text-[13.5px] leading-[1.6] text-ink-2">{s.body}</p>
            </motion.li>
          ))}
        </ol>

        {/* Bottom CTA — back to home */}
        <div className="mt-12 flex flex-col items-center gap-4 text-center">
          <p className="font-mono-tech text-[11px] uppercase tracking-[2.6px] text-ink-3">
            Want the full pitch first?
          </p>
          <a
            href="/"
            className="group inline-flex items-center gap-2 rounded-md border border-line-strong bg-bg-1 px-5 py-3 font-mono-tech text-[11px] uppercase tracking-[2.6px] text-ink transition-colors duration-200 hover:border-accent hover:text-accent"
          >
            See what TARS is
            <ArrowRight
              size={13}
              className="transition-transform duration-200 group-hover:translate-x-0.5"
            />
          </a>
        </div>
      </section>
    </div>
  );
}
