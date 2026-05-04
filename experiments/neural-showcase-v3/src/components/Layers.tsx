import { motion, useScroll, useTransform } from "framer-motion";
import { useRef } from "react";
import { SectionHead } from "@/components/SectionHead";
import { CornerFrame, BarStack, StatusLozenge } from "@/components/Glyphs";
import {
  Brain,
  Database,
  GitBranch,
  CalendarClock,
  MousePointerClick,
  Radio,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useT, type TKey } from "@/lib/i18n";

interface LayerCard {
  tagKey: TKey;
  titleKey: TKey;
  bodyKey: TKey;
  Icon: LucideIcon;
  accent?: "accent" | "alert" | "default";
  bars: number[];
}

const CARDS: LayerCard[] = [
  {
    tagKey: "layers.l1.tag",
    titleKey: "layers.l1.title",
    bodyKey: "layers.l1.body",
    Icon: Brain,
    accent: "accent",
    bars: [0.3, 0.55, 0.78, 0.45, 0.92, 0.7, 0.6, 0.85],
  },
  {
    tagKey: "layers.l2.tag",
    titleKey: "layers.l2.title",
    bodyKey: "layers.l2.body",
    Icon: Database,
    bars: [0.5, 0.42, 0.6, 0.7, 0.65, 0.78, 0.82, 0.5],
  },
  {
    tagKey: "layers.l3.tag",
    titleKey: "layers.l3.title",
    bodyKey: "layers.l3.body",
    Icon: GitBranch,
    bars: [0.18, 0.6, 0.55, 0.9, 0.4, 0.62, 0.7, 0.52],
  },
  {
    tagKey: "layers.l4.tag",
    titleKey: "layers.l4.title",
    bodyKey: "layers.l4.body",
    Icon: CalendarClock,
    accent: "alert",
    bars: [0.28, 0.7, 0.4, 0.56, 0.6, 0.32, 0.78, 0.48],
  },
  {
    tagKey: "layers.l5.tag",
    titleKey: "layers.l5.title",
    bodyKey: "layers.l5.body",
    Icon: MousePointerClick,
    bars: [0.35, 0.45, 0.62, 0.32, 0.7, 0.55, 0.4, 0.62],
  },
  {
    tagKey: "layers.l6.tag",
    titleKey: "layers.l6.title",
    bodyKey: "layers.l6.body",
    Icon: Radio,
    accent: "accent",
    bars: [0.5, 0.62, 0.4, 0.78, 0.5, 0.85, 0.55, 0.7],
  },
];

const dotColor = (a: LayerCard["accent"]) =>
  a === "accent"
    ? "var(--color-accent)"
    : a === "alert"
      ? "var(--color-alert)"
      : "var(--color-hud)";

export function Layers() {
  const ref = useRef<HTMLElement>(null);
  const t = useT();
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
    // Defer to useEffect — the ref is in the same component but
    // framer-motion still races layoutEffect on the first paint.
    layoutEffect: false,
  });
  const tilt = useTransform(scrollYProgress, [0, 0.5, 1], [12, 0, -12]);

  return (
    <section
      id="layers"
      ref={ref}
      className="relative z-20 mx-auto max-w-[1280px] px-8 py-28 md:px-14 md:py-32"
    >
      <SectionHead
        num="01"
        tag={t("layers.head.tag")}
        title={t("layers.head.title")}
        description={t("layers.head.description")}
      />

      {/* Iso stack — perspective wrapper */}
      <motion.div
        style={{ rotateX: tilt, perspective: 1400 }}
        className="[transform-style:preserve-3d]"
      >
        <ul className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {CARDS.map((c, i) => {
            const depth = (i % 3) * 24 - 12;
            const tag = t(c.tagKey);
            return (
              <motion.li
                key={c.tagKey}
                initial={{ opacity: 0, y: 32, rotateY: -8 }}
                whileInView={{ opacity: 1, y: 0, rotateY: 0 }}
                viewport={{ once: true, margin: "-80px" }}
                whileHover={{
                  y: -6,
                  rotateY: 0,
                  rotateX: 0,
                  transition: { type: "spring", stiffness: 220, damping: 22 },
                }}
                transition={{
                  duration: 0.7,
                  delay: (i % 3) * 0.06 + Math.floor(i / 3) * 0.12,
                  ease: [0.22, 1, 0.36, 1],
                }}
                style={{
                  transformStyle: "preserve-3d",
                  transform: `translateZ(${depth}px)`,
                }}
                className="group relative overflow-hidden rounded-[10px] border border-line bg-[linear-gradient(180deg,rgba(11,11,16,0.85),rgba(0,0,0,0.85))] p-7 backdrop-blur-md transition-colors duration-200 hover:border-line-strong"
              >
                <CornerFrame />

                {/* Glow rim that lights up on hover */}
                <span
                  aria-hidden
                  className="pointer-events-none absolute -inset-px rounded-[10px] opacity-0 transition-opacity duration-300 group-hover:opacity-100"
                  style={{
                    background: `radial-gradient(50% 80% at 50% 0%, ${dotColor(
                      c.accent,
                    )} 0%, transparent 60%)`,
                    mixBlendMode: "screen",
                  }}
                />

                {/* Header */}
                <div className="mb-5 flex items-center justify-between">
                  <div className="flex items-center gap-2.5 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
                    <span
                      className="grid h-7 w-7 place-items-center rounded-md border"
                      style={{
                        borderColor: dotColor(c.accent),
                        background: `color-mix(in srgb, ${dotColor(c.accent)} 8%, transparent)`,
                        color: dotColor(c.accent),
                      }}
                    >
                      <c.Icon size={14} strokeWidth={1.5} />
                    </span>
                    {tag}
                  </div>
                  <StatusLozenge label={`L${(i + 1).toString().padStart(2, "0")}`} tone="muted" />
                </div>

                <h3 className="mb-2 font-display text-[19px] font-semibold uppercase tracking-[0.02em] text-ink">
                  {t(c.titleKey)}
                </h3>
                <p className="mb-5 text-[13.5px] leading-[1.65] text-ink-2">{t(c.bodyKey)}</p>

                {/* Live mini-bars + scan label */}
                <div className="flex items-end justify-between border-t border-line pt-4 font-mono-tech text-[9.5px] uppercase tracking-[2.4px] text-ink-3">
                  <span>{t("layers.signal.prefix")} · {tag}</span>
                  <BarStack
                    values={c.bars}
                    height={20}
                    width={84}
                    color={dotColor(c.accent)}
                  />
                </div>

                {/* Left edge accent line that grows on hover */}
                <span
                  className="absolute left-0 top-0 h-px transition-[width,height] duration-300 group-hover:h-full group-hover:w-[2px]"
                  style={{ width: 28, background: dotColor(c.accent) }}
                />
              </motion.li>
            );
          })}
        </ul>
      </motion.div>
    </section>
  );
}
