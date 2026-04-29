import { motion } from "framer-motion";
import { useMemo } from "react";
import { useT, type TKey } from "@/lib/i18n";

/**
 * DomainsCards — replaces the 3D octahedron scene with a refined
 * card grid. Pattern reference: Vercel framework picker, Linear
 * roadmap cards, Stripe products tiles.
 *
 * Each card carries:
 *   - Top hairline accent in the pack's brand colour
 *   - Pack number (01–04) and name in mono-tech
 *   - A unique inline SVG illustration that hints at the pack's
 *     domain — sparkline for traders, KPI tiles for business,
 *     pipeline graph for entrepreneur, equation glyphs for science
 *   - One-line teaser
 * Active card lifts, scales slightly and glows in pack colour.
 *
 * Selection is controlled from <Domains/> via activeSlug + onActivate.
 * No three.js, no postprocessing, no bright primary-colour octahedrons.
 */

interface CardSpec {
  slug: "traders" | "business" | "entrepreneur" | "science";
  num: string;
  /** Translation keys; resolved at render via useT(). */
  nameKey: TKey;
  teaserKey: TKey;
  color: string; // brand colour
}

const CARDS: CardSpec[] = [
  { slug: "traders",      num: "01", nameKey: "domains.traders.name",      teaserKey: "domains.traders.teaser",      color: "#6366F1" },
  { slug: "business",     num: "02", nameKey: "domains.business.name",     teaserKey: "domains.business.teaser",     color: "#8B5CF6" },
  { slug: "entrepreneur", num: "03", nameKey: "domains.entrepreneur.name", teaserKey: "domains.entrepreneur.teaser", color: "#06B6D4" },
  { slug: "science",      num: "04", nameKey: "domains.science.name",      teaserKey: "domains.science.teaser",      color: "#A78BFA" },
];

/** Sparkline — a 28-point candle-walk that suggests price action. */
function TradersGlyph({ color }: { color: string }) {
  // Deterministic walk so it doesn't jitter per render
  const points = useMemo(() => {
    const n = 32;
    let y = 18;
    const out: [number, number][] = [];
    for (let i = 0; i < n; i++) {
      const noise = Math.sin(i * 0.6) * 4 + Math.sin(i * 1.7) * 2 + Math.cos(i * 0.3) * 3;
      y = Math.max(4, Math.min(28, 18 + noise + (i / n) * 4));
      out.push([(i / (n - 1)) * 184, y]);
    }
    return out;
  }, []);

  const d =
    `M ${points[0][0]},${points[0][1]} ` +
    points
      .slice(1)
      .map(([x, y]) => `L ${x.toFixed(1)},${y.toFixed(1)}`)
      .join(" ");

  // Filled area below
  const lastX = points[points.length - 1][0];
  const dArea = `${d} L ${lastX},32 L 0,32 Z`;

  return (
    <svg viewBox="0 0 184 36" className="block h-9 w-full" fill="none" aria-hidden>
      <defs>
        <linearGradient id="td-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.45" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={dArea} fill="url(#td-grad)" />
      <path d={d} stroke={color} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
      {/* Last-point marker */}
      <circle cx={points[points.length - 1][0]} cy={points[points.length - 1][1]} r="2" fill={color} />
      <circle
        cx={points[points.length - 1][0]}
        cy={points[points.length - 1][1]}
        r="5"
        fill="none"
        stroke={color}
        strokeOpacity="0.4"
      >
        <animate attributeName="r" values="3;7;3" dur="2.4s" repeatCount="indefinite" />
        <animate attributeName="stroke-opacity" values="0.5;0;0.5" dur="2.4s" repeatCount="indefinite" />
      </circle>
    </svg>
  );
}

/** Business — six KPI tiles in a 3×2 mini grid with one pulsing. */
function BusinessGlyph({ color }: { color: string }) {
  return (
    <svg viewBox="0 0 184 36" className="block h-9 w-full" fill="none" aria-hidden>
      {[0, 1, 2, 3, 4, 5].map(i => {
        const col = i % 3;
        const row = Math.floor(i / 3);
        const x = 4 + col * 60;
        const y = 4 + row * 16;
        const w = 52;
        const h = 12;
        const fillVal = [0.6, 0.85, 0.45, 0.75, 0.55, 0.92][i];
        return (
          <g key={i}>
            <rect x={x} y={y} width={w} height={h} rx="2" fill={color} fillOpacity="0.08" stroke={color} strokeOpacity="0.25" />
            <rect x={x} y={y} width={w * fillVal} height={h} rx="2" fill={color} fillOpacity={i === 5 ? 0.7 : 0.32}>
              {i === 5 && <animate attributeName="fill-opacity" values="0.4;0.85;0.4" dur="2s" repeatCount="indefinite" />}
            </rect>
          </g>
        );
      })}
    </svg>
  );
}

/** Entrepreneur — pipeline graph: root → segments → leads (same shape as the
 *  former MLM glyph; the metaphor still reads as "your network", just framed
 *  as pipeline depth instead of downline). */
function EntrepreneurGlyph({ color }: { color: string }) {
  // Tree positions in a 184×36 viewBox
  const root = { x: 14, y: 18 };
  const layer1 = [
    { x: 64, y: 6 },
    { x: 64, y: 18 },
    { x: 64, y: 30 },
  ];
  const layer2 = [
    { x: 124, y: 4 }, { x: 124, y: 10 },
    { x: 124, y: 16 }, { x: 124, y: 22 },
    { x: 124, y: 28 }, { x: 124, y: 34 },
  ];
  const leaves = [
    { x: 174, y: 6 }, { x: 174, y: 18 }, { x: 174, y: 30 },
  ];

  return (
    <svg viewBox="0 0 184 36" className="block h-9 w-full" fill="none" aria-hidden>
      {/* root → layer1 */}
      {layer1.map((p, i) => (
        <line key={`a${i}`} x1={root.x} y1={root.y} x2={p.x} y2={p.y} stroke={color} strokeOpacity="0.28" strokeWidth="0.8" />
      ))}
      {/* layer1 → layer2 */}
      {layer1.map((p, i) =>
        [layer2[i * 2], layer2[i * 2 + 1]].map((c, j) => (
          <line key={`b${i}${j}`} x1={p.x} y1={p.y} x2={c.x} y2={c.y} stroke={color} strokeOpacity="0.22" strokeWidth="0.8" />
        )),
      )}
      {/* layer2 → leaves (just decorative) */}
      {leaves.map((l, i) => (
        <line key={`c${i}`} x1={layer2[i * 2].x} y1={(layer2[i * 2].y + layer2[i * 2 + 1].y) / 2} x2={l.x} y2={l.y} stroke={color} strokeOpacity="0.18" strokeWidth="0.8" />
      ))}

      {/* nodes */}
      <circle cx={root.x} cy={root.y} r="3" fill={color} />
      {layer1.map((p, i) => (
        <circle key={`n1${i}`} cx={p.x} cy={p.y} r="2.4" fill={color} fillOpacity="0.85" />
      ))}
      {layer2.map((p, i) => (
        <circle key={`n2${i}`} cx={p.x} cy={p.y} r="1.6" fill={color} fillOpacity="0.6" />
      ))}
      {leaves.map((p, i) => (
        <circle key={`n3${i}`} cx={p.x} cy={p.y} r="1.4" fill={color} fillOpacity="0.45" />
      ))}

      {/* Pulsing trail on root → middle child */}
      <circle cx={root.x} cy={root.y} r="1.6" fill={color}>
        <animateMotion dur="2.6s" repeatCount="indefinite" path={`M0,0 Q25,0 50,0 Q85,0 110,0`} />
        <animate attributeName="fill-opacity" values="1;0;1" dur="2.6s" repeatCount="indefinite" />
      </circle>
    </svg>
  );
}

/** Science — citation tree (3 linked cards with hash refs) */
function ScienceGlyph({ color }: { color: string }) {
  return (
    <svg viewBox="0 0 184 36" className="block h-9 w-full" fill="none" aria-hidden>
      {/* Three paper "cards" */}
      {[12, 86, 160].map((cx, i) => (
        <g key={i}>
          <rect
            x={cx - 14}
            y={4}
            width="28"
            height="28"
            rx="2"
            fill={color}
            fillOpacity="0.08"
            stroke={color}
            strokeOpacity={i === 1 ? 0.55 : 0.25}
          />
          <line x1={cx - 9} y1={11} x2={cx + 9} y2={11} stroke={color} strokeOpacity="0.6" strokeWidth="0.8" />
          <line x1={cx - 9} y1={15} x2={cx + 6} y2={15} stroke={color} strokeOpacity="0.4" strokeWidth="0.8" />
          <line x1={cx - 9} y1={19} x2={cx + 9} y2={19} stroke={color} strokeOpacity="0.4" strokeWidth="0.8" />
          <line x1={cx - 9} y1={23} x2={cx + 4} y2={23} stroke={color} strokeOpacity="0.3" strokeWidth="0.8" />
        </g>
      ))}
      {/* Citation arcs between cards */}
      <path d="M 26 18 Q 56 6 72 18" stroke={color} strokeOpacity="0.4" strokeWidth="0.8" fill="none" />
      <path d="M 100 18 Q 130 30 146 18" stroke={color} strokeOpacity="0.4" strokeWidth="0.8" fill="none" />
      {/* Travelling dot along the first arc */}
      <circle r="1.6" fill={color}>
        <animateMotion dur="3.2s" repeatCount="indefinite" path="M 26 18 Q 56 6 72 18" />
        <animate attributeName="fill-opacity" values="1;0.2;1" dur="3.2s" repeatCount="indefinite" />
      </circle>
    </svg>
  );
}

const GLYPHS: Record<CardSpec["slug"], (p: { color: string }) => JSX.Element> = {
  traders: TradersGlyph,
  business: BusinessGlyph,
  entrepreneur: EntrepreneurGlyph,
  science: ScienceGlyph,
};

interface Props {
  activeSlug: string;
  onActivate: (slug: string) => void;
}

export function DomainsCards({ activeSlug, onActivate }: Props) {
  const t = useT();
  return (
    <div className="grid h-full grid-cols-1 gap-px overflow-hidden rounded-[14px] border border-line bg-line sm:grid-cols-2">
      {CARDS.map((c, i) => {
        const Glyph = GLYPHS[c.slug];
        const active = c.slug === activeSlug;
        return (
          <motion.button
            key={c.slug}
            type="button"
            onClick={() => onActivate(c.slug)}
            onMouseEnter={() => onActivate(c.slug)}
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{ duration: 0.55, delay: i * 0.06, ease: [0.22, 1, 0.36, 1] }}
            aria-pressed={active}
            className="relative flex flex-col items-stretch gap-5 bg-bg-1 p-7 text-left transition-all duration-200 hover:bg-bg-2/50 md:p-8"
            style={{
              boxShadow: active ? `inset 0 0 0 1px ${c.color}, 0 0 24px -4px ${c.color}55` : undefined,
            }}
          >
            {/* Top accent line */}
            <div
              aria-hidden
              className="absolute inset-x-0 top-0 h-px transition-opacity duration-200"
              style={{
                background: c.color,
                boxShadow: active ? `0 0 16px ${c.color}` : undefined,
                opacity: active ? 1 : 0.35,
              }}
            />

            {/* Header — number + name */}
            <header className="flex items-center justify-between">
              <div className="flex items-baseline gap-3 font-mono-tech text-[11px] uppercase tracking-[3px]">
                <span style={{ color: c.color }}>{c.num}</span>
                <span className="text-ink">{t(c.nameKey)}</span>
              </div>
              {/* Subtle activate dot */}
              <span
                aria-hidden
                className="h-1.5 w-1.5 rounded-full transition-all duration-200"
                style={{
                  background: active ? c.color : "var(--color-line-strong)",
                  boxShadow: active ? `0 0 10px ${c.color}` : undefined,
                }}
              />
            </header>

            {/* Glyph illustration */}
            <div className="flex-1">
              <Glyph color={c.color} />
            </div>

            {/* Teaser */}
            <p className="font-display text-[14.5px] leading-[1.35] tracking-[-0.005em] text-ink">
              {t(c.teaserKey)}
            </p>
          </motion.button>
        );
      })}
    </div>
  );
}
