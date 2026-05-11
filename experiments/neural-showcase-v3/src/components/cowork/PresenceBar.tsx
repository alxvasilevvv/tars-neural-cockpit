/**
 * <PresenceBar /> — Wave 129
 *
 * Compact horizontal stack of member avatars (initial + dot) showing
 * who's currently in a cowork session. Avatars have a coloured dot
 * (green = live within 25 s, grey = stale) and the member's
 * display-name on hover.
 *
 * Pure presentational — no fetches. Parent passes the members list +
 * a "now" tick so the live/stale boundary recomputes when the parent
 * re-renders (every 5 s is fine).
 */

import type { CoworkMember } from "@/lib/cowork";
import { isLive } from "@/lib/cowork";

interface PresenceBarProps {
  members: CoworkMember[];
  now?: number; // seconds since epoch — defaults to Date.now()/1000
  className?: string;
  /** Show numeric counter "N live · M total" beside the stack. */
  showCount?: boolean;
}

export function PresenceBar({
  members,
  now,
  className,
  showCount = true,
}: PresenceBarProps) {
  const nowSec = now ?? Date.now() / 1000;
  const liveCount = members.filter((m) => isLive(m.last_seen_at, nowSec)).length;

  return (
    <div
      className={
        "flex items-center gap-3 " + (className ?? "")
      }
      data-testid="cowork-presence-bar"
    >
      <div className="flex -space-x-2">
        {members.slice(0, 8).map((m) => {
          const live = isLive(m.last_seen_at, nowSec);
          const initial = (m.display_name?.[0] ?? "?").toUpperCase();
          return (
            <div
              key={m.id}
              title={`${m.display_name}${live ? " · live" : " · away"}`}
              className="relative grid h-7 w-7 place-items-center rounded-full border border-bg-1 font-mono-tech text-[11px] uppercase tracking-[1.4px]"
              style={{
                background: `${m.color ?? "#6366F1"}26`,
                color: m.color ?? "#6366F1",
                boxShadow: `inset 0 0 0 1px ${m.color ?? "#6366F1"}50`,
              }}
              data-live={live ? "1" : "0"}
              data-testid={`cowork-presence-avatar-${m.id}`}
            >
              {initial}
              <span
                aria-hidden
                className="absolute -bottom-0.5 -right-0.5 h-2 w-2 rounded-full border border-bg-1"
                style={{
                  background: live ? "#34D399" : "#6B7280",
                  boxShadow: live
                    ? "0 0 6px rgba(52, 211, 153, 0.7)"
                    : "none",
                }}
              />
            </div>
          );
        })}
        {members.length > 8 && (
          <div className="grid h-7 w-7 place-items-center rounded-full border border-line bg-bg-1 font-mono-tech text-[10px] text-ink-2">
            +{members.length - 8}
          </div>
        )}
      </div>
      {showCount && (
        <span className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-2">
          {liveCount} live · {members.length} total
        </span>
      )}
    </div>
  );
}
