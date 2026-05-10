// SYNC: claude-w80-fe-only
/**
 * <Compliance /> — Wave 80-D
 *
 * Receipts feed + verifier route. Polls /api/audit/list every 5s
 * (configurable), filters client-side by $-threshold, time range,
 * actor, and action type. Backend hand-off contract:
 *
 *   GET  /api/audit/list?since=<unix>&until=<unix>
 *        → { rows: AuditRow[], next_cursor?: string }
 *   GET  /api/audit/export?format=csv  → text/csv stream
 *   POST /api/receipts/verify          → see <ReceiptVerifier />
 *
 * Backend missing → mock 24h of plausible audit data so the page
 * still demos to compliance officers / regulators without a
 * production daemon.
 *
 * URL surface:
 *   /compliance               → full feed, default filters
 *   /compliance?agent=<id>    → pre-filter actor=agent:<id>
 *   /compliance#verify        → scrolls to <ReceiptVerifier />
 *
 * Page chrome mirrors /settings: corner-frame back-link, eyebrow,
 * display-md headline, status lozenge for live count.
 */

import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Download,
  RefreshCcw,
  ShieldCheck,
} from "lucide-react";
import { useDocumentMeta } from "@/lib/meta";
import { CornerFrame, StatusLozenge } from "@/components/Glyphs";
import { BrandHairline } from "@/components/BrandHairline";
import { API_BASE } from "@/lib/api";
import {
  ComplianceLog,
  type AuditRow,
} from "@/components/compliance/ComplianceLog";
import { ReceiptVerifier } from "@/components/compliance/ReceiptVerifier";

type RangeKey = "24h" | "7d" | "30d" | "custom";

const RANGE_MS: Record<Exclude<RangeKey, "custom">, number> = {
  "24h": 24 * 60 * 60 * 1000,
  "7d": 7 * 24 * 60 * 60 * 1000,
  "30d": 30 * 24 * 60 * 60 * 1000,
};

const ACTION_OPTIONS = [
  { value: "all",            label: "all actions" },
  { value: "agent.score",    label: "agent.score" },
  { value: "agent.run",      label: "agent.run" },
  { value: "playbook.run",   label: "playbook.run" },
  { value: "wallet.spend",   label: "wallet.spend" },
  { value: "policy.confirm", label: "policy.confirm" },
];

/* ─── Mock generator — only used when backend returns 404 ───────── */

function makeMock(now: number): AuditRow[] {
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
    const ts = now - Math.round(Math.random() * RANGE_MS["7d"]);
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

export function Compliance() {
  useDocumentMeta({
    title: "Compliance · TARS",
    description:
      "Signed action receipts, $-impact filters, and one-click signature verifier.",
  });

  const [params, setParams] = useSearchParams();
  const agentFilter = params.get("agent");

  const [allRows, setAllRows] = useState<AuditRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [lastFetched, setLastFetched] = useState<number | null>(null);

  // Filters
  const [minDollar, setMinDollar] = useState<number>(0);
  const [range, setRange] = useState<RangeKey>("7d");
  const [actor, setActor] = useState<string>(
    agentFilter ? `agent:${agentFilter}` : "",
  );
  const [actionType, setActionType] = useState<string>("all");

  // Wave 95 — unified receipt ledger surface: Merkle root pill
  // for today + on-demand chain integrity check.
  type ChainState =
    | { kind: "idle" }
    | { kind: "checking" }
    | { kind: "ok"; count: number; day: string }
    | { kind: "fail"; reason: string; day: string; index?: number };
  const [chainState, setChainState] = useState<ChainState>({ kind: "idle" });
  const [merkleToday, setMerkleToday] = useState<{
    day_iso: string;
    root_hex: string;
    leaf_count: number;
    anchored_at: number | null;
  } | null>(null);


  const fetchAudit = async (signal?: AbortSignal) => {
    try {
      const r = await fetch(`${API_BASE}/api/audit/list`, { signal });
      if (r.status === 404) {
        setAllRows(makeMock(Date.now()));
        setPending(true);
        return;
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = (await r.json()) as { rows?: AuditRow[] };
      setAllRows(body.rows ?? []);
      setPending(false);
    } catch {
      // Offline / abort — fall back to mock so the page is usable.
      setAllRows(makeMock(Date.now()));
      setPending(true);
    } finally {
      setLoading(false);
      setLastFetched(Date.now());
    }
  };

  useEffect(() => {
    const ctrl = new AbortController();
    void fetchAudit(ctrl.signal);
    const id = window.setInterval(
      () => void fetchAudit(),
      5_000,
    );
    return () => {
      ctrl.abort();
      window.clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Wave 95 — fetch today's Merkle root for the header pill. Fires
  // once on mount; the daemon caches per-day so the request is cheap.
  useEffect(() => {
    const ctrl = new AbortController();
    void (async () => {
      try {
        const r = await fetch(`${API_BASE}/api/receipts/merkle/today`, {
          signal: ctrl.signal,
        });
        if (!r.ok) return;
        const body = await r.json();
        if (body && body.day_iso) setMerkleToday(body);
      } catch {
        /* offline — pill stays hidden */
      }
    })();
    return () => ctrl.abort();
  }, []);

  const verifyChainToday = async () => {
    setChainState({ kind: "checking" });
    try {
      const r = await fetch(
        `${API_BASE}/api/receipts/chain/verify?day=today`,
      );
      if (!r.ok) {
        setChainState({
          kind: "fail",
          reason: `daemon HTTP ${r.status}`,
          day: "today",
        });
        return;
      }
      const body = await r.json();
      if (body.ok) {
        setChainState({
          kind: "ok",
          count: body.count ?? 0,
          day: body.day ?? "today",
        });
      } else {
        setChainState({
          kind: "fail",
          reason: body.reason ?? "chain_invalid",
          day: body.day ?? "today",
          index: body.broken_at_index,
        });
      }
    } catch (e) {
      setChainState({
        kind: "fail",
        reason: (e as Error).message,
        day: "today",
      });
    }
  };

  // Sync `?agent=…` param into the actor filter on URL change.
  useEffect(() => {
    if (agentFilter) setActor(`agent:${agentFilter}`);
  }, [agentFilter]);

  const filtered = useMemo(() => {
    const now = Date.now();
    const since =
      range === "custom" ? 0 : now - RANGE_MS[range as Exclude<RangeKey, "custom">];
    const actorL = actor.trim().toLowerCase();
    const action = actionType === "all" ? null : actionType;
    return allRows.filter((r) => {
      if (Math.abs(r.cost_usd) < minDollar) return false;
      if (r.ts < since) return false;
      if (actorL && !r.actor.toLowerCase().includes(actorL)) return false;
      if (action && r.action !== action) return false;
      return true;
    });
  }, [allRows, minDollar, range, actor, actionType]);

  const stats = useMemo(() => {
    const verified = filtered.filter((r) => r.sig_verified).length;
    const totalImpact = filtered.reduce(
      (acc, r) => acc + Math.abs(r.cost_usd),
      0,
    );
    return {
      count: filtered.length,
      verified,
      pctVerified: filtered.length === 0 ? 1 : verified / filtered.length,
      totalImpact,
    };
  }, [filtered]);

  const handleExport = () => {
    // Try the backend stream first; fall back to client-side CSV from
    // the currently-filtered rows so the operator always gets a file.
    const url = `${API_BASE}/api/audit/export?format=csv`;
    if (pending) {
      // Backend missing — emit local CSV.
      const csv = toCsv(filtered);
      const blob = new Blob([csv], { type: "text/csv" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `tars-audit-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
    } else {
      window.location.href = url;
    }
  };

  const clearAgentFilter = () => {
    const sp = new URLSearchParams(params);
    sp.delete("agent");
    setParams(sp, { replace: true });
    setActor("");
  };

  return (
    <section className="relative z-10 mx-auto max-w-[1200px] px-6 pb-24 pt-32 md:px-12">
      <div className="relative mb-6">
        <CornerFrame />
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3 transition-colors hover:text-ink"
        >
          <ArrowLeft size={11} strokeWidth={2} aria-hidden />
          <span>back</span>
        </Link>
      </div>

      <header className="mb-10 grid gap-6 md:grid-cols-[1fr_auto] md:items-end">
        <div>
          <div className="mb-3 inline-flex items-center gap-2.5 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
            <ShieldCheck
              size={12}
              strokeWidth={1.7}
              aria-hidden
              style={{ color: "var(--brand-cyan)" }}
            />
            <span>compliance</span>
          </div>
          <h1
            className="font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
            style={{ fontSize: "var(--text-display-md)" }}
          >
            Every action, signed.
          </h1>
          <p className="mt-3 max-w-[60ch] font-mono-tech text-[12px] leading-[1.6] text-ink-2">
            The receipts feed below is what auditors review. Filter by
            cost-impact, time, actor, action, then export to CSV. Paste a
            receipt at the bottom to verify any signature out-of-band.
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <StatusLozenge
            label={`${stats.count} receipts`}
            tone={pending ? "muted" : "accent"}
          />
          <span className="font-mono-tech text-[9.5px] uppercase tracking-[1.6px] text-ink-3">
            {pending ? "mock data · backend WIP" : "live"}
            {lastFetched
              ? ` · refreshed ${new Date(lastFetched).toLocaleTimeString()}`
              : ""}
          </span>
          {merkleToday && merkleToday.root_hex && (
            <span
              className="mt-1 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono-tech text-[9.5px] uppercase tracking-[1.6px]"
              style={{
                borderColor: merkleToday.anchored_at
                  ? "var(--color-success)"
                  : "var(--brand-cyan)",
                color: merkleToday.anchored_at
                  ? "var(--color-success)"
                  : "var(--brand-cyan)",
              }}
              title={`day ${merkleToday.day_iso} · ${merkleToday.leaf_count} receipts`}
            >
              merkle · {merkleToday.root_hex.slice(0, 10)}…
              {merkleToday.anchored_at ? " · anchored" : ""}
            </span>
          )}
          <button
            type="button"
            onClick={() => void verifyChainToday()}
            disabled={chainState.kind === "checking"}
            className="mt-1 inline-flex items-center gap-1.5 rounded-md border border-line-strong bg-bg-2/60 px-2.5 py-1 font-mono-tech text-[9.5px] uppercase tracking-[1.6px] text-ink transition-colors hover:border-accent disabled:opacity-50"
          >
            {chainState.kind === "checking"
              ? "verifying…"
              : chainState.kind === "ok"
                ? `chain ok · ${chainState.count}`
                : chainState.kind === "fail"
                  ? `chain BROKEN @ ${chainState.index ?? "?"}`
                  : "verify chain integrity"}
          </button>
        </div>
      </header>

      <BrandHairline variant="static" />

      {pending && (
        <p
          role="status"
          className="mt-6 inline-flex items-start gap-2 rounded-md border border-amber-400/30 bg-amber-400/[0.06] px-3 py-2 text-[11.5px] leading-[1.5] text-amber-200"
        >
          <RefreshCcw size={12} strokeWidth={1.7} aria-hidden className="mt-0.5" />
          <span>
            Backend WIP — Cursor shipping audit endpoints. Showing 24h of mock
            data so the console stays demo-able.
          </span>
        </p>
      )}

      {agentFilter && (
        <p className="mt-4 inline-flex items-center gap-2 rounded-full border border-line/60 bg-bg-2/40 px-3 py-1 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink-2">
          <span>filtering · agent {agentFilter}</span>
          <button
            type="button"
            onClick={clearAgentFilter}
            className="text-ink-3 transition-colors hover:text-ink"
            aria-label="clear agent filter"
          >
            ×
          </button>
        </p>
      )}

      <motion.section
        initial={{ opacity: 1 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3 }}
        className="mt-8 grid gap-6"
      >
        {/* ── Filters strip ──────────────────────────────────── */}
        <div className="grid gap-4 rounded-[12px] border border-line/60 bg-bg-1/40 p-4 md:grid-cols-[1.3fr_1fr_1fr_1.3fr_auto]">
          <label className="grid gap-1.5">
            <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
              $ threshold · ≥ ${minDollar.toFixed(2)}
            </span>
            <input
              type="range"
              min={0}
              max={50}
              step={0.5}
              value={minDollar}
              onChange={(e) => setMinDollar(parseFloat(e.target.value))}
              className="accent-[color:var(--color-accent)]"
              aria-label="minimum dollar impact"
            />
          </label>
          <label className="grid gap-1.5">
            <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
              time range
            </span>
            <select
              value={range}
              onChange={(e) => setRange(e.target.value as RangeKey)}
              className="rounded-md border border-line/60 bg-bg-0/50 px-3 py-2 font-mono-tech text-[11.5px] text-ink outline-none focus:border-accent"
            >
              <option value="24h">last 24h</option>
              <option value="7d">last 7 days</option>
              <option value="30d">last 30 days</option>
              <option value="custom">all time</option>
            </select>
          </label>
          <label className="grid gap-1.5">
            <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
              action type
            </span>
            <select
              value={actionType}
              onChange={(e) => setActionType(e.target.value)}
              className="rounded-md border border-line/60 bg-bg-0/50 px-3 py-2 font-mono-tech text-[11.5px] text-ink outline-none focus:border-accent"
            >
              {ACTION_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1.5">
            <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
              actor
            </span>
            <input
              value={actor}
              onChange={(e) => setActor(e.target.value)}
              placeholder="agent:… or operator:email"
              className="rounded-md border border-line/60 bg-bg-0/50 px-3 py-2 font-mono-tech text-[11.5px] text-ink outline-none focus:border-accent"
            />
          </label>
          <button
            type="button"
            onClick={handleExport}
            className="inline-flex items-center gap-2 self-end rounded-md border border-line-strong bg-bg-2/60 px-3 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink transition-colors hover:border-accent"
          >
            <Download size={12} strokeWidth={1.7} aria-hidden />
            export csv
          </button>
        </div>

        {/* ── Aggregate strip ────────────────────────────────── */}
        <div className="grid grid-cols-3 gap-3 rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
          <Stat
            label="receipts (filtered)"
            value={String(stats.count)}
            accent="var(--brand-indigo)"
          />
          <Stat
            label="signatures verified"
            value={`${Math.round(stats.pctVerified * 100)}%`}
            accent={
              stats.pctVerified === 1 ? "var(--color-success)" : "var(--brand-amber)"
            }
          />
          <Stat
            label="$ impact (abs)"
            value={`$${stats.totalImpact.toFixed(2)}`}
            accent="var(--brand-cyan)"
          />
        </div>

        {/* ── The actual feed ────────────────────────────────── */}
        <ComplianceLog rows={filtered} loading={loading} />

        {/* ── Verifier ───────────────────────────────────────── */}
        <ReceiptVerifier />
      </motion.section>
    </section>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div>
      <span className="font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
        {label}
      </span>
      <p
        className="mt-1 font-display text-[22px] leading-none text-ink"
        style={{ color: accent }}
      >
        {value}
      </p>
    </div>
  );
}

function toCsv(rows: AuditRow[]): string {
  const header = "id,ts,actor,action,resource,cost_usd,sig_verified";
  const escape = (v: string) =>
    /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
  const body = rows
    .map((r) =>
      [
        r.id,
        new Date(r.ts).toISOString(),
        escape(r.actor),
        escape(r.action),
        escape(r.resource),
        r.cost_usd.toFixed(4),
        r.sig_verified ? "1" : "0",
      ].join(","),
    )
    .join("\n");
  return `${header}\n${body}\n`;
}

export default Compliance;
