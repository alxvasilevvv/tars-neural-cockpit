// SYNC: claude-w108-perf
import type { LatencyStats } from "./types";

interface Props {
  title: string;
  stats?: LatencyStats;
}

function fmt(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value >= 1000) return `${(value / 1000).toFixed(2)}s`;
  return `${value.toFixed(0)}ms`;
}

export function LatencyCard({ title, stats }: Props) {
  const count = stats?.count ?? 0;
  return (
    <div className="rounded-lg border border-line bg-bg-1/40 p-4">
      <div className="flex items-baseline justify-between">
        <h3 className="font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2">{title}</h3>
        <span className="font-mono-tech text-[10px] text-ink-3">n={count}</span>
      </div>
      <div className="mt-3 grid grid-cols-4 gap-2 text-center">
        {([
          ["P50", stats?.p50],
          ["P95", stats?.p95],
          ["P99", stats?.p99],
          ["Max", stats?.max],
        ] as Array<[string, number | null | undefined]>).map(([label, value]) => (
          <div key={label} className="rounded bg-bg-0/60 px-2 py-2">
            <div className="font-mono-tech text-[9px] uppercase tracking-[1.5px] text-ink-3">{label}</div>
            <div className="mt-1 font-mono-tech text-[13px] tabular-nums text-ink">{fmt(value)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
