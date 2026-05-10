/**
 * Wave 85 — Workshop recipe library (discovery surface).
 *
 * Hand-maintained mirror of every JSON playbook under
 * ``playbooks/_workshop/algotrade/*.json`` and
 * ``playbooks/_workshop/quant/*.json``. The frontend doesn't read the
 * filesystem — Cursor owns ``backend/*`` and the playbook loader, and
 * the `/workshop/materials` hub needs an inventory it can render
 * without a network round-trip. So we mirror metadata here, by hand.
 *
 * IMPORTANT: this is the discovery surface. When a new workshop
 * playbook lands under ``playbooks/_workshop/{algotrade,quant}/``,
 * append a matching entry below. The CI a11y test snapshots this
 * length; if it disagrees with the filesystem the snapshot diff will
 * scream.
 *
 * `path` is the source-of-truth filesystem path (relative to the
 * repo root) — the materials hub displays it as a copy-able hint so
 * an attendee on a CLI can `cat` the recipe directly.
 */

export type WorkshopVertical = "algotrade" | "quant";

export interface WorkshopRecipe {
  /** Stable id — matches the `id` field in the playbook JSON. */
  id: string;
  /** Vertical the recipe ships under. Drives card accent colour. */
  vertical: WorkshopVertical;
  /** Display name (matches `name` in JSON). */
  name: string;
  /** One-sentence "what does this teach" (matches `_meta.teaches`). */
  teaches: string;
  /** Repo-relative path to the JSON file. */
  path: string;
  /** `_meta.estimated_runtime_seconds` — surfaced as a chip on the card. */
  estimatedRuntime: number;
}

export const RECIPE_LIBRARY: WorkshopRecipe[] = [
  // ── algotrade pack ──────────────────────────────────────────────
  {
    id: "_workshop.algotrade.mean_reversion_strategy",
    vertical: "algotrade",
    name: "Mean reversion (Bollinger + RSI)",
    teaches:
      "How to compose a mean-reversion Strategy IR (Bollinger lower-band + RSI oversold), backtest it on BTC/USDT 1h candles, then promote to a 7-day paper session under a strict risk policy.",
    path: "playbooks/_workshop/algotrade/mean_reversion_strategy.json",
    estimatedRuntime: 45,
  },
  {
    id: "_workshop.algotrade.momentum_breakout_strategy",
    vertical: "algotrade",
    name: "Momentum trend follower (MA cross + trailing)",
    teaches:
      "How to design a momentum trend-follower (MA crossover with trailing stop), backtest on BTC/USDT 1h, and ship to paper with a hardened risk policy.",
    path: "playbooks/_workshop/algotrade/momentum_breakout_strategy.json",
    estimatedRuntime: 45,
  },
  {
    id: "_workshop.algotrade.live_paper_session",
    vertical: "algotrade",
    name: "Live paper session (strict risk)",
    teaches:
      "How to start a paper trading session under a strict risk policy (kill_switch on, $1k position cap, $50 daily loss cap) and watch the 15-minute monitor.",
    path: "playbooks/_workshop/algotrade/live_paper_session.json",
    estimatedRuntime: 60,
  },
  {
    id: "_workshop.algotrade.backtest_to_live_pipeline",
    vertical: "algotrade",
    name: "Backtest → paper → live promotion",
    teaches:
      "End-to-end promotion pipeline: pick a registered strategy, re-backtest it, gate on Sharpe>1.5, run a 30-day paper, then human-approval before mock live.",
    path: "playbooks/_workshop/algotrade/backtest_to_live_pipeline.json",
    estimatedRuntime: 300,
  },
  {
    id: "_workshop.algotrade.risk_audit_weekly",
    vertical: "algotrade",
    name: "Risk audit (weekly)",
    teaches:
      "How to run a weekly compliance audit across every algotrade session: read the JSONL ledger, summarise breaches, email compliance, and anchor on Solana.",
    path: "playbooks/_workshop/algotrade/risk_audit_weekly.json",
    estimatedRuntime: 90,
  },

  // ── quant pack ──────────────────────────────────────────────────
  {
    id: "_workshop.quant.recipe_to_paper",
    vertical: "quant",
    name: "Recipe → register → paper session",
    teaches:
      "The full lifecycle hello-world: load a starter recipe, register it in the local strategy registry, then start a 24h paper session.",
    path: "playbooks/_workshop/quant/recipe_to_paper.json",
    estimatedRuntime: 15,
  },
  {
    id: "_workshop.quant.strategy_lab",
    vertical: "quant",
    name: "Strategy lab — fork → backtest → register",
    teaches:
      "Mid-workshop strategy lab: fork a recipe, override a parameter (instrument or timeframe), backtest the variant, and persist it back as a child of the parent in the registry.",
    path: "playbooks/_workshop/quant/strategy_lab.json",
    estimatedRuntime: 25,
  },
  {
    id: "_workshop.quant.backtest_compare",
    vertical: "quant",
    name: "Backtest A/B compare",
    teaches:
      "How to A/B two strategy variants on the same data so attendees see deterministic Sharpe / drawdown / hit-rate side by side.",
    path: "playbooks/_workshop/quant/backtest_compare.json",
    estimatedRuntime: 35,
  },
  {
    id: "_workshop.quant.morning_pnl",
    vertical: "quant",
    name: "Morning PnL sweep (07:00 weekdays)",
    teaches:
      "Daily quant ops: how to pull a live PnL strip across every paper session, surface laggards, and prep the morning desk note.",
    path: "playbooks/_workshop/quant/morning_pnl.json",
    estimatedRuntime: 12,
  },
  {
    id: "_workshop.quant.risk_review",
    vertical: "quant",
    name: "Risk review (per session)",
    teaches:
      "How to audit a session: pull its risk policy + recent audit ledger, look for triggers, and decide pause/continue.",
    path: "playbooks/_workshop/quant/risk_review.json",
    estimatedRuntime: 10,
  },
];

/**
 * Convenience grouping for the materials hub renderer.
 */
export function recipesByVertical(): Record<WorkshopVertical, WorkshopRecipe[]> {
  return {
    algotrade: RECIPE_LIBRARY.filter((r) => r.vertical === "algotrade"),
    quant: RECIPE_LIBRARY.filter((r) => r.vertical === "quant"),
  };
}
