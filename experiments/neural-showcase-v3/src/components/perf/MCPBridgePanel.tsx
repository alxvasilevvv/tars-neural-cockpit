// SYNC: cursor-wave-m6-cockpit
/**
 * <MCPBridgePanel /> — Wave M6.
 *
 * Operator-facing snapshot of the TARS MCP bridge:
 *   - Configured remote servers (count + names)
 *   - Registered bridged packs (slug + tool count + pooled flag)
 *   - On-disk discovery cache (server / age / freshness)
 *   - Live SessionPool stats (count + per-session age/idle/tools)
 *   - Refresh button — re-bootstraps every server on demand
 *
 * Backed by /api/mcp/bridge/{status,servers,refresh}. The router
 * gracefully degrades to ``available: false`` when the M3/M5/M6
 * modules are missing, so this panel renders an empty-state copy
 * instead of crashing on cockpit branches that don't yet have
 * the full MCP stack merged.
 */

import { useState } from "react";
import type { MCPBridgeStatusEnvelope } from "./types";

interface Props {
  data?: MCPBridgeStatusEnvelope;
  onRefresh?: () => void | Promise<void>;
}

function fmtAge(seconds: number | undefined | null): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)}m`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}d`;
}

function freshnessBadge(fresh: boolean | undefined): {
  label: string;
  color: string;
} {
  if (fresh === undefined) return { label: "?", color: "text-ink-3" };
  return fresh
    ? { label: "fresh", color: "text-emerald-300" }
    : { label: "stale", color: "text-amber-300" };
}

export function MCPBridgePanel({ data, onRefresh }: Props) {
  const [refreshing, setRefreshing] = useState(false);

  async function handleRefresh() {
    if (!onRefresh) return;
    setRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setRefreshing(false);
    }
  }

  const available = data?.available ?? false;
  const servers = data?.servers ?? [];
  const registered = data?.registered ?? [];
  const cache = data?.cache ?? [];
  const pool = data?.pool ?? null;

  return (
    <div className="rounded-lg border border-line bg-bg-1/40 p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2">
          MCP bridge
        </h3>
        {onRefresh && available && (
          <button
            type="button"
            onClick={handleRefresh}
            disabled={refreshing}
            className="rounded border border-line bg-bg-0/60 px-3 py-1 font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-2 transition-colors hover:border-accent/40 hover:text-accent disabled:opacity-50"
          >
            {refreshing ? "Refreshing…" : "Refresh all"}
          </button>
        )}
      </div>

      {!available && (
        <p className="mt-3 text-[12px] text-ink-3">
          {data?.reason ?? "MCP bridge unavailable on this build."}{" "}
          <span className="text-ink-3/70">
            Configure remote servers in <code>$TARS_HOME/mcp/servers.json</code>{" "}
            and run the bridge bootstrap to populate.
          </span>
        </p>
      )}

      {available && (
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {/* Headline counters */}
          <ul className="space-y-2 text-[12px]">
            <li className="rounded bg-bg-0/60 px-3 py-2">
              <div className="flex items-center justify-between">
                <span className="font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-3">
                  Servers configured
                </span>
                <span className="text-ink">{servers.length}</span>
              </div>
              {servers.length > 0 && (
                <p className="mt-1 font-mono-tech text-[10px] text-ink-3">
                  {servers.map((s) => s.name).join(", ")}
                </p>
              )}
            </li>
            <li className="rounded bg-bg-0/60 px-3 py-2">
              <div className="flex items-center justify-between">
                <span className="font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-3">
                  Bridged packs registered
                </span>
                <span className="text-ink">{registered.length}</span>
              </div>
              {registered.length > 0 && (
                <p className="mt-1 font-mono-tech text-[10px] text-ink-3">
                  {registered
                    .map(
                      (p) =>
                        `${p.slug} (${p.tool_count} tools${
                          p.pooled ? " · pooled" : ""
                        })`,
                    )
                    .join(" · ")}
                </p>
              )}
            </li>
            <li className="rounded bg-bg-0/60 px-3 py-2">
              <div className="flex items-center justify-between">
                <span className="font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-3">
                  Pool sessions live
                </span>
                <span className="text-ink">{pool?.count ?? 0}</span>
              </div>
              {pool?.sessions && pool.sessions.length > 0 && (
                <ul className="mt-1 space-y-0.5 font-mono-tech text-[10px] text-ink-3">
                  {pool.sessions.map((s) => (
                    <li key={s.name}>
                      {s.name} · age {fmtAge(s.age_seconds)} · idle{" "}
                      {fmtAge(s.idle_seconds)} · {s.tool_count ?? "?"} tools
                    </li>
                  ))}
                </ul>
              )}
            </li>
          </ul>

          {/* Cache table */}
          <div className="rounded bg-bg-0/60 px-3 py-2">
            <div className="font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-3">
              Discovery cache
            </div>
            <table className="mt-2 w-full text-left text-[11px]">
              <thead>
                <tr className="border-b border-line/30 font-mono-tech text-[9px] uppercase tracking-[1.5px] text-ink-3">
                  <th className="py-1">Server</th>
                  <th>Age</th>
                  <th>Tools</th>
                  <th>State</th>
                </tr>
              </thead>
              <tbody>
                {cache.length === 0 ? (
                  <tr>
                    <td
                      colSpan={4}
                      className="py-3 text-center text-ink-3"
                    >
                      Cache empty — run refresh to discover.
                    </td>
                  </tr>
                ) : (
                  cache.map((row) => {
                    const badge = freshnessBadge(row.fresh);
                    return (
                      <tr
                        key={row.server}
                        className="border-b border-line/15"
                      >
                        <td className="py-1 text-ink">{row.server}</td>
                        <td className="font-mono-tech text-[10px] text-ink-3">
                          {fmtAge(row.age_seconds)}
                        </td>
                        <td className="font-mono-tech text-[10px] text-ink-3">
                          {row.tool_count ?? "—"}
                        </td>
                        <td
                          className={`font-mono-tech text-[10px] ${badge.color}`}
                        >
                          {badge.label}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
