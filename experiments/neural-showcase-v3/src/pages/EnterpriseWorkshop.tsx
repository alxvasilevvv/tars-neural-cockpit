import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  ShieldCheck,
  Activity,
  Layers,
  Lock,
  KeyRound,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";
import { useDocumentMeta } from "@/lib/meta";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { WorkshopTutorial } from "@/components/WorkshopTutorial";

/**
 * /workshop/enterprise — generic B2B workshop landing for fund
 * partners, quant teams, and research desks.
 *
 * Distinct from /workshop (the generic 4-phase wizard). This page is
 * the marketing surface attendees land on after the calendar invite —
 * it sets context for Day 1, surfaces the 5 algotrade playbooks, and
 * frames the risk-first posture quants will actually scrutinise.
 *
 * Defensive `initial: { opacity: 1 }` on motion wrappers — if the
 * lazy chunk's framer dependency is slow to hydrate, the page is still
 * legible (we learned this from Wave 69's ScrollStory black zone).
 */

interface PlaybookCard {
  slug: string;
  title: string;
  oneLiner: string;
  phase: "design" | "test" | "deploy";
}

const PLAYBOOKS: PlaybookCard[] = [
  {
    slug: "mean_reversion_strategy",
    title: "Mean reversion (SMA + RSI)",
    oneLiner:
      "Compose a Strategy IR, backtest 2024 BTC/USDT, gate, then 7-day paper.",
    phase: "design",
  },
  {
    slug: "momentum_breakout_strategy",
    title: "Momentum breakout",
    oneLiner:
      "Bollinger band breakout with EMA(50) trend filter — same gate-then-paper loop.",
    phase: "design",
  },
  {
    slug: "live_paper_session",
    title: "Live paper session",
    oneLiner:
      "Strict risk policy (kill_switch, $1k pos cap, $50 daily loss cap) + 15-min monitor.",
    phase: "test",
  },
  {
    slug: "backtest_to_live_pipeline",
    title: "Backtest → live pipeline",
    oneLiner:
      "Pick → re-backtest → Sharpe>1.5 → 30-day paper → human approval → live (mock).",
    phase: "deploy",
  },
  {
    slug: "risk_audit_weekly",
    title: "Weekly risk audit",
    oneLiner:
      "Friday 18:00: aggregate every audit JSONL, email compliance, anchor on Solana.",
    phase: "deploy",
  },
];

const PHASE_COLOR: Record<PlaybookCard["phase"], string> = {
  design: "var(--brand-indigo)",
  test: "var(--brand-cyan)",
  deploy: "var(--brand-violet)",
};

export function EnterpriseWorkshop() {
  useDocumentMeta({
    // Wave 83 — per-route OG SVG variant. og-workshop-enterprise.svg
    // is shipped in public/ alongside the other per-route OG cards
    // (see Wave 11/44).
    // Wave 127 — auto-fix: trimmed from "Algorithmic Workshop —
    // Enterprise B2B onboarding" (69 chars w/ suffix) to fit the
    // 60-char Twitter title cap. Full headline still in <h1> below.
    title: "Enterprise B2B workshop",
    description:
      "Workshop landing for fund partners, quant teams, and research desks. Strategy IR → backtest → risk gate → paper → live, all running on TARS.",
    ogImage: "https://tars.meeet.world/og-workshop-enterprise.svg",
  });

  return (
    <div className="relative min-h-[calc(100vh-72px)] overflow-hidden bg-bg-0 text-ink">
      {/* Ambient backdrop — same triad as Pitch */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background: `
            radial-gradient(ellipse 50% 40% at 18% 10%, rgba(99,102,241,0.10) 0%, transparent 60%),
            radial-gradient(ellipse 45% 35% at 82% 88%, rgba(139,92,246,0.10) 0%, transparent 60%),
            radial-gradient(ellipse 30% 25% at 50% 50%, rgba(6,182,212,0.05) 0%, transparent 60%)
          `,
        }}
      />

      <article className="mx-auto max-w-[1100px] px-6 pb-28 pt-14 md:px-12 md:pt-20">
        {/* Wave 83 — breadcrumbs replace ad-hoc Back link.
            Provides Home → Workshop → Enterprise trail with proper
            <nav aria-label="Breadcrumb"> + aria-current="page" semantics. */}
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
              { label: "Enterprise" },
            ]}
          />
        </motion.div>

        {/* Hero */}
        <motion.header
          initial={{ opacity: 1, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.05, ease: [0.22, 1, 0.36, 1] }}
          className="mb-14 mt-8 grid grid-cols-1 gap-4 border-b border-line pb-12"
        >
          <div className="flex items-center gap-3 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
            <span style={{ color: "var(--brand-indigo)" }}>W81</span>
            <span>Workshop · Enterprise</span>
          </div>
          <h1
            className="max-w-[24ch] font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
            style={{ fontSize: "clamp(2.4rem, 5.4vw, 4.4rem)" }}
          >
            Algorithmic workshop —{" "}
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(95deg, var(--brand-indigo) 0%, var(--brand-violet) 50%, var(--brand-cyan) 100%)",
              }}
            >
              built for fund partners,
            </span>{" "}
            quant teams, and research desks.
          </h1>
          <p className="mt-2 max-w-[64ch] text-[15px] leading-[1.65] text-ink-2">
            One day. Five playbooks. By the end of Day 1 you have a
            mean-reversion strategy in 7-day paper, a momentum breakout in
            review, a scheduled risk audit, and a promotion pipeline ready to
            ship to live (Binance v9.2 adapter — vault-key + multi-sig
            confirm + daily caps before any real order is placed).
          </p>
        </motion.header>

        {/* 3-step CTA */}
        <motion.section
          initial={{ opacity: 1, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="mb-16 grid grid-cols-1 gap-4 md:grid-cols-3"
          aria-labelledby="workshop-steps-heading"
        >
          {/* Visually hidden heading keeps the h1→h2→h3 order correct
              for screen readers. The aria-labelledby above pairs the
              region with this title. */}
          <h2 id="workshop-steps-heading" className="sr-only">
            How the workshop runs in three steps
          </h2>
          {[
            {
              n: "01",
              title: "Pick a strategy template",
              body: "Mean reversion, momentum breakout, or fork your own Strategy IR.",
              icon: Layers,
            },
            {
              n: "02",
              title: "Backtest on your data",
              body: "BTC/USDT 2024 candles ship with the pack — swap to any instrument the adapter supports.",
              icon: Activity,
            },
            {
              n: "03",
              title: "Promote to paper / live",
              body: "Risk gate → 7-day paper → 30-day paper → HIL approval → live.",
              icon: ArrowRight,
            },
          ].map((s) => {
            const Icon = s.icon;
            return (
              <div
                key={s.n}
                className="rounded-md border border-line bg-bg-1/50 p-6 backdrop-blur-sm"
              >
                <div className="mb-4 flex items-center justify-between">
                  <span
                    className="font-mono-tech text-[10.5px] uppercase tracking-[2.4px]"
                    style={{ color: "var(--brand-indigo)" }}
                  >
                    {s.n}
                  </span>
                  <Icon
                    size={16}
                    strokeWidth={1.6}
                    aria-hidden="true"
                    className="text-ink-2"
                  />
                </div>
                <h3 className="mb-2 font-display text-[18px] leading-[1.2] text-ink">
                  {s.title}
                </h3>
                <p className="text-[13.5px] leading-[1.6] text-ink-2">
                  {s.body}
                </p>
              </div>
            );
          })}
        </motion.section>

        {/* Quote box — workshop description */}
        <motion.aside
          initial={{ opacity: 1, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
          className="mb-16 rounded-md border-l-2 px-7 py-7"
          style={{
            borderLeftColor: "var(--brand-violet)",
            background:
              "linear-gradient(95deg, rgba(99,102,241,0.06), rgba(139,92,246,0.04) 50%, transparent 100%)",
          }}
        >
          <p
            className="font-display text-[18px] leading-[1.45] text-ink"
            style={{ fontStyle: "italic" }}
          >
            "The algorithmic workshop runs for in-house quant teams,
            research desks, and fund partners. One day. From Strategy IR
            to a paper session under a real risk policy. By the end of
            Day 1 every attendee leaves with five playbooks running on
            their machine."
          </p>
          <p className="mt-3 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
            Wave 81 · 2026-05-10 · workshop charter
          </p>
        </motion.aside>

        {/* What you'll have at the end of Day 1 */}
        <motion.section
          initial={{ opacity: 1, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
          className="mb-16"
          aria-labelledby="workshop-playbooks-heading"
          data-tutorial-id="enterprise-playbooks"
        >
          <header className="mb-7 flex items-baseline justify-between border-b border-line pb-4">
            <h2
              id="workshop-playbooks-heading"
              className="font-display text-[26px] leading-[1.05] tracking-[-0.01em] text-ink"
            >
              What you'll have at the end of Day 1
            </h2>
            <span className="font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
              5 playbooks
            </span>
          </header>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {PLAYBOOKS.map((pb) => (
              <a
                key={pb.slug}
                href={`/playbooks/_workshop/algotrade/${pb.slug}.json`}
                aria-label={`${pb.title} (${pb.phase} phase) — open playbook JSON`}
                className="group block rounded-md border border-line bg-bg-1/40 p-5 transition-colors duration-150 hover:border-ink-3 hover:bg-bg-1/70 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)]"
              >
                <div className="mb-3 flex items-center justify-between">
                  <span
                    className="font-mono-tech text-[10px] uppercase tracking-[2.4px]"
                    style={{ color: PHASE_COLOR[pb.phase] }}
                  >
                    {pb.phase}
                  </span>
                  <ArrowRight
                    size={13}
                    strokeWidth={1.6}
                    aria-hidden="true"
                    className="text-ink-3 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-ink"
                  />
                </div>
                <h3 className="mb-2 font-display text-[16.5px] leading-[1.25] text-ink">
                  {pb.title}
                </h3>
                <p className="text-[13px] leading-[1.55] text-ink-2">
                  {pb.oneLiner}
                </p>
              </a>
            ))}
          </div>
        </motion.section>

        {/* Risk-first emphasis */}
        <motion.section
          initial={{ opacity: 1, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className="mb-16 rounded-md border border-line p-7"
          style={{
            background:
              "linear-gradient(150deg, rgba(139,92,246,0.05), rgba(6,182,212,0.04))",
          }}
          aria-labelledby="workshop-risk-heading"
          data-tutorial-id="enterprise-risk"
        >
          <header className="mb-5 flex items-center gap-3">
            <ShieldCheck
              size={18}
              strokeWidth={1.6}
              aria-hidden="true"
              style={{ color: "var(--brand-violet)" }}
            />
            <h2
              id="workshop-risk-heading"
              className="font-display text-[22px] leading-[1.05] tracking-[-0.01em] text-ink"
            >
              Live = vault-key + multi-sig confirm + daily caps
            </h2>
          </header>
          <p className="mb-6 max-w-[64ch] text-[14px] leading-[1.65] text-ink-2">
            Quant teams care about this more than any other surface, so we
            keep it on the front page. No strategy reaches the live adapter
            without crossing every one of these gates:
          </p>
          <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {[
              {
                icon: CheckCircle2,
                t: "Risk gate",
                b: "Sharpe > 1.5, max drawdown < 20% on the most recent 6 months.",
              },
              {
                icon: Activity,
                t: "30-day paper observation",
                b: "Live is not even considered before 30 green days of paper.",
              },
              {
                icon: AlertTriangle,
                t: "Human-in-the-loop",
                b: "Head of Trading gets the email — manual approve / reject.",
              },
              {
                icon: KeyRound,
                t: "Vault-key + multi-sig",
                b: "Binance v9.2 adapter refuses orders without it.",
              },
              {
                icon: Lock,
                t: "Daily caps in the loop",
                b: "kill_switch, max_position_usd, daily_loss_cap_usd — enforced inside the session, not in a wrapper.",
              },
              {
                icon: ShieldCheck,
                t: "Audit on Solana (optional)",
                b: "Weekly aggregate Merkle-rooted via wallet.anchor_memo — verifiable by compliance.",
              },
            ].map((row) => {
              const Icon = row.icon;
              return (
                <li
                  key={row.t}
                  className="flex items-start gap-3 rounded-sm border border-line/60 bg-bg-0/40 p-3"
                >
                  <Icon
                    size={14}
                    strokeWidth={1.6}
                    aria-hidden="true"
                    className="mt-1 flex-shrink-0 text-ink-2"
                  />
                  <div>
                    <div className="font-display text-[14px] leading-[1.25] text-ink">
                      {row.t}
                    </div>
                    <div className="mt-0.5 text-[12.5px] leading-[1.55] text-ink-2">
                      {row.b}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </motion.section>

        {/* Footer link */}
        <motion.footer
          initial={{ opacity: 1, y: 0 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
          className="flex flex-col items-start justify-between gap-4 border-t border-line pt-6 md:flex-row md:items-center"
          data-tutorial-id="enterprise-cta"
        >
          <p className="font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
            Need the generic onboarding?
          </p>
          <div className="flex flex-wrap items-center gap-3">
            {/* Wave 84 — pill link to ROI calculator. Quant teams ask
                "what's the dollar saving?" almost immediately; surface
                the live calculator next to the workshop fallback. */}
            <Link
              to="/workshop/roi"
              className="inline-flex items-center gap-2 rounded-sm border border-line px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-ink-2 transition-colors duration-150 hover:border-ink-3 hover:bg-bg-1/60 hover:text-ink"
            >
              ROI calculator
              <ArrowRight size={12} strokeWidth={1.8} />
            </Link>
            <Link
              to="/workshop"
              className="inline-flex items-center gap-2 rounded-sm border border-line px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-ink transition-colors duration-150 hover:border-ink-3 hover:bg-bg-1/60"
            >
              Generic 4-phase workshop wizard
              <ArrowRight size={12} strokeWidth={1.8} />
            </Link>
          </div>
        </motion.footer>
      </article>

      {/* Wave 92 — first-run interactive tour for enterprise visitors (5 steps). */}
      <WorkshopTutorial pageKey="workshop-enterprise" />
    </div>
  );
}
