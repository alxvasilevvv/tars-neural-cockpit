import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { Users, Plus, Archive } from "lucide-react";
import { useDocumentMeta } from "@/lib/meta";
import { CornerFrame } from "@/components/Glyphs";
import { BrandHairline } from "@/components/BrandHairline";
import { WorkspaceCard, type WorkspaceCardData } from "@/components/workspaces/WorkspaceCard";
import { MembersTable, type MemberRow } from "@/components/workspaces/MembersTable";
import { InviteMemberDialog } from "@/components/workspaces/InviteMemberDialog";
import { RoleChip } from "@/components/workspaces/RoleChip";

interface InviteRow {
  id: string;
  email: string;
  role: string;
  invited_at: number;
  expires_at: number;
  status: string;
}

interface ApiResponse<T> {
  ok: boolean;
  detail?: string;
}

/**
 * <Workspaces /> — multi-tenant Workspaces management page (Wave 110).
 *
 * v9.1.0 ships single-tenant: workspaces register but the backend
 * does NOT scope queries on them yet. The page loudly says so via
 * the banner at the top — the toggle flips in v9.3.
 *
 * Layout: 12-col grid. Left column lists every workspace the user
 * belongs to; right column shows the selected workspace's detail
 * (members + pending invites + invite/archive controls).
 */
export function Workspaces() {
  useDocumentMeta({
    title: "Workspaces · TARS",
    description: "Manage workspaces, members, invites, and roles.",
  });

  const [workspaces, setWorkspaces] = useState<WorkspaceCardData[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [members, setMembers] = useState<MemberRow[]>([]);
  const [invites, setInvites] = useState<InviteRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  // Read-only fetch — no auth headers required (loopback).
  const refresh = useCallback(async () => {
    setLoading(true);
    setErrMsg(null);
    try {
      const r = await fetch("/api/workspaces");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      const list: WorkspaceCardData[] = (data.workspaces || []).map(
        (w: WorkspaceCardData) => ({
          id: w.id,
          slug: w.slug,
          name: w.name,
          plan: w.plan,
          is_active: w.is_active,
        }),
      );
      setWorkspaces(list);
      // Default to "personal" or first if none selected.
      setSelectedId((prev) => prev ?? (list[0]?.id ?? null));
    } catch (e) {
      setErrMsg((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Pull members + invites whenever the selection changes.
  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    (async () => {
      try {
        const [memR, invR] = await Promise.all([
          fetch(`/api/workspaces/${selectedId}/members`),
          fetch(`/api/workspaces/${selectedId}/invites`),
        ]);
        if (cancelled) return;
        if (memR.ok) {
          const md = await memR.json();
          setMembers(md.members || []);
        } else {
          setMembers([]);
        }
        if (invR.ok) {
          const id = await invR.json();
          setInvites(id.invites || []);
        } else {
          setInvites([]);
        }
      } catch {
        if (!cancelled) {
          setMembers([]);
          setInvites([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const selected = useMemo(
    () => workspaces.find((w) => w.id === selectedId) ?? null,
    [workspaces, selectedId],
  );

  async function inviteMember(email: string, role: string) {
    if (!selectedId) return;
    const r = await fetch(`/api/workspaces/${selectedId}/invites`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, role }),
    });
    if (!r.ok) {
      const data: ApiResponse<unknown> = await r.json().catch(() => ({ ok: false }));
      throw new Error(data.detail || `HTTP ${r.status}`);
    }
    const data = await r.json();
    setInvites((prev) => [data.invite, ...prev]);
  }

  async function changeMemberRole(userId: string, newRole: string) {
    if (!selectedId) return;
    await fetch(`/api/workspaces/${selectedId}/members/${userId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: newRole }),
    });
    // Optimistic refresh.
    const r = await fetch(`/api/workspaces/${selectedId}/members`);
    if (r.ok) setMembers((await r.json()).members || []);
  }

  async function removeMember(userId: string) {
    if (!selectedId) return;
    if (!window.confirm(`Revoke this member?`)) return;
    await fetch(`/api/workspaces/${selectedId}/members/${userId}`, {
      method: "DELETE",
    });
    setMembers((prev) =>
      prev.map((m) =>
        m.user_id === userId ? { ...m, status: "revoked" } : m,
      ),
    );
  }

  async function archive() {
    if (!selectedId || selected?.id === "personal") return;
    if (!window.confirm("Archive this workspace? It cannot be undone in v9.1.")) return;
    const r = await fetch(`/api/workspaces/${selectedId}/archive`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (r.ok) {
      void refresh();
    }
  }

  return (
    <section className="relative z-10 mx-auto max-w-[1180px] px-6 pb-24 pt-32 md:px-12">
      <CornerFrame>
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3 transition-colors hover:text-ink"
        >
          <Users size={12} strokeWidth={1.7} />
          back to home
        </Link>
      </CornerFrame>

      <header className="mt-8 flex items-end justify-between">
        <div>
          <p className="flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3">
            <Users size={12} strokeWidth={1.7} />
            <span>workspaces</span>
          </p>
          <h1
            className="font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
            style={{ fontSize: "var(--text-display-md)" }}
          >
            Tenants &amp; teammates
          </h1>
        </div>
        <button
          type="button"
          onClick={() => alert("Workspace creation lands as a HIL-gated dialog in v9.2 — wired here for v9.3.")}
          className="inline-flex items-center gap-1.5 rounded-md border border-line/60 bg-bg-1/40 px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[1.5px] text-ink-2 hover:border-[color:var(--brand-indigo)]/60"
        >
          <Plus size={12} /> New workspace
        </button>
      </header>

      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="mt-6 rounded-xl border border-[color:var(--brand-indigo)]/40 bg-[color:var(--brand-indigo)]/10 px-4 py-3 text-[12px] text-ink-2"
        role="status"
      >
        v9.1.0 ships single-tenant — workspaces register but don't fence
        data yet. Multi-tenant data fencing arrives in v9.3.
      </motion.div>

      {errMsg && (
        <p className="mt-4 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-[12px] text-red-300">
          {errMsg}
        </p>
      )}

      <div className="mt-8 grid gap-6 lg:grid-cols-[320px_1fr]">
        <aside className="space-y-3">
          {loading && workspaces.length === 0 ? (
            <p className="font-mono-tech text-[11px] uppercase tracking-[1.5px] text-ink-3">
              Loading…
            </p>
          ) : (
            workspaces.map((w) => (
              <WorkspaceCard
                key={w.id}
                workspace={w}
                selected={w.id === selectedId}
                onSelect={setSelectedId}
              />
            ))
          )}
        </aside>

        <article className="rounded-xl border border-line/50 bg-bg-1/30 p-5">
          {!selected ? (
            <p className="font-mono-tech text-[11px] uppercase tracking-[1.5px] text-ink-3">
              Select a workspace.
            </p>
          ) : (
            <>
              <header className="flex items-end justify-between">
                <div>
                  <p className="font-mono-tech text-[10.5px] uppercase tracking-[1.5px] text-ink-3">
                    {selected.slug}
                  </p>
                  <h2 className="mt-0.5 font-display text-[22px] font-medium text-ink">
                    {selected.name}
                  </h2>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setInviteOpen(true)}
                    className="inline-flex items-center gap-1.5 rounded-md bg-[color:var(--brand-indigo)] px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[1.5px] text-bg-0 hover:opacity-90"
                  >
                    <Plus size={12} /> Invite member
                  </button>
                  {selected.id !== "personal" && (
                    <button
                      type="button"
                      onClick={archive}
                      className="inline-flex items-center gap-1.5 rounded-md border border-line/60 px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[1.5px] text-ink-2 hover:border-red-400/60 hover:text-red-300"
                    >
                      <Archive size={12} /> Archive
                    </button>
                  )}
                </div>
              </header>
              <BrandHairline className="mt-4" />

              <h3 className="mt-6 font-mono-tech text-[10.5px] uppercase tracking-[1.5px] text-ink-3">
                Members ({members.length})
              </h3>
              <div className="mt-3">
                <MembersTable
                  members={members}
                  onChangeRole={changeMemberRole}
                  onRemove={removeMember}
                />
              </div>

              <h3 className="mt-8 font-mono-tech text-[10.5px] uppercase tracking-[1.5px] text-ink-3">
                Pending invites ({invites.length})
              </h3>
              {invites.length === 0 ? (
                <p className="mt-3 rounded-md border border-dashed border-line/60 px-4 py-4 text-center font-mono-tech text-[11px] uppercase tracking-[1.5px] text-ink-3">
                  No pending invites.
                </p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {invites.map((inv) => (
                    <li
                      key={inv.id}
                      className="flex items-center justify-between rounded-md border border-line/40 bg-bg-2/30 px-3 py-2 text-[12px]"
                    >
                      <div className="flex items-center gap-2">
                        <RoleChip role={inv.role} />
                        <span className="text-ink-2">{inv.email}</span>
                      </div>
                      <span className="font-mono-tech text-[10px] uppercase tracking-[1px] text-ink-3">
                        expires {Math.max(0, Math.round((inv.expires_at - Date.now() / 1000) / 86400))}d
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </article>
      </div>

      <InviteMemberDialog
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        onInvite={inviteMember}
      />
    </section>
  );
}

/**
 * <WorkspaceInviteAccept /> — public landing for accepting an invite
 * via a token URL (Wave 110).
 *
 * Mounts at /workspaces/invite/:token. The token IS the auth — no
 * additional credentials required. POSTs to
 * ``/api/workspaces/invites/{token}/accept`` with a stub user_id so
 * the local sidecar can wire the membership; v9.3 reads this from
 * the JWT.
 */
export function WorkspaceInviteAccept() {
  useDocumentMeta({
    title: "Accept workspace invite · TARS",
    description: "Join a TARS workspace via an invite link.",
  });
  const { token } = useParams<{ token: string }>();
  const [state, setState] = useState<
    | { kind: "idle" }
    | { kind: "loading" }
    | { kind: "ok"; workspaceId: string }
    | { kind: "error"; message: string }
  >({ kind: "idle" });

  async function accept() {
    if (!token) return;
    setState({ kind: "loading" });
    try {
      const userId = `local-${Math.random().toString(36).slice(2, 9)}`;
      const r = await fetch(`/api/workspaces/invites/${encodeURIComponent(token)}/accept`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId }),
      });
      if (!r.ok) {
        const data: { detail?: string } = await r.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${r.status}`);
      }
      const data = await r.json();
      setState({ kind: "ok", workspaceId: data.membership.workspace_id });
    } catch (e) {
      setState({ kind: "error", message: (e as Error).message });
    }
  }

  return (
    <section className="relative z-10 mx-auto max-w-[640px] px-6 pb-24 pt-40 md:px-12">
      <h1
        className="font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
        style={{ fontSize: "var(--text-display-sm)" }}
      >
        Accept workspace invite
      </h1>
      <p className="mt-3 text-[13px] text-ink-2">
        You've been invited to a TARS workspace. Click the button below
        to confirm and join.
      </p>
      {state.kind === "idle" && (
        <button
          type="button"
          onClick={accept}
          className="mt-6 rounded-md bg-[color:var(--brand-indigo)] px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[1.5px] text-bg-0 hover:opacity-90"
        >
          Accept invite
        </button>
      )}
      {state.kind === "loading" && (
        <p className="mt-6 font-mono-tech text-[11px] uppercase tracking-[1.5px] text-ink-3">
          Joining…
        </p>
      )}
      {state.kind === "ok" && (
        <div className="mt-6 rounded-md border border-[color:var(--brand-indigo)]/40 bg-[color:var(--brand-indigo)]/10 px-4 py-3 text-[12px] text-ink-2">
          Joined workspace <code>{state.workspaceId}</code>.{" "}
          <Link to="/workspaces" className="underline">
            Open workspaces
          </Link>
          .
        </div>
      )}
      {state.kind === "error" && (
        <p className="mt-6 rounded-md border border-red-500/40 bg-red-500/10 px-4 py-3 text-[12px] text-red-300">
          {state.message}
        </p>
      )}
    </section>
  );
}

export default Workspaces;
