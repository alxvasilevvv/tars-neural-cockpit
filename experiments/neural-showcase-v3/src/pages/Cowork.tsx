/**
 * <Cowork /> — Wave 129 / split in Wave 136.
 *
 * `/cowork` list view. Light surface: just the session list + intro
 * copy. The heavy session viewer (PresenceBar, SessionViewer,
 * HandoffDialog, SSE stream) lives in CoworkSession.tsx so this
 * chunk stays small for visitors who never click into a session.
 *
 * Wave 136 split: Cowork.tsx (this file, list only) +
 * CoworkSession.tsx (single-session view, heavy components) +
 * CoworkHandoffAccept.tsx (recipient screen, tiny). Each is a
 * separate React.lazy chunk in App.tsx so the marketing surface
 * doesn't pay for code it never uses.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";

import { Breadcrumbs } from "@/components/Breadcrumbs";
import { useDocumentMeta } from "@/lib/meta";
import {
  COWORK_MOCK,
  type CoworkSession,
  listSessions,
} from "@/lib/cowork";

export function Cowork() {
  useDocumentMeta({
    title: "Cowork — Shared agent sessions",
    description:
      "Run agent sessions with your team. Real-time presence, shared cursors, one-click handoff.",
    ogImage: "https://tars.meeet.world/og-cowork.svg",
  });

  const [sessions, setSessions] = useState<CoworkSession[]>([
    COWORK_MOCK.session,
  ]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    listSessions().then((list) => {
      if (cancelled) return;
      setSessions(list);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="relative z-20 mx-auto max-w-[1100px] px-6 pb-24 pt-12 md:px-10 md:pt-16">
      <Breadcrumbs items={[{ label: "Cowork" }]} />

      <motion.div
        initial={{ opacity: 1, y: 0 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-10"
      >
        <div className="mb-3 inline-flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
          <span
            className="h-1 w-1 rounded-full"
            style={{
              background: "var(--color-accent)",
              boxShadow: "0 0 8px var(--color-accent-soft)",
            }}
          />
          Cowork · multiplayer
        </div>
        <h1
          className="mb-4 font-display font-medium leading-[0.94] tracking-[-0.02em] text-ink"
          style={{ fontSize: "clamp(2rem, 4.4vw, 3.2rem)" }}
        >
          Run agent sessions with your team.
        </h1>
        <p className="max-w-[640px] text-[14.5px] leading-[1.65] text-ink-2">
          Cowork lets several humans + a TARS agent share one session. Live
          presence, shared cursors over your workspace files, a fan-out of
          every agent frame, and a one-click handoff that transfers
          ownership of an active session.
        </p>
      </motion.div>

      <div className="mb-6 flex items-center justify-between">
        <div className="font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
          Active sessions
        </div>
        <div className="font-mono-tech text-[10px] tabular-nums text-ink-3">
          {loading ? "loading…" : `${sessions.length} live`}
        </div>
      </div>

      <ul
        className="grid grid-cols-1 gap-3 md:grid-cols-2"
        data-testid="cowork-session-list"
      >
        {sessions.map((s) => (
          <li key={s.id}>
            <Link
              to={`/cowork/${s.slug}`}
              className="group flex flex-col gap-3 rounded-[14px] border border-line bg-bg-1/70 p-6 backdrop-blur-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong"
            >
              <div className="flex items-center justify-between">
                <span className="font-display text-[16px] font-medium text-ink">
                  {s.name}
                </span>
                <span
                  className="rounded-full px-2 py-0.5 font-mono-tech text-[9px] uppercase tracking-[2px]"
                  style={{
                    background:
                      s.status === "live"
                        ? "rgba(52, 211, 153, 0.14)"
                        : "rgba(107, 114, 128, 0.18)",
                    color: s.status === "live" ? "#34D399" : "#9CA3AF",
                  }}
                >
                  {s.status}
                </span>
              </div>
              <div className="flex items-center justify-between text-[12.5px] text-ink-2">
                <span className="font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
                  /cowork/{s.slug}
                </span>
                <span className="font-mono-tech text-[10px] tabular-nums text-ink-3 transition group-hover:text-ink">
                  open →
                </span>
              </div>
            </Link>
          </li>
        ))}
      </ul>

      <div className="mt-10 rounded-[14px] border border-line bg-bg-1/50 p-6">
        <div className="mb-2 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
          What is this?
        </div>
        <p className="max-w-[760px] text-[13.5px] leading-[1.65] text-ink-2">
          Cowork mirrors the multiplayer mode Anthropic ships in Claude
          Desktop: several teammates and an agent share one live session.
          Backend lives at <code className="rounded bg-bg-2 px-1.5 py-0.5 font-mono-tech text-[11.5px] text-ink">backend/core/cowork/</code>{" "}
          (sessions + presence + stream + handoff). When the brother's
          core-bridge wires <code className="rounded bg-bg-2 px-1.5 py-0.5 font-mono-tech text-[11.5px] text-ink">/api/cowork/*</code>{" "}
          endpoints, the same UI swaps from mock to live — no page-level
          changes needed.
        </p>
      </div>
    </section>
  );
}
