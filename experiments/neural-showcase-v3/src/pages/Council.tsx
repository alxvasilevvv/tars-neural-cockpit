/**
 * /cockpit/council — council debug page.
 *
 * IDEAS #18 follow-up — backend `/api/council/deliberate` shipped
 * Phase K-C, every deliberation already drops a `sampler.decision`
 * event into the meeet trail. This page is the operator-facing
 * surface that finally makes the dual-voice diff browsable.
 *
 * Anatomy:
 *
 *   - Sticky header: back to cockpit, refresh history.
 *   - Two-column workspace:
 *     - Left: stage form (prompt + context JSON + mode) and a
 *       newest-first history of `sampler.decision` events
 *       (winner / agreement / mode / time).
 *     - Right: rendered deliberation. Six-stat header (chosen /
 *       agreement / mode / total tokens / total latency / voice
 *       count) + per-voice card grid with stance pill, confidence
 *       bar, summary, recommended actions, rationale, latency,
 *       tokens. Contradictions list rendered below.
 *
 * Polling:
 *
 *   - History refreshes every 6 s (matches OperatorStrip cadence).
 *   - Stage button is the only mutator; result lands inline +
 *     refreshes history one tick later.
 */

import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  Loader2,
  Plug,
  RefreshCcw,
  ShieldAlert,
  Sparkles,
} from "lucide-react";

import { useDocumentMeta } from "@/lib/meta";
import { useT, type TKey } from "@/lib/i18n";
import { useDeliberation, type CouncilMode, type Deliberation, type Proposal } from "@/lib/council";
import { useMeeetEvents } from "@/lib/meeet";
import {
  confidenceWidth,
  fmtConfidencePct,
  fmtLatencyMs,
  pickWinningVoice,
  rollupVoices,
  stanceTone,
} from "@/lib/councilFmt";
import { API_BASE } from "@/lib/api";
import { BrandHairline } from "@/components/BrandHairline";

type TFn = (key: TKey, vars?: Record<string, string | number>) => string;

const MODES: readonly CouncilMode[] = ["single", "dual_vote", "n_vote"] as const;

function tryParseJson(raw: string): { ok: true; value: Record<string, unknown> } | { ok: false } {
  try {
    const out = JSON.parse(raw);
    if (out && typeof out === "object" && !Array.isArray(out)) {
      return { ok: true, value: out as Record<string, unknown> };
    }
    return { ok: false };
  } catch {
    return { ok: false };
  }
}

function fmtTs(epoch: number): string {
  try {
    return new Date(epoch * 1000).toLocaleTimeString();
  } catch {
    return "—";
  }
}

interface SamplerDecisionPayload {
  winner?: string;
  winning_stance?: string;
  agreement?: number;
  mode?: string;
  contradictions?: string[];
}

export function Council() {
  const t = useT();
  useDocumentMeta({
    title: "Council debug",
    description:
      "Watch the TARS council deliberate — local + cloud voices, agreement scoring, contradictions, and a meeet-backed history.",
    ogImage: "https://tars.meeet.world/og-cockpit.svg",
  });

  const [prompt, setPrompt] = useState("interpret morning market");
  const [contextRaw, setContextRaw] = useState(
    `{"topic":"market","avg_change_24h":-0.8}`,
  );
  const [mode, setMode] = useState<CouncilMode>("dual_vote");

  const { deliberation, loading, error, run } = useDeliberation();

  const onRun = useCallback(() => {
    const parsed = tryParseJson(contextRaw);
    void run(prompt, parsed.ok ? parsed.value : {}, mode);
  }, [prompt, contextRaw, mode, run]);

  const ctxParsed = useMemo(() => tryParseJson(contextRaw), [contextRaw]);

  const {
    events: history,
    loading: historyLoading,
    refresh: refreshHistory,
    error: historyError,
  } = useMeeetEvents({
    kind: "sampler.decision",
    limit: 25,
    intervalMs: 6000,
  });

  return (
    <section className="relative z-20 mx-auto min-h-screen max-w-[1480px] px-6 pb-24 pt-6 md:px-12">
      <div className="relative mb-8 overflow-hidden rounded-[14px] border border-line bg-bg-1/60 px-4 py-3 backdrop-blur-md md:px-6">
        <BrandHairline />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link
              to="/cockpit"
              className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-line px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-2 transition-colors duration-200 hover:border-line-strong hover:text-ink"
            >
              <ArrowLeft size={12} strokeWidth={1.6} aria-hidden />
              cockpit
            </Link>
            <span className="font-mono-tech text-[10px] uppercase tracking-[3px] text-ink-3">
              {t("council.eyebrow")}
            </span>
          </div>
          <button
            type="button"
            onClick={() => void refreshHistory()}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-line px-2 py-1 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3 transition-colors hover:border-line-strong hover:text-ink"
          >
            {historyLoading ? (
              <Loader2 size={11} className="animate-spin" strokeWidth={1.6} />
            ) : (
              <RefreshCcw size={11} strokeWidth={1.6} />
            )}
            <span>{t("council.refresh")}</span>
          </button>
        </div>
      </div>

      <div className="mb-8">
        <div className="mb-3 inline-flex items-center gap-2.5 font-mono-tech text-[10px] uppercase tracking-[3px] text-ink-2">
          <span style={{ color: "var(--brand-indigo)" }}>OPERATOR</span>
          <span aria-hidden className="opacity-50">//</span>
          <span>COUNCIL</span>
          <span aria-hidden className="opacity-50">//</span>
          <span style={{ color: "var(--brand-cyan)" }}>v9.0</span>
        </div>
        <h1
          className="font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
          style={{ fontSize: "var(--text-display-md)" }}
        >
          {t("council.title")}
        </h1>
        <p className="mt-3 max-w-[80ch] font-mono-tech text-[12px] uppercase tracking-[2.4px] text-ink-2">
          {t("council.subtitle")}
        </p>
      </div>

      {error && (
        <div className="mb-6 rounded-md border border-alert/40 bg-alert/[0.04] p-4 font-mono-tech text-[12px] text-alert">
          <header className="mb-1 flex items-center gap-2 font-display text-[13px] uppercase tracking-[0.04em]">
            <Plug size={13} strokeWidth={1.6} />
            {t("council.error.title")}
          </header>
          <p>
            {t("council.error.hint")} <code className="text-ink-2">{API_BASE}</code>
          </p>
          <p className="mt-1 text-ink-3">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[420px_1fr]">
        <aside className="grid gap-4 self-start">
          <StageForm
            prompt={prompt}
            onPrompt={setPrompt}
            contextRaw={contextRaw}
            onContext={setContextRaw}
            mode={mode}
            onMode={setMode}
            onRun={onRun}
            loading={loading}
            invalidContext={!ctxParsed.ok}
            t={t}
          />
          <HistoryRail
            events={history}
            loading={historyLoading}
            error={historyError}
            t={t}
          />
        </aside>
        <div className="min-h-[200px]">
          {deliberation ? (
            <DeliberationDetail deliberation={deliberation} t={t} />
          ) : (
            <EmptyDetail t={t} />
          )}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StageForm({
  prompt,
  onPrompt,
  contextRaw,
  onContext,
  mode,
  onMode,
  onRun,
  loading,
  invalidContext,
  t,
}: {
  prompt: string;
  onPrompt: (s: string) => void;
  contextRaw: string;
  onContext: (s: string) => void;
  mode: CouncilMode;
  onMode: (m: CouncilMode) => void;
  onRun: () => void;
  loading: boolean;
  invalidContext: boolean;
  t: TFn;
}) {
  return (
    <div className="rounded-[14px] border border-line bg-bg-1 p-5">
      <header className="mb-3 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
        stage
      </header>
      <label className="mb-1 block font-mono-tech text-[9.5px] uppercase tracking-[2.4px] text-ink-3">
        {t("council.form.prompt")}
      </label>
      <input
        type="text"
        value={prompt}
        onChange={(e) => onPrompt(e.target.value)}
        placeholder={t("council.form.prompt.placeholder")}
        className="mb-3 w-full rounded border border-line bg-bg-0/40 px-3 py-2 font-mono-tech text-[12px] text-ink outline-none focus:border-line-hot"
      />

      <label className="mb-1 block font-mono-tech text-[9.5px] uppercase tracking-[2.4px] text-ink-3">
        {t("council.form.context")}
      </label>
      <textarea
        value={contextRaw}
        onChange={(e) => onContext(e.target.value)}
        placeholder={t("council.form.context.placeholder")}
        rows={4}
        className={`mb-1 w-full resize-y rounded border bg-bg-0/40 px-3 py-2 font-mono-tech text-[11px] leading-snug text-ink outline-none focus:border-line-hot ${
          invalidContext ? "border-alert/50" : "border-line"
        }`}
      />
      {invalidContext && (
        <p className="mb-3 font-mono-tech text-[10px] tracking-[1.4px] text-alert">
          <ShieldAlert size={10} strokeWidth={1.8} className="mr-1 inline" />
          {t("council.form.invalidJson")}
        </p>
      )}

      <label className="mb-1 mt-2 block font-mono-tech text-[9.5px] uppercase tracking-[2.4px] text-ink-3">
        {t("council.form.mode")}
      </label>
      <div className="mb-4 flex flex-wrap items-center gap-1.5">
        {MODES.map((m) => {
          const active = m === mode;
          return (
            <button
              key={m}
              type="button"
              onClick={() => onMode(m)}
              className={`rounded-md border px-2.5 py-1 font-mono-tech text-[10px] uppercase tracking-[2px] transition-colors ${
                active
                  ? "border-line-hot bg-accent-deep text-accent"
                  : "border-line text-ink-2 hover:border-line-strong hover:text-ink"
              }`}
            >
              {t(`council.form.mode.${m}` as TKey)}
            </button>
          );
        })}
      </div>

      <button
        type="button"
        onClick={onRun}
        disabled={loading || !prompt.trim()}
        className="inline-flex w-full cursor-pointer items-center justify-center gap-2 rounded border border-line-hot bg-accent-deep px-4 py-2 font-display text-[12px] uppercase tracking-[0.16em] text-accent hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? (
          <>
            <Loader2 size={12} className="animate-spin" strokeWidth={1.6} />
            {t("council.running")}
          </>
        ) : (
          <>
            <Sparkles size={12} strokeWidth={1.8} />
            {t("council.run")}
          </>
        )}
      </button>
    </div>
  );
}

function HistoryRail({
  events,
  loading,
  error,
  t,
}: {
  events: ReadonlyArray<{
    id: number;
    ts: number;
    trace_id: string;
    payload: Record<string, unknown>;
  }>;
  loading: boolean;
  error: string | null;
  t: TFn;
}) {
  return (
    <div className="rounded-[14px] border border-line bg-bg-1 p-3">
      <div className="mb-1 px-1 font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
        {t("council.history.title")} · {events.length}
      </div>
      {loading && events.length === 0 && (
        <div className="flex items-center gap-2 px-2 py-3 font-mono-tech text-[11px] text-ink-3">
          <Loader2 size={12} className="animate-spin" strokeWidth={1.6} />
          {t("council.history.loading")}
        </div>
      )}
      {!loading && events.length === 0 && (
        <div className="px-2 py-3 font-mono-tech text-[11px] text-ink-3">
          {t("council.history.empty")}
        </div>
      )}
      {error && (
        <div className="px-2 py-2 font-mono-tech text-[11px] text-alert">
          {error}
        </div>
      )}
      <ul className="grid max-h-[40vh] gap-1 overflow-auto">
        {events.map((ev) => {
          const p = ev.payload as SamplerDecisionPayload;
          const tone = stanceTone(p.winning_stance ?? null);
          return (
            <li
              key={ev.id}
              className="rounded-md border border-line bg-bg-0/40 px-2.5 py-1.5"
            >
              <div className="flex items-center justify-between gap-2 font-mono-tech text-[10px] uppercase tracking-[1.8px]">
                <span className="text-ink-3">{fmtTs(ev.ts)}</span>
                <span className={`rounded-md border px-1.5 py-0.5 text-[9px] tracking-[1.6px] ${tone.cls}`}>
                  {tone.label}
                </span>
              </div>
              <div className="mt-0.5 truncate font-mono-tech text-[10px] tracking-[1.4px] text-ink-2">
                <span className="text-ink-3">winner</span>{" "}
                <span className="text-ink">{p.winner ?? "—"}</span>{" "}
                <span className="text-ink-3">· agr</span>{" "}
                <span className="text-ink">
                  {typeof p.agreement === "number" ? p.agreement.toFixed(2) : "—"}
                </span>{" "}
                <span className="text-ink-3">· {String(p.mode ?? "—")}</span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function DeliberationDetail({
  deliberation,
  t,
}: {
  deliberation: Deliberation;
  t: TFn;
}) {
  const winner = pickWinningVoice(deliberation.voices);
  const rollup = rollupVoices(deliberation.voices);
  const tone = stanceTone(deliberation.chosen);

  return (
    <div
      data-testid="deliberation-detail"
      className="rounded-[14px] border border-line bg-bg-1 p-5"
    >
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-3">
            {t("council.detail.eyebrow")}
          </span>
          <span
            className={`rounded-md border px-2 py-0.5 font-mono-tech text-[9px] uppercase tracking-[1.6px] ${tone.cls}`}
          >
            {tone.label}
          </span>
        </div>
        {deliberation.trace_id && (
          <code className="font-mono-tech text-[10.5px] tracking-[0.4px] text-ink-3">
            {deliberation.trace_id}
          </code>
        )}
      </header>

      <dl className="mb-4 grid grid-cols-2 gap-x-4 gap-y-2 font-mono-tech text-[11px] text-ink-2 md:grid-cols-3">
        <Stat label={t("council.detail.chosen")} value={deliberation.chosen} />
        <Stat
          label={t("council.detail.agreement")}
          value={deliberation.agreement.toFixed(2)}
        />
        <Stat label="mode" value={deliberation.mode} />
        <Stat
          label={t("council.detail.tokens")}
          value={`${rollup.total_tokens_in.toLocaleString()} → ${rollup.total_tokens_out.toLocaleString()}`}
        />
        <Stat
          label={t("council.detail.latency")}
          value={fmtLatencyMs(rollup.total_latency_ms, { ms: "ms", s: "s" })}
        />
        <Stat label="voices" value={String(rollup.voice_count)} />
      </dl>

      <h3 className="mb-2 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
        {t("council.detail.contradictions")}
      </h3>
      {deliberation.contradictions.length === 0 ? (
        <p className="mb-4 font-mono-tech text-[11px] text-ink-3">
          {t("council.detail.contradictions.none")}
        </p>
      ) : (
        <ul className="mb-4 grid list-disc gap-1 pl-5 font-mono-tech text-[11px] text-ink-2 marker:text-ink-3">
          {deliberation.contradictions.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      )}

      {deliberation.rationale && (
        <>
          <h3 className="mb-1 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
            {t("council.detail.rationale")}
          </h3>
          <p className="mb-4 font-mono-tech text-[11.5px] leading-relaxed text-ink-2">
            {deliberation.rationale}
          </p>
        </>
      )}

      <h3 className="mb-2 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
        {t("council.detail.voices", { n: deliberation.voices.length })}
      </h3>
      <div className="grid gap-3 md:grid-cols-2">
        {deliberation.voices.map((v) => (
          <VoiceCard key={v.model} voice={v} winner={v.model === winner} t={t} />
        ))}
      </div>
    </div>
  );
}

function VoiceCard({
  voice,
  winner,
  t,
}: {
  voice: Proposal;
  winner: boolean;
  t: TFn;
}) {
  const tone = stanceTone(voice.stance);
  const unavailable = voice.stance === "unavailable";
  const width = confidenceWidth(voice.confidence);

  return (
    <div
      className={`rounded-[12px] border bg-bg-0/40 p-4 ${
        winner ? "border-line-hot" : "border-line"
      }`}
    >
      <header className="mb-2 flex items-center justify-between gap-2">
        <code className="font-mono-tech text-[11px] tracking-[0.4px] text-ink">
          {voice.model}
        </code>
        <span
          className={`rounded-md border px-1.5 py-0.5 font-mono-tech text-[9px] uppercase tracking-[1.6px] ${tone.cls}`}
        >
          {tone.label}
        </span>
      </header>
      {winner && (
        <p className="mb-2 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-accent">
          ★ {t("council.detail.winner")}
        </p>
      )}

      {unavailable ? (
        <p className="font-mono-tech text-[11px] text-ink-3">
          <ShieldAlert size={11} strokeWidth={1.8} className="mr-1 inline" />
          {t("council.voice.unavailable")}
        </p>
      ) : (
        <>
          <div className="mb-2">
            <div className="mb-1 flex items-center justify-between font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
              <span>{t("council.voice.confidence")}</span>
              <span className="text-ink">{fmtConfidencePct(voice.confidence)}</span>
            </div>
            <div className="h-1 rounded-full bg-line/30">
              <div
                className="h-full rounded-full bg-accent transition-all"
                style={{ width: `${width * 100}%` }}
              />
            </div>
          </div>

          <h4 className="mb-0.5 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
            {t("council.voice.summary")}
          </h4>
          <p className="mb-2 font-mono-tech text-[11px] leading-relaxed text-ink-2">
            {voice.summary}
          </p>

          {voice.actions_recommended.length > 0 && (
            <>
              <h4 className="mb-0.5 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
                {t("council.voice.actions")}
              </h4>
              <ul className="mb-2 grid list-disc gap-0.5 pl-4 font-mono-tech text-[10.5px] text-ink-2 marker:text-ink-3">
                {voice.actions_recommended.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </>
          )}

          <div className="mt-2 flex flex-wrap items-center gap-2 font-mono-tech text-[9.5px] uppercase tracking-[1.6px] text-ink-3">
            <span>
              {voice.tokens_in.toLocaleString()} → {voice.tokens_out.toLocaleString()}
            </span>
            <span aria-hidden>·</span>
            <span>{fmtLatencyMs(voice.latency_ms, { ms: "ms", s: "s" })}</span>
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="font-mono-tech text-[9px] uppercase tracking-[2.4px] text-ink-3">
        {label}
      </dt>
      <dd className="mt-0.5 truncate font-mono-tech text-[12px] text-ink">{value}</dd>
    </div>
  );
}

function EmptyDetail({ t }: { t: TFn }) {
  return (
    <div className="flex h-full min-h-[260px] items-center justify-center rounded-[14px] border border-dashed border-line p-10 text-center">
      <div>
        <h3 className="font-display text-[18px] tracking-[-0.01em] text-ink">
          {t("council.detail.empty.title")}
        </h3>
        <p className="mt-2 font-mono-tech text-[11.5px] tracking-[1.4px] text-ink-3">
          {t("council.detail.empty.body")}
        </p>
      </div>
    </div>
  );
}
