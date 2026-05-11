/**
 * <CoworkSession /> — Wave 129 / split out in Wave 136.
 *
 * `/cowork/:slug` single-session view. Heavy chunk: pulls in
 * PresenceBar + SessionViewer + HandoffDialog + the SSE stream
 * hook. Lazy-loaded as its own bundle so the `/cowork` list page
 * doesn't pay for it.
 *
 * Layout:
 *   ┌──────────────────────────────────────────────────────────────┐
 *   │ Breadcrumb / title / PresenceBar / "Hand off" CTA            │
 *   ├──────────────────────────────────────────────────────────────┤
 *   │ left rail (members)               │  Live stream viewer      │
 *   │                                   │                          │
 *   └──────────────────────────────────────────────────────────────┘
 */

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Send, Users } from "lucide-react";

import { Breadcrumbs } from "@/components/Breadcrumbs";
import { PresenceBar } from "@/components/cowork/PresenceBar";
import { SessionViewer } from "@/components/cowork/SessionViewer";
import { HandoffDialog } from "@/components/cowork/HandoffDialog";
import { useDocumentMeta } from "@/lib/meta";
import {
  type CoworkMember,
  type CoworkSession as TSession,
  fetchSession,
  listMembers,
  useCoworkStream,
} from "@/lib/cowork";

export function CoworkSession() {
  const { slug } = useParams<{ slug: string }>();
  const [session, setSession] = useState<TSession | null>(null);
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
