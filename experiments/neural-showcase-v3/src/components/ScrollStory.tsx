import { motion, useScroll, useTransform } from "framer-motion";
import type { MotionValue } from "framer-motion";
import { useRef } from "react";
import {
  CalendarDays,
  Activity,
  Brain,
  ShieldCheck,
  Mail,
  GitPullRequest,
  Slack,
  Cpu,
  Lock,
  Eye,
  Zap,
} from "lucide-react";
import type { TKey } from "@/lib/i18n";
import { useT } from "@/lib/i18n";

const SCROLL_IDS = ["s1", "s2", "s3", "s4"] as const;
const SCROLL_VISUALS: Segment["visual"][] = [
  "briefing",
  "watch",
  "memory",
  "vault",
];
const SCROLL_ACCENTS = [
  "var(--brand-indigo)",
  "var(--brand-violet)",
  "var(--brand-cyan)",
  "var(--brand-orchid)",
] as const;

/**
 * <ScrollStory /> — scroll-pinned storytelling section. Pattern:
 * Linear / Apple-style scroll story. Four features unfold as the operator
 * scrolls through a 400vh tall container; the left column stays
 * sticky and crossfades headline + body, while the right column
 * cycles through a per-segment visual panel.
 *
 * Layout:
 *   Desktop  — sticky two-column. Left = headline, right = panel.
 *              `top` clears the sticky site nav (~py-5 + blur bar).
 *   Mobile   — stacks: each segment gets its own card, 100vh tall,
 *              auto-revealed on viewport entry (no sticky behaviour
 *              since iOS Safari position:sticky inside scroll-snap
 *              fights pinch-zoom).
 *
 * Segments load copy via ``useT()`` — add a fifth by extending ``SCROLL_IDS``
 * and tuning the wrapper height calc. Reduced-motion users get a single
 * static snapshot per segment (animations skipped).
 */

interface Segment {
  num: string;
  eyebrow: string;
  title: string;
  body: string;
  /** which visual to render in the right column */
  visual: "briefing" | "watch" | "memory" | "vault";
  /** accent colour for the segment's eyebrow + glyph (brand triad) */
  accent: string;
}

function buildSegments(
  tt: (key: TKey, vars?: Record<string, string | number>) => string,
): Segment[] {
  return SCROLL_IDS.map((id, i) => ({
    num: `0${i + 1}`,
    eyebrow: tt(`scrollStory.${id}.eyebrow` as TKey),
    title: tt(`scrollStory.${id}.title` as TKey),
    body: tt(`scrollStory.${id}.body` as TKey),
    visual: SCROLL_VISUALS[i]!,
    accent: SCROLL_ACCENTS[i]!,
  }));
}

export function ScrollStory() {
  const tr = useT();
  const segments = buildSegments(tr);

  return (
    <section
      aria-label={tr("scrollStory.aria")}
      className="relative z-20 mx-auto max-w-[1280px] px-6 py-20 md:px-12 md:py-32"
    >
      {/* Section header */}
      <header className="mb-12 grid gap-6 md:mb-20 md:grid-cols-[1fr_auto] md:items-end">
        <div>
          <div className="mb-4 inline-flex items-center gap-2.5 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
            <span style={{ color: "var(--brand-indigo)" }}>
              {tr("scrollStory.head.num")}
            </span>
            <span aria-hidden>·</span>
            <span>{tr("scrollStory.head.eyebrow")}</span>
          </div>
          <h2
            className="font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
            style={{ fontSize: "var(--text-display-md)" }}
          >
            {tr("scrollStory.head.title.before")}
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(95deg, var(--brand-indigo) 0%, var(--brand-violet) 50%, var(--brand-cyan) 100%)",
              }}
            >
              {tr("scrollStory.head.title.grad")}
            </span>
            .
          </h2>
        </div>
        <p className="max-w-[36ch] font-mono-tech text-[12.5px] leading-[1.65] text-ink-2 md:text-right">
          {tr("scrollStory.head.subtitle")}
        </p>
      </header>

      {/* Desktop: pinned scroll-driven storytelling. md+ only. */}
      <div className="hidden md:block">
        <PinnedTrack segments={segments} />
      </div>

      {/* Mobile: stack of full-bleed segment cards. */}
      <div className="space-y-12 md:hidden">
        {segments.map((s, i) => (
          <MobileSegment
            key={s.num}
            segment={s}
            index={i}
            segmentCount={segments.length}
          />
        ))}
      </div>
    </section>
  );
}

/* ─── Desktop pinned track ──────────────────────────────────────── */

function PinnedTrack({ segments }: { segments: Segment[] }) {
  const trackRef = useRef<HTMLDivElement | null>(null);
  // Track height = N segments × 100vh (so each occupies one viewport
  // of scroll). Inside, the visual column is sticky.
  const SEG_COUNT = segments.length;

  // Single source of truth for scroll progress. Lifted up here so:
  //   1. ref is hydrated synchronously (same component as ref decl)
  //   2. children share one `useScroll` listener instead of N
  //   3. framer-motion stops warning about higher-up refs
  const { scrollYProgress } = useScroll({
    target: trackRef,
    offset: ["start start", "end end"],
    layoutEffect: false,
  });

  return (
    <div
      ref={trackRef}
      className="relative"
      style={{ height: `${SEG_COUNT * 100}vh` }}
    >
      <div className="sticky top-24 z-10 grid grid-cols-[1fr_1.1fr] gap-12 md:top-28 lg:gap-20">
        {/* Left — copy column with progress rail */}
        <div className="relative flex h-[80vh] flex-col">
          <ProgressRail
            scrollYProgress={scrollYProgress}
            segmentCount={segments.length}
          />
          <div className="flex-1 pl-8">
            {segments.map((s, i) => (
              <CopyPane
                key={s.num}
                segment={s}
                index={i}
                segmentCount={segments.length}
                scrollYProgress={scrollYProgress}
              />
            ))}
          </div>
        </div>

        {/* Right — visual column */}
        <div className="relative flex h-[80vh] items-center">
          <div className="relative h-full w-full">
            {segments.map((s, i) => (
              <VisualPane
                key={s.num}
                segment={s}
                index={i}
                segmentCount={segments.length}
                scrollYProgress={scrollYProgress}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ProgressRail({
  scrollYProgress,
  segmentCount,
}: {
  scrollYProgress: MotionValue<number>;
  segmentCount: number;
}) {
  const fillHeight = useTransform(scrollYProgress, [0, 1], ["0%", "100%"]);
  const denom = Math.max(1, segmentCount - 1);

  return (
    <div className="absolute left-0 top-0 h-full w-px bg-line">
      <motion.div
        aria-hidden
        className="absolute left-0 top-0 w-px"
        style={{
          height: fillHeight,
          background:
            "linear-gradient(180deg, var(--brand-indigo), var(--brand-violet), var(--brand-cyan))",
        }}
      />
      {/* Segment ticks */}
      {Array.from({ length: segmentCount }, (_, i) => (
        <div
          key={i}
          aria-hidden
          className="absolute left-[-3px] h-1.5 w-1.5 rounded-full bg-bg-1"
          style={{
            top: `${(i / denom) * 100}%`,
            border: "1px solid var(--color-line-strong)",
          }}
        />
      ))}
    </div>
  );
}

function CopyPane({
  segment,
  index,
  segmentCount,
  scrollYProgress,
}: {
  segment: Segment;
  index: number;
  segmentCount: number;
  scrollYProgress: MotionValue<number>;
}) {
  // Each segment owns a 1/N slice of the scroll.
  const N = segmentCount;
  const start = index / N;
  const end = (index + 1) / N;
  const peak = (start + end) / 2;
  // Edge-segment fix: the first segment must be fully visible from the
  // moment the section pins (scroll=0), the last must stay visible until
  // the section unpins (scroll=1). Without this, both ends fade through
  // 0 and the operator sees a huge empty container. (Wave 59-1.)
  const isFirst = index === 0;
  const isLast = index === segmentCount - 1;
  const startScroll = isFirst ? 0 : Math.max(0, start - 0.04);
  const endScroll = isLast ? 1 : Math.min(1, end + 0.04);
  const opacity = useTransform(
    scrollYProgress,
    [startScroll, peak, endScroll],
    [isFirst ? 1 : 0, 1, isLast ? 1 : 0],
  );
  const y = useTransform(
    scrollYProgress,
    [startScroll, peak, endScroll],
    [isFirst ? 0 : 16, 0, isLast ? 0 : -16],
  );

  return (
    <motion.div
      style={{ opacity, y }}
      className="absolute inset-0 flex flex-col justify-center pl-2 pr-4"
      aria-hidden={false}
    >
      <div
        className="mb-4 inline-flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[3px]"
        style={{ color: segment.accent }}
      >
        <span className="tabular-nums">{segment.num}</span>
        <span aria-hidden className="opacity-50">·</span>
        <span>{segment.eyebrow}</span>
      </div>
      <h3
        className="mb-5 max-w-[20ch] whitespace-pre-line font-display font-medium leading-[1.04] tracking-[-0.018em] text-ink"
        style={{ fontSize: "clamp(1.7rem, 2.4vw, 2.4rem)" }}
      >
        {segment.title}
      </h3>
      <p className="max-w-[44ch] text-[15px] leading-[1.65] text-ink-2">
        {segment.body}
      </p>
    </motion.div>
  );
}

function VisualPane({
  segment,
  index,
  segmentCount,
  scrollYProgress,
}: {
  segment: Segment;
  index: number;
  segmentCount: number;
  scrollYProgress: MotionValue<number>;
}) {
  const N = segmentCount;
  const start = index / N;
  const end = (index + 1) / N;
  const peak = (start + end) / 2;
  // Same edge-segment fix as CopyPane (Wave 59-1).
  const isFirst = index === 0;
  const isLast = index === segmentCount - 1;
  const startScroll = isFirst ? 0 : Math.max(0, start - 0.05);
  const endScroll = isLast ? 1 : Math.min(1, end + 0.05);
  const opacity = useTransform(
    scrollYProgress,
    [startScroll, peak, endScroll],
    [isFirst ? 1 : 0, 1, isLast ? 1 : 0],
  );
  const scale = useTransform(
    scrollYProgress,
    [startScroll, peak, endScroll],
    [isFirst ? 1 : 0.96, 1, isLast ? 1 : 1.02],
  );

  return (
    <motion.div
      style={{ opacity, scale }}
      className="absolute inset-0 flex items-center justify-center"
    >
      <Visual kind={segment.visual} accent={segment.accent} />
    </motion.div>
  );
}

/* ─── Mobile fallback ───────────────────────────────────────────── */

function MobileSegment({
  segment,
  index,
  segmentCount,
}: {
  segment: Segment;
  index: number;
  segmentCount: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-15% 0px" }}
      transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
      className="grid gap-6"
    >
      <div
        className="inline-flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[3px]"
        style={{ color: segment.accent }}
      >
        <span className="tabular-nums">{segment.num}</span>
        <span aria-hidden className="opacity-50">·</span>
        <span>{segment.eyebrow}</span>
      </div>
      <h3
        className="max-w-[22ch] whitespace-pre-line font-display font-medium leading-[1.04] tracking-[-0.018em] text-ink"
        style={{ fontSize: "clamp(1.6rem, 6vw, 2.2rem)" }}
      >
        {segment.title}
      </h3>
      <p className="max-w-[44ch] text-[14.5px] leading-[1.65] text-ink-2">
        {segment.body}
      </p>
      <div className="aspect-[4/3] w-full max-w-[520px] overflow-hidden rounded-[14px] border border-line bg-bg-1/60 p-5">
        <Visual kind={segment.visual} accent={segment.accent} />
      </div>
      {/* divider unless last */}
      {index < segmentCount - 1 && (
        <div className="mt-2 h-px w-16 bg-line-strong" aria-hidden />
      )}
    </motion.div>
  );
}

/* ─── Per-segment visuals — pure CSS / inline SVG, no deps ─────── */

function Visual({
  kind,
  accent,
}: {
  kind: Segment["visual"];
  accent: string;
}) {
  switch (kind) {
    case "briefing":
      return <BriefingVisual accent={accent} />;
    case "watch":
      return <WatchVisual accent={accent} />;
    case "memory":
      return <MemoryVisual accent={accent} />;
    case "vault":
      return <VaultVisual accent={accent} />;
  }
}

const cardCls =
  "h-full w-full rounded-[14px] border border-line bg-bg-1/60 p-5 backdrop-blur-md";

function BriefingVisual({ accent }: { accent: string }) {
  const items = [
    { Icon: CalendarDays, when: "10:00", what: "Sync · Phase 9 review", muted: false },
    { Icon: Mail,         when: "08:14", what: "3 replies need yours",   muted: false },
    { Icon: GitPullRequest, when: "07:42", what: "PR #142 awaiting review", muted: false },
    { Icon: Slack,        when: "06:55", what: "@you in #ops · 2 messages", muted: true },
  ];
  return (
    <div className={cardCls}>
      <div className="mb-4 flex items-center justify-between">
        <span
          className="inline-flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.4px]"
          style={{ color: accent }}
        >
          <CalendarDays size={12} strokeWidth={1.7} aria-hidden />
          today's brief
        </span>
        <span className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
          08:42 · ready
        </span>
      </div>
      <ul className="space-y-2.5">
        {items.map((it, i) => (
          <motion.li
            key={i}
            initial={{ opacity: 0, x: -6 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.06 * i, duration: 0.4 }}
            className={`flex items-center gap-3 rounded-md border border-line/60 bg-bg-2/40 px-3 py-2.5 ${it.muted ? "opacity-65" : ""}`}
          >
            <span
              className="grid h-7 w-7 shrink-0 place-items-center rounded-md"
              style={{
                background: "color-mix(in srgb, var(--color-bg-2) 60%, transparent)",
                color: accent,
              }}
              aria-hidden
            >
              <it.Icon size={13} strokeWidth={1.7} />
            </span>
            <span className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3 tabular-nums">
              {it.when}
            </span>
            <span className="flex-1 truncate font-mono-tech text-[12px] text-ink">
              {it.what}
            </span>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}

function WatchVisual({ accent }: { accent: string }) {
  const lines = [
    { t: "08:42:01", k: "shell.run",  v: "ls ~/Downloads | wc -l", ok: true },
    { t: "08:42:01", k: "result",     v: "47 files", ok: true },
    { t: "08:42:02", k: "shell.run",  v: "mkdir -p ~/Downloads/{PDF,Images,Code}", ok: true },
    { t: "08:42:02", k: "files.move", v: "12 → ~/Downloads/PDF/", ok: true },
    { t: "08:42:03", k: "files.move", v: "18 → ~/Downloads/Images/", ok: true },
    { t: "08:42:04", k: "receipt",    v: "rcp_a91f0c2 anchored · solana", ok: true },
  ];
  return (
    <div className={cardCls}>
      <div className="mb-4 flex items-center justify-between">
        <span
          className="inline-flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.4px]"
          style={{ color: accent }}
        >
          <Activity size={12} strokeWidth={1.7} aria-hidden />
          watch me work · live
        </span>
        <span
          className="inline-flex items-center gap-1.5 font-mono-tech text-[10px] uppercase tracking-[2px]"
          style={{ color: "var(--color-success)" }}
        >
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{
              background: "var(--color-success)",
              boxShadow: "0 0 8px rgba(52,211,153,0.6)",
              animation: "pulseDot 1.6s ease-in-out infinite",
            }}
          />
          streaming
        </span>
      </div>
      <ul className="space-y-1.5 font-mono text-[11.5px] leading-[1.6]">
        {lines.map((l, i) => (
          <motion.li
            key={i}
            initial={{ opacity: 0, y: 4 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.08 * i, duration: 0.35 }}
            className="grid grid-cols-[80px_120px_1fr] items-baseline gap-3"
          >
            <span className="text-ink-3 tabular-nums">{l.t}</span>
            <span style={{ color: accent }}>{l.k}</span>
            <span className="truncate text-ink/95">{l.v}</span>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}

function MemoryVisual({ accent }: { accent: string }) {
  // Concentric "memory rings" with sample style traits orbiting.
  const traits = [
    { t: "concise replies",    pct: 92 },
    { t: "no exclamation",     pct: 88 },
    { t: "leads with the ask", pct: 81 },
    { t: "follow-up after 24h",pct: 74 },
  ];
  return (
    <div className={`${cardCls} flex flex-col`}>
      <div className="mb-4 flex items-center justify-between">
        <span
          className="inline-flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.4px]"
          style={{ color: accent }}
        >
          <Brain size={12} strokeWidth={1.7} aria-hidden />
          ai clone · v0.7
        </span>
        <span className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
          confidence 82%
        </span>
      </div>

      <div className="relative grid flex-1 place-items-center">
        <svg
          viewBox="0 0 240 200"
          className="h-full w-full max-h-[220px]"
          aria-hidden
        >
          <defs>
            <radialGradient id="ms-glow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor={accent} stopOpacity="0.32" />
              <stop offset="60%" stopColor={accent} stopOpacity="0.08" />
              <stop offset="100%" stopColor={accent} stopOpacity="0" />
            </radialGradient>
          </defs>
          <circle cx="120" cy="100" r="84" fill="url(#ms-glow)" />
          {[28, 48, 68].map((r, i) => (
            <circle
              key={r}
              cx="120"
              cy="100"
              r={r}
              fill="none"
              stroke="currentColor"
              strokeOpacity={0.15 + i * 0.05}
              className="text-ink"
            />
          ))}
          <circle cx="120" cy="100" r="6" fill={accent} />
          {/* Trait ticks orbiting at fixed positions */}
          {[
            { x: 120, y: 28 },
            { x: 200, y: 100 },
            { x: 120, y: 172 },
            { x: 40,  y: 100 },
          ].map((p, i) => (
            <g key={i}>
              <circle cx={p.x} cy={p.y} r="3.5" fill={accent} />
              <line
                x1="120"
                y1="100"
                x2={p.x}
                y2={p.y}
                stroke={accent}
                strokeOpacity="0.35"
                strokeDasharray="2 4"
              />
            </g>
          ))}
        </svg>
      </div>

      <ul className="mt-2 grid grid-cols-2 gap-1.5 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-2">
        {traits.map(t => (
          <li key={t.t} className="flex items-center justify-between gap-2">
            <span className="truncate">{t.t}</span>
            <span className="tabular-nums" style={{ color: accent }}>
              {t.pct}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function VaultVisual({ accent }: { accent: string }) {
  const layers = [
    { Icon: Cpu,  label: "your machine", detail: "macos · keychain · master keyring" },
    { Icon: Lock, label: "encrypt",      detail: "xchacha20-poly1305 · x25519" },
    { Icon: ShieldCheck, label: "meeet.world", detail: "ciphertext only · contract 1.1.0" },
    { Icon: Eye,  label: "sees nothing", detail: "zero-knowledge sync · audit-grade receipts" },
  ];
  return (
    <div className={`${cardCls} flex flex-col`}>
      <div className="mb-4 flex items-center justify-between">
        <span
          className="inline-flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.4px]"
          style={{ color: accent }}
        >
          <ShieldCheck size={12} strokeWidth={1.7} aria-hidden />
          envelope · L5
        </span>
        <span className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
          contract 1.1.0
        </span>
      </div>
      <ol className="grid flex-1 items-center gap-2.5">
        {layers.map((l, i) => (
          <motion.li
            key={l.label}
            initial={{ opacity: 0, x: -8 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.08 * i, duration: 0.4 }}
            className="grid grid-cols-[28px_1fr_auto] items-center gap-3 rounded-md border border-line/60 bg-bg-2/40 px-3 py-2.5"
          >
            <span
              className="grid h-7 w-7 shrink-0 place-items-center rounded-md"
              style={{
                background: "color-mix(in srgb, var(--color-bg-2) 60%, transparent)",
                color: accent,
              }}
              aria-hidden
            >
              <l.Icon size={13} strokeWidth={1.7} />
            </span>
            <span className="min-w-0">
              <span className="block font-mono-tech text-[12px] text-ink">
                {l.label}
              </span>
              <span className="block truncate font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3">
                {l.detail}
              </span>
            </span>
            <span aria-hidden style={{ color: accent }} className="opacity-70">
              <Zap size={11} strokeWidth={1.7} />
            </span>
          </motion.li>
        ))}
      </ol>
    </div>
  );
}
