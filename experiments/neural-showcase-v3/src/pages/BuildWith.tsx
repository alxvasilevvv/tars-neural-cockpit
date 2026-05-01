import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { ArrowLeft, Copy, Check, ExternalLink } from "lucide-react";
import { useMemo, useState } from "react";
import { useDocumentMeta } from "@/lib/meta";
import { trackClick } from "@/lib/analytics";
import { BrandHairline } from "@/components/BrandHairline";
import { useT } from "@/lib/i18n";

/**
 * /build-with — viral hook page. Operators who shipped with TARS
 * grab an embed badge from here and stick it in their README, blog,
 * project site, etc. Surfaces the share-link / "Built with TARS"
 * mechanic from task #69 frontend-side.
 *
 * Two sizes (compact 80px, full 120px) × two themes (dark/light) =
 * 4 variants. SVG inline, fully self-contained, copy-paste embed
 * code with attribution link to https://meeet.world.
 */

type Size = "compact" | "full";
type Theme = "dark" | "light";

const PALETTE = {
  dark: {
    bg: "#0B0B10",
    ink: "#F5F5F0",
    inkDim: "#7A786F",
    accentA: "#6366F1",
    accentB: "#8B5CF6",
    accentC: "#06B6D4",
    border: "rgba(99,102,241,0.45)",
  },
  light: {
    bg: "#FFFFFF",
    ink: "#0B0B10",
    inkDim: "#6E6C63",
    accentA: "#6366F1",
    accentB: "#8B5CF6",
    accentC: "#06B6D4",
    border: "rgba(99,102,241,0.55)",
  },
};

export function BuildWith() {
  useDocumentMeta({
    title: "Built with TARS",
    description:
      "Grab the embed badge for your project — 4 variants, paste-ready HTML or Markdown, attribution back to meeet.world.",
    ogImage: "https://tars.meeet.world/og-build-with.svg",
  });
  const [size, setSize] = useState<Size>("full");
  const [theme, setTheme] = useState<Theme>("dark");
  const [copied, setCopied] = useState<"html" | "md" | null>(null);
  const [linkOverride, setLinkOverride] = useState<string>("");
  const t = useT();

  const linkHref = linkOverride.trim() || "https://meeet.world";
  const svg = useMemo(() => buildBadgeSvg({ size, theme }), [size, theme]);
  const html = useMemo(
    () => buildHtml({ svg, href: linkHref }),
    [svg, linkHref],
  );
  const md = useMemo(
    () => buildMarkdown({ href: linkHref, size, theme }),
    [linkHref, size, theme],
  );

  const copy = (kind: "html" | "md", payload: string) => {
    navigator.clipboard?.writeText(payload);
    setCopied(kind);
    trackClick(`badge_copy_${kind}`, { size, theme });
    setTimeout(() => setCopied(null), 1600);
  };

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

          <header className="mb-10 mt-8 grid grid-cols-1 gap-3 border-b border-line pb-10">
            <div className="flex items-center gap-3 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
              <span style={{ color: "var(--brand-indigo)" }}>09</span>
              <span>{t("buildWith.eyebrow")}</span>
            </div>
            <h1
              className="font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
              style={{ fontSize: "var(--text-display-md)" }}
            >
              {t("buildWith.title.lead")}{" "}
              <span
                className="bg-clip-text text-transparent"
                style={{
                  backgroundImage:
                    "linear-gradient(95deg, var(--brand-indigo) 0%, var(--brand-violet) 50%, var(--brand-cyan) 100%)",
                }}
              >
                {t("buildWith.title.tail")}
              </span>
              .
            </h1>
            <p className="mt-3 max-w-[60ch] text-[14.5px] leading-[1.65] text-ink-2">
              {t("buildWith.body")}
            </p>
          </header>

          {/* Variant picker */}
          <section className="mb-8">
            <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
              <Variant
                label={t("buildWith.size.label")}
                options={[
                  { id: "full",    label: t("buildWith.size.full") },
                  { id: "compact", label: t("buildWith.size.compact") },
                ]}
                value={size}
                onChange={v => setSize(v as Size)}
              />
              <Variant
                label={t("buildWith.theme.label")}
                options={[
                  { id: "dark",  label: t("buildWith.theme.dark") },
                  { id: "light", label: t("buildWith.theme.light") },
                ]}
                value={theme}
                onChange={v => setTheme(v as Theme)}
              />
            </div>

            <label
              htmlFor="bw-link-override"
              className="mb-1.5 block font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3"
            >
              {t("buildWith.link.label")}
            </label>
            <input
              id="bw-link-override"
              type="url"
              inputMode="url"
              autoComplete="url"
              value={linkOverride}
              onChange={e => setLinkOverride(e.target.value)}
              placeholder="https://your-project.example/"
              aria-describedby="bw-link-override-help"
              className="w-full rounded-md border border-line bg-bg-2/50 px-3 py-2.5 font-mono text-[12.5px] text-ink placeholder:text-ink-3 focus:border-accent"
            />
            <p
              id="bw-link-override-help"
              className="sr-only"
            >
              The badge will link to this URL when copied. Leaving it empty
              uses meeet.world.
            </p>
          </section>

          {/* Preview */}
          <section className="mb-10">
            <div className="mb-3 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
              {t("buildWith.preview")}
            </div>
            <div
              className="rounded-[12px] border border-line p-8 grid place-items-center"
              style={{ background: theme === "dark" ? "var(--color-bg-1)" : "#F5F5F0" }}
            >
              <span
                aria-label="Built with TARS badge preview"
                dangerouslySetInnerHTML={{ __html: svg }}
              />
            </div>
          </section>

          {/* Embed code blocks */}
          <section className="mb-8 grid gap-4">
            <CodeBlock
              label="HTML"
              body={html}
              copied={copied === "html"}
              onCopy={() => copy("html", html)}
            />
            <CodeBlock
              label="Markdown"
              body={md}
              copied={copied === "md"}
              onCopy={() => copy("md", md)}
            />
          </section>

          {/* Usage */}
          <section className="mb-12 rounded-[12px] border border-line bg-bg-1/60 p-6">
            <h2 className="mb-3 font-display text-[18px] tracking-[-0.005em] text-ink">
              {t("buildWith.usage.title")}
            </h2>
            <ul className="grid gap-2 text-[13.5px] leading-[1.6] text-ink-2">
              <li className="grid grid-cols-[14px_1fr] items-baseline gap-3">
                <span className="text-accent">·</span>
                <span>
                  Free for any project, MIT or proprietary. No attribution
                  required, but appreciated.
                </span>
              </li>
              <li className="grid grid-cols-[14px_1fr] items-baseline gap-3">
                <span className="text-accent">·</span>
                <span>
                  SVG is self-contained — no external font, no external image
                  request, no tracking pixel.
                </span>
              </li>
              <li className="grid grid-cols-[14px_1fr] items-baseline gap-3">
                <span className="text-accent">·</span>
                <span>
                  Don't recolour or distort the marks. Keep the brand triad
                  and proportions intact.
                </span>
              </li>
              <li className="grid grid-cols-[14px_1fr] items-baseline gap-3">
                <span className="text-accent">·</span>
                <span>
                  Need a higher-res raster, custom palette, or partnership
                  badge? Email{" "}
                  <a href="mailto:hello@meeet.world" className="text-ink underline-offset-2 hover:underline">
                    hello@meeet.world
                  </a>
                  .
                </span>
              </li>
            </ul>
          </section>

          {/* Examples in the wild */}
          <section className="mb-6">
            <h2 className="mb-3 font-display text-[18px] tracking-[-0.005em] text-ink">
              {t("buildWith.examples.title")}
            </h2>
            <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {[
                { label: "GitHub README — top of file",   hint: "after the project title, before description" },
                { label: "Personal site — footer",         hint: "alongside other tech credits" },
                { label: "Slide decks — last slide",       hint: '"Tools used" credits row' },
                { label: "Blog post — about-the-author",   hint: "next to your bio link" },
              ].map(e => (
                <li
                  key={e.label}
                  className="rounded-[10px] border border-line bg-bg-1/40 px-4 py-3"
                >
                  <div className="font-display text-[13.5px] tracking-[0.01em] text-ink">
                    {e.label}
                  </div>
                  <div className="mt-0.5 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3">
                    {e.hint}
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <footer className="mt-12 border-t border-line pt-6 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
            {t("buildWith.footer")}{" "}
            <a
              href="https://github.com/topics/built-with-tars"
              target="_blank"
              rel="noopener"
              className="inline-flex items-center gap-1 text-ink-2 hover:text-ink"
            >
              built-with-tars <ExternalLink size={10} strokeWidth={1.7} />
            </a>{" "}
            {t("buildWith.footer.tail")}
          </footer>
        </motion.div>
      </article>
    </div>
  );
}

/* ─── Helpers ──────────────────────────────────────────────────────── */

function Variant({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { id: string; label: string }[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div>
      <div className="mb-1.5 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
        {label}
      </div>
      <div className="grid grid-cols-2 gap-2">
        {options.map(o => {
          const active = o.id === value;
          return (
            <button
              key={o.id}
              type="button"
              onClick={() => onChange(o.id)}
              className="rounded-md border px-3 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] transition-colors duration-200"
              style={{
                borderColor: active ? "#6366F1" : "var(--color-line-strong)",
                background: active
                  ? "color-mix(in srgb, #6366F1 14%, transparent)"
                  : "var(--color-bg-1)",
                color: active ? "var(--color-ink)" : "var(--color-ink-2)",
              }}
            >
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function CodeBlock({
  label,
  body,
  copied,
  onCopy,
}: {
  label: string;
  body: string;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <div className="rounded-[12px] border border-line bg-bg-1/60">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
        <span>{label}</span>
        <button
          type="button"
          onClick={onCopy}
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
      <pre className="overflow-x-auto p-4 font-mono text-[12px] leading-[1.55] text-ink-2">
        <code>{body}</code>
      </pre>
    </div>
  );
}

/* ─── Badge generation ─────────────────────────────────────────────── */

function buildBadgeSvg({ size, theme }: { size: Size; theme: Theme }): string {
  const p = PALETTE[theme];
  const w = size === "full" ? 220 : 160;
  const h = size === "full" ? 60 : 44;
  const r = 8;
  const padX = size === "full" ? 14 : 12;
  const titleSize = size === "full" ? 14 : 11;
  const subSize = size === "full" ? 9 : 8;
  const monoSize = size === "full" ? 11 : 9;

  const monolithSize = size === "full" ? 28 : 22;
  const monolithX = padX;
  const monolithY = (h - monolithSize) / 2;

  const textX = monolithX + monolithSize + (size === "full" ? 12 : 9);

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" aria-label="Built with TARS · meeet.world">
  <defs>
    <linearGradient id="brandSweep" x1="0" y1="0" x2="${w}" y2="0" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="${p.accentA}"/>
      <stop offset="50%" stop-color="${p.accentB}"/>
      <stop offset="100%" stop-color="${p.accentC}"/>
    </linearGradient>
    <linearGradient id="monolith" x1="0" y1="0" x2="0" y2="${monolithSize}" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="${p.accentA}"/>
      <stop offset="100%" stop-color="${p.accentC}"/>
    </linearGradient>
  </defs>
  <rect x="0.5" y="0.5" width="${w - 1}" height="${h - 1}" rx="${r}" fill="${p.bg}" stroke="${p.border}" stroke-width="1"/>
  <rect x="${r}" y="0" width="${w - 2 * r}" height="2" fill="url(#brandSweep)" opacity="0.85"/>
  <!-- Monolith icosahedron silhouette -->
  <g transform="translate(${monolithX} ${monolithY})">
    <polygon points="${monolithSize / 2},0 ${monolithSize * 0.95},${monolithSize * 0.5} ${monolithSize / 2},${monolithSize} ${monolithSize * 0.05},${monolithSize * 0.5}" fill="url(#monolith)" opacity="0.85"/>
    <polygon points="${monolithSize / 2},0 ${monolithSize * 0.95},${monolithSize * 0.5} ${monolithSize / 2},${monolithSize * 0.5}" fill="${p.accentB}" opacity="0.55"/>
    <polygon points="${monolithSize / 2},0 ${monolithSize * 0.05},${monolithSize * 0.5} ${monolithSize / 2},${monolithSize * 0.5}" fill="${p.accentA}" opacity="0.6"/>
  </g>
  <!-- Text block -->
  <text x="${textX}" y="${size === "full" ? 22 : 16}" font-family="'Share Tech Mono','Fira Code',ui-monospace,monospace" font-size="${monoSize}" letter-spacing="2" fill="${p.inkDim}">BUILT WITH</text>
  <text x="${textX}" y="${size === "full" ? 41 : 30}" font-family="'Share Tech Mono','Fira Code',ui-monospace,monospace" font-size="${titleSize}" font-weight="600" letter-spacing="0" fill="${p.ink}">TARS</text>
  ${size === "full" ? `<text x="${textX}" y="${52}" font-family="'Share Tech Mono','Fira Code',ui-monospace,monospace" font-size="${subSize}" letter-spacing="2" fill="${p.inkDim}">meeet.world</text>` : ""}
</svg>`;
}

function buildHtml({ svg, href }: { svg: string; href: string }): string {
  // Strip trailing newlines and inline so it pastes as one logical block
  return `<a href="${href}" target="_blank" rel="noopener" aria-label="Built with TARS">
  ${svg.replace(/\n\s+/g, " ").trim()}
</a>`;
}

function buildMarkdown({
  href,
  size,
  theme,
}: {
  href: string;
  size: Size;
  theme: Theme;
}): string {
  // Markdown can't embed inline SVG portably, so we point at the hosted
  // static SVG (4 variants ship in `public/badge/`). Brother will upgrade
  // these to a generated/cached endpoint when tars.meeet.world stands up.
  const slug =
    size === "compact"
      ? theme === "light"
        ? "built-with-tars-compact-light"
        : "built-with-tars-compact"
      : theme === "light"
        ? "built-with-tars-light"
        : "built-with-tars";
  const badgeUrl = `https://meeet.world/badge/${slug}.svg`;
  return `[![Built with TARS](${badgeUrl})](${href})`;
}
