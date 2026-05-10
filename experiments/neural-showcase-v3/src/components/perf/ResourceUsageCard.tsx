// SYNC: claude-w108-perf
import type { ResourceUsageEnvelope } from "./types";

interface Props {
  data?: ResourceUsageEnvelope;
}

function fmtBytes(n?: number | null): string {
  if (n === null || n === undefined) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = n;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value.toFixed(1)} ${units[i]}`;
}

export function ResourceUsageCard({ data }: Props) {
  if (!data || !data.available) {
    return (
      <div className="rounded-lg border border-line bg-bg-1/40 p-4">
        <h3 className="font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2">
          Resource usage
        </h3>
        <p className="mt-3 text-[12px] text-ink-3">
          {data?.reason === "psutil_not_installed"
            ? "psutil not installed — pip install psutil for host metrics."
            : data?.reason || "Resource data unavailable."}
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-line bg-bg-1/40 p-4">
      <h3 className="font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2">
        Resource usage
      </h3>
      <ul className="mt-3 space-y-2 text-[12px]">
        <li className="flex items-center justify-between">
          <span className="text-ink-3">CPU</span>
          <span className="font-mono-tech tabular-nums text-ink">
            {(data.cpu_percent ?? 0).toFixed(1)}%
          </span>
        </li>
        <li className="flex items-center justify-between">
          <span className="text-ink-3">Memory</span>
          <span className="font-mono-tech tabular-nums text-ink">
            {fmtBytes(data.memory?.used)} / {fmtBytes(data.memory?.total)} (
            {(data.memory?.percent ?? 0).toFixed(0)}%)
          </span>
        </li>
        <li className="flex items-center justify-between">
          <span className="text-ink-3">Disk (~/.tars)</span>
          <span className="font-mono-tech tabular-nums text-ink">
            {fmtBytes(data.disk?.used)} used · {fmtBytes(data.disk?.free)} free
          </span>
        </li>
      </ul>
    </div>
  );
}
