import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";
import { MarkdownView, extractHeadings } from "@/components/MarkdownView";
import { useDocumentMeta } from "@/lib/meta";
import { BrandHairline } from "@/components/BrandHairline";

/**
 * Shared layout for /privacy, /terms, /security, /roadmap, /changelog —
 * top bar with brand-triad accent, "← Back to home" link, eyebrow +
 * title pair, MarkdownView body.
 *
 * `showToc` opens a sticky table-of-contents sidebar on xl+, built
 * from the markdown's h2/h3 headings. /changelog turns this on so the
 * version list scans at-a-glance; /privacy keeps it off (single
 * narrative).
 */

interface Props {
  source: string;
  eyebrow: string;
  title: string;
  /** ISO date string for "Last reviewed". */
  lastReviewed?: string;
  /** Render a sticky TOC sidebar on xl+. Default: false. */
  showToc?: boolean;
}

export function LegalLayout({ source, eyebrow, title, lastReviewed, showToc }: Props) {
  // Pull a one-line description from the markdown source — first non-heading
  // paragraph or fallback to the title. Keeps og:description accurate per page.
  const description =
    deriveLeadParagraph(source) ?? `${title} for TARS · meeet.world.`;
  useDocumentMeta({ title, description });

  const headings = showToc ? extractHeadings(source) : [];

  return (
    <div className="relative min-h-[calc(100vh-72px)]">
      <BrandHairline />

      <article
        className={`mx-auto px-6 pb-28 pt-14 md:px-12 md:pt-20 ${
          showToc ? "max-w-[1180px]" : "max-w-[920px]"
        }`}
      >
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        >
          <Link
            to="/"
            className="inline-flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2 transition-colors duration-150 hover:text-ink"
          >
            <ArrowLeft size={12} strokeWidth={1.8} /> back to home
          </Link>

          <header className="mb-10 mt-8 grid grid-cols-1 gap-3 border-b border-line pb-10">
            <div className="flex items-center gap-3 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
              <span style={{ color: "var(--brand-indigo)" }}>{eyebrow}</span>
              {lastReviewed && (
                <>
                  <span aria-hidden>·</span>
                  <span className="text-ink-3">last reviewed {lastReviewed}</span>
                </>
              )}
            </div>
            <h1
              className="font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
              style={{ fontSize: "var(--text-display-lg)" }}
            >
              {title}
            </h1>
          </header>

          {showToc && headings.length > 0 ? (
            <div className="grid grid-cols-1 gap-12 xl:grid-cols-[1fr_220px]">
              <div className="min-w-0">
                <MarkdownView source={source} />
              </div>
              <Toc headings={headings} />
            </div>
          ) : (
            <MarkdownView source={source} />
          )}

          {/* Footer tail */}
          <footer className="mt-16 border-t border-line pt-8 text-center font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
            issued by meeet.world LLC · contact{" "}
            <a href="mailto:legal@meeet.world" className="text-ink-2 hover:text-ink">
              legal@meeet.world
            </a>
          </footer>
        </motion.div>
      </article>
    </div>
  );
}

/**
 * Toc — sticky right-rail table of contents derived from h2/h3
 * headings. Hidden on lg- because the page already scans well at
 * narrower widths. Click smooth-scrolls (browsers honour scroll-mt
 * we set on each heading). h3 entries indent.
 */
function Toc({
  headings,
}: {
  headings: { level: 2 | 3; text: string; id: string }[];
}) {
  return (
    <aside
      aria-label="on this page"
      className="hidden xl:block xl:sticky xl:top-24 xl:self-start"
    >
      <div className="font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
        on this page
      </div>
      <ol className="mt-3 grid gap-1.5 border-l border-line pl-3">
        {headings.map(h => (
          <li
            key={h.id}
            className={h.level === 3 ? "pl-3" : ""}
          >
            <a
              href={`#${h.id}`}
              className="block truncate font-mono-tech text-[11.5px] leading-[1.5] text-ink-2 transition-colors hover:text-ink"
              title={h.text}
            >
              {h.text}
            </a>
          </li>
        ))}
      </ol>
    </aside>
  );
}

/**
 * Pull a short summary line from the markdown source for og:description.
 * Skips the first heading, code blocks, blockquotes, lists; takes the
 * first prose line, strips Markdown punctuation, truncates to ~160 chars.
 */
function deriveLeadParagraph(md: string): string | null {
  const lines = md.split(/\r?\n/);
  let inFence = false;
  for (const raw of lines) {
    const line = raw.trim();
    if (line.startsWith("```")) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue;
    if (!line) continue;
    if (line.startsWith("#")) continue;
    if (line.startsWith(">")) continue;
    if (/^[-*+]\s/.test(line)) continue;
    if (/^\d+\.\s/.test(line)) continue;
    if (/^[\|\-:]+$/.test(line)) continue;
    // Strip inline markdown markers
    const clean = line
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/__([^_]+)__/g, "$1")
      .replace(/\*([^*]+)\*/g, "$1")
      .replace(/_([^_]+)_/g, "$1")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      .replace(/<[^>]+>/g, "")
      .trim();
    if (!clean) continue;
    return clean.length > 158 ? clean.slice(0, 155).trimEnd() + "…" : clean;
  }
  return null;
}
