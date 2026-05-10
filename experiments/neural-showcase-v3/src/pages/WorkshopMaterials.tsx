/**
 * <WorkshopMaterials /> — Wave 85.
 *
 * Central hub at /workshop/materials for everything attendees need
 * during and after the algorithmic workshop cohort:
 *
 *   - Slide decks (PDFs)
 *   - Handouts (1-page PDFs)
 *   - Recipe library — 10 algotrade + quant playbooks (live links to
 *     the JSON sources, sourced from src/lib/recipes.ts so this stays
 *     in sync without hardcoding here)
 *   - Video walkthroughs — Loom / YouTube embed slots (URL TODOs left
 *     for the post-cohort recording pass)
 *   - Community — cohort Slack invite
 *   - Office hours — Cal.com calendar embed slot
 *
 * Asset URLs are placeholders today (decks + handouts not yet
 * uploaded; videos not yet recorded). Each anchor still works as a
 * relative link into /assets/ so the moment Cursor drops the real
 * files in `public/assets/` they go live with no FE redeploy.
 *
 * Defensive `initial: opacity: 1` on every motion node — same pattern
 * as Wave 70 / 81. Keeps the page legible if framer-motion bails on
 * variant resolution mid-render.
 */

import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  Calendar,
  Download,
  FileText,
  Film,
  FlaskRound,
  MessageCircle,
  PlayCircle,
  Slack,
} from "lucide-react";
import { useDocumentMeta } from "@/lib/meta";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import {
  RECIPE_LIBRARY,
  recipesByVertical,
  type WorkshopRecipe,
} from "@/lib/recipes";

// ── data ────────────────────────────────────────────────────────────

interface DeckLink {
  title: string;
  href: string;
  pages: string;
}

const SLIDE_DECKS: DeckLink[] = [
  {
    title: "Algorithmic Workshop — Day 1",
    href: "/assets/decks/algorithmic-edge-day1.pdf",
    pages: "PDF · 42 slides",
  },
  {
    title: "Algorithmic Workshop — Day 2",
    href: "/assets/decks/algorithmic-edge-day2.pdf",
    pages: "PDF · 38 slides",
  },
  {
    title: "Risk policy deep-dive",
    href: "/assets/decks/risk-policy-deep-dive.pdf",
    pages: "PDF · 24 slides",
  },
];

interface HandoutLink {
  title: string;
  href: string;
  body: string;
}

const HANDOUTS: HandoutLink[] = [
  {
    title: "Strategy IR cheat sheet",
    href: "/assets/handouts/strategy-ir-cheatsheet.pdf",
    body: "Every field in the Strategy IR with one-line meanings and a worked example.",
  },
  {
    title: "Risk policy template",
    href: "/assets/handouts/risk-policy-template.pdf",
    body: "Copy-paste JSON: kill switch, position cap, daily loss cap, cooldowns.",
  },
  {
    title: "Audit log fields reference",
    href: "/assets/handouts/audit-log-fields.pdf",
    body: "Every field in the JSONL audit ledger — what compliance reads, what you anchor.",
  },
];

interface VideoEmbed {
  title: string;
  duration: string;
  /** Loom share id once recorded — leave empty for the placeholder. */
  loomId?: string;
  /** YouTube id once mirrored — leave empty for the placeholder. */
  ytId?: string;
}

const VIDEOS: VideoEmbed[] = [
  { title: "Workshop kickoff", duration: "5 min" },
  { title: "Strategy IR deep-dive", duration: "12 min" },
  { title: "Backtest engine internals", duration: "8 min" },
  { title: "Risk gate + paper trade demo", duration: "15 min" },
];

// Cohort Slack invite — placeholder. Brother will swap once the
// channel is live. 30-day rotating link per Slack ToS.
const COHORT_SLACK_INVITE =
  "https://join.slack.com/t/tars-workshop/shared_invite/PLACEHOLDER";

// Office hours via Cal.com — placeholder. Real URL lands once the
// ops team books the recurring slot.
const OFFICE_HOURS_CAL_URL = "https://cal.com/tars-workshop/office-hours";

// ── helpers ────────────────────────────────────────────────────────

const VERTICAL_ACCENT: Record<WorkshopRecipe["vertical"], string> = {
  algotrade: "var(--brand-indigo)",
  quant: "var(--brand-violet)",
};

const VERTICAL_LABEL: Record<WorkshopRecipe["vertical"], string> = {
  algotrade: "ALGOTRADE",
  quant: "QUANT",
};

function formatRuntime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) {
    const m = Math.round(seconds / 60);
    return `${m} min`;
  }
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return m === 0 ? `${h}h` : `${h}h ${m}m`;
}

// ── page ───────────────────────────────────────────────────────────

export function WorkshopMaterials() {
  useDocumentMeta({
    title: "Workshop materials — decks, recipes, videos",
    description:
      "Everything algorithmic workshop attendees need: slide decks, handouts, the 10-playbook recipe library, video walkthroughs, Slack community, and office hours.",
    ogImage: "https://tars.meeet.world/og-workshop.svg",
  });

  const grouped = recipesByVertical();

  return (
    <div className="relative min-h-[calc(100vh-72px)] overflow-hidden bg-bg-0 text-ink">
      {/* Ambient backdrop — same triad as the rest of the workshop
          surface, tuned slightly cooler so the reading-heavy hub
          feels like a library rather than a sales page. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background: `
            radial-gradient(ellipse 50% 40% at 12% 6%, rgba(99,102,241,0.08) 0%, transparent 60%),
            radial-gradient(ellipse 45% 35% at 88% 92%, rgba(139,92,246,0.08) 0%, transparent 60%)
          `,
        }}
      />

      <article className="mx-auto max-w-[1200px] px-6 pb-28 pt-14 md:px-12 md:pt-20">
        {/* breadcrumbs */}
        <motion.div
          initial={{ opacity: 1, y: 0 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
          className="flex items-center gap-4"
        >
          <Breadcrumbs
            items={[
              { label: "Home", to: "/" },
              { label: "Workshop", to: "/workshop" },
              { label: "Materials" },
            ]}
          />
        </motion.div>

        {/* hero */}
        <motion.header
          initial={{ opacity: 1, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.05, ease: [0.22, 1, 0.36, 1] }}
          className="mb-14 mt-8 grid grid-cols-1 gap-4 border-b border-line pb-12"
        >
          <div className="flex items-center gap-3 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
            <span style={{ color: "var(--brand-indigo)" }}>W85</span>
            <span>Workshop · Materials hub</span>
          </div>
          <h1
            className="max-w-[28ch] font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
            style={{ fontSize: "clamp(2.2rem, 4.8vw, 3.8rem)" }}
          >
            Everything you need from the{" "}
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(95deg, var(--brand-indigo) 0%, var(--brand-violet) 50%, var(--brand-cyan) 100%)",
              }}
            >
              Algorithmic Workshop
            </span>{" "}
            workshop, in one page.
          </h1>
          <p className="mt-2 max-w-[64ch] text-[15px] leading-[1.65] text-ink-2">
            Decks, handouts, the {RECIPE_LIBRARY.length}-playbook recipe
            library, video walkthroughs, the cohort Slack channel, and
            the recurring office hours. Bookmark this page — it works
            offline (PWA cache) and updates whenever new material
            ships.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link
              to="/workshop"
              className="inline-flex items-center gap-2 rounded-sm border border-line px-3 py-1.5 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2 transition-colors hover:border-[var(--brand-indigo)] hover:text-ink"
            >
              <ArrowLeft size={11} />
              Back to workshop
            </Link>
            <Link
              to="/workshop/enterprise"
              className="inline-flex items-center gap-2 rounded-sm border border-line px-3 py-1.5 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2 transition-colors hover:border-[var(--brand-indigo)] hover:text-ink"
            >
              Workshop landing
            </Link>
            {/* Wave 88 — pre-workshop self-assessment. Sits in the hero
                CTA row so cohort attendees see it the moment they land
                here, before they binge the decks. */}
            <Link
              to="/workshop/assess"
              className="inline-flex items-center gap-2 rounded-sm border border-line px-3 py-1.5 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2 transition-colors hover:border-[var(--brand-violet)] hover:text-ink"
            >
              Pre-workshop self-assessment →
            </Link>
          </div>
        </motion.header>

        {/* ── 1. SLIDE DECKS ───────────────────────────────────── */}
        <motion.section
          initial={{ opacity: 1, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
          className="mb-16"
          aria-labelledby="materials-decks-heading"
        >
          <SectionHeading
            id="materials-decks-heading"
            eyebrow="01 · Slide decks"
            title="Slide decks"
            blurb="The talking-deck for each of the two workshop days, plus the risk-policy deep-dive used in the Day 2 lab."
          />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {SLIDE_DECKS.map((deck) => (
              <a
                key={deck.href}
                href={deck.href}
                download
                className="group flex flex-col justify-between rounded-md border border-line bg-bg-1/50 p-5 backdrop-blur-sm transition-colors hover:border-[var(--brand-indigo)]"
              >
                <div className="flex items-start gap-3">
                  <FileText
                    size={18}
                    className="mt-0.5 shrink-0"
                    style={{ color: "var(--brand-indigo)" }}
                    aria-hidden
                  />
                  <div className="flex-1">
                    <div className="font-medium leading-snug text-ink">
                      {deck.title}
                    </div>
                    <div className="mt-1 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3">
                      {deck.pages}
                    </div>
                  </div>
                </div>
                <div className="mt-4 flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-2 transition-colors group-hover:text-[var(--brand-indigo)]">
                  <Download size={11} aria-hidden />
                  Download PDF
                </div>
              </a>
            ))}
          </div>
        </motion.section>

        {/* ── 2. HANDOUTS ──────────────────────────────────────── */}
        <motion.section
          initial={{ opacity: 1, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="mb-16"
          aria-labelledby="materials-handouts-heading"
        >
          <SectionHeading
            id="materials-handouts-heading"
            eyebrow="02 · Handouts"
            title="One-pagers"
            blurb="Short reference sheets — print, pin to the wall, hand to the compliance officer who will ask in week 2."
          />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {HANDOUTS.map((h) => (
              <div
                key={h.href}
                className="flex flex-col justify-between rounded-md border border-line bg-bg-1/50 p-5 backdrop-blur-sm"
              >
                <div>
                  <div className="font-medium leading-snug text-ink">
                    {h.title}
                  </div>
                  <p className="mt-2 text-[13.5px] leading-[1.55] text-ink-2">
                    {h.body}
                  </p>
                </div>
                <div className="mt-4 flex items-center gap-2">
                  <a
                    href={h.href}
                    download
                    className="inline-flex items-center gap-2 rounded-sm border border-line px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-2 transition-colors hover:border-[var(--brand-indigo)] hover:text-ink"
                  >
                    <Download size={11} aria-hidden />
                    Download
                  </a>
                  <button
                    type="button"
                    onClick={() => {
                      if (typeof navigator !== "undefined" && navigator.clipboard) {
                        navigator.clipboard
                          .writeText(window.location.origin + h.href)
                          .catch(() => undefined);
                      }
                    }}
                    className="inline-flex items-center gap-2 rounded-sm border border-line px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-2 transition-colors hover:border-[var(--brand-violet)] hover:text-ink"
                  >
                    Copy link
                  </button>
                </div>
              </div>
            ))}
          </div>
        </motion.section>

        {/* ── 3. RECIPE LIBRARY ────────────────────────────────── */}
        <motion.section
          initial={{ opacity: 1, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.12, ease: [0.22, 1, 0.36, 1] }}
          className="mb-16"
          aria-labelledby="materials-recipes-heading"
        >
          <SectionHeading
            id="materials-recipes-heading"
            eyebrow="03 · Recipe library"
            title={`Recipe library · ${RECIPE_LIBRARY.length} playbooks`}
            blurb="Every workshop playbook ships as a JSON recipe. Click through to the source — read it, copy it, fork it. Hover any card for what it teaches."
          />
          {(["algotrade", "quant"] as const).map((vertical) => (
            <div key={vertical} className="mb-8 last:mb-0">
              <div className="mb-3 flex items-center gap-3 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
                <span
                  aria-hidden
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ background: VERTICAL_ACCENT[vertical] }}
                />
                <span>{VERTICAL_LABEL[vertical]} pack</span>
                <span className="text-ink-3">·</span>
                <span>{grouped[vertical].length} recipes</span>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                {grouped[vertical].map((r) => (
                  <a
                    key={r.id}
                    href={`https://github.com/meeet-world/tars/blob/main/${r.path}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={r.teaches}
                    className="group flex flex-col rounded-md border border-line bg-bg-1/40 p-4 backdrop-blur-sm transition-colors hover:border-[color:var(--accent)]"
                    style={
                      {
                        // CSS custom property used by the hover style
                        ["--accent" as never]: VERTICAL_ACCENT[vertical],
                      } as React.CSSProperties
                    }
                  >
                    <div className="flex items-start gap-2">
                      <FlaskRound
                        size={15}
                        className="mt-0.5 shrink-0"
                        style={{ color: VERTICAL_ACCENT[vertical] }}
                        aria-hidden
                      />
                      <div className="flex-1">
                        <div className="text-[14px] font-medium leading-snug text-ink">
                          {r.name}
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
                          <span>{formatRuntime(r.estimatedRuntime)}</span>
                          <span aria-hidden>·</span>
                          <span className="truncate">
                            {r.id.replace("_workshop.", "")}
                          </span>
                        </div>
                      </div>
                    </div>
                    <p className="mt-3 line-clamp-3 text-[12.5px] leading-[1.55] text-ink-2">
                      {r.teaches}
                    </p>
                  </a>
                ))}
              </div>
            </div>
          ))}
        </motion.section>

        {/* ── 4. VIDEO WALKTHROUGHS ────────────────────────────── */}
        <motion.section
          initial={{ opacity: 1, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.14, ease: [0.22, 1, 0.36, 1] }}
          className="mb-16"
          aria-labelledby="materials-videos-heading"
        >
          <SectionHeading
            id="materials-videos-heading"
            eyebrow="04 · Video walkthroughs"
            title="Recorded walkthroughs"
            blurb="Short async cuts you can rewatch between sessions. Loom + YouTube mirrors will land here once the post-cohort recording pass finishes."
          />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {VIDEOS.map((v) => (
              <figure
                key={v.title}
                className="overflow-hidden rounded-md border border-line bg-bg-1/40 backdrop-blur-sm"
              >
                <div className="relative aspect-video w-full bg-bg-1">
                  {/* TODO: drop the real Loom share URL into `src` once
                      the recording is published. The data-* attrs make
                      the swap a one-line change in the editor. The SW
                      runtime cache deliberately skips loom/yt origins
                      so we never cache video bytes. */}
                  <iframe
                    title={`Video: ${v.title}`}
                    src=""
                    data-loom-id={v.loomId ?? ""}
                    data-yt-id={v.ytId ?? ""}
                    loading="lazy"
                    allow="autoplay; fullscreen"
                    className="h-full w-full opacity-0"
                  />
                  {/* Visible placeholder until the iframe has a src.
                      Centred play glyph + caption keeps the layout
                      from collapsing for sighted users. */}
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-bg-1 text-ink-3">
                    <PlayCircle
                      size={32}
                      style={{ color: "var(--brand-violet)" }}
                      aria-hidden
                    />
                    <div className="font-mono-tech text-[10.5px] uppercase tracking-[2px]">
                      Recording pending
                    </div>
                  </div>
                </div>
                <figcaption className="flex items-center justify-between border-t border-line px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Film size={14} className="text-ink-3" aria-hidden />
                    <span className="text-[14px] font-medium text-ink">
                      {v.title}
                    </span>
                  </div>
                  <span className="font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3">
                    {v.duration}
                  </span>
                </figcaption>
              </figure>
            ))}
          </div>
        </motion.section>

        {/* ── 5. COMMUNITY ────────────────────────────────────── */}
        <motion.section
          initial={{ opacity: 1, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.16, ease: [0.22, 1, 0.36, 1] }}
          className="mb-16"
          aria-labelledby="materials-community-heading"
        >
          <SectionHeading
            id="materials-community-heading"
            eyebrow="05 · Community"
            title="Cohort channel"
            blurb="A private Slack workspace for cohort attendees — peer questions, ops escalations, post-workshop strategy reviews."
          />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <a
              href={COHORT_SLACK_INVITE}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-start gap-4 rounded-md border border-line bg-bg-1/50 p-5 backdrop-blur-sm transition-colors hover:border-[var(--brand-indigo)]"
            >
              <Slack
                size={22}
                className="mt-0.5 shrink-0"
                style={{ color: "var(--brand-indigo)" }}
                aria-hidden
              />
              <div className="flex-1">
                <div className="font-medium text-ink">
                  Join the TARS workshop Slack
                </div>
                <p className="mt-1 text-[13.5px] leading-[1.55] text-ink-2">
                  30-day rotating invite. Channels: #strategy-review,
                  #risk-questions, #ops-pager.
                </p>
                <div className="mt-3 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3 transition-colors group-hover:text-[var(--brand-indigo)]">
                  tars-workshop.slack.com →
                </div>
              </div>
            </a>
            <Link
              to="/workshop/enterprise"
              className="group flex items-start gap-4 rounded-md border border-line bg-bg-1/50 p-5 backdrop-blur-sm transition-colors hover:border-[var(--brand-violet)]"
            >
              <MessageCircle
                size={22}
                className="mt-0.5 shrink-0"
                style={{ color: "var(--brand-violet)" }}
                aria-hidden
              />
              <div className="flex-1">
                <div className="font-medium text-ink">Workshop landing</div>
                <p className="mt-1 text-[13.5px] leading-[1.55] text-ink-2">
                  Workshop overview, three-step demo, the five Day 1
                  algotrade playbooks.
                </p>
                <div className="mt-3 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3 transition-colors group-hover:text-[var(--brand-violet)]">
                  /workshop/enterprise →
                </div>
              </div>
            </Link>
          </div>
        </motion.section>

        {/* ── 6. OFFICE HOURS ─────────────────────────────────── */}
        <motion.section
          initial={{ opacity: 1, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.18, ease: [0.22, 1, 0.36, 1] }}
          className="mb-8"
          aria-labelledby="materials-office-hours-heading"
        >
          <SectionHeading
            id="materials-office-hours-heading"
            eyebrow="06 · Office hours"
            title="Recurring office hours"
            blurb="Weekly 30-minute open slots — bring a Strategy IR, a backtest result, or a risk question. Reserve a slot via Cal.com below."
          />
          <div className="overflow-hidden rounded-md border border-line bg-bg-1/40 backdrop-blur-sm">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <div className="flex items-center gap-2">
                <Calendar
                  size={14}
                  style={{ color: "var(--brand-cyan)" }}
                  aria-hidden
                />
                <span className="text-[14px] font-medium text-ink">
                  cal.com / tars-workshop / office-hours
                </span>
              </div>
              <a
                href={OFFICE_HOURS_CAL_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-sm border border-line px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-2 transition-colors hover:border-[var(--brand-cyan)] hover:text-ink"
              >
                Open in new tab
              </a>
            </div>
            <div className="relative aspect-[16/9] w-full bg-bg-1">
              {/* TODO: replace src with the real Cal.com embed URL
                  (`https://cal.com/tars-workshop/office-hours/embed`)
                  once the team books the recurring slot. The empty
                  src + visible placeholder keeps the layout intact
                  in the meantime. */}
              <iframe
                title="Office hours calendar"
                src=""
                data-cal-url={OFFICE_HOURS_CAL_URL}
                loading="lazy"
                className="h-full w-full opacity-0"
              />
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-bg-1 text-ink-3">
                <Calendar
                  size={28}
                  style={{ color: "var(--brand-cyan)" }}
                  aria-hidden
                />
                <div className="font-mono-tech text-[10.5px] uppercase tracking-[2px]">
                  Calendar embed pending
                </div>
                <a
                  href={OFFICE_HOURS_CAL_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 text-[12.5px] text-ink-2 underline decoration-[var(--brand-cyan)] underline-offset-4 hover:text-ink"
                >
                  Book a slot directly →
                </a>
              </div>
            </div>
          </div>
        </motion.section>
      </article>
    </div>
  );
}

// ── shared subcomponent ────────────────────────────────────────────

function SectionHeading({
  id,
  eyebrow,
  title,
  blurb,
}: {
  id: string;
  eyebrow: string;
  title: string;
  blurb: string;
}) {
  return (
    <header className="mb-6">
      <div className="mb-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
        {eyebrow}
      </div>
      <h2
        id={id}
        className="font-display text-[26px] font-medium leading-tight tracking-[-0.01em] text-ink"
      >
        {title}
      </h2>
      <p className="mt-2 max-w-[68ch] text-[14px] leading-[1.6] text-ink-2">
        {blurb}
      </p>
    </header>
  );
}

export default WorkshopMaterials;
