/**
 * UsageStrip — token + USD ledger for the cockpit.
 *
 * Surfaces the K2/K3 cost ledger:
 * - Header counters (calls / tokens-in-out / total cost).
 * - Per-route breakdown (edge vs cloud vs fallback) — shows where compute
 *   is actually crossing the boundary.
 * - Per-model breakdown — quick "who's expensive" leaderboard.
 *
 * Polls /api/usage every 8s. No animations / heavy deps — the visual
 * polish is Claude's lane; this is the data wiring.
 */

import { useUsageRollup } from "@/lib/usage";

function fmtUsd(n: number): string {
  if (!Number.isFinite(n) || n === 0) return "$0.000";
  if (Math.abs(n) < 0.001) return `$${n.toFixed(6)}`;
  if (Math.abs(n) < 1) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(2)}`;
}

function fmtTok(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

const ROUTE_LABELS: Record<string, string> = {
  edge: "edge · local",
  cloud: "cloud · LLM",
  fallback: "fallback · degraded",
  mixed: "mixed",
  "(unset)": "untagged",
};

const ROUTE_TONE: Record<string, string> = {
  edge: "text-ink",
  cloud: "text-accent",
  fallback: "text-alert",
  mixed: "text-ink-2",
  "(unset)": "text-ink-3",
};

function bucketLatencyAvg(latencyTotal: number, calls: number): string {
  if (!calls) return "—";
  return `${Math.round(latencyTotal / calls)}ms`;
}

export function UsageStrip({ sessionId }: { sessionId?: string } = {}) {
  const { data, error, loading } = useUsageRollup({ sessionId });
  const total = data?.total_calls ?? 0;
  const cost = data?.total_cost_usd ?? 0;

  return (
    <section className="mt-6 rounded-[14px] border border-line bg-bg-1 p-5">
      <header className="mb-3 flex flex-wrap items-baseline justify-between gap-3 font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
        <span>usage · cost ledger // {total} calls</span>
        <span className="text-ink-3">
          {sessionId ? `session ${sessionId}` : "all sessions"}
          {loading ? " · loading" : ""}
          {error ? ` · ${error.message}` : ""}
        </span>
      </header>

      <div className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_1fr]">
        <Counter label="calls" value={total.toString()} />
        <Counter
          label="tokens in"
          value={fmtTok(data?.total_tokens_in ?? 0)}
        />
        <Counter
          label="tokens out"
          value={fmtTok(data?.total_tokens_out ?? 0)}
        />
        <Counter
          label="USD"
          value={fmtUsd(cost)}
          accent={cost > 0 ? "accent" : "muted"}
        />
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <BucketTable
          title="by route"
          buckets={data?.by_route ?? {}}
          renderKey={(k) => (
            <span className={ROUTE_TONE[k] ?? "text-ink-2"}>
              {ROUTE_LABELS[k] ?? k}
            </span>
          )}
        />
        <BucketTable
          title="by model"
          buckets={data?.by_model ?? {}}
          renderKey={(k) => <span className="text-accent">{k}</span>}
        />
      </div>
    </section>
  );
}

function Counter({
  label,
  value,
  accent = "default",
}: {
  label: string;
  value: string;
  accent?: "default" | "accent" | "muted";
}) {
  const tone =
    accent === "accent"
      ? "text-accent"
      : accent === "muted"
        ? "text-ink-3"
        : "text-ink";
  return (
    <div className="rounded border border-line bg-[rgba(0,0,0,0.4)] p-3">
      <div className="font-mono-tech text-[9px] uppercase tracking-[1.8px] text-ink-3">
        {label}
      </div>
      <div className={`mt-1 font-display text-[20px] tracking-[-0.01em] ${tone}`}>
        {value}
      </div>
    </div>
  );
}

interface BucketLike {
  calls: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  latency_ms_total: number;
}

function BucketTable({
  title,
  buckets,
  renderKey,
}: {
  title: string;
  buckets: Record<string, BucketLike>;
  renderKey: (key: string) => React.ReactNode;
}) {
  const entries = Object.entries(buckets).sort(
    (a, b) => b[1].calls - a[1].calls,
  );
  return (
    <div className="rounded border border-line bg-[rgba(0,0,0,0.4)] p-3">
      <div className="mb-2 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-2">
        {title}
      </div>
      {entries.length === 0 ? (
        <p className="font-mono-tech text-[10.5px] text-ink-3">
          no calls in window
        </p>
      ) : (
        <table className="w-full font-mono-tech text-[10.5px] text-ink-2">
          <thead>
            <tr className="text-ink-3">
              <th className="text-left font-normal">key</th>
              <th className="text-right font-normal">calls</th>
              <th className="text-right font-normal">in</th>
              <th className="text-right font-normal">out</th>
              <th className="text-right font-normal">avg ms</th>
              <th className="text-right font-normal">USD</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([k, b]) => (
              <tr key={k} className="border-t border-line/40">
                <td className="py-1 pr-2">{renderKey(k)}</td>
                <td className="py-1 text-right">{b.calls}</td>
                <td className="py-1 text-right">{fmtTok(b.tokens_in)}</td>
                <td className="py-1 text-right">{fmtTok(b.tokens_out)}</td>
                <td className="py-1 text-right">
                  {bucketLatencyAvg(b.latency_ms_total, b.calls)}
                </td>
                <td className="py-1 text-right text-ink">{fmtUsd(b.cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
