/**
 * Operator strip — barebones surface for the post-Phase-K endpoints.
 *
 * Functionally complete: pending-confirmation row, playbook runner,
 * meeet bridge badge, vault-status badges, council on-demand widget.
 *
 * Visual layer is intentionally minimal — Claude polishes the look.
 */

import { useState } from "react";

import { useDeliberation } from "@/lib/council";
import { useMeeetEvents, useMeeetHealth } from "@/lib/meeet";
import { usePlaybooks, usePlaybookRun } from "@/lib/playbooks";
import {
  cancelToken,
  confirmToken,
  usePendingConfirmations,
} from "@/lib/policy";
import type { PolicyMode } from "@/lib/api";
import { useVaultStatus } from "@/lib/vault";

function fmtAge(ts: number): string {
  const d = Math.max(0, Math.round(Date.now() / 1000 - ts));
  if (d < 60) return `${d}s ago`;
  if (d < 3600) return `${Math.round(d / 60)}m ago`;
  return `${Math.round(d / 3600)}h ago`;
}

export function OperatorStrip() {
  const { health: meeet } = useMeeetHealth(5000);
  const { events: samplerEvents } = useMeeetEvents({
    kind: "sampler.decision",
    limit: 8,
    intervalMs: 6000,
  });
  const { status: vault } = useVaultStatus(60000);
  const { pending, refresh: refreshPending } = usePendingConfirmations(4000);
  const { playbooks } = usePlaybooks();
  const { run, loading: pbLoading, invoke: invokePlaybook } = usePlaybookRun();
  const { deliberation, loading: cnLoading, run: runCouncil } = useDeliberation();
  const [pbId, setPbId] = useState<string>("");
  const [pbMode, setPbMode] = useState<PolicyMode>("autopilot");
  const [pendingBusy, setPendingBusy] = useState<string | null>(null);

  const onConfirm = async (token: string) => {
    setPendingBusy(token);
    try {
      await confirmToken(token);
    } finally {
      setPendingBusy(null);
      void refreshPending();
    }
  };
  const onCancel = async (token: string) => {
    setPendingBusy(token);
    try {
      await cancelToken(token);
    } finally {
      setPendingBusy(null);
      void refreshPending();
    }
  };

  return (
    <section className="mt-10 grid gap-4 lg:grid-cols-[1.1fr_1fr_1fr]">
      {/* ── Pending confirmations ────────────────────── */}
      <div className="rounded-[14px] border border-line bg-bg-1 p-5">
        <header className="mb-3 flex items-center justify-between font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
          <span>policy · pending // {pending.length}</span>
          <button
            type="button"
            onClick={() => void refreshPending()}
            className="cursor-pointer rounded border border-line px-2 py-0.5 hover:border-line-strong"
          >
            refresh
          </button>
        </header>
        {pending.length === 0 && (
          <p className="font-mono-tech text-[11px] text-ink-3">
            no destructive actions awaiting confirmation
          </p>
        )}
        <ul className="grid gap-2">
          {pending.map((p) => (
            <li
              key={p.token}
              className="rounded border border-line bg-[rgba(0,0,0,0.4)] p-3"
            >
              <div className="font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink">
                {p.slug}.{p.action_id}
              </div>
              <div className="mt-1 font-mono-tech text-[10.5px] tracking-[1px] text-ink-3">
                token {p.token} · created {fmtAge(p.created_at)}
              </div>
              <pre className="mt-2 max-h-[120px] overflow-auto whitespace-pre-wrap break-words font-mono-tech text-[10.5px] leading-[1.5] text-ink-2">
                {JSON.stringify(p.args, null, 2)}
              </pre>
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  onClick={() => void onConfirm(p.token)}
                  disabled={pendingBusy === p.token}
                  className="cursor-pointer rounded border border-line-hot bg-accent-deep px-3 py-1 font-display text-[11px] uppercase tracking-[0.16em] text-accent hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  confirm
                </button>
                <button
                  type="button"
                  onClick={() => void onCancel(p.token)}
                  disabled={pendingBusy === p.token}
                  className="cursor-pointer rounded border border-line px-3 py-1 font-display text-[11px] uppercase tracking-[0.16em] text-ink-2 hover:border-alert hover:text-alert disabled:opacity-50"
                >
                  cancel
                </button>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {/* ── Playbook runner ──────────────────────────── */}
      <div className="rounded-[14px] border border-line bg-bg-1 p-5">
        <header className="mb-3 font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
          playbooks // {playbooks.length}
        </header>
        <select
          value={pbId}
          onChange={(e) => setPbId(e.target.value)}
          className="mb-2 w-full rounded border border-line bg-[rgba(0,0,0,0.45)] p-2 font-mono-tech text-[12px] text-ink outline-none focus:border-line-hot"
        >
          <option value="">pick a playbook…</option>
          {playbooks.map((p) => (
            <option key={p.id} value={p.id}>
              {p.id} · {p.steps.length} steps
            </option>
          ))}
        </select>
        <select
          value={pbMode}
          onChange={(e) => setPbMode(e.target.value as PolicyMode)}
          className="mb-2 w-full rounded border border-line bg-[rgba(0,0,0,0.45)] p-2 font-mono-tech text-[12px] text-ink outline-none focus:border-line-hot"
        >
          <option value="autopilot">autopilot</option>
          <option value="confirm">confirm</option>
          <option value="dry_run">dry_run</option>
        </select>
        <button
          type="button"
          disabled={!pbId || pbLoading}
          onClick={() => pbId && void invokePlaybook(pbId, { mode: pbMode })}
          className="w-full cursor-pointer rounded border border-line-hot bg-accent-deep px-3 py-2 font-display text-[11px] uppercase tracking-[0.18em] text-accent hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {pbLoading ? "running…" : "run playbook"}
        </button>
        {run && (
          <div className="mt-3 rounded border border-line bg-[rgba(0,0,0,0.4)] p-2">
            <div className="font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-2">
              {run.playbook_id} · ok={String(run.ok)} · trace {run.trace_id}
            </div>
            <ol className="mt-1 grid gap-1 font-mono-tech text-[10.5px] text-ink-2">
              {run.steps.map((s) => (
                <li
                  key={s.id}
                  className={
                    s.blocked
                      ? "text-accent"
                      : s.ok
                        ? "text-ink"
                        : "text-alert"
                  }
                >
                  {s.id} · {s.action} · {s.took_ms.toFixed(1)}ms
                  {s.blocked ? " · blocked" : ""}
                  {s.error ? ` · ${s.error}` : ""}
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>

      {/* ── Meeet + Vault + Council ──────────────────── */}
      <div className="rounded-[14px] border border-line bg-bg-1 p-5">
        <header className="mb-3 font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
          bridges
        </header>

        <div className="mb-3 rounded border border-line bg-[rgba(0,0,0,0.4)] p-2">
          <div className="font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-2">
            meeet
          </div>
          {meeet ? (
            <ul className="mt-1 grid gap-0.5 font-mono-tech text-[10.5px] text-ink-2">
              <li>
                ingest{" "}
                <span className={meeet.client.enabled ? "text-ink" : "text-ink-3"}>
                  {meeet.client.enabled ? "live" : "local-only"}
                </span>
              </li>
              <li>
                store {meeet.store.total} events · unpushed{" "}
                {meeet.store.unpushed}
              </li>
              {meeet.last_replay && (
                <li>
                  last replay{" "}
                  {meeet.last_replay.ran_at
                    ? fmtAge(meeet.last_replay.ran_at)
                    : "—"}
                  {meeet.last_replay.pushed != null
                    ? ` · pushed ${meeet.last_replay.pushed}`
                    : ""}
                </li>
              )}
            </ul>
          ) : (
            <p className="mt-1 font-mono-tech text-[10.5px] text-ink-3">…</p>
          )}
        </div>

        <div className="mb-3 rounded border border-line bg-[rgba(0,0,0,0.4)] p-2">
          <div className="font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-2">
            sampler.decision (recent)
          </div>
          {samplerEvents.length === 0 ? (
            <p className="mt-1 font-mono-tech text-[10.5px] text-ink-3">
              no deliberations logged yet — run council
            </p>
          ) : (
            <ul className="mt-1 grid max-h-[120px] gap-1 overflow-auto font-mono-tech text-[9.5px] text-ink-2">
              {samplerEvents.slice(0, 8).map((ev) => {
                const payload = ev.payload as {
                  winner?: string;
                  winning_stance?: string;
                  agreement?: number;
                  mode?: string;
                };
                return (
                  <li key={ev.id} className="border-b border-line/40 pb-1">
                    <span className="text-ink-3">
                      {new Date(ev.ts * 1000).toISOString().slice(11, 19)}
                    </span>{" "}
                    <span className="text-accent">
                      {(payload?.winning_stance ?? "—").toString()}
                    </span>{" "}
                    · {(payload?.winner ?? "—").toString()} · agr{" "}
                    {typeof payload?.agreement === "number"
                      ? payload.agreement.toFixed(2)
                      : "—"}{" "}
                    · {String(payload?.mode ?? "—")}
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="mb-3 rounded border border-line bg-[rgba(0,0,0,0.4)] p-2">
          <div className="font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-2">
            vault
          </div>
          {vault ? (
            <ul className="mt-1 grid gap-0.5 font-mono-tech text-[10.5px] text-ink-2">
              {vault.keys.map((k) => (
                <li key={k.key}>
                  <span className="text-ink-3">{k.key}</span>{" "}
                  <span
                    className={
                      k.available
                        ? k.source === "env"
                          ? "text-ink"
                          : "text-accent"
                        : "text-ink-3"
                    }
                  >
                    {k.source}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 font-mono-tech text-[10.5px] text-ink-3">…</p>
          )}
        </div>

        <div className="rounded border border-line bg-[rgba(0,0,0,0.4)] p-2">
          <div className="mb-1 flex items-center justify-between font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-2">
            <span>council</span>
            <button
              type="button"
              onClick={() =>
                void runCouncil(
                  "interpret morning market",
                  { topic: "market", avg_change_24h: -0.8 },
                  "n_vote",
                )
              }
              className="cursor-pointer rounded border border-line px-2 py-0.5 hover:border-line-strong"
            >
              {cnLoading ? "…" : "deliberate"}
            </button>
          </div>
          {deliberation ? (
            <ul className="grid gap-0.5 font-mono-tech text-[10.5px] text-ink-2">
              <li>
                chosen{" "}
                <span className="text-ink">{deliberation.chosen}</span> ·
                agreement {deliberation.agreement.toFixed(2)}
              </li>
              {deliberation.voices.map((v) => (
                <li key={v.model}>
                  <span className="text-ink-3">{v.model}</span> · {v.stance} ·
                  conf {v.confidence.toFixed(2)}
                </li>
              ))}
            </ul>
          ) : (
            <p className="font-mono-tech text-[10.5px] text-ink-3">
              click deliberate to consult the council
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
