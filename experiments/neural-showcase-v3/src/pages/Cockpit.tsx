import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Loader2, Play, Plug } from "lucide-react";
import {
  listDomains,
  invokeAction,
  getHealth,
  API_BASE,
} from "@/lib/api";
import type { DomainPack, DomainAction, InvokeResult } from "@/lib/api";
import { CornerFrame, StatusLozenge, BarStack } from "@/components/Glyphs";
import { Waveform } from "@/components/Waveform";
import { sound } from "@/lib/sound";
import { AwarenessTicker } from "@/components/AwarenessTicker";
import { OperatorStrip } from "@/components/OperatorStrip";

interface TraceEntry {
  at: string;
  kind: "request" | "ok" | "error";
  text: string;
  trace_id?: string | null;
  took_ms?: number;
}

function defaultArgsFor(action: DomainAction | null): string {
  if (!action) return "{}";
  const props = (action.schema?.properties ?? {}) as Record<string, any>;
  const example: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(props)) {
    if (v?.type === "string") {
      if (k === "query") example[k] = "graph neural network";
      else if (k === "ticker") example[k] = "WBTC";
      else if (k === "ref") example[k] = "arxiv:2305.13245";
      else if (k === "seed") example[k] = "small neural cores";
      else example[k] = "";
    } else if (v?.type === "integer" || v?.type === "number") {
      example[k] = k === "limit" ? 3 : 0;
    } else if (v?.type === "boolean") {
      example[k] = false;
    } else if (Array.isArray(v?.enum)) {
      example[k] = v.enum[0];
    }
  }
  return JSON.stringify(example, null, 2);
}

export function Cockpit() {
  const [packs, setPacks] = useState<DomainPack[] | null>(null);
  const [activeSlug, setActiveSlug] = useState<string | null>(null);
  const [activeActionId, setActiveActionId] = useState<string | null>(null);
  const [argsText, setArgsText] = useState<string>("{}");
  const [running, setRunning] = useState(false);
  const [response, setResponse] = useState<InvokeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<Awaited<ReturnType<typeof getHealth>> | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [trace, setTrace] = useState<TraceEntry[]>([]);

  const activePack = packs?.find((p) => p.slug === activeSlug) ?? null;
  const activeAction =
    activePack?.actions.find((a) => a.id === activeActionId) ?? null;

  // Bootstrap: health + domains
  useEffect(() => {
    void (async () => {
      try {
        const h = await getHealth();
        setHealth(h);
      } catch (e) {
        setHealthError(String((e as Error)?.message ?? e));
      }
      try {
        const ps = await listDomains();
        setPacks(ps);
        if (ps.length) {
          setActiveSlug(ps[0].slug);
          setActiveActionId(ps[0].actions[0]?.id ?? null);
        }
      } catch (e) {
        setError(String((e as Error)?.message ?? e));
      }
    })();
  }, []);

  // Auto-fill args when action changes.
  useEffect(() => {
    setArgsText(defaultArgsFor(activeAction));
    setResponse(null);
    setError(null);
  }, [activeActionId, activeSlug]);

  const canRun = useMemo(() => {
    if (!activeSlug || !activeActionId || running) return false;
    try {
      JSON.parse(argsText);
      return true;
    } catch {
      return false;
    }
  }, [activeSlug, activeActionId, argsText, running]);

  const onRun = async () => {
    if (!activeSlug || !activeActionId) return;
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(argsText);
    } catch (e) {
      setError(`Invalid JSON · ${(e as Error).message}`);
      return;
    }
    setRunning(true);
    setError(null);
    setResponse(null);
    sound.click();
    const startedAt = new Date();
    setTrace((t) => [
      {
        at: startedAt.toISOString().slice(11, 19),
        kind: "request",
        text: `→ ${activeSlug}.${activeActionId} ${JSON.stringify(parsed)}`,
      },
      ...t.slice(0, 19),
    ]);
    try {
      const r = await invokeAction(activeSlug, activeActionId, parsed);
      setResponse(r);
      const ok = (r.result as { ok?: unknown })?.ok;
      setTrace((t) => [
        {
          at: new Date().toISOString().slice(11, 19),
          kind: ok === false ? "error" : "ok",
          text: `← ${activeSlug}.${activeActionId} ${ok === false ? "ok=false" : "ok=true"}`,
          trace_id: r.trace_id,
          took_ms: r.took_ms,
        },
        ...t.slice(0, 19),
      ]);
    } catch (e) {
      const msg = (e as Error)?.message ?? String(e);
      setError(msg);
      setTrace((t) => [
        {
          at: new Date().toISOString().slice(11, 19),
          kind: "error",
          text: `× ${msg}`,
        },
        ...t.slice(0, 19),
      ]);
    } finally {
      setRunning(false);
    }
  };

  const backendOffline = !!healthError;

  return (
    <section className="relative z-20 mx-auto min-h-screen max-w-[1480px] px-6 pb-24 pt-6 md:px-12">
      {/* Top strip */}
      <div className="mb-6 flex items-center justify-between gap-4">
        <Link
          to="/"
          className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-line px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-2 transition-colors duration-200 hover:border-line-strong hover:text-ink"
        >
          <ArrowLeft size={12} strokeWidth={1.6} />
          back to landing
        </Link>
        <div className="flex items-center gap-2">
          <StatusLozenge
            label={backendOffline ? "BACKEND OFFLINE" : "BACKEND ONLINE"}
            tone={backendOffline ? "alert" : "success"}
          />
          {health && (
            <StatusLozenge
              label={`MEEET ${health.meeet_ingest ? "ON" : "LOCAL"}`}
              tone={health.meeet_ingest ? "accent" : "muted"}
            />
          )}
        </div>
      </div>

      <div className="mb-10">
        <span className="font-mono-tech text-[10px] uppercase tracking-[3px] text-ink-2">
          OPERATOR // COCKPIT
        </span>
        <h1 className="mt-3 font-display text-[clamp(2.4rem,5vw,4.4rem)] font-medium uppercase leading-[0.96] tracking-[0.02em] text-ink">
          Run a domain action.
        </h1>
        <p className="mt-3 max-w-[60ch] font-mono-tech text-[12px] uppercase tracking-[2.4px] text-ink-2">
          API · {API_BASE}{" "}
          {health ? `· uptime ${health.uptime_s.toFixed(1)}s` : ""}
        </p>
      </div>

      <div className="mb-8">
        <AwarenessTicker />
      </div>

      {backendOffline && (
        <div className="mb-8 rounded-[10px] border border-alert/40 bg-alert/[0.04] p-5 font-mono-tech text-[12px] text-ink-2">
          <header className="mb-2 flex items-center gap-2 font-display text-[14px] uppercase tracking-[0.04em] text-alert">
            <Plug size={14} strokeWidth={1.6} />
            backend offline
          </header>
          <p className="mb-2">{healthError}</p>
          <p>
            Start it with:&nbsp;
            <code className="text-ink">
              cd Jarvis/jarvis &amp;&amp; PYTHONPATH=. PORT=8765
              .venv/bin/python serve.py
            </code>
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-px overflow-hidden rounded-[14px] border border-line bg-line lg:grid-cols-[260px_320px_1fr]">
        {/* Domain list */}
        <aside className="bg-bg-1 p-4">
          <CornerFrame />
          <div className="mb-3 font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
            domains // {packs?.length ?? "…"}
          </div>
          <ul className="grid gap-1">
            {(packs ?? []).map((p) => (
              <li key={p.slug}>
                <button
                  type="button"
                  onClick={() => {
                    setActiveSlug(p.slug);
                    setActiveActionId(p.actions[0]?.id ?? null);
                  }}
                  className={`group block w-full cursor-pointer rounded-md border px-3 py-2.5 text-left transition-colors duration-200 ${
                    p.slug === activeSlug
                      ? "border-line-hot bg-accent-deep text-ink"
                      : "border-line bg-transparent text-ink-2 hover:border-line-strong hover:text-ink"
                  }`}
                >
                  <div className="font-mono-tech text-[10px] uppercase tracking-[2.6px]">
                    <span className="opacity-60">{p.slug.toUpperCase()}</span>
                  </div>
                  <div className="font-display text-[14px] font-medium uppercase tracking-[0.02em] text-ink">
                    {p.name}
                  </div>
                  <div className="mt-1 line-clamp-2 font-mono-tech text-[10.5px] tracking-[1.4px] text-ink-2">
                    {p.short}
                  </div>
                </button>
              </li>
            ))}
            {!packs && (
              <li className="px-3 py-2 font-mono-tech text-[10px] text-ink-3">
                loading…
              </li>
            )}
          </ul>
        </aside>

        {/* Action list */}
        <aside className="bg-bg-1 p-4">
          <CornerFrame />
          <div className="mb-3 font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
            actions // {activePack?.actions.length ?? 0}
          </div>
          <ul className="grid gap-1">
            {(activePack?.actions ?? []).map((a) => (
              <li key={a.id}>
                <button
                  type="button"
                  onClick={() => setActiveActionId(a.id)}
                  className={`group block w-full cursor-pointer rounded-md border px-3 py-2.5 text-left transition-colors duration-200 ${
                    a.id === activeActionId
                      ? "border-line-hot bg-accent-deep"
                      : "border-line bg-transparent hover:border-line-strong"
                  }`}
                >
                  <div className="font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink">
                    {a.name}
                  </div>
                  <div className="mt-1 font-mono-tech text-[10.5px] tracking-[1.4px] text-ink-2">
                    {a.description}
                  </div>
                  <div className="mt-1 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
                    /{a.id}
                  </div>
                </button>
              </li>
            ))}
            {!activePack && (
              <li className="px-3 py-2 font-mono-tech text-[10px] text-ink-3">
                pick a domain
              </li>
            )}
          </ul>
        </aside>

        {/* Argument editor + invoke */}
        <section className="grid grid-rows-[auto_1fr_auto] bg-bg-1 p-5 md:p-7">
          <CornerFrame />

          <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
                invocation
              </div>
              <h2 className="font-display text-[18px] font-medium uppercase tracking-[0.02em] text-ink">
                {activePack?.name ?? "—"} ·{" "}
                <span className="text-accent">
                  {activeAction?.name ?? "—"}
                </span>
              </h2>
            </div>
            <div className="flex items-center gap-2">
              <Waveform
                bars={20}
                width={120}
                height={16}
                color="var(--color-accent)"
              />
              <button
                type="button"
                disabled={!canRun}
                onClick={onRun}
                className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-line-hot bg-accent-deep px-4 py-2.5 font-display text-[12px] uppercase tracking-[0.18em] text-accent transition-colors duration-200 hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {running ? (
                  <Loader2 size={14} className="animate-spin" strokeWidth={1.6} />
                ) : (
                  <Play size={12} strokeWidth={1.8} />
                )}
                {running ? "running" : "invoke"}
              </button>
            </div>
          </header>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <div className="mb-1.5 font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
                args · json
              </div>
              <textarea
                value={argsText}
                onChange={(e) => setArgsText(e.target.value)}
                spellCheck={false}
                rows={12}
                className="w-full resize-none rounded-md border border-line bg-[rgba(0,0,0,0.45)] p-3 font-mono-tech text-[12px] leading-[1.6] tracking-[0.6px] text-ink outline-none transition-colors duration-200 focus:border-line-hot"
              />
              {error && (
                <div className="mt-2 font-mono-tech text-[11px] text-alert">
                  {error}
                </div>
              )}
            </div>

            <div className="min-h-[260px] rounded-md border border-line bg-[rgba(0,0,0,0.6)] p-3">
              <div className="mb-1.5 flex items-center justify-between font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
                <span>response</span>
                {response && (
                  <span className="text-ink">
                    {response.took_ms.toFixed(1)}ms ·{" "}
                    <span className="text-accent">
                      {response.trace_id ?? "—"}
                    </span>
                  </span>
                )}
              </div>
              <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap break-words font-mono-tech text-[12px] leading-[1.6] tracking-[0.4px] text-ink-2">
                {response
                  ? JSON.stringify(response.result, null, 2)
                  : running
                    ? "…"
                    : "—"}
              </pre>
            </div>
          </div>

          {/* Live trace timeline */}
          <footer className="mt-5 border-t border-line pt-4">
            <div className="mb-2 flex items-center justify-between font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
              <span>trace · live</span>
              <span className="flex items-center gap-2">
                <BarStack
                  values={[0.4, 0.65, 0.5, 0.8, 0.6, 0.9, 0.55, 0.72]}
                  height={12}
                  width={56}
                  color="var(--color-accent)"
                />
                {trace.length} events
              </span>
            </div>
            <ol className="grid max-h-[180px] gap-1 overflow-auto font-mono-tech text-[11.5px] tracking-[0.6px] text-ink-2">
              <AnimatePresence initial={false}>
                {trace.map((e, idx) => (
                  <motion.li
                    key={`${e.at}-${idx}-${e.text.slice(0, 6)}`}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0 }}
                    className="grid grid-cols-[60px_1fr_auto] items-center gap-2"
                  >
                    <span className="text-ink-3 tabular-nums">{e.at}</span>
                    <span
                      className={
                        e.kind === "error"
                          ? "text-alert"
                          : e.kind === "ok"
                            ? "text-ink"
                            : "text-accent"
                      }
                    >
                      {e.text}
                    </span>
                    {typeof e.took_ms === "number" && (
                      <span className="text-ink-3 tabular-nums">
                        {e.took_ms.toFixed(1)}ms
                      </span>
                    )}
                  </motion.li>
                ))}
              </AnimatePresence>
              {!trace.length && (
                <li className="text-ink-3">no events yet</li>
              )}
            </ol>
          </footer>
        </section>
      </div>

      <OperatorStrip />
    </section>
  );
}
