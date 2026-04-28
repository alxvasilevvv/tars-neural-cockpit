import { motion } from "framer-motion";
import { SectionHead } from "@/components/SectionHead";

interface LayerCard {
  tag: string;
  title: string;
  body: string;
  accent?: "accent" | "alert" | "default";
}

const CARDS: LayerCard[] = [
  {
    tag: "concept",
    title: "Knowledge graph of your work",
    body: "Files, docs, threads. Embedded and clustered. The concept layer is the spine of the graph.",
    accent: "accent",
  },
  {
    tag: "memory",
    title: "Long-term recall",
    body: "Decisions, names, projects. Pinned to a shell that orbits the concept core.",
  },
  {
    tag: "code",
    title: "Repository awareness",
    body: "Your codebases linked into the graph as a tight, ordered arm.",
  },
  {
    tag: "calendar",
    title: "Time-aware context",
    body: "Events become time-anchored nodes that fire when relevant.",
    accent: "alert",
  },
  {
    tag: "mac actions",
    title: "Hands on the OS",
    body: "Open, type, click, automate — under explicit policy.",
  },
  {
    tag: "voice",
    title: "Always-on listener",
    body: "Voice intents threaded through every other layer.",
    accent: "accent",
  },
];

const dotColor = (a: LayerCard["accent"]) =>
  a === "accent"
    ? "var(--color-accent)"
    : a === "alert"
      ? "var(--color-alert)"
      : "var(--color-ink-2)";

export function Layers() {
  return (
    <section
      id="layers"
      className="relative z-20 mx-auto max-w-[1280px] px-8 py-32 md:px-14 md:py-36"
    >
      <SectionHead
        num="01"
        tag="AWARENESS"
        title="Six streams, one graph."
        description="Every signal lands on the core and gets clustered into the graph. No upload — local-first by default."
      />
      <ul className="grid grid-cols-1 gap-px overflow-hidden rounded-[22px] border border-line bg-line md:grid-cols-2 lg:grid-cols-3">
        {CARDS.map((c, i) => (
          <motion.li
            key={c.tag}
            initial={{ opacity: 0, y: 28 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{
              duration: 0.6,
              delay: (i % 3) * 0.05,
              ease: [0.22, 1, 0.36, 1],
            }}
            className="group relative bg-bg-1 p-9 transition-colors duration-200 hover:bg-bg-2"
          >
            <span
              className="absolute left-0 top-0 h-px w-7 transition-[width] duration-200 group-hover:w-16"
              style={{ background: dotColor(c.accent) }}
            />
            <div className="mb-4 flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: dotColor(c.accent) }}
              />
              {c.tag}
            </div>
            <h3 className="mb-2 font-display text-[18px] font-semibold tracking-[-0.02em] text-ink">
              {c.title}
            </h3>
            <p className="text-[14px] leading-[1.6] text-ink-2">{c.body}</p>
          </motion.li>
        ))}
      </ul>
    </section>
  );
}
