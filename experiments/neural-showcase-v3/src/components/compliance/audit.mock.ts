/**
 * audit.mock — Wave 124 split out of /pages/Compliance.tsx.
 * Plausible 60-row receipts dataset for when the backend is offline.
 * Pure function; no side effects.
 */

import type { AuditRow } from "@/components/compliance/ComplianceLog";

const RANGE_MS_7D = 7 * 24 * 60 * 60 * 1000;

export function makeMock(now: number): AuditRow[] {
  const actors = [
    "agent:trader-01",
    "agent:research-02",
    "agent:portfolio-03",
    "operator:alice@acme.io",
    "operator:bob@acme.io",
  ];
  const actions = [
    "agent.score",
    "agent.run",
    "playbook.run",
    "wallet.spend",
    "policy.confirm",
  ];
  const resources = [
    "WBTC", "ETH", "AAPL", "SOL",
    "playbook:daily-brief",
    "agent:trader-01",
    "schedule:weekday-9am",
    "file:portfolio.csv",
  ];
  const out: AuditRow[] = [];
  for (let i = 0; i < 60; i++) {
    const ts = now - Math.round(Math.random() * RANGE_MS_7D);
    const a = actions[i % actions.length];
    const isSpend = a === "wallet.spend";
    out.push({
      id: `mock-${i}`,
      ts,
      actor: actors[i % actors.length],
      action: a,
      resource: resources[i % resources.length],
      cost_usd: isSpend
        ? +(Math.random() * 30).toFixed(3)
        : a === "agent.score"
          ? +(Math.random() * 0.05).toFixed(4)
          : 0,
      sig_verified: i % 17 !== 0, // ~6% invalid for demo
      payload: {
        trace_id: `tr-${i.toString().padStart(4, "0")}`,
        action: a,
        notes: "mock receipt — backend WIP",
      },
    });
  }
  return out.sort((a, b) => b.ts - a.ts);
}

export default makeMock;
