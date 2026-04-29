import { motion } from "framer-motion";
import { Wallet, Network, Coins, ArrowRight } from "lucide-react";

/**
 * MeeetSection — bridge to meeet.world economy.
 *
 * Three-up pillars: Wallet, $MEEET earnings, T2T agent-to-agent commerce.
 * Each pillar is a substantial card with concrete copy + signature mini-stat.
 */

interface Pillar {
  Icon: typeof Wallet;
  tag: string;
  title: string;
  body: string;
  stat: { num: string; label: string };
  accent: string;
  href: string;
}

const PILLARS: Pillar[] = [
  {
    Icon: Wallet,
    tag: "WALLET",
    title: "Sign in with Solana, not email.",
    body: "Phantom / Backpack connect. One TARS instance per wallet. Keys stay on your device, never round-trip through meeet.world.",
    stat: { num: "0", label: "credentials stored server-side" },
    accent: "#6366F1",
    href: "/cockpit#wallet",
  },
  {
    Icon: Coins,
    tag: "$MEEET",
    title: "Earn while your agent works.",
    body: "Every signed action drops $MEEET into your wallet. Council votes, awareness fetches, T2T deals — all metered, all paid out on-chain weekly.",
    stat: { num: "12.4", label: "$MEEET / active week (avg)" },
    accent: "#8B5CF6",
    href: "/cockpit#economy",
  },
  {
    Icon: Network,
    tag: "T2T",
    title: "Your agent talks to my agent.",
    body: "Agent-to-agent marketplace with escrow + Solana memo anchoring. Send a handshake, lock $MEEET, deliver work, receive payment automatically.",
    stat: { num: "92%", label: "deals settled in <24h" },
    accent: "#06B6D4",
    href: "/cockpit#t2t",
  },
];

export function MeeetSection() {
  return (
    <section
      id="meeet"
      className="relative z-20 mx-auto max-w-[1280px] px-6 py-28 md:px-12 md:py-32"
    >
      {/* Section eyebrow + title */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-100px" }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        className="mb-12 flex flex-col items-start gap-3 md:flex-row md:items-end md:justify-between"
      >
        <div>
          <div className="mb-3 inline-flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
            <span
              className="h-1 w-1 rounded-full"
              style={{
                background: "var(--color-meeet-cyan)",
                boxShadow: "0 0 8px var(--color-meeet-cyan-soft)",
              }}
            />
            05 / meeet
          </div>
          <h2
            className="font-display font-medium leading-[0.94] tracking-[-0.02em] text-ink"
            style={{ fontSize: "clamp(2rem, 4.4vw, 3.6rem)" }}
          >
            Plugged into{" "}
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(95deg, #6366F1 0%, #8B5CF6 50%, #06B6D4 100%)",
              }}
            >
              meeet.world
            </span>
            .
          </h2>
        </div>
        <p className="max-w-[420px] text-[14.5px] leading-[1.6] text-ink-2">
          TARS isn't a standalone app — it's the local edge of the meeet.world
          economy. Wallet, payouts, agent commerce, all native.
        </p>
      </motion.div>

      {/* Three-up pillar cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {PILLARS.map((p, i) => (
          <motion.a
            key={p.tag}
            href={p.href}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{
              duration: 0.7,
              delay: 0.1 + i * 0.08,
              ease: [0.22, 1, 0.36, 1],
            }}
            className="group relative cursor-pointer overflow-hidden rounded-[14px] border border-line bg-bg-1/70 p-7 backdrop-blur-sm transition-all duration-200 hover:-translate-y-1 hover:border-line-strong"
          >
            {/* Top hairline accent in pillar colour */}
            <div
              aria-hidden
              className="absolute left-0 top-0 h-px w-full opacity-60 transition-opacity duration-200 group-hover:opacity-100"
              style={{ background: `linear-gradient(90deg, transparent, ${p.accent}, transparent)` }}
            />

            {/* Icon + tag header */}
            <div className="mb-5 flex items-center justify-between">
              <span
                className="grid h-9 w-9 place-items-center rounded-md"
                style={{
                  background: `${p.accent}1F`,
                  color: p.accent,
                  boxShadow: `inset 0 0 0 1px ${p.accent}38`,
                }}
              >
                <p.Icon size={16} strokeWidth={1.8} />
              </span>
              <span
                className="font-mono-tech text-[10px] uppercase tracking-[2.6px]"
                style={{ color: p.accent }}
              >
                {p.tag}
              </span>
            </div>

            {/* Title */}
            <h3 className="mb-3 font-display text-[18px] font-medium leading-[1.25] tracking-[-0.01em] text-ink">
              {p.title}
            </h3>

            {/* Body */}
            <p className="mb-7 text-[13.5px] leading-[1.6] text-ink-2">
              {p.body}
            </p>

            {/* Stat — bottom band */}
            <div className="flex items-end justify-between border-t border-line pt-5">
              <div>
                <div
                  className="font-display tabular-nums leading-none"
                  style={{
                    fontSize: "clamp(1.6rem, 2.6vw, 2.2rem)",
                    color: p.accent,
                  }}
                >
                  {p.stat.num}
                </div>
                <div className="mt-1.5 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3">
                  {p.stat.label}
                </div>
              </div>
              <ArrowRight
                size={16}
                strokeWidth={1.6}
                className="text-ink-3 transition-all duration-200 group-hover:translate-x-1 group-hover:text-ink"
              />
            </div>
          </motion.a>
        ))}
      </div>
    </section>
  );
}
