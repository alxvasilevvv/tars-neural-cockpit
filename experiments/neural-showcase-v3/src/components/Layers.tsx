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

interface LayerCard {
  tag: string;
  title: string;
  body: string;
  Icon: LucideIcon;
  accent?: "accent" | "alert" | "default";
  bars: number[];
}

const CARDS: LayerCard[] = [
  {
    tag: "concept",
    title: "Knowledge graph",
    body: "Files, docs and threads embedded into a graph. The concept layer is the spine.",
    Icon: Brain,
    accent: "accent",
    bars: [0.3, 0.55, 0.78, 0.45, 0.92, 0.7, 0.6, 0.85],
  },
  {
    tag: "memory",
    title: "Long-term recall",
    body: "Decisions, names, projects pinned to a shell that orbits the concept core.",
    Icon: Database,
    bars: [0.5, 0.42, 0.6, 0.7, 0.65, 0.78, 0.82, 0.5],
  },
  {
    tag: "code",
    title: "Repo awareness",
    body: "Codebases linked into the graph as a tight, ordered arm — symbol-aware.",
    Icon: GitBranch,
    bars: [0.18, 0.6, 0.55, 0.9, 0.4, 0.62, 0.7, 0.52],
  },
  {
    tag: "calendar",
    title: "Time-aware context",
    body: "Events become time-anchored nodes that fire when relevant.",
    Icon: CalendarClock,
    accent: "alert",
    bars: [0.28, 0.7, 0.4, 0.56, 0.6, 0.32, 0.78, 0.48],
  },
  {
    tag: "mac actions",
    title: "Hands on the OS",
    body: "Open, type, click, automate — under explicit policy.",
    Icon: MousePointerClick,
    bars: [0.35, 0.45, 0.62, 0.32, 0.7, 0.55, 0.4, 0.62],
  },
  {
    tag: "voice",
    title: "Always-on listener",
    body: "Voice intents threaded through every other layer.",
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
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
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
        tag="AWARENESS"
        title="Six streams, one graph."
        description="Every signal lands on the core and gets clustered into the graph. No upload — local-first by default."
      />

      {/* Iso stack — perspective wrapper */}
      <motion.div
        style={{ rotateX: tilt, perspective: 1400 }}
        className="[transform-style:preserve-3d]"
      >
        <ul className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {CARDS.map((c, i) => {
            const depth = (i % 3) * 24 - 12;
            return (
              <motion.li
                key={c.tag}
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
                    {c.tag}
                  </div>
                  <StatusLozenge label={`L${(i + 1).toString().padStart(2, "0")}`} tone="muted" />
                </div>

                <h3 className="mb-2 font-display text-[19px] font-semibold uppercase tracking-[0.02em] text-ink">
                  {c.title}
                </h3>
                <p className="mb-5 text-[13.5px] leading-[1.65] text-ink-2">{c.body}</p>

                {/* Live mini-bars + scan label */}
                <div className="flex items-end justify-between border-t border-line pt-4 font-mono-tech text-[9.5px] uppercase tracking-[2.4px] text-ink-3">
                  <span>signal · {c.tag}</span>
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
