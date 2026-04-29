import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { ArrowLeft, Download, Copy, Check, Mail, Twitter, Github } from "lucide-react";
import { useState } from "react";
import { CornerFrame } from "@/components/Glyphs";
import { useDocumentMeta } from "@/lib/meta";
import { BrandHairline } from "@/components/BrandHairline";
import { useT } from "@/lib/i18n";

/**
 * /press — press kit + brand guidelines for journalists, partners,
 * and people writing about TARS. Contains:
 *   - Boilerplate paragraphs (one-liner, 50-word, 100-word)
 *   - Brand palette swatches with hex codes (copyable)
 *   - Logo download links (favicon.svg + og.svg from public/)
 *   - Founder/team contact + social
 *   - Press release feed (latest from CHANGELOG)
 */

const BOILERPLATE_SHORT =
  "TARS is the local-first AI agent built for operators. Multi-LLM council, sandboxed Mac actions, signed receipts, $MEEET economy. Released under the meeet.world brand.";

const BOILERPLATE_50 =
  "TARS is a local-first AI agent platform. Operators install it on their Mac in 60 seconds, choose a role (founder, trader, researcher, marketer, engineer, operator, or custom), and let the agent handle daily briefings, file moves, code review, and inbox triage — all sandboxed, all auditable.";

const BOILERPLATE_100 =
  "TARS is the local-first AI agent platform built for operators. Where IDE assistants stay inside the editor and chat clients stay inside one window, TARS lives at the OS level — running on the operator's Mac, watching calendar and mail, executing real Mac actions through sandbox-exec, and reasoning across files, code, and conversations. Every action passes through a two-voice LLM council and a policy gate. Receipts are signed, audited, and optionally anchored to Solana. Released MIT under the meeet.world brand, with paid tiers (Pro / Business / Lifetime) for cloud sync, T2T deals, and AI Clone training.";

const PALETTE = [
  { name: "Indigo (primary)",       hex: "#6366F1", role: "Brand accent · CTA gradients · ‘Pro’ tier" },
  { name: "Violet (secondary)",     hex: "#8B5CF6", role: "Recommended states · Council voting · Lifetime tier" },
  { name: "Brand cyan (HUD)",       hex: "#06B6D4", role: "Live indicators · awareness · Free tier" },
  { name: "Violet-soft",            hex: "#A78BFA", role: "Researcher pack · soft accents" },
  { name: "Success",                hex: "#34D399", role: "LIVE / verified / linked" },
  { name: "Alert",                  hex: "#EF4444", role: "Errors · destructive confirms" },
  { name: "Ink (foreground)",       hex: "#F5F5F0", role: "Body type on OLED" },
  { name: "Bg-0 (OLED)",            hex: "#000000", role: "Background" },
];

const ASSETS = [
  { label: "Favicon (SVG)",      file: "/favicon.svg",  hint: "64×64, brand triad" },
  { label: "Open Graph (SVG)",   file: "/og.svg",       hint: "1200×630, social card" },
];

export function Press() {
  useDocumentMeta({
    title: "Press kit",
    description: "Brand assets, boilerplate paragraphs, palette, founder bios, and contact for journalists writing about TARS.",
    ogImage: "https://meeet.world/og-press.svg",
  });
  const t = useT();
  return (
    <div className="relative min-h-[calc(100vh-72px)]">
      <BrandHairline />

      <article className="mx-auto max-w-[920px] px-6 pb-28 pt-14 md:px-12 md:pt-20">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        >
          <Link
            to="/"
            className="inline-flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2 transition-colors duration-150 hover:text-ink"
          >
            <ArrowLeft size={12} strokeWidth={1.8} /> {t("common.back")}
          </Link>

          <header className="mb-12 mt-8 grid grid-cols-1 gap-3 border-b border-line pb-10">
            <div className="flex items-center gap-3 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
              <span style={{ color: "var(--brand-indigo)" }}>04</span>
              <span>{t("press.eyebrow")}</span>
              <span aria-hidden>·</span>
              <span className="text-ink-3">v9.0 · 2026 Q2</span>
            </div>
            <h1
              className="font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
              style={{ fontSize: "var(--text-display-lg)" }}
            >
              {t("press.title.lead")}{" "}
              <br className="hidden md:block" />
              {t("press.title.tail")}
            </h1>
            <p className="mt-3 max-w-[60ch] text-[14.5px] leading-[1.65] text-ink-2">
              {t("press.body")}
            </p>
          </header>

          {/* Boilerplate */}
          <section className="mb-14">
            <SectionTitle num="01" tag={t("press.section.boilerplate.tag")} title={t("press.section.boilerplate.title")} />
            <Copyable label="One-liner (28 words)"      body={BOILERPLATE_SHORT} />
            <Copyable label="Short (50 words)"          body={BOILERPLATE_50} />
            <Copyable label="Long (100 words)"          body={BOILERPLATE_100} />
          </section>

          {/* Brand palette */}
          <section className="mb-14">
            <SectionTitle num="02" tag={t("press.section.brand.tag")} title={t("press.section.brand.title")} />
            <p className="mb-5 max-w-[60ch] text-[13px] leading-[1.6] text-ink-2">
              {t("press.section.brand.body")}
            </p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {PALETTE.map(p => (
                <Swatch key={p.hex} {...p} />
              ))}
            </div>
          </section>

          {/* Assets */}
          <section className="mb-14">
            <SectionTitle num="03" tag={t("press.section.assets.tag")} title={t("press.section.assets.title")} />

            {/* One-line brand-kit downloader — pulls every asset listed
                below plus colours.txt + README.txt into ./tars-brand-kit/ */}
            <BrandKitPill />

            <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {ASSETS.map(a => (
                <li key={a.file}>
                  <a
                    href={a.file}
                    download
                    className="group relative flex items-center gap-3 rounded-[12px] border border-line bg-bg-1/60 p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong"
                  >
                    <CornerFrame />
                    <span
                      className="grid h-10 w-10 place-items-center rounded-md text-accent"
                      style={{
                        background: "color-mix(in srgb, var(--color-accent) 12%, transparent)",
                        boxShadow: "inset 0 0 0 1px rgba(99,102,241,0.32)",
                      }}
                    >
                      <Download size={16} strokeWidth={1.7} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="font-display text-[14px] tracking-[0.02em] text-ink">
                        {a.label}
                      </div>
                      <div className="font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3">
                        {a.hint}
                      </div>
                    </div>
                  </a>
                </li>
              ))}
            </ul>
            <p className="mt-4 max-w-[60ch] text-[12px] leading-[1.55] text-ink-3">
              Don't recolour or distort the marks. Don't combine with other
              logos in a way that implies endorsement. Need a bigger raster?
              Email{" "}
              <a href="mailto:press@meeet.world" className="text-ink-2 hover:text-ink">
                press@meeet.world
              </a>
              .
            </p>
          </section>

          {/* Quick facts */}
          <section className="mb-14">
            <SectionTitle num="04" tag={t("press.section.facts.tag")} title={t("press.section.facts.title")} />
            <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {QUICK_FACTS.map((f, i) => (
                <li
                  key={i}
                  className="rounded-[12px] border border-line bg-bg-1/60 p-4"
                >
                  <div className="font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
                    {f.label}
                  </div>
                  <div className="mt-1 font-display text-[16px] tracking-[0.02em] text-ink">
                    {f.value}
                  </div>
                </li>
              ))}
            </ul>
          </section>

          {/* Contact */}
          <section className="mb-12">
            <SectionTitle num="05" tag={t("press.section.contact.tag")} title={t("press.section.contact.title")} />
            <ul className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <ContactCard
                Icon={Mail}
                label="Press inquiries"
                value="press@meeet.world"
                href="mailto:press@meeet.world"
              />
              <ContactCard
                Icon={Twitter}
                label="Twitter / X"
                value="@meeet_world"
                href="https://x.com/meeet_world"
              />
              <ContactCard
                Icon={Github}
                label="GitHub"
                value="meeet-world/tars"
                href="https://github.com/meeet-world/tars"
              />
            </ul>
          </section>
        </motion.div>
      </article>
    </div>
  );
}

const QUICK_FACTS = [
  { label: "founded",   value: "2026, Delaware (meeet.world LLC)" },
  { label: "license",   value: "MIT — local agent core" },
  { label: "platforms", value: "macOS arm64+x64 · Linux · Windows (v9.1)" },
  { label: "languages", value: "Python (host) · TypeScript (cockpit) · Swift / Kotlin (mobile, L10)" },
  { label: "pricing",   value: "Free / Pro $19 / Business $79 / Lifetime $299" },
  { label: "models",    value: "8 LLMs supported (Anthropic, OpenAI, Google, xAI, Mistral, DeepSeek, Llama, Ollama)" },
];

function SectionTitle({ num, tag, title }: { num: string; tag: string; title: string }) {
  return (
    <div className="mb-6 flex items-baseline gap-3">
      <span className="font-mono-tech text-[11px] uppercase tracking-[3px]" style={{ color: "var(--brand-indigo)" }}>
        {num}
      </span>
      <span className="font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
        {tag}
      </span>
      <h2 className="ml-2 font-display text-[20px] tracking-[-0.005em] text-ink">{title}</h2>
    </div>
  );
}

function Copyable({ label, body }: { label: string; body: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard?.writeText(body);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };
  return (
    <div className="mb-3 rounded-[12px] border border-line bg-bg-1/60 p-4">
      <div className="mb-2 flex items-center justify-between font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
        <span>{label}</span>
        <button
          type="button"
          onClick={copy}
          className="inline-flex items-center gap-1.5 transition-colors hover:text-ink"
          aria-label={`copy ${label}`}
        >
          {copied ? (
            <>
              <Check size={11} strokeWidth={2.2} className="text-success" /> copied
            </>
          ) : (
            <>
              <Copy size={11} strokeWidth={1.8} /> copy
            </>
          )}
        </button>
      </div>
      <p className="text-[13.5px] leading-[1.65] text-ink-2">{body}</p>
    </div>
  );
}

function Swatch({ name, hex, role }: { name: string; hex: string; role: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard?.writeText(hex);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button
      type="button"
      onClick={copy}
      title={`copy ${hex}`}
      className="group flex flex-col items-stretch overflow-hidden rounded-[10px] border border-line bg-bg-1/60 text-left transition-colors hover:border-line-strong"
    >
      <span className="block h-16" style={{ background: hex }} aria-hidden />
      <span className="flex flex-col gap-1 p-3">
        <span className="flex items-center justify-between">
          <span className="font-display text-[13px] tracking-[0.02em] text-ink">{name}</span>
          <span className="font-mono-tech text-[10px] tracking-[2px] text-ink-3">
            {copied ? "copied" : hex}
          </span>
        </span>
        <span className="text-[11px] leading-[1.45] text-ink-3">{role}</span>
      </span>
    </button>
  );
}

function ContactCard({
  Icon,
  label,
  value,
  href,
}: {
  Icon: typeof Mail;
  label: string;
  value: string;
  href: string;
}) {
  const ext = /^https?:/.test(href);
  return (
    <li>
      <a
        href={href}
        {...(ext ? { target: "_blank", rel: "noopener" } : {})}
        className="group flex items-center gap-3 rounded-[12px] border border-line bg-bg-1/60 p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong"
      >
        <span
          className="grid h-10 w-10 place-items-center rounded-md text-accent"
          style={{
            background: "color-mix(in srgb, var(--color-accent) 12%, transparent)",
            boxShadow: "inset 0 0 0 1px rgba(99,102,241,0.32)",
          }}
        >
          <Icon size={16} strokeWidth={1.7} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
            {label}
          </div>
          <div className="mt-0.5 truncate font-display text-[14px] tracking-[0.02em] text-ink">
            {value}
          </div>
        </div>
      </a>
    </li>
  );
}

/**
 * BrandKitPill — one-line `curl | bash` that pulls the canonical
 * brand kit into ./tars-brand-kit/. Pre-press will appreciate it; the
 * raw asset grid below stays for browser-only journalists.
 */
function BrandKitPill() {
  const cmd = "curl -fsSL https://meeet.world/press/brand-kit.sh | bash";
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard?.writeText(cmd);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className="mb-5 grid items-center gap-3 rounded-[12px] border border-line bg-bg-1/60 p-4 sm:grid-cols-[1fr_auto] sm:p-5">
      <div className="min-w-0">
        <div className="mb-1 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
          one-line brand kit · 11 files · README + colours
        </div>
        <code className="block truncate font-mono-tech text-[12px] text-ink">
          {cmd}
        </code>
      </div>
      <button
        type="button"
        onClick={copy}
        className="inline-flex shrink-0 items-center justify-center gap-2 rounded-md px-4 py-2.5 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-white transition-all duration-200 hover:-translate-y-0.5"
        style={{
          background: "var(--brand-cta-gradient)",
          boxShadow: "var(--shadow-brand-cta)",
        }}
      >
        {copied ? (
          <>
            <Check size={12} strokeWidth={2.2} aria-hidden /> copied
          </>
        ) : (
          <>
            <Copy size={12} strokeWidth={1.8} aria-hidden /> copy
          </>
        )}
      </button>
    </div>
  );
}
