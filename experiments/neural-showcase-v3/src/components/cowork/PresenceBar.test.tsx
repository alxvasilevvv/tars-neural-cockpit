/**
 * Smoke test for <PresenceBar /> — Wave 129.
 *
 * Verifies the component renders the live/away dot correctly for
 * members inside and outside the 25 s presence window, and shows the
 * "+N" overflow when more than 8 members are passed in.
 */

import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";

import { PresenceBar } from "./PresenceBar";
import type { CoworkMember } from "@/lib/cowork";

const baseMember = (over: Partial<CoworkMember> = {}): CoworkMember => ({
  id: "cm_x",
  session_id: "cw_1",
  display_name: "Alice",
  user_id: null,
  email: null,
  role: "editor",
  color: "#6366F1",
  joined_at: 0,
  last_seen_at: 0,
  ...over,
});

describe("PresenceBar", () => {
  test("renders one avatar per member up to 8", () => {
    const now = 1_000_000;
    const members: CoworkMember[] = [
      baseMember({ id: "cm_a", display_name: "Alice", last_seen_at: now }),
      baseMember({ id: "cm_b", display_name: "Bob", last_seen_at: now - 1 }),
    ];
    render(<PresenceBar members={members} now={now} />);
    expect(screen.getByTestId("cowork-presence-avatar-cm_a")).toBeTruthy();
    expect(screen.getByTestId("cowork-presence-avatar-cm_b")).toBeTruthy();
  });

  test("marks live vs away via data-live attribute", () => {
    const now = 1_000_000;
    const members: CoworkMember[] = [
      baseMember({ id: "cm_live", last_seen_at: now - 5 }),
      baseMember({ id: "cm_stale", last_seen_at: now - 600 }),
    ];
    render(<PresenceBar members={members} now={now} />);
    const live = screen.getByTestId("cowork-presence-avatar-cm_live");
    const stale = screen.getByTestId("cowork-presence-avatar-cm_stale");
    expect(live.getAttribute("data-live")).toBe("1");
    expect(stale.getAttribute("data-live")).toBe("0");
  });

  test("renders +N overflow when more than 8 members", () => {
    const now = 1_000_000;
    const members: CoworkMember[] = Array.from({ length: 11 }, (_, i) =>
      baseMember({
        id: `cm_${i}`,
        display_name: `M${i}`,
        last_seen_at: now,
      }),
    );
    render(<PresenceBar members={members} now={now} />);
    expect(screen.getByText("+3")).toBeTruthy();
  });

  test("counter reports correct live vs total", () => {
    const now = 1_000_000;
    const members: CoworkMember[] = [
      baseMember({ id: "a", last_seen_at: now }),
      baseMember({ id: "b", last_seen_at: now - 1000 }),
      baseMember({ id: "c", last_seen_at: now - 2 }),
    ];
    render(<PresenceBar members={members} now={now} />);
    expect(screen.getByText("2 live · 3 total")).toBeTruthy();
  });

  test("respects showCount=false", () => {
    const now = 1_000_000;
    render(
      <PresenceBar
        members={[baseMember({ last_seen_at: now })]}
        now={now}
        showCount={false}
      />,
    );
    expect(screen.queryByText(/live · /)).toBeNull();
  });
});
