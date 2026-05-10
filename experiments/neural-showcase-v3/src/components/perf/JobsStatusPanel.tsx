// SYNC: claude-w108-perf
import type { JobsEnvelope } from "./types";

interface Props {
  data?: JobsEnvelope;
}

function fmtSeconds(s?: number | null): string {
  if (s === null || s === undefined) return "—";
  if (s < 0) return "due";
  if (s < 60) return `${s.toFixed(0)}s`;
  if (s < 3600) return `${(s / 60).toFixed(1)}m`;
  return `${(s / 3600).toFixed(1)}h`;
}

export function JobsStatusPanel({ data }: Props) {
  return (
    <div className="rounded-lg border border-line bg-bg-1/40 p-4">
      <h3 className="font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2">
        Background jobs
      </h3>
      <ul className="mt-3 space-y-2 text-[12px]">
        <li className="rounded bg-bg-0/60 px-3 py-2">
          <div className="flex items-center justify-between">
            <span className="font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-3">
              Scheduler
            </span>
            <span className="text-ink-2">
              {data?.scheduler.available
                ? `${data.scheduler.enabled_count ?? 0}/${data.scheduler.schedule_count ?? 0} enabled`
                : data?.scheduler.reason || "disabled"}
            </span>
          </div>
          {data?.scheduler.available && (
            <p className="mt-1 text-[10px] text-ink-3">
              tick {data.scheduler.tick_interval_s ?? "?"}s · next run in{" "}
              <span className="text-ink-2">
                {fmtSeconds(data.scheduler.next_run_in_s)}
              </span>
            </p>
          )}
        </li>
        <li className="rounded bg-bg-0/60 px-3 py-2">
          <div className="flex items-center justify-between">
            <span className="font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-3">
              Reflection loop
            </span>
            <span className="text-ink-2">
              {data?.reflection.enabled ? "enabled" : "disabled"}
            </span>
          </div>
          {data?.reflection.interval_s !== null && data?.reflection.interval_s !== undefined && (
            <p className="mt-1 text-[10px] text-ink-3">
              interval {data.reflection.interval_s}s
            </p>
          )}
        </li>
        <li className="rounded bg-bg-0/60 px-3 py-2">
          <div className="flex items-center justify-between">
            <span className="font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-3">
              Autopilot
            </span>
            <span className="text-ink-2">
              {data?.autopilot.enabled ? "enabled" : "disabled"}
            </span>
          </div>
          {data?.autopilot.tick_s !== null && data?.autopilot.tick_s !== undefined && (
            <p className="mt-1 text-[10px] text-ink-3">tick {data.autopilot.tick_s}s</p>
          )}
        </li>
      </ul>
    </div>
  );
}
