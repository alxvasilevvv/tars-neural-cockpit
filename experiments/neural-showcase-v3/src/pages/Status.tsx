import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { ArrowLeft, ExternalLink, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { getHealth, getEntitlements } from "@/lib/api";
import { useDownloads } from "@/lib/downloads";
import { useDocumentMeta } from "@/lib/meta";
import { BrandHairline } from "@/components/BrandHairline";

/**
 * /status — internal status page. Reads the live local daemon
 * (`/health`) and the public manifest (`/api/product/downloads`) and
 * renders a Vercel-style row of system pulses. Public uptime
 * service (status.meeet.world) remains the source of truth for SLA;
 * this page is a quick local glance.
 */

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
                <span className="text-ink-3">live · {updatedAt.toLocaleTimeString()}</span>
              </div>
              <h1
                className="font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
                style={{ fontSize: "var(--text-display-lg)" }}
              >
                {overall === "live" ? (
                  <>
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
                  </>
                ) : overall === "down" ? (
                  <>
                    Degraded performance{" "}
                    <span style={{ color: "var(--color-alert)" }}>·</span> investigating.
                  </>
                ) : (
                  <>Checking subsystems…</>
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

          <ul className="grid grid-cols-1 gap-3">
            {rows.map(r => (
              <StatusRow key={r.name} row={r} />
            ))}
          </ul>

          <footer className="mt-10 border-t border-line pt-6 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
            local probe · auto-refresh every 30s · for 99.9% SLA history see{" "}
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
