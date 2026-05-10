// SYNC: claude-w108-perf
import { useState } from "react";
import type { ConnectorHealthEnvelope, ConnectorHealthRow } from "./types";

interface Props {
  data?: ConnectorHealthEnvelope;
  onTestAll?: () => void | Promise<void>;
}

function statusBadge(row: ConnectorHealthRow) {
  if (!row.configured) return { label: "not configured", color: "text-ink-3" };
  if (!row.connected) return { label: "configured · no token", color: "text-amber-300" };
  return { label: "connected", color: "text-emerald-300" };
}

export function ConnectorHealthTable({ data, onTestAll }: Props) {
  const [testing, setTesting] = useState(false);

  async function handleTest() {
    if (!onTestAll) return;
    setTesting(true);
    try {
      await onTestAll();
    } finally {
      setTesting(false);
    }
  }

  const rows = data?.connectors ?? [];

  return (
    <div className="rounded-lg border border-line bg-bg-1/40 p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2">
          Connector health
        </h3>
        {onTestAll && (
          <button
            type="button"
            onClick={handleTest}
            disabled={testing}
            className="rounded border border-line bg-bg-0/60 px-3 py-1 font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-2 transition-colors hover:border-accent/40 hover:text-accent disabled:opacity-50"
          >
            {testing ? "Testing…" : "Test all"}
          </button>
        )}
      </div>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-left text-[12px]">
          <thead>
            <tr className="border-b border-line/40 font-mono-tech text-[9px] uppercase tracking-[1.5px] text-ink-3">
              <th className="py-2">Name</th>
              <th>Status</th>
              <th>Env</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={3} className="py-4 text-center text-ink-3">
                  No connector data available
                </td>
              </tr>
            ) : (
              rows.map((row) => {
                const badge = statusBadge(row);
                return (
                  <tr key={row.name} className="border-b border-line/20">
                    <td className="py-2 text-ink">{row.label}</td>
                    <td className={`font-mono-tech text-[11px] ${badge.color}`}>{badge.label}</td>
                    <td className="font-mono-tech text-[10px] text-ink-3">
                      {row.env_vars.join(", ")}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
