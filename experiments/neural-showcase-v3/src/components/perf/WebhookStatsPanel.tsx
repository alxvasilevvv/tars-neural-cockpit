// SYNC: claude-w108-perf
import type { WebhookStatsEnvelope } from "./types";

interface Props {
  data?: WebhookStatsEnvelope;
  onReplay?: (deliveryId: string) => void | Promise<void>;
}

export function WebhookStatsPanel({ data, onReplay }: Props) {
  if (!data || !data.available) {
    return (
      <div className="rounded-lg border border-line bg-bg-1/40 p-4">
        <h3 className="font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2">Webhooks</h3>
        <p className="mt-3 text-[12px] text-ink-3">
          {data?.reason === "disabled"
            ? "Webhooks module disabled (set TARS_WEBHOOKS_ENABLED=1)."
            : "No webhook data available."}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-line bg-bg-1/40 p-4">
      <h3 className="font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2">
        Webhook deliveries
      </h3>
      <div className="mt-3 grid grid-cols-4 gap-2">
        {[
          ["Total", data.total ?? 0, "text-ink"],
          ["Success", data.success ?? 0, "text-emerald-300"],
          ["Retrying", data.retrying ?? 0, "text-amber-300"],
          ["Failed", data.failed ?? 0, "text-rose-300"],
        ].map(([label, value, color]) => (
          <div key={label as string} className="rounded bg-bg-0/60 px-2 py-2 text-center">
            <div className="font-mono-tech text-[9px] uppercase tracking-[1.5px] text-ink-3">{label}</div>
            <div className={`mt-1 font-mono-tech text-[14px] tabular-nums ${color}`}>{value}</div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[10px] text-ink-3">
        Avg signature compute:{" "}
        <span className="text-ink-2">
          {data.avg_signature_ms !== null && data.avg_signature_ms !== undefined
            ? `${data.avg_signature_ms.toFixed(2)}ms`
            : "—"}
        </span>
      </p>
      {data.failed_recent && data.failed_recent.length > 0 && (
        <div className="mt-3 max-h-40 overflow-auto rounded border border-line/40">
          <table className="w-full text-left text-[11px]">
            <thead>
              <tr className="border-b border-line/40 font-mono-tech text-[9px] uppercase tracking-[1.5px] text-ink-3">
                <th className="px-2 py-1">Event</th>
                <th>Error</th>
                <th>Tries</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.failed_recent.map((row) => (
                <tr key={row.id} className="border-b border-line/20">
                  <td className="px-2 py-1 font-mono-tech text-ink-2">{row.event_type}</td>
                  <td className="text-rose-200">{row.last_error || "—"}</td>
                  <td className="text-ink-3">{row.attempts}</td>
                  <td className="px-2 text-right">
                    {onReplay && (
                      <button
                        type="button"
                        onClick={() => void onReplay(row.id)}
                        className="rounded border border-line px-2 py-0.5 font-mono-tech text-[10px] text-ink-2 hover:border-accent hover:text-accent"
                      >
                        replay
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
