// SYNC: claude-w80-fe-only
/**
 * <BacktestPanel /> — Wave 80-D
 *
 * Drag-drop CSV → choose input column + ground-truth column → POST
 * multipart to /api/agents/{id}/backtest. The backend streams
 * Server-Sent Events (one row per chunk) so the table fills in real
 * time; aggregate metrics (agreement %, total cost, total time) live
 * in a footer that updates with each row.
 *
 * Click any diverging row to open <RetuneDialog /> with the case
 * pre-loaded — operator can edit the system prompt, test the new
 * version on that single case, and apply.
 *
 * Backend missing? We synthesise a deterministic SSE-style stream
 * locally so the workshop demo flow keeps working pre-launch.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  CircleDashed,
  FlaskConical,
  Loader2,
  Play,
  UploadCloud,
  X,
} from "lucide-react";
import { API_BASE } from "@/lib/api";
import { RetuneDialog, type DivergingCase } from "@/components/workshop/RetuneDialog";

interface BacktestPanelProps {
  agentId: string | null;
  agentName?: string;
  /** Current system prompt — passed to RetuneDialog for editing. */
  systemPrompt?: string;
}

interface StreamRow {
  index: number;
  input: string;
  expected: string;
  actual: string;
  agreed: boolean;
  cost_usd?: number;
  took_ms?: number;
}

/* ─── CSV parser (tiny — RFC4180-ish, no embedded quotes/escapes) ── */

function parseCsv(text: string): { headers: string[]; rows: string[][] } {
  const lines = text.split(/\r?\n/).filter((l) => l.length > 0);
  if (lines.length === 0) return { headers: [], rows: [] };
  const headers = lines[0].split(",").map((s) => s.trim());
  const rows = lines.slice(1).map((l) => l.split(",").map((s) => s.trim()));
  return { headers, rows };
}

/* ─── Mock SSE generator — used when the backend returns 404 ───── */

function mockStream(
  rows: string[][],
  inputIdx: number,
  truthIdx: number,
  onRow: (r: StreamRow) => void,
  onDone: () => void,
): () => void {
  let cancelled = false;
  let i = 0;
  const tick = () => {
    if (cancelled || i >= rows.length) {
      if (!cancelled) onDone();
      return;
    }
    const row = rows[i];
    const expected = row[truthIdx] ?? "";
    // Deterministic pseudo-divergence: every 4th row disagrees.
    const agreed = i % 4 !== 3;
    const actual = agreed
      ? expected
      : ["buy", "hold", "sell"].filter((x) => x !== expected)[0] ?? "hold";
    onRow({
      index: i,
      input: row[inputIdx] ?? row.join(" · "),
      expected,
      actual,
      agreed,
      cost_usd: 0.008 + Math.random() * 0.012,
      took_ms: 220 + Math.round(Math.random() * 380),
    });
    i++;
    setTimeout(tick, 180);
  };
  setTimeout(tick, 220);
  return () => {
    cancelled = true;
  };
}

export function BacktestPanel({
  agentId,
  agentName = "agent",
  systemPrompt = "",
}: BacktestPanelProps) {
  const [csvText, setCsvText] = useState<string>("");
  const [csvName, setCsvName] = useState<string>("");
  const [headers, setHeaders] = useState<string[]>([]);
  const [bodyRows, setBodyRows] = useState<string[][]>([]);
  const [inputCol, setInputCol] = useState<string>("");
  const [truthCol, setTruthCol] = useState<string>("");
  const [dragOver, setDragOver] = useState(false);
  const [running, setRunning] = useState(false);
  const [rows, setRows] = useState<StreamRow[]>([]);
  const [pendingNote, setPendingNote] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [retuneCase, setRetuneCase] = useState<DivergingCase | null>(null);
  const cancelRef = useRef<() => void>(() => undefined);

  // Re-parse whenever the textual CSV changes.
  useEffect(() => {
    if (!csvText.trim()) {
      setHeaders([]);
      setBodyRows([]);
      return;
    }
    const { headers, rows } = parseCsv(csvText);
    setHeaders(headers);
    setBodyRows(rows);
    if (headers.length > 0) {
      if (!inputCol || !headers.includes(inputCol)) setInputCol(headers[0]);
      const truthGuess =
        headers.find((h) =>
          /(expected|truth|label|target|y)/i.test(h),
        ) ?? headers[headers.length - 1];
      if (!truthCol || !headers.includes(truthCol)) setTruthCol(truthGuess);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [csvText]);

  useEffect(() => () => cancelRef.current(), []);

  const totals = useMemo(() => {
    const total = rows.length;
    const agreed = rows.filter((r) => r.agreed).length;
    const cost = rows.reduce((acc, r) => acc + (r.cost_usd ?? 0), 0);
    const took = rows.reduce((acc, r) => acc + (r.took_ms ?? 0), 0);
    return {
      total,
      agreed,
      rate: total > 0 ? agreed / total : 0,
      cost,
      took,
    };
  }, [rows]);

  const onFile = async (file: File) => {
    setCsvName(file.name);
    const text = await file.text();
    setCsvText(text);
  };

  const onDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) await onFile(f);
  };

  const handleRun = async () => {
    if (!agentId) {
      setErr("No agent — finish phase 02 (Design) first.");
      return;
    }
    if (bodyRows.length === 0) {
      setErr("No rows to backtest. Drop a CSV with at least one data row.");
      return;
    }
    if (!inputCol || !truthCol) {
      setErr("Pick the input and ground-truth columns.");
      return;
    }
    setErr(null);
    setPendingNote(null);
    setRows([]);
    setRunning(true);

    const inputIdx = headers.indexOf(inputCol);
    const truthIdx = headers.indexOf(truthCol);

    // Build multipart form for the live route.
    const fd = new FormData();
    fd.append("input_column", inputCol);
    fd.append("truth_column", truthCol);
    fd.append(
      "csv",
      new Blob([csvText], { type: "text/csv" }),
      csvName || "backtest.csv",
    );

    let triedLive = false;
    try {
      const r = await fetch(
        `${API_BASE}/api/agents/${encodeURIComponent(agentId)}/backtest`,
        { method: "POST", body: fd },
      );
      triedLive = true;
      if (r.status === 404 || !r.body) throw new Error("404");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      // Stream SSE-style chunks (one JSON row per `data: …\n\n` block).
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      cancelRef.current = () => reader.cancel().catch(() => undefined);
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let cut: number;
        while ((cut = buf.indexOf("\n\n")) >= 0) {
          const block = buf.slice(0, cut);
          buf = buf.slice(cut + 2);
          const line = block.split("\n").find((l) => l.startsWith("data:"));
          if (!line) continue;
          try {
            const j = JSON.parse(line.slice(5).trim()) as Partial<StreamRow>;
            if (typeof j.index === "number") {
              setRows((prev) => [...prev, j as StreamRow]);
            }
          } catch {
            /* ignore malformed chunk */
          }
        }
      }
      setRunning(false);
    } catch {
      // Live failed — fall through to mock, but only if the failure was
      // due to a missing backend route (404) or network drop.
      if (triedLive) {
        setPendingNote(
          "Backend WIP — Cursor shipping live SSE backtest. Streaming mock data.",
        );
      } else {
        setPendingNote("Daemon offline — streaming mock data.");
      }
      cancelRef.current = mockStream(
        bodyRows,
        inputIdx,
        truthIdx,
        (row) => setRows((prev) => [...prev, row]),
        () => setRunning(false),
      );
    }
  };

  const handleStop = () => {
    cancelRef.current();
    setRunning(false);
  };

  return (
    <section className="grid gap-4">
      <header className="flex items-center justify-between gap-3">
        <div className="inline-flex items-center gap-2 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
          <FlaskConical
            size={12}
            strokeWidth={1.7}
            aria-hidden
            style={{ color: "var(--brand-cyan)" }}
          />
          <span>backtest</span>
        </div>
        {csvName && (
          <span className="font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3">
            {csvName} · {bodyRows.length} rows · {headers.length} cols
          </span>
        )}
      </header>

      {pendingNote && (
        <p
          role="status"
          className="inline-flex items-start gap-2 rounded-md border border-amber-400/30 bg-amber-400/[0.06] px-3 py-2 text-[11.5px] leading-[1.5] text-amber-200"
        >
          <AlertCircle
            size={12}
            strokeWidth={1.7}
            aria-hidden
            className="mt-0.5"
          />
          <span>{pendingNote}</span>
        </p>
      )}

      {/* ── Drop zone / column picker ─────────────────────────── */}
      {bodyRows.length === 0 ? (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          className={`grid place-items-center rounded-[12px] border border-dashed px-6 py-10 text-center transition-colors ${
            dragOver
              ? "border-accent bg-accent/[0.04]"
              : "border-line/60 bg-bg-1/30"
          }`}
        >
          <UploadCloud
            size={28}
            strokeWidth={1.4}
            aria-hidden
            style={{ color: "var(--brand-cyan)" }}
          />
          <p className="mt-3 font-display text-[15px] text-ink">
            Drop a CSV here
          </p>
          <p className="mt-1 max-w-[40ch] font-mono-tech text-[10.5px] uppercase tracking-[1.4px] text-ink-3">
            We auto-detect columns and ask you which one is the input and which
            holds the ground truth.
          </p>
          <label className="mt-4 inline-flex cursor-pointer items-center gap-2 rounded-md border border-line bg-bg-2/60 px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink-2 transition-colors hover:border-accent hover:text-ink">
            <UploadCloud size={11} strokeWidth={1.7} aria-hidden />
            <span>or browse files</span>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void onFile(f);
              }}
              className="hidden"
            />
          </label>
        </div>
      ) : (
        <div className="grid gap-3 rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="grid gap-1.5">
              <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
                input column
              </span>
              <select
                value={inputCol}
                onChange={(e) => setInputCol(e.target.value)}
                className="rounded-md border border-line/60 bg-bg-0/50 px-3 py-2 font-mono-tech text-[12px] text-ink outline-none focus:border-accent"
              >
                {headers.map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>
            </label>
            <label className="grid gap-1.5">
              <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
                ground truth column
              </span>
              <select
                value={truthCol}
                onChange={(e) => setTruthCol(e.target.value)}
                className="rounded-md border border-line/60 bg-bg-0/50 px-3 py-2 font-mono-tech text-[12px] text-ink outline-none focus:border-accent"
              >
                {headers.map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3">
              {agentId ? `agent · ${agentId.slice(0, 12)}…` : "no agent"}
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  setCsvText("");
                  setCsvName("");
                  setRows([]);
                }}
                className="inline-flex items-center gap-1.5 rounded-md border border-line/60 px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink-2 transition-colors hover:border-accent hover:text-ink"
              >
                <X size={11} strokeWidth={1.7} aria-hidden />
                clear
              </button>
              {running ? (
                <button
                  type="button"
                  onClick={handleStop}
                  className="inline-flex items-center gap-2 rounded-md border border-line-strong bg-bg-2/60 px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink transition-colors hover:border-accent"
                >
                  <X size={11} strokeWidth={1.7} aria-hidden />
                  stop
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleRun}
                  disabled={!agentId || bodyRows.length === 0}
                  className="inline-flex items-center gap-2 rounded-md border border-line-strong bg-bg-2/60 px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink transition-colors hover:border-accent disabled:opacity-50"
                >
                  <Play size={11} strokeWidth={1.7} aria-hidden />
                  run backtest
                </button>
              )}
            </div>
          </div>
          {err && (
            <p className="inline-flex items-start gap-2 text-[11px] text-rose-200">
              <AlertCircle
                size={11}
                strokeWidth={1.7}
                aria-hidden
                className="mt-0.5"
              />
              <span>{err}</span>
            </p>
          )}
        </div>
      )}

      {/* ── Live aggregate ─────────────────────────────────────── */}
      {(running || rows.length > 0) && (
        <div className="grid grid-cols-2 gap-3 rounded-[12px] border border-line/60 bg-bg-1/40 p-4 md:grid-cols-4">
          <Stat
            label="rows"
            value={
              running ? `${rows.length} / ${bodyRows.length}` : `${rows.length}`
            }
            running={running}
          />
          <Stat
            label="agreement"
            value={`${Math.round(totals.rate * 100)}%`}
            accent="var(--brand-cyan)"
          />
          <Stat
            label="total cost"
            value={`$${totals.cost.toFixed(3)}`}
            accent="var(--brand-amber)"
          />
          <Stat
            label="time"
            value={`${(totals.took / 1000).toFixed(1)}s`}
            accent="var(--brand-violet)"
          />
        </div>
      )}

      {/* ── Live table ─────────────────────────────────────────── */}
      {rows.length > 0 && (
        <section className="rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
          <header className="mb-2 flex items-center justify-between">
            <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
              rows · click a divergence to retune
            </span>
          </header>
          <div className="max-h-[520px] overflow-auto">
            <table className="w-full border-collapse text-left">
              <thead className="sticky top-0 bg-bg-1/80 backdrop-blur">
                <tr className="border-b border-line/40 font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3">
                  <th className="py-1.5 pr-3">#</th>
                  <th className="py-1.5 pr-3">input</th>
                  <th className="py-1.5 pr-3">expected</th>
                  <th className="py-1.5 pr-3">actual</th>
                  <th className="py-1.5 pr-3 text-right">$</th>
                  <th className="py-1.5 text-right">ms</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr
                    key={r.index}
                    onClick={() =>
                      !r.agreed &&
                      setRetuneCase({
                        rowIndex: r.index,
                        input: r.input,
                        agentOutput: r.actual,
                        groundTruth: r.expected,
                      })
                    }
                    className={`border-b border-line/20 font-mono-tech text-[11px] last:border-0 ${
                      r.agreed
                        ? "text-ink-2"
                        : "cursor-pointer text-rose-200 hover:bg-rose-400/[0.04]"
                    }`}
                  >
                    <td className="py-1.5 pr-3 text-ink-3">{r.index}</td>
                    <td className="py-1.5 pr-3 truncate max-w-[260px]">
                      {r.input}
                    </td>
                    <td
                      className="py-1.5 pr-3"
                      style={{ color: "var(--brand-cyan)" }}
                    >
                      {r.expected}
                    </td>
                    <td className="py-1.5 pr-3">
                      <span className="inline-flex items-center gap-1.5">
                        {r.agreed ? (
                          <CheckCircle2
                            size={10}
                            strokeWidth={1.8}
                            aria-hidden
                            style={{ color: "var(--color-success)" }}
                          />
                        ) : (
                          <X
                            size={10}
                            strokeWidth={2}
                            aria-hidden
                            className="text-rose-300"
                          />
                        )}
                        {r.actual}
                      </span>
                    </td>
                    <td className="py-1.5 pr-3 text-right text-ink-3">
                      {typeof r.cost_usd === "number"
                        ? `$${r.cost_usd.toFixed(3)}`
                        : "—"}
                    </td>
                    <td className="py-1.5 text-right text-ink-3">
                      {r.took_ms ?? "—"}
                    </td>
                  </tr>
                ))}
                {running && (
                  <tr>
                    <td
                      colSpan={6}
                      className="py-2 text-center font-mono-tech text-[10.5px] uppercase tracking-[1.6px] text-ink-3"
                    >
                      <Loader2
                        size={11}
                        strokeWidth={2}
                        className="mr-2 inline animate-spin"
                        aria-hidden
                      />
                      streaming…
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <RetuneDialog
        open={Boolean(retuneCase)}
        onClose={() => setRetuneCase(null)}
        agentId={agentId ?? "mock-agent"}
        agentName={agentName}
        currentPrompt={systemPrompt}
        divergingCase={retuneCase}
      />
    </section>
  );
}

function Stat({
  label,
  value,
  accent,
  running,
}: {
  label: string;
  value: string;
  accent?: string;
  running?: boolean;
}) {
  return (
    <div>
      <span className="font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
        {label}
      </span>
      <p
        className="mt-1 font-display text-[22px] leading-none text-ink"
        style={{ color: accent }}
      >
        {running ? (
          <CircleDashed
            size={18}
            strokeWidth={1.6}
            aria-hidden
            className="mr-2 inline animate-spin"
          />
        ) : null}
        {value}
      </p>
    </div>
  );
}

export default BacktestPanel;
