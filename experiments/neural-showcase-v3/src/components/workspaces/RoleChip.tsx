import type { CSSProperties } from "react";

/**
 * <RoleChip /> — colored badge for a workspace role (Wave 110).
 *
 * Mirrors the backend RBAC enum from
 * ``backend/core/workspaces/roles.py``. Colours come from the brand
 * tokens — no hardcoded hex.
 */
export type WorkspaceRole =
  | "owner"
  | "admin"
  | "designer"
  | "analyst"
  | "viewer";

const STYLES: Record<WorkspaceRole, { bg: string; ink: string; label: string }> = {
  owner:    { bg: "var(--brand-indigo)",  ink: "#0b0510", label: "Owner" },
  admin:    { bg: "var(--brand-violet)",  ink: "#0b0510", label: "Admin" },
  designer: { bg: "var(--brand-cyan)",    ink: "#0b0510", label: "Designer" },
  analyst:  { bg: "var(--ink-2)",         ink: "var(--bg-0)", label: "Analyst" },
  viewer:   { bg: "transparent",          ink: "var(--ink-2)", label: "Viewer" },
};

export function RoleChip({ role }: { role: WorkspaceRole | string }) {
  const norm = (role || "").toString().toLowerCase() as WorkspaceRole;
  const cfg = STYLES[norm] ?? STYLES.viewer;
  const isOutline = norm === "viewer";
  const style: CSSProperties = {
    backgroundColor: isOutline ? "transparent" : cfg.bg,
    color: cfg.ink,
    borderColor: isOutline ? "var(--line)" : cfg.bg,
  };
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono-tech text-[10px] uppercase tracking-[1.5px]"
      style={style}
    >
      {cfg.label}
    </span>
  );
}

export default RoleChip;
