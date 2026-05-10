"""SQLite-backed durable store for the Workspaces module (Wave 110).

Tables: ``workspaces``, ``memberships``, ``invites``. Same WAL +
``asyncio.to_thread`` discipline as :mod:`backend.core.cohort.store`.

Persists at ``~/.tars/workspaces.sqlite`` by default. Override with
``TARS_WORKSPACES_DB_PATH``. Disable the whole store with
``TARS_WORKSPACES_STORE=disabled``.

Auto-creates a "personal" workspace on first call so existing
single-tenant code implicitly "lives in" one row without any migration.
The personal workspace has a fixed ``id == "personal"`` so the
middleware can default to it without an extra lookup.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
from typing import Any, Mapping, Optional

from .models import (
    CONTRACT_VERSION,
    Invite,
    InviteStatus,
    Membership,
    MembershipStatus,
    Plan,
    VALID_INVITE_STATUSES,
    VALID_MEMBERSHIP_STATUSES,
    VALID_PLANS,
    Workspace,
    new_invite_id,
    new_invite_token,
    new_membership_id,
    new_workspace_id,
)
from .roles import VALID_ROLES, Role


DEFAULT_DB_PATH = "~/.tars/workspaces.sqlite"
PERSONAL_ID = "personal"
PERSONAL_SLUG = "personal"
PERSONAL_NAME = "Personal"
PERSONAL_OWNER = "local"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    owner_user_id TEXT NOT NULL,
    plan TEXT NOT NULL,
    created_at REAL NOT NULL,
    archived_at REAL,
    settings_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS memberships (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    email TEXT NOT NULL,
    display_name TEXT,
    role TEXT NOT NULL,
    invited_by TEXT,
    joined_at REAL,
    invited_at REAL NOT NULL,
    status TEXT NOT NULL,
    UNIQUE (workspace_id, user_id),
    FOREIGN KEY (workspace_id) REFERENCES workspaces (id)
);

CREATE TABLE IF NOT EXISTS invites (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    invited_by TEXT NOT NULL,
    invited_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    accepted_at REAL,
    status TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces (id)
);

CREATE INDEX IF NOT EXISTS idx_workspaces_slug ON workspaces (slug);
CREATE INDEX IF NOT EXISTS idx_workspaces_owner ON workspaces (owner_user_id);
CREATE INDEX IF NOT EXISTS idx_memberships_ws ON memberships (workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_memberships_user ON memberships (user_id, status);
CREATE INDEX IF NOT EXISTS idx_invites_ws ON invites (workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_invites_token ON invites (token);
"""


def _resolve_db_path(override: Optional[str] = None) -> str:
    raw = override or os.getenv("TARS_WORKSPACES_DB_PATH") or DEFAULT_DB_PATH
    return os.path.expanduser(raw)


def _is_disabled() -> bool:
    flag = (os.getenv("TARS_WORKSPACES_STORE") or "").strip().lower()
    return flag in {"disabled", "off", "0", "false", "no"}


def _now() -> float:
    return time.time()


def _norm_role(role: str) -> str:
    r = (role or "").strip().lower()
    if r not in VALID_ROLES:
        raise ValueError(f"invalid role: {role!r}")
    return r


def _norm_plan(plan: str) -> str:
    p = (plan or "").strip().lower()
    if p not in VALID_PLANS:
        raise ValueError(f"invalid plan: {plan!r}")
    return p


def _norm_email(email: str) -> str:
    e = (email or "").strip().lower()
    if not e or "@" not in e:
        raise ValueError(f"invalid email: {email!r}")
    return e


class WorkspacesStore:
    """Durable workspace + membership + invite store. Auto-initialised."""

    contract_version = CONTRACT_VERSION

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._disabled = _is_disabled()
        self._db_path = _resolve_db_path(db_path)
        self._inited = False
        self._personal_seeded = False

    @property
    def enabled(self) -> bool:
        return not self._disabled

    @property
    def db_path(self) -> str:
        return self._db_path

    def _ensure_dir(self) -> None:
        directory = os.path.dirname(self._db_path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        self._ensure_dir()
        conn = sqlite3.connect(self._db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        if not self._inited:
            conn.executescript(_SCHEMA)
            self._inited = True
        if not self._personal_seeded:
            self._seed_personal_sync(conn)
            self._personal_seeded = True
        return conn

    # ---- row mapping ---------------------------------------------------

    @staticmethod
    def _row_to_workspace(row: sqlite3.Row) -> Workspace:
        try:
            settings = json.loads(row["settings_json"] or "{}")
        except json.JSONDecodeError:
            settings = {}
        if not isinstance(settings, dict):
            settings = {}
        return Workspace(
            id=row["id"],
            slug=row["slug"],
            name=row["name"],
            owner_user_id=row["owner_user_id"],
            plan=row["plan"],
            created_at=float(row["created_at"]),
            archived_at=row["archived_at"],
            settings=settings,
        )

    @staticmethod
    def _row_to_membership(row: sqlite3.Row) -> Membership:
        return Membership(
            id=row["id"],
            workspace_id=row["workspace_id"],
            user_id=row["user_id"],
            email=row["email"],
            display_name=row["display_name"],
            role=row["role"],
            invited_by=row["invited_by"],
            joined_at=row["joined_at"],
            invited_at=float(row["invited_at"]),
            status=row["status"],
        )

    @staticmethod
    def _row_to_invite(row: sqlite3.Row) -> Invite:
        return Invite(
            id=row["id"],
            workspace_id=row["workspace_id"],
            email=row["email"],
            role=row["role"],
            token=row["token"],
            invited_by=row["invited_by"],
            invited_at=float(row["invited_at"]),
            expires_at=float(row["expires_at"]),
            accepted_at=row["accepted_at"],
            status=row["status"],
        )

    # ---- personal seed --------------------------------------------------

    def _seed_personal_sync(self, conn: sqlite3.Connection) -> None:
        cur = conn.execute("SELECT 1 FROM workspaces WHERE id = ?", (PERSONAL_ID,))
        if cur.fetchone() is not None:
            return
        now = _now()
        conn.execute(
            "INSERT INTO workspaces (id, slug, name, owner_user_id, plan, created_at, archived_at, settings_json) "
            "VALUES (?, ?, ?, ?, ?, ?, NULL, ?)",
            (
                PERSONAL_ID,
                PERSONAL_SLUG,
                PERSONAL_NAME,
                PERSONAL_OWNER,
                Plan.FREE.value,
                now,
                "{}",
            ),
        )
        # Owner membership for the local user.
        conn.execute(
            "INSERT INTO memberships (id, workspace_id, user_id, email, display_name, role, invited_by, joined_at, invited_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)",
            (
                new_membership_id(),
                PERSONAL_ID,
                PERSONAL_OWNER,
                "local@tars.local",
                "Local operator",
                Role.OWNER.value,
                now,
                now,
                MembershipStatus.ACTIVE.value,
            ),
        )
        conn.commit()

    # ---- workspace CRUD -------------------------------------------------

    def _create_workspace_sync(
        self,
        *,
        slug: str,
        name: str,
        owner_user_id: str,
        plan: str,
        settings: Optional[Mapping[str, Any]],
    ) -> Workspace:
        slug = (slug or "").strip().lower()
        name = (name or "").strip()
        owner_user_id = (owner_user_id or "").strip()
        if not slug:
            raise ValueError("slug is required")
        if not name:
            raise ValueError("name is required")
        if not owner_user_id:
            raise ValueError("owner_user_id is required")
        plan = _norm_plan(plan)
        ws_id = new_workspace_id()
        now = _now()
        settings_json = json.dumps(dict(settings or {}))
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO workspaces (id, slug, name, owner_user_id, plan, created_at, archived_at, settings_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, NULL, ?)",
                    (ws_id, slug, name, owner_user_id, plan, now, settings_json),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"slug already exists: {slug!r}") from exc
            # Owner gets an active membership row immediately.
            conn.execute(
                "INSERT INTO memberships (id, workspace_id, user_id, email, display_name, role, invited_by, joined_at, invited_at, status) "
                "VALUES (?, ?, ?, ?, NULL, ?, NULL, ?, ?, ?)",
                (
                    new_membership_id(),
                    ws_id,
                    owner_user_id,
                    f"{owner_user_id}@tars.local",
                    Role.OWNER.value,
                    now,
                    now,
                    MembershipStatus.ACTIVE.value,
                ),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,)).fetchone()
        return self._row_to_workspace(row)

    async def create_workspace(
        self,
        slug: str,
        name: str,
        owner_user_id: str,
        plan: str = Plan.FREE.value,
        settings: Optional[Mapping[str, Any]] = None,
    ) -> Workspace:
        return await asyncio.to_thread(
            self._create_workspace_sync,
            slug=slug,
            name=name,
            owner_user_id=owner_user_id,
            plan=plan,
            settings=settings,
        )

    def _get_workspace_sync(self, id_or_slug: str) -> Optional[Workspace]:
        if not id_or_slug:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM workspaces WHERE id = ? OR slug = ? LIMIT 1",
                (id_or_slug, id_or_slug),
            ).fetchone()
        return self._row_to_workspace(row) if row else None

    async def get_workspace(self, id_or_slug: str) -> Optional[Workspace]:
        return await asyncio.to_thread(self._get_workspace_sync, id_or_slug)

    def _list_workspaces_sync(self, user_id: Optional[str]) -> list[Workspace]:
        with self._connect() as conn:
            if user_id:
                rows = conn.execute(
                    "SELECT w.* FROM workspaces w "
                    "JOIN memberships m ON m.workspace_id = w.id "
                    "WHERE m.user_id = ? AND m.status = ? "
                    "ORDER BY w.created_at ASC",
                    (user_id, MembershipStatus.ACTIVE.value),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM workspaces ORDER BY created_at ASC"
                ).fetchall()
        return [self._row_to_workspace(r) for r in rows]

    async def list_workspaces(
        self, user_id: Optional[str] = None
    ) -> list[Workspace]:
        return await asyncio.to_thread(self._list_workspaces_sync, user_id)

    def _archive_workspace_sync(self, ws_id: str) -> bool:
        if ws_id == PERSONAL_ID:
            raise ValueError("personal workspace cannot be archived")
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE workspaces SET archived_at = ? WHERE id = ? AND archived_at IS NULL",
                (_now(), ws_id),
            )
            conn.commit()
            return cur.rowcount > 0

    async def archive_workspace(self, ws_id: str) -> bool:
        return await asyncio.to_thread(self._archive_workspace_sync, ws_id)

    def _update_workspace_sync(
        self,
        ws_id: str,
        *,
        name: Optional[str] = None,
        plan: Optional[str] = None,
        settings: Optional[Mapping[str, Any]] = None,
    ) -> Optional[Workspace]:
        sets: list[str] = []
        args: list[Any] = []
        if name is not None:
            n = name.strip()
            if not n:
                raise ValueError("name cannot be empty")
            sets.append("name = ?")
            args.append(n)
        if plan is not None:
            sets.append("plan = ?")
            args.append(_norm_plan(plan))
        if settings is not None:
            sets.append("settings_json = ?")
            args.append(json.dumps(dict(settings)))
        if not sets:
            return self._get_workspace_sync(ws_id)
        args.append(ws_id)
        with self._connect() as conn:
            cur = conn.execute(
                f"UPDATE workspaces SET {', '.join(sets)} WHERE id = ?",
                tuple(args),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
            row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,)).fetchone()
        return self._row_to_workspace(row) if row else None

    async def update_workspace(
        self,
        ws_id: str,
        *,
        name: Optional[str] = None,
        plan: Optional[str] = None,
        settings: Optional[Mapping[str, Any]] = None,
    ) -> Optional[Workspace]:
        return await asyncio.to_thread(
            self._update_workspace_sync,
            ws_id,
            name=name,
            plan=plan,
            settings=settings,
        )

    # ---- membership CRUD -----------------------------------------------

    def _add_member_sync(
        self,
        *,
        workspace_id: str,
        user_id: str,
        email: str,
        role: str,
        invited_by: Optional[str],
        display_name: Optional[str],
        status: str,
    ) -> Membership:
        if not workspace_id or not user_id:
            raise ValueError("workspace_id and user_id are required")
        role = _norm_role(role)
        email = _norm_email(email)
        if status not in VALID_MEMBERSHIP_STATUSES:
            raise ValueError(f"invalid membership status: {status!r}")
        now = _now()
        joined_at = now if status == MembershipStatus.ACTIVE.value else None
        m_id = new_membership_id()
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO memberships (id, workspace_id, user_id, email, display_name, role, invited_by, joined_at, invited_at, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        m_id,
                        workspace_id,
                        user_id,
                        email,
                        display_name,
                        role,
                        invited_by,
                        joined_at,
                        now,
                        status,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(
                    f"user {user_id!r} is already a member of {workspace_id!r}"
                ) from exc
            conn.commit()
            row = conn.execute(
                "SELECT * FROM memberships WHERE id = ?", (m_id,)
            ).fetchone()
        return self._row_to_membership(row)

    async def add_member(
        self,
        workspace_id: str,
        user_id: str,
        email: str,
        role: str,
        invited_by: Optional[str] = None,
        display_name: Optional[str] = None,
        status: str = MembershipStatus.ACTIVE.value,
    ) -> Membership:
        return await asyncio.to_thread(
            self._add_member_sync,
            workspace_id=workspace_id,
            user_id=user_id,
            email=email,
            role=role,
            invited_by=invited_by,
            display_name=display_name,
            status=status,
        )

    def _update_member_role_sync(
        self, workspace_id: str, user_id: str, new_role: str
    ) -> Optional[Membership]:
        new_role = _norm_role(new_role)
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE memberships SET role = ? WHERE workspace_id = ? AND user_id = ?",
                (new_role, workspace_id, user_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM memberships WHERE workspace_id = ? AND user_id = ?",
                (workspace_id, user_id),
            ).fetchone()
        return self._row_to_membership(row) if row else None

    async def update_member_role(
        self, workspace_id: str, user_id: str, new_role: str
    ) -> Optional[Membership]:
        return await asyncio.to_thread(
            self._update_member_role_sync, workspace_id, user_id, new_role
        )

    def _revoke_member_sync(self, workspace_id: str, user_id: str) -> bool:
        with self._connect() as conn:
            # Refuse to revoke the workspace owner — every workspace
            # must keep at least one owner.
            row = conn.execute(
                "SELECT role FROM memberships WHERE workspace_id = ? AND user_id = ?",
                (workspace_id, user_id),
            ).fetchone()
            if row is None:
                return False
            if row["role"] == Role.OWNER.value:
                raise ValueError("cannot revoke the workspace owner")
            cur = conn.execute(
                "UPDATE memberships SET status = ? WHERE workspace_id = ? AND user_id = ?",
                (MembershipStatus.REVOKED.value, workspace_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0

    async def revoke_member(self, workspace_id: str, user_id: str) -> bool:
        return await asyncio.to_thread(
            self._revoke_member_sync, workspace_id, user_id
        )

    def _list_members_sync(self, workspace_id: str) -> list[Membership]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memberships WHERE workspace_id = ? ORDER BY invited_at ASC",
                (workspace_id,),
            ).fetchall()
        return [self._row_to_membership(r) for r in rows]

    async def list_members(self, workspace_id: str) -> list[Membership]:
        return await asyncio.to_thread(self._list_members_sync, workspace_id)

    # ---- invite flow ----------------------------------------------------

    def _create_invite_sync(
        self,
        *,
        workspace_id: str,
        email: str,
        role: str,
        invited_by: str,
        expires_in_days: int,
    ) -> Invite:
        email = _norm_email(email)
        role = _norm_role(role)
        if not invited_by:
            raise ValueError("invited_by is required")
        if expires_in_days <= 0:
            raise ValueError("expires_in_days must be positive")
        # Workspace must exist + be active.
        ws = self._get_workspace_sync(workspace_id)
        if ws is None:
            raise ValueError(f"workspace not found: {workspace_id!r}")
        if not ws.is_active:
            raise ValueError(f"workspace is archived: {workspace_id!r}")
        inv_id = new_invite_id()
        token = new_invite_token()
        now = _now()
        expires_at = now + expires_in_days * 24 * 3600
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO invites (id, workspace_id, email, role, token, invited_by, invited_at, expires_at, accepted_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)",
                (
                    inv_id,
                    workspace_id,
                    email,
                    role,
                    token,
                    invited_by,
                    now,
                    expires_at,
                    InviteStatus.PENDING.value,
                ),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM invites WHERE id = ?", (inv_id,)).fetchone()
        return self._row_to_invite(row)

    async def create_invite(
        self,
        workspace_id: str,
        email: str,
        role: str,
        invited_by: str,
        expires_in_days: int = 7,
    ) -> Invite:
        return await asyncio.to_thread(
            self._create_invite_sync,
            workspace_id=workspace_id,
            email=email,
            role=role,
            invited_by=invited_by,
            expires_in_days=expires_in_days,
        )

    def _accept_invite_sync(self, token: str, user_id: str) -> Membership:
        if not token:
            raise ValueError("token is required")
        if not user_id:
            raise ValueError("user_id is required")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM invites WHERE token = ?", (token,)
            ).fetchone()
            if row is None:
                raise ValueError("invite not found")
            inv = self._row_to_invite(row)
            if inv.status != InviteStatus.PENDING.value:
                raise ValueError(f"invite not pending: {inv.status}")
            if inv.is_expired:
                # Auto-mark expired so subsequent reads see the right state.
                conn.execute(
                    "UPDATE invites SET status = ? WHERE id = ?",
                    (InviteStatus.EXPIRED.value, inv.id),
                )
                conn.commit()
                raise ValueError("invite expired")
            now = _now()
            # Try to insert the new membership. If the user is already
            # a member of this workspace we leave the existing row in
            # place but still mark the invite accepted.
            try:
                m_id = new_membership_id()
                conn.execute(
                    "INSERT INTO memberships (id, workspace_id, user_id, email, display_name, role, invited_by, joined_at, invited_at, status) "
                    "VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?)",
                    (
                        m_id,
                        inv.workspace_id,
                        user_id,
                        inv.email,
                        inv.role,
                        inv.invited_by,
                        now,
                        inv.invited_at,
                        MembershipStatus.ACTIVE.value,
                    ),
                )
            except sqlite3.IntegrityError:
                # Already a member — re-activate if revoked.
                conn.execute(
                    "UPDATE memberships SET status = ?, role = ?, joined_at = COALESCE(joined_at, ?) "
                    "WHERE workspace_id = ? AND user_id = ?",
                    (
                        MembershipStatus.ACTIVE.value,
                        inv.role,
                        now,
                        inv.workspace_id,
                        user_id,
                    ),
                )
            conn.execute(
                "UPDATE invites SET status = ?, accepted_at = ? WHERE id = ?",
                (InviteStatus.ACCEPTED.value, now, inv.id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM memberships WHERE workspace_id = ? AND user_id = ?",
                (inv.workspace_id, user_id),
            ).fetchone()
        return self._row_to_membership(row)

    async def accept_invite(self, token: str, user_id: str) -> Membership:
        return await asyncio.to_thread(self._accept_invite_sync, token, user_id)

    def _revoke_invite_sync(self, invite_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE invites SET status = ? WHERE id = ? AND status = ?",
                (
                    InviteStatus.REVOKED.value,
                    invite_id,
                    InviteStatus.PENDING.value,
                ),
            )
            conn.commit()
            return cur.rowcount > 0

    async def revoke_invite(self, invite_id: str) -> bool:
        return await asyncio.to_thread(self._revoke_invite_sync, invite_id)

    def _list_pending_invites_sync(self, workspace_id: str) -> list[Invite]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM invites WHERE workspace_id = ? AND status = ? ORDER BY invited_at DESC",
                (workspace_id, InviteStatus.PENDING.value),
            ).fetchall()
        invites: list[Invite] = []
        # Lazy expiry: surface the right status to callers without a
        # background sweeper.
        now = _now()
        with self._connect() as conn:
            for r in rows:
                inv = self._row_to_invite(r)
                if inv.expires_at < now:
                    conn.execute(
                        "UPDATE invites SET status = ? WHERE id = ?",
                        (InviteStatus.EXPIRED.value, inv.id),
                    )
                else:
                    invites.append(inv)
            conn.commit()
        return invites

    async def list_pending_invites(self, workspace_id: str) -> list[Invite]:
        return await asyncio.to_thread(
            self._list_pending_invites_sync, workspace_id
        )

    def _get_invite_by_token_sync(self, token: str) -> Optional[Invite]:
        if not token:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM invites WHERE token = ? LIMIT 1", (token,)
            ).fetchone()
        return self._row_to_invite(row) if row else None

    async def get_invite_by_token(self, token: str) -> Optional[Invite]:
        return await asyncio.to_thread(self._get_invite_by_token_sync, token)


# ---- module singleton -----------------------------------------------------

_store_singleton: Optional[WorkspacesStore] = None


def get_store() -> WorkspacesStore:
    """Return the process-wide singleton store, creating it if needed."""

    global _store_singleton
    if _store_singleton is None:
        _store_singleton = WorkspacesStore()
    return _store_singleton


def reset_store() -> None:
    """Drop the singleton (test-only — production never calls this)."""

    global _store_singleton
    _store_singleton = None


__all__ = [
    "DEFAULT_DB_PATH",
    "PERSONAL_ID",
    "PERSONAL_NAME",
    "PERSONAL_OWNER",
    "PERSONAL_SLUG",
    "WorkspacesStore",
    "get_store",
    "reset_store",
]
