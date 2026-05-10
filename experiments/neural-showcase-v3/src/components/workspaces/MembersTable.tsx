import { useState } from "react";
import { RoleChip, type WorkspaceRole } from "./RoleChip";

/**
 * <MembersTable /> — list members of a workspace (Wave 110).
 *
 * Renders a slim 3-column table: identity, role chip, status. Role
 * cell hosts an inline select so admins can change a member's role.
 * Remove button fires the parent's ``onRemove`` callback.
 */
export interface MemberRow {
  id: string;
  user_id: string;
  email: string;
  display_name?: string | null;
  role: string;
  status: string;
  joined_at?: number | null;
}

const ROLE_OPTIONS: WorkspaceRole[] = [
  "owner",
  "admin",
  "designer",
  "analyst",
  "viewer",
];

export function MembersTable({
  members,
  onChangeRole,
  onRemove,
}: {
  members: MemberRow[];
  onChangeRole?: (userId: string, newRole: string) => Promise<void> | void;
  onRemove?: (userId: string) => Promise<void> | void;
}) {
  const [busyUser, setBusyUser] = useState<string | null>(null);

  if (members.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-line/60 px-4 py-6 text-center font-mono-tech text-[11px] uppercase tracking-[1.5px] text-ink-3">
        No members yet.
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-line/50">
      <table className="w-full text-left text-[12.5px] text-ink-2">
        <thead className="border-b border-line/50 bg-bg-2/40 text-[10.5px] uppercase tracking-[1.5px] text-ink-3">
          <tr>
            <th className="px-3 py-2 font-mono-tech font-normal">Member</th>
            <th className="px-3 py-2 font-mono-tech font-normal">Role</th>
            <th className="px-3 py-2 font-mono-tech font-normal">Status</th>
            <th className="px-3 py-2 font-mono-tech font-normal text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {members.map((m) => {
            const busy = busyUser === m.user_id;
            return (
              <tr
                key={m.id}
                className="border-b border-line/30 last:border-0"
              >
                <td className="px-3 py-2.5">
                  <div className="flex flex-col">
                    <span className="text-ink">
                      {m.display_name || m.email}
                    </span>
                    {m.display_name && (
                      <span className="font-mono-tech text-[10.5px] text-ink-3">
                        {m.email}
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <RoleChip role={m.role} />
                    {onChangeRole && m.role !== "owner" && (
                      <select
                        aria-label={`Change role for ${m.email}`}
                        className="rounded-md border border-line/60 bg-bg-1/40 px-1.5 py-0.5 font-mono-tech text-[10px] uppercase tracking-[1px] text-ink-2"
                        value={m.role}
                        disabled={busy}
                        onChange={async (e) => {
                          const next = e.target.value;
                          setBusyUser(m.user_id);
                          try {
                            await onChangeRole(m.user_id, next);
                          } finally {
                            setBusyUser(null);
                          }
                        }}
                      >
                        {ROLE_OPTIONS.filter((r) => r !== "owner").map((r) => (
                          <option key={r} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                </td>
                <td className="px-3 py-2.5 font-mono-tech text-[10.5px] uppercase tracking-[1px] text-ink-3">
                  {m.status}
                </td>
                <td className="px-3 py-2.5 text-right">
                  {onRemove && m.role !== "owner" && m.status === "active" && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={async () => {
                        setBusyUser(m.user_id);
                        try {
                          await onRemove(m.user_id);
                        } finally {
                          setBusyUser(null);
                        }
                      }}
                      className="rounded-md border border-line/60 px-2 py-0.5 font-mono-tech text-[10px] uppercase tracking-[1px] text-ink-3 transition-colors hover:border-red-400/60 hover:text-red-300 disabled:opacity-50"
                    >
                      Revoke
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default MembersTable;
