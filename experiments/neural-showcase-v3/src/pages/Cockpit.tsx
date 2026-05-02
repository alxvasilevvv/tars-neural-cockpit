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
import { useDocumentMeta } from "@/lib/meta";
import type { DomainPack, DomainAction, InvokeResult } from "@/lib/api";
import { CornerFrame, StatusLozenge, BarStack } from "@/components/Glyphs";
import { Waveform } from "@/components/Waveform";
import { sound } from "@/lib/sound";
import { AwarenessTicker } from "@/components/AwarenessTicker";
import { ChatPane } from "@/components/ChatPane";
import { CommandPalette } from "@/components/CommandPalette";
import { JumpPalette } from "@/components/JumpPalette";
import { OperatorPalette } from "@/components/OperatorPalette";
import { OperatorStrip } from "@/components/OperatorStrip";
import { UsageStrip } from "@/components/UsageStrip";
import { AgentsPanel } from "@/components/AgentsPanel";
import { PairingPanel } from "@/components/PairingPanel";
import { VaultSecretsPanel } from "@/components/VaultSecretsPanel";
import { RecoverySetup } from "@/components/RecoverySetup";
import { WalletPanel } from "@/components/WalletPanel";
import { getIdentity } from "@/lib/pairing";
import { getSessionId } from "@/lib/session";
import { CockpitRightRail } from "@/components/CockpitRightRail";
import { BrandHairline } from "@/components/BrandHairline";
import { WatchMeWork } from "@/components/WatchMeWork";
import { RobotAvatar, type RobotState } from "@/components/RobotAvatar";
import { toast } from "@/lib/toast";
import { DiffView } from "@/components/DiffView";
import { recordOp, useRecentOps, ago } from "@/lib/recentOps";
import { CockpitTour } from "@/components/CockpitTour";

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
  useDocumentMeta({
    title: "Cockpit",
    description: "Live operator console — invoke domain-pack actions, watch the daemon, view your TARS-to-TARS feed.",
    ogImage: "https://tars.meeet.world/og-cockpit.svg",
  });
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
  const [showRecoveryGate, setShowRecoveryGate] = useState(false);
  const [showRecoveryModal, setShowRecoveryModal] = useState(false);
  const [voiceListening, setVoiceListening] = useState(false);
  const [watchOpen, setWatchOpen] = useState(false);

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

  // First-pair prompt: persistent vault + freshly minted host id + no backup yet.
  useEffect(() => {
    if (healthError) return;
    void (async () => {
      try {
        const id = await getIdentity();
        let verified = false;
        let skipped = false;
        try {
          verified = !!localStorage.getItem("tars_recovery_verified_fp");
          skipped = localStorage.getItem("tars_recovery_skipped") === "1";
        } catch {
          /* private mode */
        }
        if (id.vault.configured && id.vault.freshly_minted && !verified && !skipped) {
          setShowRecoveryGate(true);
        }
      } catch {
        /* backend offline or older host */
      }
    })();
  }, [healthError]);

  // Auto-fill args when action changes.
  useEffect(() => {
    setArgsText(defaultArgsFor(activeAction));
    setResponse(null);
    setError(null);
  }, [activeActionId, activeSlug]);

  // Cmd/Ctrl + Shift + W → toggle Watch-me-work fullscreen
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey;
      if (meta && e.shiftKey && (e.key === "w" || e.key === "W")) {
        e.preventDefault();
        setWatchOpen(prev => !prev);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

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
      const r = await invokeAction(activeSlug, activeActionId, parsed, {
        sessionId: getSessionId(),
      });
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
      // Record the (slug, actionId, args) tuple if the run was OK so
      // the operator can re-run it via the Recent lozenge below.
      if (ok !== false) {
        recordOp({ slug: activeSlug, actionId: activeActionId, args: argsText });
      }
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

  // Single source of truth for the robot state — used by both the
  // mini-map in the top chrome and the right-rail companion.
  const robotState: RobotState = running
    ? "thinking"
    : error
      ? "error"
      : response
        ? "ok"
        : voiceListening
          ? "listening"
          : "idle";

  // Empty / first-run state: backend unreachable AND no packs ever
  // loaded. Render a welcome panel with the robot at its centre and
  // dim out the rest of the workspace until the daemon is running.
  const emptyFirstRun = backendOffline && !packs;

  return (
    <section className="relative z-20 mx-auto min-h-screen max-w-[1480px] px-6 pb-24 pt-6 md:px-12">
      {/* Operator chrome — sticky-ish top bar with brand-hairline,
          back link, mini-map TARS-9, anchor nav, and live status pills. */}
      <div className="relative mb-8 overflow-hidden rounded-[14px] border border-line bg-bg-1/60 px-4 py-3 backdrop-blur-md md:px-6">
        <BrandHairline />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link
              to="/"
              className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-line px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-2 transition-colors duration-200 hover:border-line-strong hover:text-ink"
            >
              <ArrowLeft size={12} strokeWidth={1.6} aria-hidden />
              back
            </Link>

            {/* Mini-map TARS-9 — always-on state mirror. Click opens
                the Watch-me-work cinema. Hidden on small viewports
                where horizontal space is precious. */}
            <button
              type="button"
              onClick={() => setWatchOpen(true)}
              aria-label="Open Watch-me-work · current robot state"
              title="Watch me work · ⌘⇧W"
              className="hidden items-center gap-2 rounded-md border border-line bg-bg-2/40 px-2 py-1 transition-colors hover:border-line-strong sm:inline-flex"
            >
              <RobotAvatar state={robotState} width={28} />
              <span
                className="font-mono-tech text-[9.5px] uppercase tracking-[2px]"
                style={{
                  color:
                    robotState === "thinking"
                      ? "var(--brand-violet)"
                      : robotState === "ok"
                        ? "var(--color-success)"
                        : robotState === "error"
                          ? "var(--color-alert)"
                          : robotState === "listening"
                            ? "var(--brand-cyan)"
                            : "var(--color-ink-3)",
                }}
              >
                TARS-9 · {robotState}
              </span>
            </button>
          </div>

          <nav
            aria-label="cockpit anchors"
            className="hidden items-center gap-3 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3 sm:flex"
          >
            <a href="#ops" className="transition-colors hover:text-ink">agents</a>
            <span aria-hidden className="text-line-strong">·</span>
            <a href="#wallets" className="transition-colors hover:text-ink">wallets</a>
            <span aria-hidden className="text-line-strong">·</span>
            <a href="#security" className="transition-colors hover:text-ink">security</a>
            <span aria-hidden className="text-line-strong">·</span>
            <a href="#vault-keys" className="transition-colors hover:text-ink">keys</a>
            <span aria-hidden className="text-line-strong">·</span>
            <Link
              to="/cockpit/planner"
              className="transition-colors hover:text-ink"
            >
              planner
            </Link>
            <span aria-hidden className="text-line-strong">·</span>
            <Link
              to="/cockpit/traces"
              className="transition-colors hover:text-ink"
            >
              traces
            </Link>
            <span aria-hidden className="text-line-strong">·</span>
            <Link
              to="/cockpit/policy"
              className="transition-colors hover:text-ink"
            >
              policy
            </Link>
            <span aria-hidden className="text-line-strong">·</span>
            <Link
              to="/cockpit/council"
              className="transition-colors hover:text-ink"
            >
              council
            </Link>
            <span aria-hidden className="text-line-strong">·</span>
            <Link
              to="/cockpit/awareness"
              className="transition-colors hover:text-ink"
            >
              awareness
            </Link>
          </nav>

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
      </div>

      {/* Hero block — eyebrow + h1 + meta. Restraint pass: smaller h1
          than the marketing hero so it reads as "operator console",
          not another landing page. */}
      <div className="mb-10">
        <div className="mb-3 inline-flex items-center gap-2.5 font-mono-tech text-[10px] uppercase tracking-[3px] text-ink-2">
          <span style={{ color: "var(--brand-indigo)" }}>OPERATOR</span>
          <span aria-hidden className="opacity-50">//</span>
          <span>COCKPIT</span>
          <span aria-hidden className="opacity-50">//</span>
          <span style={{ color: "var(--brand-cyan)" }}>v9.0</span>
        </div>
        <h1
          className="font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
          style={{ fontSize: "var(--text-display-md)" }}
        >
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

      <ChatPane defaultPackSlug={activeSlug ?? undefined} />

      <div id="ops" className="mb-8 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <AgentsPanel />
        <WalletPanel />
      </div>

      <div id="security" className="mb-8 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <PairingPanel />
        <aside className="relative overflow-hidden rounded-[14px] border border-line bg-bg-1 p-6">
          <BrandHairline />
          <CornerFrame />
          <div className="font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
            recovery phrase
          </div>
          <p className="mt-3 max-w-[54ch] text-[13px] leading-[1.65] text-ink-2">
            Backup your operator key with a 24-word phrase. Recommended before pairing mobile
            devices — we never sync the words to any server.
          </p>
          <button
            type="button"
            onClick={() => setShowRecoveryModal(true)}
            className="mt-6 rounded-md border border-line px-4 py-2.5 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink transition-colors hover:border-line-strong disabled:opacity-40"
          >
            Open backup wizard
          </button>
        </aside>
        <VaultSecretsPanel />
      </div>

      {(showRecoveryGate || showRecoveryModal) && (
        <div
          className="fixed inset-0 z-[80] flex items-center justify-center bg-[rgba(8,10,15,0.78)] p-4 backdrop-blur-[2px]"
          role="dialog"
          aria-modal="true"
          aria-labelledby="recovery-setup-title"
        >
          <div className="relative max-h-[92vh] w-full max-w-2xl overflow-y-auto">
            <button
              type="button"
              onClick={() => {
                if (showRecoveryGate) {
                  try {
                    localStorage.setItem("tars_recovery_skipped", "1");
                  } catch {
                    /* ignore */
                  }
                  setShowRecoveryGate(false);
                }
                setShowRecoveryModal(false);
              }}
              className="absolute right-3 top-3 z-10 rounded-md border border-line bg-bg-1 px-3 py-1.5 font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-3 hover:text-ink"
            >
              Close
            </button>
            <h2 id="recovery-setup-title" className="sr-only">
              Recovery backup phrase wizard
            </h2>
            <RecoverySetup
              onCompleted={(fp) => {
                setShowRecoveryGate(false);
                setShowRecoveryModal(false);
                toast.successT("toast.recovery.verified", {
                  hint: `fingerprint ${fp}`,
                  duration: 8000,
                });
              }}
              onSkip={
                showRecoveryGate
                  ? () => {
                      try {
                        localStorage.setItem("tars_recovery_skipped", "1");
                      } catch {
                        /* ignore */
                      }
                      setShowRecoveryGate(false);
                    }
                  : undefined
              }
            />
          </div>
        </div>
      )}

      {/* Toast bus is mounted globally in <AppShell />; cockpit just
          calls toast.* and the bus handles render + auto-dismiss. */}

      <CommandPalette
        onJumpToThread={(threadId) => {
          window.dispatchEvent(
            new CustomEvent("tars:open-thread", { detail: { threadId } }),
          );
        }}
      />

      <JumpPalette />

      {/* IDEAS #20 — operator command palette (⌘. / Ctrl+.). Indexes
          packs / actions / playbooks / awareness sources / recent
          traces; deep-links navigation and runs invocations through
          the policy gate. */}
      <OperatorPalette
        onToast={(tone, message) => {
          if (tone === "ok") toast.success(message);
          else if (tone === "warn") toast.warn(message);
          else toast.error(message);
        }}
      />

      {/* First-run welcome — only when backend never came online AND
          we've never seen domain packs. After that the operator gets
          the dense workspace below. */}
      {emptyFirstRun && (
        <div className="relative mb-8 grid gap-6 overflow-hidden rounded-[14px] border border-line bg-bg-1/60 px-6 py-10 backdrop-blur-md md:grid-cols-[auto_1fr] md:gap-10 md:px-10 md:py-14">
          <BrandHairline />
          <div className="flex justify-center md:justify-start">
            <RobotAvatar state="idle" width={180} />
          </div>
          <div className="self-center">
            <div className="mb-3 inline-flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[3px] text-ink-2">
              <span style={{ color: "var(--brand-indigo)" }}>FIRST RUN</span>
              <span aria-hidden className="opacity-50">//</span>
              <span>cockpit waiting</span>
            </div>
            <h2
              className="mb-3 max-w-[20ch] font-display font-medium leading-[0.98] tracking-[-0.018em] text-ink"
              style={{ fontSize: "clamp(1.7rem, 3.6vw, 2.6rem)" }}
            >
              TARS-9 is online.{" "}
              <span
                className="bg-clip-text text-transparent"
                style={{
                  backgroundImage:
                    "linear-gradient(95deg, var(--brand-indigo) 0%, var(--brand-violet) 50%, var(--brand-cyan) 100%)",
                }}
              >
                Daemon isn't.
              </span>
            </h2>
            <p className="mb-5 max-w-[52ch] text-[14px] leading-[1.65] text-ink-2">
              The cockpit can't reach <code className="text-ink">{API_BASE}</code>. Start the local
              daemon and this surface fills in automatically — no refresh, no
              re-login.
            </p>
            <pre className="rounded-md border border-line bg-bg-2/50 px-4 py-3 font-mono-tech text-[12px] leading-[1.55] text-ink/95 overflow-x-auto">
              cd Jarvis/jarvis && PYTHONPATH=. PORT=8765 \
                .venv/bin/python serve.py
            </pre>
            <p className="mt-3 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
              {healthError ?? "still polling…"}
            </p>
          </div>
        </div>
      )}

      {backendOffline && !emptyFirstRun && (
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

      {/* Workspace + companion right rail. The workspace keeps its
          existing 3-col anatomy (domains / actions / invocation); the
          right rail floats alongside on xl+ and stacks on smaller. */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_300px]">
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
          <RecentOpsRail
            onPick={(slug, actionId, args) => {
              setActiveSlug(slug);
              setActiveActionId(actionId);
              setArgsText(args);
              setError(null);
              setResponse(null);
            }}
          />
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
              {/* Live diff vs the last successful invocation of this same
                  (slug, action). Renders nothing if there's no history
                  for the current selection or args are unchanged. */}
              <ArgsDiff
                slug={activeSlug}
                actionId={activeActionId}
                current={argsText}
              />
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

        {/* Right rail — sticky on xl+, stacks below on lg- */}
        <div className="xl:sticky xl:top-6 xl:self-start">
          <CockpitRightRail
            running={running}
            lastError={error}
            lastOk={response ? !!(response.result as { ok?: unknown })?.ok : null}
            uptimeS={health?.uptime_s ?? null}
            meeetOnline={health?.meeet_ingest ?? null}
            voiceListening={voiceListening}
            onToggleVoice={() => setVoiceListening(v => !v)}
            onWatchMeWork={() => setWatchOpen(true)}
          />
        </div>
      </div>

      <OperatorStrip />
      <UsageStrip sessionId={getSessionId()} />

      {/* First-visit welcome — auto-shows once, persists `tars-tour-seen`. */}
      <CockpitTour />

      {/* Cinematic Watch-me-work fullscreen — Cmd+Shift+W to toggle. */}
      <WatchMeWork
        open={watchOpen}
        onClose={() => setWatchOpen(false)}
        events={trace}
        state={
          running
            ? "thinking"
            : error
              ? "error"
              : response
                ? "ok"
                : voiceListening
                  ? "listening"
                  : "idle"
        }
        uptimeS={health?.uptime_s ?? null}
        totalEvents={trace.length}
        avgLatencyMs={
          (() => {
            const ts = trace
              .map(e => e.took_ms)
              .filter((n): n is number => typeof n === "number");
            if (!ts.length) return null;
            return ts.reduce((a, b) => a + b, 0) / ts.length;
          })()
        }
      />
    </section>
  );
}

/**
 * RecentOpsRail — horizontal pill row above the action list. Click a
 * pill to instantly load that (slug, actionId, args) tuple back into
 * the workspace. Empty by default; appears the moment the operator
 * runs their first successful invocation.
 */
function RecentOpsRail({
  onPick,
}: {
  onPick: (slug: string, actionId: string, args: string) => void;
}) {
  const recent = useRecentOps();
  if (!recent.length) return null;
  return (
    <div className="mb-3">
      <div className="mb-1.5 flex items-center justify-between font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-3">
        <span>recent · re-run</span>
        <span className="tabular-nums">{recent.length}</span>
      </div>
      <ul className="flex flex-wrap gap-1.5">
        {recent.map((r, i) => (
          <li key={`${r.slug}-${r.actionId}-${r.at}-${i}`}>
            <button
              type="button"
              onClick={() => onPick(r.slug, r.actionId, r.args)}
              className="inline-flex items-center gap-2 rounded-full border border-line bg-bg-2/50 px-2.5 py-1 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-2 transition-all duration-150 hover:-translate-y-px hover:border-line-strong hover:text-ink"
              title={`${r.slug}.${r.actionId} · ${ago(r.at)}`}
            >
              <span style={{ color: "var(--brand-indigo)" }}>{r.slug}</span>
              <span aria-hidden className="opacity-50">.</span>
              <span>{r.actionId}</span>
              <span className="text-ink-3 tabular-nums">{ago(r.at)}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * ArgsDiff — given (slug, actionId, current text) shows the diff vs
 * the last persisted args for that combination. Returns null when
 * there's no history or the text hasn't changed.
 */
function ArgsDiff({
  slug,
  actionId,
  current,
}: {
  slug: string | null;
  actionId: string | null;
  current: string;
}) {
  const recent = useRecentOps();
  if (!slug || !actionId) return null;
  const previous = recent.find(r => r.slug === slug && r.actionId === actionId);
  if (!previous) return null;
  if (previous.args.trim() === current.trim()) return null;
  return (
    <div className="mt-3">
      <DiffView prev={previous.args} next={current} />
    </div>
  );
}
