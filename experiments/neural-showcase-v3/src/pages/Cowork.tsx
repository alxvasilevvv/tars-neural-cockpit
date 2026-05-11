/**
 * <Cowork /> — Wave 129
 *
 * Multi-user real-time collaboration over a TARS agent session.
 * Mounted at `/cowork` (list view) and `/cowork/:slug` (single session).
 *
 * Closes the W122 audit gap on tasks #99 (Shared Agent Sessions) and
 * #100 (TARS Handoff) — historically marked complete but never
 * actually shipped on the backend. This page binds to the new
 * `backend/core/cowork/` module via `@/lib/cowork`.
 *
 * Layout:
 *   ┌──────────────────────────────────────────────────────────────┐
 *   │ Breadcrumb / title / PresenceBar / "Hand off" CTA            │
 *   ├──────────────────────────────────────────────────────────────┤
 *   │ left rail (session meta + members)  │  Live stream viewer    │
 *   │                                     │                        │
 *   └──────────────────────────────────────────────────────────────┘
 *
 * Design conventions (Wave 70 / 89 / 94 pattern):
 *   - Defensive `initial: opacity: 1` on motion wrappers so the page
 *     stays legible if framer hydrates late.
 *   - All copy in plain English (i18n keys exist but we skip the t()
 *     dance — adds bundle weight, no localisation shipping today).
 *   - The page is demo-able offline via the mock fallback in
 *     `@/lib/cowork` — visitors landing on `/cowork` without a backend
 *     still see a working session.
 */

import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, Send, Users } from "lucide-react";

import { Breadcrumbs } from "@/components/Breadcrumbs";
import { PresenceBar } from "@/components/cowork/PresenceBar";
import { SessionViewer } from "@/components/cowork/SessionViewer";
import { HandoffDialog } from "@/components/cowork/HandoffDialog";
import { useDocumentMeta } from "@/lib/meta";
import {
  COWORK_MOCK,
  type CoworkMember,
  type CoworkSession,
  fetchSession,
  listMembers,
  listSessions,
  useCoworkStream,
} from "@/lib/cowork";

// ── /cowork (list) ────────────────────────────────────────────────

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

// ── /cowork/:slug (single session) ────────────────────────────────

export function CoworkSession() {
  const { slug } = useParams<{ slug: string }>();
  const [session, setSession] = useState<CoworkSession | null>(null);
  const [members, setMembers] = useState<CoworkMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [handoffOpen, setHandoffOpen] = useState(false);
  const [nowTick, setNowTick] = useState(Date.now() / 1000);

  useDocumentMeta({
    title: session ? `Cowork · ${session.name}` : "Cowork",
    description:
      "Shared agent session with real-time presence and one-click handoff.",
  });

  useEffect(() => {
    if (!slug) return;
    let cancelled = false;
    (async () => {
      const s = await fetchSession(slug);
      if (cancelled) return;
      setSession(s);
      if (s) {
        const ms = await listMembers(s.id);
        if (!cancelled) setMembers(ms);
      }
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [slug]);

  // Recompute presence-live boundary every 5 s.
  useEffect(() => {
    const id = setInterval(() => setNowTick(Date.now() / 1000), 5000);
    return () => clearInterval(id);
  }, []);

  const events = useCoworkStream(session?.id ?? null);

  const sessionForDialog = useMemo(() => session, [session?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <section className="mx-auto max-w-[1100px] px-6 py-24 text-center text-ink-2">
        Loading session…
      </section>
    );
  }
  if (!session) {
    return (
      <section className="mx-auto max-w-[760px] px-6 py-24 text-center">
        <div className="mb-3 font-display text-[22px] text-ink">Session not found</div>
        <p className="mb-6 text-[14px] text-ink-2">
          That cowork session doesn't exist or has ended.
        </p>
        <Link
          to="/cowork"
          className="inline-flex items-center gap-2 rounded-md border border-line bg-bg-2 px-4 py-2.5 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-ink transition hover:bg-bg-1"
        >
          <ArrowLeft size={14} strokeWidth={1.6} />
          Back to sessions
        </Link>
      </section>
    );
  }

  return (
    <section className="relative z-20 mx-auto max-w-[1280px] px-6 pb-24 pt-10 md:px-10 md:pt-14">
      <Breadcrumbs
        items={[
          { label: "Cowork", to: "/cowork" },
          { label: session.name },
        ]}
      />

      {/* Header */}
      <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
            <Users size={12} strokeWidth={1.8} />
            /cowork/{session.slug}
          </div>
          <h1
            className="font-display font-medium leading-[1] tracking-[-0.02em] text-ink"
            style={{ fontSize: "clamp(1.6rem, 3.2vw, 2.4rem)" }}
          >
            {session.name}
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <PresenceBar members={members} now={nowTick} />
          <button
            type="button"
            onClick={() => setHandoffOpen(true)}
            className="inline-flex items-center gap-2 rounded-md border border-line bg-bg-2 px-4 py-2.5 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-ink transition hover:bg-bg-1"
            data-testid="cowork-handoff-open"
          >
            <Send size={13} strokeWidth={1.6} />
            Hand off
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[320px_1fr]">
        {/* Left rail — members */}
        <aside className="rounded-[14px] border border-line bg-bg-1/70 p-5 backdrop-blur-sm">
          <div className="mb-3 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
            Members
          </div>
          <ul className="space-y-2">
            {members.map((m) => (
              <li
                key={m.id}
                className="flex items-center gap-3 rounded-md border border-transparent p-2 transition hover:border-line"
                data-testid={`cowork-member-${m.id}`}
              >
                <span
                  className="grid h-7 w-7 place-items-center rounded-full font-mono-tech text-[11px] uppercase tracking-[1.4px]"
                  style={{
                    background: `${m.color ?? "#6366F1"}26`,
                    color: m.color ?? "#6366F1",
                    boxShadow: `inset 0 0 0 1px ${m.color ?? "#6366F1"}50`,
                  }}
                >
                  {(m.display_name?.[0] ?? "?").toUpperCase()}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[13px] text-ink">
                    {m.display_name}
                  </div>
                  <div className="font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3">
                    {m.role}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </aside>

        {/* Right pane — stream */}
        <SessionViewer events={events} members={members} />
      </div>

      <HandoffDialog
        open={handoffOpen}
        sessionId={session.id}
        fromUserId={session.owner_user_id}
        onClose={() => setHandoffOpen(false)}
      />
    </section>
  );
}

// ── /cowork/handoff/:token (recipient accept) ─────────────────────

export function CoworkHandoffAccept() {
  const { token } = useParams<{ token: string }>();

  useDocumentMeta({
    title: "Accept cowork handoff",
    description:
      "Accept ownership of a TARS cowork session that was handed off to you.",
  });

  return (
    <section className="mx-auto max-w-[640px] px-6 py-20">
      <Breadcrumbs
        items={[
          { label: "Cowork", to: "/cowork" },
          { label: "Accept handoff" },
        ]}
      />
      <div className="rounded-[14px] border border-line bg-bg-1/70 p-8 backdrop-blur-sm">
        <div className="mb-2 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
          Handoff received
        </div>
        <h1 className="mb-4 font-display text-[24px] font-medium leading-[1.1] tracking-[-0.01em] text-ink">
          You've been handed a cowork session.
        </h1>
        <p className="mb-6 text-[13.5px] leading-[1.65] text-ink-2">
          To accept ownership of this session, open it in the desktop TARS
          app (which carries your local identity). The token below is
          single-use and expires shortly.
        </p>
        <div className="mb-6 break-all rounded-md border border-line bg-bg-2 px-3 py-2 font-mono-tech text-[12.5px] text-ink">
          {token ?? "(missing token)"}
        </div>
        <Link
          to="/cowork"
          className="inline-flex items-center gap-2 rounded-md border border-line bg-bg-2 px-4 py-2.5 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-ink transition hover:bg-bg-1"
        >
          <ArrowLeft size={14} strokeWidth={1.6} />
          Back to sessions
        </Link>
      </div>
    </section>
  );
}
