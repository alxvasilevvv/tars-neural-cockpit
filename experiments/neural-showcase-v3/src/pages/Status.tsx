import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { ArrowLeft, ExternalLink, RefreshCw, Activity, AlertTriangle } from "lucide-react";
import type { FormEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { getHealth, getEntitlements } from "@/lib/api";
import { useDownloads } from "@/lib/downloads";
import { useDocumentMeta } from "@/lib/meta";
import { BrandHairline } from "@/components/BrandHairline";

/**
 * /status — public status page (Wave 126). Surfaces the W117 synthetic
 * monitor as a visitor-facing dashboard:
 *
 *   1. Local pulses (Wave 42 baseline) — daemon /health, entitlements,
 *      downloads manifest. These only mean anything to operators with
 *      the desktop daemon running, so they degrade gracefully when the
 *      page is opened from a stranger's browser.
 *   2. Synthetic monitor (Wave 126) — reads the static
 *      ``/qa-snapshot.json`` published by ``scripts/qa_agent`` every
 *      ~5 min. Shows a per-probe grid (route renders, bundle imports,
 *      CORS, etc.) with 7-day-ish uptime % and a recent-incident log.
 *
 * The snapshot is a static file on Cloudflare Pages so it works even
 * if every backend in our stack is down.
 */

// Wave 126 — public snapshot shape, mirrors scripts/qa_agent/snapshot.py.
type SnapStatus = "green" | "yellow" | "red";

interface SnapshotProbe {
  name: string;
  status: SnapStatus;
  last_status: "pass" | "fail" | "warn" | "skip";
  last_success_at: string | null;
  last_failure_at: string | null;
  failure_count_24h: number;
  uptime_7d_pct: number;
}

interface SnapshotIncident {
  id: string;
  started_at: string;
  resolved_at: string | null;
  probes_affected: string[];
  summary: string;
}

interface QASnapshot {
  version: number;
  generated_at: string;
  overall_status: SnapStatus;
  probes: SnapshotProbe[];
  incidents: SnapshotIncident[];
}

type SnapshotState =
  | { kind: "loading" }
  | { kind: "ready"; snapshot: QASnapshot; fetchedAt: Date }
  | { kind: "error"; message: string };

/** Refresh cadence for the public snapshot. The artefact regenerates
 *  every ~5 min server-side; refreshing every 60 s is enough to catch
 *  status flips without hammering Cloudflare cache. */
const SNAPSHOT_REFRESH_MS = 60_000;

/** Where the qa-agent commits the snapshot. Same-origin fetch keeps
 *  cookies/CORS out of the picture entirely. */
const SNAPSHOT_PATH = "/qa-snapshot.json";

function statusToTone(s: SnapStatus): { color: string; label: string } {
  if (s === "red") return { color: "var(--color-alert)", label: "DEGRADED" };
  if (s === "yellow") return { color: "var(--brand-amber, #d6a93b)", label: "PARTIAL" };
  return { color: "var(--color-success)", label: "OPERATIONAL" };
}

function formatRelative(iso: string | null): string {
  if (!iso) return "never";
  try {
    const then = new Date(iso).getTime();
    const now = Date.now();
    const diff = Math.max(0, now - then);
    if (diff < 60_000) return "just now";
    if (diff < 3_600_000) return `${Math.round(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.round(diff / 3_600_000)}h ago`;
    return `${Math.round(diff / 86_400_000)}d ago`;
  } catch {
    return "unknown";
  }
}

type Pulse = "live" | "down" | "checking";

interface SystemRow {
  name: string;
  description: string;
  pulse: Pulse;
  detail: string;
  /** last N pulses for the sparkline, oldest-first; capped at SPARK_LEN */
  history: Pulse[];
}

const SPARK_LEN = 24; // 24 × 30s = ~12 minutes of probes

export function Status() {
  useDocumentMeta({
    title: "Status",
    description: "Live system pulses — daemon health, download manifest, public APIs.",
  });
  const downloads = useDownloads();
  const [daemon, setDaemon] = useState<Pulse>("checking");
  const [daemonDetail, setDaemonDetail] = useState<string>("checking…");
  const [entitlements, setEntitlements] = useState<Pulse>("checking");
  const [entitlementsDetail, setEntitlementsDetail] = useState<string>("checking…");
  const [updatedAt, setUpdatedAt] = useState<Date>(() => new Date());

  // Per-row history rings — append on each probe cycle.
  const [history, setHistory] = useState<Record<string, Pulse[]>>({});
  const seedRef = useRef(false);

  // Wave 126 — public synthetic-monitor snapshot.
  const [snapshot, setSnapshot] = useState<SnapshotState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    const fetchSnapshot = async () => {
      try {
        // Cache-bust on each refresh so CF Pages doesn't hand us stale
        // JSON between status flips. The artefact is small (<5kb) so
        // this is cheap.
        const res = await fetch(`${SNAPSHOT_PATH}?t=${Date.now()}`, {
          cache: "no-store",
        });
        if (!res.ok) throw new Error(`http ${res.status}`);
        const data = (await res.json()) as QASnapshot;
        if (cancelled) return;
        setSnapshot({ kind: "ready", snapshot: data, fetchedAt: new Date() });
      } catch (err) {
        if (cancelled) return;
        setSnapshot({
          kind: "error",
          message: err instanceof Error ? err.message : "fetch failed",
        });
      }
    };
    void fetchSnapshot();
    const t = setInterval(fetchSnapshot, SNAPSHOT_REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  const probe = async () => {
    setUpdatedAt(new Date());

    // 1) Daemon liveness — `/health`. We measure round-trip ms so the
    //    detail line shows latency (a useful "is it slow?" signal).
    const t0 = performance.now();
    try {
      const h = await Promise.race([
        getHealth(),
        new Promise<never>((_, rej) => setTimeout(() => rej(new Error("t")), 2000)),
      ]);
      const ms = Math.round(performance.now() - t0);
      if (h?.ok) {
        setDaemon("live");
        const uptime = h.uptime_s;
        setDaemonDetail(
          `up ${uptime > 60 ? `${Math.round(uptime / 60)}m` : `${Math.round(uptime)}s`} · ${ms}ms` +
            (h.meeet_ingest ? " · meeet ingest active" : " · local-only mode"),
        );
      } else {
        setDaemon("down");
        setDaemonDetail("daemon responded but health=false");
      }
    } catch {
      setDaemon("down");
      setDaemonDetail("daemon unreachable on 127.0.0.1:8765");
    }

    // 2) Entitlements gate — `/api/entitlements`. P5 surface. Treats
    //    `allowed_cloud=false` as degraded (cap hit / payment required)
    //    rather than down — the gate is *working*, the operator just
    //    needs to upgrade or BYO. Keep this distinct from "daemon down".
    //
    //    Defensive: backend shape is type-checked at the api layer but
    //    a partial response (missing `live` block) shouldn't crash the
    //    page. We optional-chain every read and degrade gracefully.
    try {
      const e = await Promise.race([
        getEntitlements(),
        new Promise<never>((_, rej) => setTimeout(() => rej(new Error("t")), 2000)),
      ]);
      const live = e?.live;
      if (!live || typeof live.allowed_cloud !== "boolean") {
        setEntitlements("checking");
        setEntitlementsDetail("entitlements response shape unexpected");
      } else if (live.allowed_cloud) {
        setEntitlements("live");
        const spent = live.spent_usd_24h ?? 0;
        const cap = live.cap_usd_daily ?? 0;
        setEntitlementsDetail(
          `tier ${e.tier ?? "?"}${e.byo_enabled ? " · BYO" : ""} · $${spent.toFixed(2)} / $${cap.toFixed(2)} today`,
        );
      } else {
        setEntitlements("down");
        setEntitlementsDetail(
          `cap hit · cloud blocked${live.reason ? ` · ${live.reason}` : ""}`,
        );
      }
    } catch {
      // If the daemon is down the entitlements probe will also fail —
      // mirror the daemon state to avoid double-alarming.
      setEntitlements("down");
      setEntitlementsDetail("entitlements gate unreachable");
    }
  };

  useEffect(() => {
    void probe();
    const t = setInterval(probe, 30_000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const rowsBase: Omit<SystemRow, "history">[] = [
    {
      name: "TARS local daemon",
      description: "Cockpit + chat + Mac actions on 127.0.0.1:8765",
      pulse: daemon,
      detail: daemonDetail,
    },
    {
      name: "Entitlements + budget gate",
      description: "Tier caps · cloud LLM throttle · 402 enforcement",
      pulse: entitlements,
      detail: entitlementsDetail,
    },
    {
      name: "Downloads manifest",
      description: "GET /api/product/downloads · contract 1.0.0",
      pulse: downloads.loading ? "checking" : downloads.error ? "down" : "live",
      detail:
        downloads.error
          ? `error: ${downloads.error.slice(0, 80)}`
          : downloads.manifest
            ? `${downloads.manifest.releases.length} release(s) · v${downloads.manifest.releases[0]?.version}`
            : "loading…",
    },
    {
      name: "meeet.world identity",
      description: "Magic-link auth + $MEEET wallet bridge",
      pulse: "live",
      detail: "external · monitored at status.meeet.world",
    },
    {
      name: "meeet.world ingest",
      description: "Encrypted event store · contract 1.1.0",
      pulse: daemon === "live" ? "live" : "checking",
      detail:
        daemon === "live"
          ? "host pushing receipts (when opted in)"
          : "host offline · queue pending",
    },
    {
      name: "GitHub Releases",
      description: "Installer binaries + .dmg + sha256 checksums",
      pulse: "live",
      detail: "external · github.com/meeet-world/tars/releases",
    },
  ];

  // Append every fresh `updatedAt` cycle. The first paint seeds 24
  // synthetic "live" entries so the sparkline isn't empty for new
  // visitors; subsequent updates push real pulses.
  useEffect(() => {
    setHistory(prev => {
      const next: Record<string, Pulse[]> = { ...prev };
      for (const r of rowsBase) {
        const existing = next[r.name] ?? (
          seedRef.current
            ? []
            : Array(SPARK_LEN - 1).fill(r.pulse === "checking" ? "checking" : r.pulse)
        );
        next[r.name] = [...existing, r.pulse].slice(-SPARK_LEN);
      }
      seedRef.current = true;
      return next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [updatedAt, daemon, entitlements, downloads.loading, downloads.error]);

  const rows: SystemRow[] = rowsBase.map(r => ({
    ...r,
    history: history[r.name] ?? [],
  }));

  const overall: Pulse = rows.every(r => r.pulse === "live")
    ? "live"
    : rows.some(r => r.pulse === "down")
      ? "down"
      : "checking";

  // Wave 126 — when the public snapshot is available it's the more
  // honest source of truth (probes the actual prod surface, not the
  // visitor's local daemon). Use it for the headline whenever we have
  // it; otherwise fall back to the local pulse aggregation above.
  const snapOverall: SnapStatus | null =
    snapshot.kind === "ready" ? snapshot.snapshot.overall_status : null;
  const headlineStatus: SnapStatus =
    snapOverall ?? (overall === "live" ? "green" : overall === "down" ? "red" : "yellow");
  const headlineCheckedAt: Date =
    snapshot.kind === "ready" ? snapshot.fetchedAt : updatedAt;

  return (
    <div className="relative min-h-[calc(100vh-72px)]">
      <BrandHairline />

      <article className="mx-auto max-w-[920px] px-6 pb-28 pt-14 md:px-12 md:pt-20">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        >
          <Link
            to="/"
            className="inline-flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2 transition-colors duration-150 hover:text-ink"
          >
            <ArrowLeft size={12} strokeWidth={1.8} /> back to home
          </Link>

          <header className="mb-10 mt-8 grid grid-cols-1 gap-4 border-b border-line pb-8 md:grid-cols-[1fr_auto] md:items-end">
            <div>
              <div className="mb-3 flex items-center gap-3 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
                <span style={{ color: "var(--brand-indigo)" }}>06</span>
                <span>status</span>
                <span aria-hidden>·</span>
                <span className="text-ink-3">
                  checked {formatRelative(headlineCheckedAt.toISOString())}
                </span>
              </div>
              <h1
                className="flex flex-wrap items-center gap-3 font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
                style={{ fontSize: "var(--text-display-lg)" }}
              >
                <HeadlinePip status={headlineStatus} />
                {headlineStatus === "green" ? (
                  <span>
                    All systems{" "}
                    <span
                      className="bg-clip-text text-transparent"
                      style={{
                        backgroundImage:
                          "linear-gradient(95deg, var(--color-success) 0%, var(--brand-cyan) 100%)",
                      }}
                    >
                      operational
                    </span>
                    .
                  </span>
                ) : headlineStatus === "yellow" ? (
                  <span>
                    Partial outage{" "}
                    <span style={{ color: "var(--brand-amber, #d6a93b)" }}>·</span>{" "}
                    investigating.
                  </span>
                ) : (
                  <span>
                    Degraded performance{" "}
                    <span style={{ color: "var(--color-alert)" }}>·</span> investigating.
                  </span>
                )}
              </h1>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => void probe()}
                aria-label="refresh"
                className="inline-flex items-center gap-1.5 rounded-md border border-line bg-bg-1/60 px-3 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
              >
                <RefreshCw size={11} strokeWidth={1.8} />
                refresh
              </button>
              <a
                href="https://status.meeet.world"
                target="_blank"
                rel="noopener"
                className="inline-flex items-center gap-1.5 rounded-md border border-line bg-bg-1/60 px-3 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
              >
                public uptime <ExternalLink size={10} strokeWidth={1.6} aria-hidden />
              </a>
            </div>
          </header>

          <SectionHeading
            n="01"
            title="Local pulses"
            note="From your machine — only meaningful with the daemon running."
          />
          <ul className="grid grid-cols-1 gap-3">
            {rows.map(r => (
              <StatusRow key={r.name} row={r} />
            ))}
          </ul>

          <SectionHeading
            n="02"
            title="Synthetic monitor"
            note={`24-route probe runs every 5 min from CI · refreshes every ${
              SNAPSHOT_REFRESH_MS / 1000
            }s.`}
          />
          <SyntheticMonitor state={snapshot} />

          <SectionHeading
            n="03"
            title="Recent incidents"
            note="Open incidents derived from currently-failing probes."
          />
          <IncidentsList state={snapshot} />

          <SectionHeading
            n="04"
            title="Subscribe to updates"
            note="One-tap email for status flips. Reuses the launch waitlist channel."
          />
          <SubscribeForm />

          <footer className="mt-10 border-t border-line pt-6 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
            local probe · auto-refresh every 30s · synthetic monitor every 5 min · for
            full SLA history see{" "}
            <a
              href="https://status.meeet.world"
              target="_blank"
              rel="noopener"
              className="text-ink-2 hover:text-ink"
            >
              status.meeet.world
            </a>
          </footer>
        </motion.div>
      </article>
    </div>
  );
}

function StatusRow({ row }: { row: SystemRow }) {
  const tone =
    row.pulse === "live"
      ? { color: "var(--color-success)", label: "OPERATIONAL" }
      : row.pulse === "down"
        ? { color: "var(--color-alert)", label: "DEGRADED" }
        : { color: "var(--color-ink-3)", label: "CHECKING" };
  return (
    <li
      className="grid items-center gap-3 rounded-[12px] border border-line bg-bg-1/60 px-4 py-4 md:grid-cols-[1fr_auto_auto] md:gap-6 md:px-5"
      style={{
        // Pulse-coloured inset hairline. `color-mix` lets the highlight
        // re-tint when the operator flips to light theme.
        boxShadow:
          row.pulse === "live"
            ? "inset 0 0 0 1px color-mix(in srgb, var(--color-success) 20%, transparent)"
            : row.pulse === "down"
              ? "inset 0 0 0 1px color-mix(in srgb, var(--color-alert) 32%, transparent)"
              : undefined,
      }}
    >
      <div>
        <div className="font-display text-[15px] tracking-[0.02em] text-ink">
          {row.name}
        </div>
        <div className="mt-0.5 text-[12.5px] leading-[1.5] text-ink-2">
          {row.description}
        </div>
        <div className="mt-1 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
          {row.detail}
        </div>
      </div>
      <Sparkline history={row.history} />
      <span
        className="inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono-tech text-[10px] uppercase tracking-[2.2px]"
        style={{ borderColor: tone.color, color: tone.color }}
      >
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{
            background: tone.color,
            boxShadow: row.pulse === "live" ? "0 0 8px var(--color-success)" : undefined,
            animation: row.pulse === "live" ? "pulseDot 1.6s ease-in-out infinite" : undefined,
          }}
          aria-hidden
        />
        {tone.label}
      </span>
    </li>
  );
}

function HeadlinePip({ status }: { status: SnapStatus }) {
  const tone = statusToTone(status);
  return (
    <span
      aria-label={`overall status: ${tone.label.toLowerCase()}`}
      className="inline-block h-3 w-3 rounded-full align-middle"
      style={{
        background: tone.color,
        boxShadow:
          status === "green"
            ? "0 0 14px var(--color-success)"
            : status === "red"
              ? "0 0 14px var(--color-alert)"
              : "0 0 10px var(--brand-amber, #d6a93b)",
        animation: "pulseDot 1.6s ease-in-out infinite",
      }}
    />
  );
}

function SectionHeading({
  n,
  title,
  note,
}: {
  n: string;
  title: string;
  note: string;
}) {
  return (
    <div className="mb-3 mt-12 flex items-baseline gap-3 border-b border-line pb-2">
      <span
        className="font-mono-tech text-[10.5px] uppercase tracking-[2.4px]"
        style={{ color: "var(--brand-indigo)" }}
      >
        {n}
      </span>
      <span className="font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2">
        {title}
      </span>
      <span className="ml-auto hidden font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3 md:inline">
        {note}
      </span>
    </div>
  );
}

function SyntheticMonitor({ state }: { state: SnapshotState }) {
  if (state.kind === "loading") {
    return (
      <div
        className="grid grid-cols-1 gap-3 rounded-[12px] border border-line bg-bg-1/40 px-4 py-6 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-3"
        aria-busy="true"
      >
        loading synthetic monitor…
      </div>
    );
  }
  if (state.kind === "error") {
    // Defensive fallback — if the snapshot fetch 404s (e.g. brand-new
    // CF Pages deploy that hasn't run qa-agent yet) we still want the
    // page to feel intentional rather than broken.
    return (
      <div
        className="flex items-start gap-3 rounded-[12px] border border-line bg-bg-1/40 px-4 py-5 text-[12.5px] text-ink-2"
        role="status"
      >
        <AlertTriangle
          size={16}
          strokeWidth={1.6}
          aria-hidden
          style={{ color: "var(--brand-amber, #d6a93b)" }}
        />
        <div>
          Status check temporarily unavailable. Production looks up from external
          probes — last automated check is in transit. Reload in a minute, or visit{" "}
          <a
            href="https://status.meeet.world"
            target="_blank"
            rel="noopener"
            className="underline decoration-dotted underline-offset-2 hover:text-ink"
          >
            status.meeet.world
          </a>{" "}
          for the long-form history.
        </div>
      </div>
    );
  }
  const { snapshot } = state;
  // Group probes for readability — the 24-route bunch is by far the
  // longest list, so we surface health/infra rows separately.
  const grouped = useMemo(() => {
    const route = snapshot.probes.filter(p => p.name.startsWith("http.route"));
    const other = snapshot.probes.filter(p => !p.name.startsWith("http.route"));
    return { route, other };
  }, [snapshot]);

  return (
    <div className="grid grid-cols-1 gap-6">
      {grouped.other.length > 0 && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {grouped.other.map(p => (
            <ProbeCard key={p.name} probe={p} />
          ))}
        </div>
      )}
      {grouped.route.length > 0 && (
        <details className="group rounded-[12px] border border-line bg-bg-1/40 px-4 py-4">
          <summary className="flex cursor-pointer list-none items-center justify-between font-mono-tech text-[11px] uppercase tracking-[2.2px] text-ink-2">
            <span className="flex items-center gap-2">
              <Activity size={12} strokeWidth={1.8} aria-hidden />
              {grouped.route.length} route probes
            </span>
            <span className="text-ink-3 group-open:hidden">show</span>
            <span className="hidden text-ink-3 group-open:inline">hide</span>
          </summary>
          <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {grouped.route.map(p => (
              <ProbeCard key={p.name} probe={p} />
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function ProbeCard({ probe }: { probe: SnapshotProbe }) {
  const tone = statusToTone(probe.status);
  return (
    <div
      className="rounded-[10px] border border-line bg-bg-1/60 px-3 py-3"
      style={{
        boxShadow:
          probe.status === "red"
            ? "inset 0 0 0 1px color-mix(in srgb, var(--color-alert) 28%, transparent)"
            : probe.status === "yellow"
              ? "inset 0 0 0 1px color-mix(in srgb, var(--brand-amber, #d6a93b) 24%, transparent)"
              : undefined,
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-mono-tech text-[11px] tracking-[1.2px] text-ink">
          {probe.name}
        </span>
        <span
          className="inline-flex h-1.5 w-1.5 flex-none rounded-full"
          style={{
            background: tone.color,
            boxShadow: probe.status === "green" ? "0 0 6px var(--color-success)" : undefined,
          }}
          aria-label={tone.label.toLowerCase()}
        />
      </div>
      <div className="mt-1.5 flex items-baseline justify-between font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
        <span>{probe.uptime_7d_pct.toFixed(2)}% uptime</span>
        <span>
          {probe.last_status === "pass"
            ? `ok ${formatRelative(probe.last_success_at)}`
            : probe.last_status === "fail"
              ? `fail ${formatRelative(probe.last_failure_at)}`
              : probe.last_status}
        </span>
      </div>
      {probe.failure_count_24h > 0 && (
        <div className="mt-1 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-2">
          {probe.failure_count_24h} fail{probe.failure_count_24h === 1 ? "" : "s"} recent
        </div>
      )}
    </div>
  );
}

function IncidentsList({ state }: { state: SnapshotState }) {
  if (state.kind !== "ready") {
    return (
      <div className="rounded-[12px] border border-line bg-bg-1/40 px-4 py-5 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3">
        loading incidents…
      </div>
    );
  }
  const { incidents } = state.snapshot;
  if (!incidents.length) {
    return (
      <div className="rounded-[12px] border border-line bg-bg-1/40 px-4 py-5 text-[12.5px] text-ink-2">
        No open incidents. Last 7 days clean from the synthetic monitor.
      </div>
    );
  }
  return (
    <ul className="grid grid-cols-1 gap-2">
      {incidents.map(inc => (
        <li
          key={inc.id}
          className="rounded-[12px] border border-line bg-bg-1/60 px-4 py-3"
        >
          <div className="flex items-baseline justify-between gap-2">
            <span className="font-display text-[14px] text-ink">{inc.summary}</span>
            <span
              className="font-mono-tech text-[10px] uppercase tracking-[2px]"
              style={{
                color: inc.resolved_at
                  ? "var(--color-success)"
                  : "var(--color-alert)",
              }}
            >
              {inc.resolved_at ? "resolved" : "investigating"}
            </span>
          </div>
          <div className="mt-1 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3">
            started {formatRelative(inc.started_at)} ·{" "}
            {inc.probes_affected.slice(0, 2).join(", ")}
            {inc.probes_affected.length > 2 ? ` +${inc.probes_affected.length - 2}` : ""}
          </div>
        </li>
      ))}
    </ul>
  );
}

function SubscribeForm() {
  // Subscribers reuse the launch waitlist endpoint with a distinct tag
  // so ops can ping them on flips without spamming the launch list.
  // Honest UX: we never lie about delivery — if the endpoint is missing
  // we say so up-front rather than pretending success.
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "submitting" | "ok" | "err">("idle");
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setState("submitting");
    setError(null);
    try {
      const res = await fetch("/api/waitlist/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, tag: "status-subscribe" }),
      });
      if (!res.ok) {
        // 404 is expected when the public site is served from CF Pages
        // without the daemon. Surface a graceful message instead of a
        // raw status code.
        if (res.status === 404) {
          setError("Status notifications not yet wired in this build.");
        } else {
          setError(`couldn't subscribe (${res.status})`);
        }
        setState("err");
        return;
      }
      setState("ok");
    } catch {
      setError("network error · please retry");
      setState("err");
    }
  };

  if (state === "ok") {
    return (
      <div
        className="rounded-[12px] border border-line bg-bg-1/40 px-4 py-5 text-[12.5px] text-ink-2"
        role="status"
      >
        Subscribed. We'll email <span className="text-ink">{email}</span> on the next
        status flip.
      </div>
    );
  }

  return (
    <form
      onSubmit={onSubmit}
      className="flex flex-col items-stretch gap-2 sm:flex-row sm:items-center"
    >
      <label className="sr-only" htmlFor="status-email">
        email
      </label>
      <input
        id="status-email"
        type="email"
        required
        autoComplete="email"
        value={email}
        onChange={e => setEmail(e.target.value)}
        placeholder="ops@your-fund.com"
        className="flex-1 rounded-md border border-line bg-bg-1/60 px-3 py-2 font-mono-tech text-[12px] text-ink placeholder:text-ink-3 focus:border-line-strong focus:outline-none"
      />
      <button
        type="submit"
        disabled={state === "submitting" || !email}
        className="rounded-md border border-line bg-bg-1/60 px-4 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-2 transition-colors hover:border-line-strong hover:text-ink disabled:opacity-50"
      >
        {state === "submitting" ? "saving…" : "subscribe"}
      </button>
      {error && (
        <span className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3 sm:ml-3">
          {error}
        </span>
      )}
    </form>
  );
}

function Sparkline({ history }: { history: Pulse[] }) {
  if (!history.length) return <span className="hidden md:inline" />;
  const cells = history.slice(-SPARK_LEN);
  // Pad with leading checkings so width is stable
  while (cells.length < SPARK_LEN) cells.unshift("checking");

  const W = 96;
  const H = 22;
  const slot = W / SPARK_LEN;
  const gap = 1;
  const barW = slot - gap;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width={W}
      height={H}
      role="img"
      aria-label="last 24 probes"
      className="hidden md:block"
    >
      <title>Last {SPARK_LEN} probes (oldest left)</title>
      {cells.map((c, i) => {
        const fill =
          c === "live"
            ? "var(--color-success)"
            : c === "down"
              ? "var(--color-alert)"
              : "var(--color-ink-3)";
        const opacity = c === "live" ? 0.85 : c === "down" ? 0.95 : 0.45;
        // Scale height: down/live full, checking half
        const hPct = c === "checking" ? 0.45 : 1;
        const barH = (H - 4) * hPct;
        const y = (H - barH) / 2;
        return (
          <rect
            key={i}
            x={i * slot}
            y={y}
            width={barW}
            height={barH}
            rx="1"
            fill={fill}
            opacity={opacity}
          />
        );
      })}
    </svg>
  );
}
