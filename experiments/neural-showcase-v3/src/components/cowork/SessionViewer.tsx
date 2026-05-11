/**
 * <SessionViewer /> — Wave 129
 *
 * Live event stream pane for a cowork session: agent frames + cursor
 * moves + chat + handoff transitions, scrolling chronologically with
 * the newest pinned at the top.
 *
 * Pure presentational. Parent passes the event buffer (already
 * fan-in'd from `useCoworkStream`) + the member roster so we can
 * resolve `member_id → display_name + color` for each row.
 */

import type { CoworkEvent, CoworkMember } from "@/lib/cowork";
import { fmtRelative } from "@/lib/cowork";

interface SessionViewerProps {
  events: CoworkEvent[];
  members: CoworkMember[];
  className?: string;
}

const TYPE_LABEL: Partial<Record<CoworkEvent["type"], string>> = {
  "agent.frame": "agent",
  presence: "presence",
  cursor: "cursor",
  chat: "chat",
  "handoff.created": "handoff opened",
  "handoff.accepted": "handoff accepted",
  "handoff.revoked": "handoff revoked",
  "session.ended": "session ended",
  heartbeat: "heartbeat",
};

const TYPE_TINT: Partial<Record<CoworkEvent["type"], string>> = {
  "agent.frame": "#6366F1",
  cursor: "#06B6D4",
  chat: "#8B5CF6",
  "handoff.created": "#F59E0B",
  "handoff.accepted": "#34D399",
  "handoff.revoked": "#EF4444",
  "session.ended": "#EF4444",
  presence: "#6B7280",
  heartbeat: "#6B7280",
};

function resolveMember(
  members: CoworkMember[],
  memberId?: unknown,
): CoworkMember | null {
  if (typeof memberId !== "string") return null;
  return members.find((m) => m.id === memberId) ?? null;
}

function renderLabel(ev: CoworkEvent): string {
  if (ev.type === "agent.frame") {
    return (ev.data.label as string) ?? (ev.data.frame_type as string) ?? "frame";
  }
  if (ev.type === "chat") {
    return (ev.data.label as string) ?? "added a comment";
  }
  if (ev.type === "cursor") {
    return `${(ev.data.label as string) ?? "moved cursor"}`;
  }
  if (ev.type === "handoff.created") {
    const to = ev.data.to_email as string | undefined;
    return to ? `handoff → ${to}` : "open handoff link generated";
  }
  if (ev.type === "handoff.accepted") {
    return "handoff accepted";
  }
  if (ev.type === "session.ended") {
    return "session ended";
  }
  return TYPE_LABEL[ev.type] ?? ev.type;
}

export function SessionViewer({
  events,
  members,
  className,
}: SessionViewerProps) {
  // Filter out heartbeats from the visible feed — they're noise.
  const visible = events
    .filter((e) => e.type !== "heartbeat")
    .slice(-30)
    .reverse();

  return (
    <div
      className={
        "rounded-[14px] border border-line bg-bg-1/70 backdrop-blur-sm " +
        (className ?? "")
      }
      data-testid="cowork-session-viewer"
    >
      <div className="flex items-center justify-between border-b border-line px-5 py-3">
        <div className="font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
          Live stream
        </div>
        <div className="font-mono-tech text-[10px] tabular-nums text-ink-3">
          {visible.length} events
        </div>
      </div>

      {visible.length === 0 ? (
        <div className="px-5 py-12 text-center text-[13.5px] text-ink-3">
          Waiting for the first event…
        </div>
      ) : (
        <ol className="max-h-[420px] divide-y divide-line overflow-y-auto">
          {visible.map((ev) => {
            const member = resolveMember(members, ev.data.member_id);
            const tint = TYPE_TINT[ev.type] ?? "#6366F1";
            return (
              <li
                key={ev.id}
                className="grid grid-cols-[80px_1fr_auto] items-center gap-3 px-5 py-3"
                data-testid={`cowork-event-${ev.id}`}
              >
                <span
                  className="font-mono-tech text-[10px] uppercase tracking-[1.8px]"
                  style={{ color: tint }}
                >
                  {TYPE_LABEL[ev.type] ?? ev.type}
                </span>
                <div className="min-w-0">
                  <div className="truncate text-[13px] text-ink">
                    {member ? (
                      <span
                        className="mr-1.5 font-medium"
                        style={{ color: member.color ?? undefined }}
                      >
                        {member.display_name}
                      </span>
                    ) : null}
                    {renderLabel(ev)}
                  </div>
                </div>
                <span className="font-mono-tech text-[10px] tabular-nums text-ink-3">
                  {fmtRelative(ev.occurred_at)}
                </span>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
