/**
 * <CoworkPreview /> — Wave 132
 *
 * Animated card on the landing page that previews the Cowork
 * multiplayer feature without leaving /. Shows three mock members
 * with a live presence dot + an event stream that cycles through
 * agent frames every 2.5 s. Mirrors the visual language of the real
 * /cowork session viewer so visitors recognise the surface.
 *
 * Self-contained: no fetches, no SSE, no router state. Pure
 * client-side animation that pauses when the user prefers reduced
 * motion (via the framer global respectReducedMotion).
 *
 * Design conventions (Wave 70/89/94 pattern):
 *   - Defensive `initial: opacity: 1` so the card stays legible if
 *     framer hydrates late or motion is disabled.
 *   - Same accent palette as /cowork session viewer for visual
 *     continuity (indigo / violet / cyan).
 *   - Mobile: stacks. Desktop: 2-col grid (left = members + copy,
 *     right = live stream).
 */

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Users } from "lucide-react";
import { Link } from "react-router-dom";

interface MockMember {
  id: string;
  name: string;
  initial: string;
  color: string;
  live: boolean;
}

interface MockEvent {
  id: number;
  type: "agent.frame" | "cursor" | "chat";
  memberId: string;
  label: string;
  ts: number;
}

const MOCK_MEMBERS: MockMember[] = [
  { id: "alice", name: "Alice", initial: "A", color: "#6366F1", live: true },
  { id: "bob", name: "Bob", initial: "B", color: "#8B5CF6", live: true },
  { id: "carol", name: "Carol", initial: "C", color: "#06B6D4", live: true },
];

const EVENT_TEMPLATES: { type: MockEvent["type"]; memberId: string; label: string }[] = [
  { type: "agent.frame", memberId: "alice", label: "drafted plan section" },
  { type: "cursor", memberId: "bob", label: "moved to line 42" },
  { type: "agent.frame", memberId: "alice", label: "ran research query" },
  { type: "chat", memberId: "carol", label: "added a comment" },
  { type: "agent.frame", memberId: "bob", label: "summarised findings" },
  { type: "cursor", memberId: "alice", label: "selected paragraph 3" },
  { type: "agent.frame", memberId: "carol", label: "executed playbook step" },
  { type: "chat", memberId: "bob", label: "asked a question" },
];

const TYPE_LABEL: Record<MockEvent["type"], string> = {
  "agent.frame": "agent",
  cursor: "cursor",
  chat: "chat",
};

const TYPE_TINT: Record<MockEvent["type"], string> = {
  "agent.frame": "#6366F1",
  cursor: "#06B6D4",
  chat: "#8B5CF6",
};

export function CoworkPreview() {
  const [events, setEvents] = useState<MockEvent[]>([]);
  const counter = useRef(0);

  useEffect(() => {
    // Respect prefers-reduced-motion — keep the card legible but
    // skip the cycling animation. The reader still sees the static
    // members + the brand copy.
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;

    // Seed with two initial events so the panel isn't empty on first paint.
    const seed = [0, 1].map((i) => {
      const t = EVENT_TEMPLATES[i];
      return {
        id: counter.current++,
        type: t.type,
        memberId: t.memberId,
        label: t.label,
        ts: Date.now() - (1 - i) * 2000,
      };
    });
    setEvents(seed);

    const interval = setInterval(() => {
      counter.current += 1;
      const tmpl = EVENT_TEMPLATES[counter.current % EVENT_TEMPLATES.length];
      const ev: MockEvent = {
        id: counter.current,
        type: tmpl.type,
        memberId: tmpl.memberId,
        label: tmpl.label,
        ts: Date.now(),
      };
      setEvents((prev) => [...prev.slice(-4), ev]);
    }, 2500);

    return () => clearInterval(interval);
  }, []);

  const memberById = (id: string) =>
    MOCK_MEMBERS.find((m) => m.id === id) ?? MOCK_MEMBERS[0];

  return (
    <section
      id="cowork-preview"
      className="relative z-20 mx-auto max-w-[1280px] px-6 py-24 md:px-12 md:py-28"
    >
      <motion.div
        initial={{ opacity: 1, y: 0 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="grid grid-cols-1 gap-8 rounded-[16px] border border-line bg-bg-1/70 p-8 backdrop-blur-sm md:p-10 lg:grid-cols-[1fr_1.1fr] lg:gap-12"
      >
        {/* Left — copy + members */}
        <div>
          <div className="mb-4 inline-flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
            <Users size={12} strokeWidth={1.8} />
            Cowork · multiplayer
          </div>
          <h2
            className="mb-4 font-display font-medium leading-[1] tracking-[-0.02em] text-ink"
            style={{ fontSize: "clamp(1.8rem, 3.6vw, 2.6rem)" }}
          >
            Agents work better with{" "}
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(95deg, #6366F1 0%, #8B5CF6 50%, #06B6D4 100%)",
              }}
            >
              a team in the room.
            </span>
          </h2>
          <p className="mb-7 max-w-[480px] text-[14px] leading-[1.65] text-ink-2">
            Share a session with your team. Live presence, shared cursors over
            workspace files, real-time agent frames, and a one-click ownership
            handoff. Multiplayer agent work without context-switching tools.
          </p>

          {/* Mock members row */}
          <div className="mb-6">
            <div className="mb-3 font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
              In session
            </div>
            <div className="flex items-center gap-3">
              {MOCK_MEMBERS.map((m) => (
                <div
                  key={m.id}
                  className="flex items-center gap-2 rounded-md border border-line bg-bg-2 px-2.5 py-1.5"
                >
                  <span
                    className="grid h-6 w-6 place-items-center rounded-full font-mono-tech text-[10px] uppercase tracking-[1.4px]"
                    style={{
                      background: `${m.color}26`,
                      color: m.color,
                      boxShadow: `inset 0 0 0 1px ${m.color}50`,
                    }}
                  >
                    {m.initial}
                  </span>
                  <span className="text-[12.5px] text-ink">{m.name}</span>
                  <span
                    aria-hidden
                    className="h-1.5 w-1.5 rounded-full"
                    style={{
                      background: m.live ? "#34D399" : "#6B7280",
                      boxShadow: m.live
                        ? "0 0 6px rgba(52, 211, 153, 0.7)"
                        : "none",
                    }}
                  />
                </div>
              ))}
            </div>
          </div>

          <Link
            to="/cowork"
            className="group inline-flex items-center gap-2 rounded-md border border-line bg-accent px-4 py-2.5 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-bg-0 transition hover:bg-accent/90"
          >
            Open Cowork
            <ArrowRight
              size={14}
              strokeWidth={1.6}
              className="transition group-hover:translate-x-0.5"
            />
          </Link>
        </div>

        {/* Right — live stream */}
        <div className="rounded-[12px] border border-line bg-bg-2/60 p-5">
          <div className="mb-4 flex items-center justify-between">
            <div className="font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
              Live stream
            </div>
            <div className="flex items-center gap-1.5 font-mono-tech text-[10px] tabular-nums text-ink-3">
              <span
                aria-hidden
                className="h-1.5 w-1.5 animate-pulse rounded-full"
                style={{
                  background: "#34D399",
                  boxShadow: "0 0 6px rgba(52, 211, 153, 0.7)",
                }}
              />
              streaming
            </div>
          </div>

          {events.length === 0 ? (
            <div className="py-8 text-center text-[13px] text-ink-3">
              Waiting for the first event…
            </div>
          ) : (
            <ol className="space-y-2.5">
              {events
                .slice(-5)
                .reverse()
                .map((ev) => {
                  const member = memberById(ev.memberId);
                  const tint = TYPE_TINT[ev.type];
                  return (
                    <motion.li
                      key={ev.id}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{
                        duration: 0.32,
                        ease: [0.22, 1, 0.36, 1],
                      }}
                      className="grid grid-cols-[60px_1fr] items-center gap-3 rounded-md border border-line bg-bg-1/50 px-3 py-2"
                    >
                      <span
                        className="font-mono-tech text-[10px] uppercase tracking-[1.8px]"
                        style={{ color: tint }}
                      >
                        {TYPE_LABEL[ev.type]}
                      </span>
                      <div className="text-[12.5px] text-ink">
                        <span
                          className="mr-1.5 font-medium"
                          style={{ color: member.color }}
                        >
                          {member.name}
                        </span>
                        {ev.label}
                      </div>
                    </motion.li>
                  );
                })}
            </ol>
          )}

          <div className="mt-4 border-t border-line pt-3 text-center font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            Demo · not a real session
          </div>
        </div>
      </motion.div>
    </section>
  );
}
