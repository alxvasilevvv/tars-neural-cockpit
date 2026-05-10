// SYNC: claude-w97-schedules
/**
 * <Schedules /> — Wave 97.
 *
 * Operator-facing page at /schedules. Lists every persisted cron
 * schedule (cron expression, attached playbook, last + next run,
 * status). Click a row to open a detail panel with recent run
 * history + cron edit + enable/disable + run-now.
 *
 * Backend lives at /api/scheduler/* (see backend/core/scheduler).
 * The lifespan loop is opt-in via TARS_SCHEDULER_ENABLED=1; this
 * page degrades gracefully (empty list + "scheduler disabled" hint)
 * when the backend returns 503.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Pause,
  Play,
  Plus,
  RotateCcw,
  Trash2,
  X,
} from "lucide-react";
import { useDocumentMeta } from "@/lib/meta";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import {
  type RunRecord,
  type Schedule,
  createSchedule,
  deleteSchedule,
  fetchHistory,
  listSchedules,
  patchSchedule,
  runScheduleNow,
  validateCron,
} from "@/lib/scheduler";

function formatTime(ts: number | null): string {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  return d.toLocaleString();
}

function formatAgo(ts: number | null): string {
  if (!ts) return "never";
  const s = Math.max(1, Math.round((Date.now() - ts * 1000) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

function statusColor(status: string | null): string {
  switch (status) {
    case "ok":
      return "var(--color-success)";
    case "failed":
      return "var(--color-alert)";
    case "blocked":
      return "var(--brand-amber)";
    case "skipped":
      return "var(--color-ink-3)";
    default:
      return "var(--color-ink-3)";
  }
}

export function Schedules() {
  useDocumentMeta({
    title: "Schedules · TARS",
    description:
      "Every cron-driven playbook trigger in this cockpit, with last/next run timing and one-click run-now.",
      ogImage: "https://tars.meeet.world/og-perf.svg",
  });

  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [serverErr, setServerErr] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setServerErr(null);
    try {
      const out = await listSchedules();
      setSchedules(out);
    } catch (e) {
      setServerErr((e as Error).message);
      setSchedules([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const selected = useMemo(
    () => schedules.find((s) => s.id === selectedId) ?? null,
    [schedules, selectedId],
  );

  return (
    <motion.section
      initial={{ opacity: 1 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="mx-auto w-full max-w-[1180px] px-6 pt-24 pb-20"
    >
      <Breadcrumbs
        items={[
          { label: "Home", to: "/" },
          { label: "Schedules" },
        ]}
      />

      <header className="mt-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <span className="font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
            wave 97 · scheduler
          </span>
          <h1 className="mt-1 font-display text-[32px] leading-[1.05] tracking-[-0.01em] text-ink md:text-[40px]">
            Schedules
          </h1>
          <p className="mt-2 max-w-[60ch] font-mono-tech text-[12px] leading-[1.6] text-ink-2">
            Cron-driven playbook triggers. Persisted to ~/.tars/scheduler.sqlite
            and restart-safe — next_run_at is recomputed on boot.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void refresh()}
            className="inline-flex items-center gap-2 rounded-md border border-line/60 bg-bg-1/40 px-3 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2 transition-colors hover:border-accent hover:text-ink"
          >
            <RotateCcw size={12} strokeWidth={1.7} aria-hidden />
            refresh
          </button>
          <button
            type="button"
            onClick={() => setShowNew(true)}
            className="inline-flex items-center gap-2 rounded-md border border-line-strong bg-bg-2/60 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink transition-colors hover:border-accent"
          >
            <Plus size={12} strokeWidth={1.7} aria-hidden />
            new schedule
          </button>
        </div>
      </header>

      {serverErr && (
        <p
          role="alert"
          className="mt-6 inline-flex items-start gap-2 rounded-md border border-amber-400/30 bg-amber-400/[0.06] px-3 py-2 text-[11.5px] leading-[1.5] text-amber-200"
        >
          <AlertCircle
            size={12}
            strokeWidth={1.7}
            aria-hidden
            className="mt-0.5"
          />
          <span>
            Scheduler backend unreachable: {serverErr}. Set TARS_SCHEDULER_ENABLED=1.
          </span>
        </p>
      )}

      <section className="mt-6 rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
        {loading ? (
          <p className="font-mono-tech text-[11px] text-ink-3">loading…</p>
        ) : schedules.length === 0 ? (
          <p className="font-mono-tech text-[11px] text-ink-3">
            No schedules yet. Click "new schedule" to wire a cron up to a playbook.
          </p>
        ) : (
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-line/40 font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3">
                <th className="py-2 pr-3">cron</th>
                <th className="py-2 pr-3">playbook</th>
                <th className="py-2 pr-3">tz</th>
                <th className="py-2 pr-3">last</th>
                <th className="py-2 pr-3">next</th>
                <th className="py-2 pr-3">status</th>
                <th className="py-2 pr-3">on</th>
              </tr>
            </thead>
            <tbody>
              {schedules.map((s) => (
                <tr
                  key={s.id}
                  onClick={() => setSelectedId(s.id)}
                  className="cursor-pointer border-b border-line/20 font-mono-tech text-[11px] text-ink-2 last:border-0 hover:bg-bg-2/40"
                >
                  <td className="py-2 pr-3 text-ink">{s.cron_expression}</td>
                  <td className="py-2 pr-3 text-ink-2">{s.playbook_id}</td>
                  <td className="py-2 pr-3 text-ink-3">{s.timezone}</td>
                  <td className="py-2 pr-3 text-ink-3">
                    {formatAgo(s.last_run_at)}
                  </td>
                  <td className="py-2 pr-3 text-ink-3">
                    {formatTime(s.next_run_at)}
                  </td>
                  <td className="py-2 pr-3">
                    <span
                      className="inline-flex items-center rounded-full border px-1.5 py-0.5 text-[9.5px] uppercase tracking-[1.6px]"
                      style={{
                        borderColor: statusColor(s.last_status),
                        color: statusColor(s.last_status),
                      }}
                    >
                      {s.last_status ?? "—"}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-ink-3">
                    {s.enabled ? "on" : "off"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {selected && (
        <ScheduleDetail
          schedule={selected}
          onClose={() => setSelectedId(null)}
          onChanged={() => void refresh()}
        />
      )}

      {showNew && (
        <NewScheduleDialog
          onClose={() => setShowNew(false)}
          onCreated={() => {
            setShowNew(false);
            void refresh();
          }}
        />
      )}
    </motion.section>
  );
}

// ── detail panel ────────────────────────────────────────────────────

interface ScheduleDetailProps {
  schedule: Schedule;
  onClose: () => void;
  onChanged: () => void;
}

function ScheduleDetail({ schedule, onClose, onChanged }: ScheduleDetailProps) {
  const [history, setHistory] = useState<RunRecord[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const rows = await fetchHistory(schedule.id, 20);
        if (!cancelled) setHistory(rows);
      } catch (e) {
        if (!cancelled) setErr((e as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [schedule.id]);

  const toggle = async () => {
    setBusy(true);
    setErr(null);
    try {
      await patchSchedule(schedule.id, { enabled: !schedule.enabled });
      onChanged();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const runNow = async () => {
    setBusy(true);
    setErr(null);
    try {
      await runScheduleNow(schedule.id);
      const rows = await fetchHistory(schedule.id, 20);
      setHistory(rows);
      onChanged();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!window.confirm(`Delete schedule ${schedule.id}?`)) return;
    setBusy(true);
    setErr(null);
    try {
      await deleteSchedule(schedule.id);
      onClose();
      onChanged();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="mt-4 rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
      <header className="mb-3 flex items-start justify-between gap-3">
        <div>
          <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            schedule · {schedule.id}
          </span>
          <p className="mt-1 font-display text-[16px] text-ink">
            {schedule.cron_expression} · {schedule.playbook_id}
          </p>
          <p className="mt-1 font-mono-tech text-[11px] text-ink-3">
            tz: {schedule.timezone} · next: {formatTime(schedule.next_run_at)}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="close detail"
          className="rounded-md border border-line/60 p-1.5 text-ink-3 transition-colors hover:border-accent hover:text-ink"
        >
          <X size={12} strokeWidth={1.7} aria-hidden />
        </button>
      </header>

      <div className="mb-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={toggle}
          disabled={busy}
          className="inline-flex items-center gap-2 rounded-md border border-line-strong bg-bg-2/60 px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink transition-colors hover:border-accent disabled:opacity-50"
        >
          {schedule.enabled ? (
            <Pause size={11} strokeWidth={1.7} aria-hidden />
          ) : (
            <Play size={11} strokeWidth={1.7} aria-hidden />
          )}
          {schedule.enabled ? "disable" : "enable"}
        </button>
        <button
          type="button"
          onClick={runNow}
          disabled={busy}
          className="inline-flex items-center gap-2 rounded-md border border-line-strong bg-bg-2/60 px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink transition-colors hover:border-accent disabled:opacity-50"
        >
          <Clock size={11} strokeWidth={1.7} aria-hidden />
          run now
        </button>
        <button
          type="button"
          onClick={remove}
          disabled={busy}
          className="inline-flex items-center gap-2 rounded-md border border-rose-400/40 bg-rose-400/[0.06] px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-rose-200 transition-colors hover:border-rose-300 disabled:opacity-50"
        >
          <Trash2 size={11} strokeWidth={1.7} aria-hidden />
          delete
        </button>
      </div>

      {err && (
        <p className="mb-2 inline-flex items-start gap-2 text-[11px] text-rose-200">
          <AlertCircle
            size={11}
            strokeWidth={1.7}
            aria-hidden
            className="mt-0.5"
          />
          <span>{err}</span>
        </p>
      )}

      <h3 className="mt-3 font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
        recent runs · last {history.length}
      </h3>
      {history.length === 0 ? (
        <p className="mt-2 font-mono-tech text-[11px] text-ink-3">
          No runs yet.
        </p>
      ) : (
        <table className="mt-2 w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-line/40 font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3">
              <th className="py-1.5 pr-3">when</th>
              <th className="py-1.5 pr-3">status</th>
              <th className="py-1.5 pr-3">duration</th>
              <th className="py-1.5 pr-3">summary</th>
            </tr>
          </thead>
          <tbody>
            {history.map((r) => (
              <tr
                key={r.id}
                className="border-b border-line/20 font-mono-tech text-[11px] text-ink-2 last:border-0"
              >
                <td className="py-1.5 pr-3 whitespace-nowrap text-ink-3">
                  {formatAgo(r.started_at)}
                </td>
                <td className="py-1.5 pr-3">
                  <span
                    className="inline-flex items-center rounded-full border px-1.5 py-0.5 text-[9.5px] uppercase tracking-[1.6px]"
                    style={{
                      borderColor: statusColor(r.status),
                      color: statusColor(r.status),
                    }}
                  >
                    {r.status}
                  </span>
                </td>
                <td className="py-1.5 pr-3 text-ink-3">
                  {r.duration_ms != null
                    ? `${Math.round(r.duration_ms)}ms`
                    : "—"}
                </td>
                <td className="py-1.5 pr-3 truncate max-w-[420px]">
                  {r.output_summary ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

// ── new-schedule dialog ─────────────────────────────────────────────

interface NewScheduleDialogProps {
  onClose: () => void;
  onCreated: () => void;
}

function NewScheduleDialog({ onClose, onCreated }: NewScheduleDialogProps) {
  const [playbookId, setPlaybookId] = useState("");
  const [cron, setCron] = useState("0 9 * * 1-5");
  const [tz, setTz] = useState("UTC");
  const [next5, setNext5] = useState<string[]>([]);
  const [validErr, setValidErr] = useState<string | null>(null);
  const [submitErr, setSubmitErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const handle = setTimeout(async () => {
      const out = await validateCron(cron, tz);
      if (cancelled) return;
      if (out.valid) {
        setValidErr(null);
        setNext5(out.next_5_runs ?? []);
      } else {
        setValidErr(out.error ?? "invalid");
        setNext5([]);
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [cron, tz]);

  const submit = async () => {
    setBusy(true);
    setSubmitErr(null);
    try {
      await createSchedule({
        playbook_id: playbookId.trim(),
        cron_expression: cron.trim(),
        timezone: tz.trim() || "UTC",
      });
      onCreated();
    } catch (e) {
      setSubmitErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="new schedule"
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-[520px] rounded-[12px] border border-line/60 bg-bg-0 p-5">
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
              new schedule
            </span>
            <h2 className="mt-1 font-display text-[18px] text-ink">
              Wire a playbook to a cron
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="close dialog"
            className="rounded-md border border-line/60 p-1.5 text-ink-3 transition-colors hover:border-accent hover:text-ink"
          >
            <X size={12} strokeWidth={1.7} aria-hidden />
          </button>
        </header>

        <label className="block">
          <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            playbook id
          </span>
          <input
            value={playbookId}
            onChange={(e) => setPlaybookId(e.target.value)}
            spellCheck={false}
            placeholder="_workshop.algotrade.morning_pnl"
            className="mt-1.5 w-full rounded-md border border-line/60 bg-bg-1/40 px-3 py-2 font-mono-tech text-[12px] text-ink outline-none focus:border-accent"
          />
        </label>

        <label className="mt-4 block">
          <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            cron · 5 fields or @daily/@hourly/...
          </span>
          <input
            value={cron}
            onChange={(e) => setCron(e.target.value)}
            spellCheck={false}
            className="mt-1.5 w-full rounded-md border border-line/60 bg-bg-1/40 px-3 py-2 font-mono-tech text-[12px] text-ink outline-none focus:border-accent"
          />
        </label>

        <label className="mt-4 block">
          <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            timezone
          </span>
          <input
            value={tz}
            onChange={(e) => setTz(e.target.value)}
            spellCheck={false}
            placeholder="UTC"
            className="mt-1.5 w-full rounded-md border border-line/60 bg-bg-1/40 px-3 py-2 font-mono-tech text-[12px] text-ink outline-none focus:border-accent"
          />
        </label>

        {validErr && (
          <p className="mt-3 inline-flex items-start gap-2 text-[11px] text-rose-200">
            <AlertCircle
              size={11}
              strokeWidth={1.7}
              aria-hidden
              className="mt-0.5"
            />
            <span>cron error: {validErr}</span>
          </p>
        )}

        {!validErr && next5.length > 0 && (
          <div className="mt-3 rounded-md border border-line/40 bg-bg-1/40 p-2">
            <p className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
              next 5 runs
            </p>
            <ul className="mt-1 space-y-0.5 font-mono-tech text-[10.5px] text-ink-2">
              {next5.map((iso) => (
                <li key={iso}>{new Date(iso).toLocaleString()}</li>
              ))}
            </ul>
          </div>
        )}

        {submitErr && (
          <p className="mt-3 inline-flex items-start gap-2 text-[11px] text-rose-200">
            <AlertCircle
              size={11}
              strokeWidth={1.7}
              aria-hidden
              className="mt-0.5"
            />
            <span>{submitErr}</span>
          </p>
        )}

        <div className="mt-5 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-line/60 px-3 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2 transition-colors hover:border-accent hover:text-ink"
          >
            cancel
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={busy || !playbookId.trim() || !!validErr}
            className="inline-flex items-center gap-2 rounded-md border border-line-strong bg-bg-2/60 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink transition-colors hover:border-accent disabled:opacity-50"
          >
            <CheckCircle2 size={12} strokeWidth={1.7} aria-hidden />
            {busy ? "creating…" : "create"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default Schedules;
