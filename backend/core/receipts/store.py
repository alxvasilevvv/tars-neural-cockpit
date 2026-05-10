"""Append-only NDJSON ledger + SQLite query index for receipts
(Wave 95).

Two-tier persistence:

- ``~/.tars/receipts/<YYYY-MM-DD>.ndjson`` — one file per UTC day,
  one receipt per line. The NDJSON is the source of truth: chain
  verification + Merkle root computation always replay from disk.

- ``~/.tars/receipts.sqlite`` — read-side mirror keyed by receipt id
  for fast filter queries (type / actor / time-range). Also stores
  the per-day ``merkle_roots`` rows.

The host signing key is loaded from
``~/.tars/host-key.json`` (override via ``TARS_RECEIPT_HOST_KEY_PATH``).
If the file doesn't exist on first append, we generate a fresh
ed25519 keypair and persist it with mode 0600. There is no recovery
flow: rotating the key invalidates everything in the existing chain
for verification purposes (operators should snapshot
``host-key.json`` to a recovery medium when they care).

Disable the whole module with ``TARS_RECEIPT_STORE=disabled``.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable



from .chain import compute_hash, sign as chain_sign
from .models import MerkleRoot, Receipt, new_receipt_id


DEFAULT_NDJSON_DIR = "~/.tars/receipts"
DEFAULT_DB_PATH = "~/.tars/receipts.sqlite"
DEFAULT_HOST_KEY_PATH = "~/.tars/host-key.json"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS receipts (
    id TEXT PRIMARY KEY,
    ts REAL NOT NULL,
    type TEXT NOT NULL,
    actor TEXT NOT NULL,
    resource TEXT,
    payload_json TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL,
    signature TEXT NOT NULL,
    public_key TEXT NOT NULL,
    day_iso TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_receipts_ts ON receipts (ts DESC);
CREATE INDEX IF NOT EXISTS idx_receipts_type_ts ON receipts (type, ts DESC);
CREATE INDEX IF NOT EXISTS idx_receipts_actor_ts ON receipts (actor, ts DESC);
CREATE INDEX IF NOT EXISTS idx_receipts_day ON receipts (day_iso);

CREATE TABLE IF NOT EXISTS merkle_roots (
    id TEXT PRIMARY KEY,
    day_iso TEXT NOT NULL UNIQUE,
    root_hex TEXT NOT NULL,
    leaf_count INTEGER NOT NULL,
    anchored_at REAL,
    solana_signature TEXT,
    created_at REAL NOT NULL
);
"""


def _expand(p: str) -> str:
    return os.path.expanduser(p)


def _resolve_ndjson_dir(override: str | None = None) -> str:
    raw = override or os.getenv("TARS_RECEIPT_DIR") or DEFAULT_NDJSON_DIR
    return _expand(raw)


def _resolve_db_path(override: str | None = None) -> str:
    raw = override or os.getenv("TARS_RECEIPT_DB_PATH") or DEFAULT_DB_PATH
    return _expand(raw)


def _resolve_host_key_path(override: str | None = None) -> str:
    raw = (
        override
        or os.getenv("TARS_RECEIPT_HOST_KEY_PATH")
        or DEFAULT_HOST_KEY_PATH
    )
    return _expand(raw)


def _is_disabled() -> bool:
    flag = (os.getenv("TARS_RECEIPT_STORE") or "").strip().lower()
    return flag in {"disabled", "off", "0", "false", "no"}


def _utc_day_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


# ----- Host signing key ----------------------------------------------------


def _load_or_create_host_key(path: str) -> tuple[bytes, bytes]:
    """Return (priv_seed_32, pub_32). Creates a fresh ed25519 keypair
    on first use and writes it to ``path`` with mode 0600.
    """

    p = Path(path)
    if p.exists():
        try:
            data = json.loads(p.read_text("utf-8"))
            priv = base64.b64decode(data["private_key"])
            pub = base64.b64decode(data["public_key"])
            if len(priv) != 32 or len(pub) != 32:
                raise ValueError("malformed host-key.json")
            return priv, pub
        except Exception as exc:
            raise RuntimeError(f"could not load receipt host key: {exc}") from exc
    from .chain import generate_keypair
    priv, pub = generate_keypair()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "scheme": "ed25519",
        "private_key": base64.b64encode(priv).decode("ascii"),
        "public_key": base64.b64encode(pub).decode("ascii"),
        "created_at": time.time(),
    }
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, p)
    return priv, pub


# ----- Store ---------------------------------------------------------------


class ReceiptStore:
    """SQLite + NDJSON-backed append-only receipt ledger."""

    def __init__(
        self,
        *,
        ndjson_dir: str | None = None,
        db_path: str | None = None,
        host_key_path: str | None = None,
    ) -> None:
        self.ndjson_dir = _resolve_ndjson_dir(ndjson_dir)
        self.db_path = _resolve_db_path(db_path)
        self.host_key_path = _resolve_host_key_path(host_key_path)
        self._lock = asyncio.Lock()
        self._priv: bytes | None = None
        self._pub: bytes | None = None
        self._pub_b64: str | None = None
        self._init_done = False

    # ----- init -----------------------------------------------------------

    def _init_sync(self) -> None:
        if self._init_done:
            return
        os.makedirs(self.ndjson_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("PRAGMA journal_mode=WAL;")
            conn.executescript(_SCHEMA)
            conn.commit()
        priv, pub = _load_or_create_host_key(self.host_key_path)
        self._priv = priv
        self._pub = pub
        self._pub_b64 = base64.b64encode(pub).decode("ascii")
        self._init_done = True

    async def _init(self) -> None:
        if self._init_done:
            return
        await asyncio.to_thread(self._init_sync)

    # ----- public key helper ---------------------------------------------

    @property
    def public_key_b64(self) -> str:
        if self._pub_b64 is None:
            self._init_sync()
        assert self._pub_b64 is not None
        return self._pub_b64

    # ----- helpers --------------------------------------------------------

    def _ndjson_path(self, day_iso: str) -> str:
        return os.path.join(self.ndjson_dir, f"{day_iso}.ndjson")

    def _last_receipt_sync(self) -> Receipt | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM receipts ORDER BY ts DESC, id DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            return _row_to_receipt(row)

    async def last_receipt(self) -> Receipt | None:
        await self._init()
        return await asyncio.to_thread(self._last_receipt_sync)

    # ----- append --------------------------------------------------------

    async def append(
        self,
        type: str,
        actor: str,
        resource: str | None,
        payload: dict[str, Any] | None = None,
        *,
        ts: float | None = None,
    ) -> Receipt:
        """Compute prev_hash → hash + sign → write NDJSON + SQLite row.

        Atomic per-call via an in-process lock; concurrent appends
        from the same process serialise. Cross-process callers should
        not share this DB.
        """

        await self._init()
        async with self._lock:
            return await asyncio.to_thread(
                self._append_sync,
                type,
                actor,
                resource,
                dict(payload or {}),
                ts,
            )

    def _append_sync(
        self,
        type: str,
        actor: str,
        resource: str | None,
        payload: dict[str, Any],
        ts: float | None,
    ) -> Receipt:
        assert self._priv is not None and self._pub_b64 is not None
        last = self._last_receipt_sync()
        prev_hash = last.hash if last is not None else ""
        rid = new_receipt_id()
        now = float(ts) if ts is not None else time.time()
        receipt = Receipt(
            id=rid,
            ts=now,
            type=type,
            actor=actor,
            resource=resource,
            payload=payload,
            prev_hash=prev_hash,
            hash="",
            signature="",
            public_key=self._pub_b64,
        )
        receipt.hash = compute_hash(receipt)
        receipt.signature = chain_sign(receipt, self._priv)

        day_iso = _utc_day_iso(now)
        # Append to NDJSON (one file per UTC day; auto-rotates).
        path = self._ndjson_path(day_iso)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        line = json.dumps(receipt.to_dict(), sort_keys=True) + "\n"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass

        # Mirror to SQLite.
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO receipts "
                "(id, ts, type, actor, resource, payload_json, "
                " prev_hash, hash, signature, public_key, day_iso) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    receipt.id,
                    receipt.ts,
                    receipt.type,
                    receipt.actor,
                    receipt.resource,
                    json.dumps(receipt.payload, sort_keys=True),
                    receipt.prev_hash,
                    receipt.hash,
                    receipt.signature,
                    receipt.public_key,
                    day_iso,
                ),
            )
            conn.commit()
        return receipt

    # ----- query --------------------------------------------------------

    async def query(
        self,
        *,
        type: str | None = None,
        actor: str | None = None,
        since: float | None = None,
        until: float | None = None,
        limit: int = 100,
    ) -> list[Receipt]:
        await self._init()
        return await asyncio.to_thread(
            self._query_sync, type, actor, since, until, limit
        )

    def _query_sync(
        self,
        type: str | None,
        actor: str | None,
        since: float | None,
        until: float | None,
        limit: int,
    ) -> list[Receipt]:
        clauses: list[str] = []
        params: list[Any] = []
        if type:
            clauses.append("type = ?")
            params.append(type)
        if actor:
            clauses.append("actor = ?")
            params.append(actor)
        if since is not None:
            clauses.append("ts >= ?")
            params.append(float(since))
        if until is not None:
            clauses.append("ts <= ?")
            params.append(float(until))
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (
            f"SELECT * FROM receipts {where} "
            "ORDER BY ts DESC, id DESC LIMIT ?"
        )
        params.append(int(limit))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_receipt(r) for r in rows]

    async def get_by_id(self, receipt_id: str) -> Receipt | None:
        await self._init()
        return await asyncio.to_thread(self._get_by_id_sync, receipt_id)

    def _get_by_id_sync(self, receipt_id: str) -> Receipt | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM receipts WHERE id = ?", (receipt_id,)
            ).fetchone()
        return _row_to_receipt(row) if row else None

    # ----- chain replay (NDJSON source of truth) ------------------------

    async def replay_chain_for_day(self, day_iso: str) -> list[Receipt]:
        await self._init()
        return await asyncio.to_thread(self._replay_sync, day_iso)

    def _replay_sync(self, day_iso: str) -> list[Receipt]:
        path = self._ndjson_path(day_iso)
        if not os.path.exists(path):
            return []
        out: list[Receipt] = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(Receipt.from_dict(json.loads(line)))
                except Exception:
                    continue
        return out

    # ----- merkle root ---------------------------------------------------

    async def get_merkle_root(self, day_iso: str) -> MerkleRoot | None:
        await self._init()
        return await asyncio.to_thread(self._get_merkle_sync, day_iso)

    def _get_merkle_sync(self, day_iso: str) -> MerkleRoot | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM merkle_roots WHERE day_iso = ?", (day_iso,)
            ).fetchone()
        if row is None:
            return None
        return _row_to_merkle(row)

    async def upsert_merkle_root(
        self,
        *,
        day_iso: str,
        root_hex: str,
        leaf_count: int,
        anchored_at: float | None = None,
        solana_signature: str | None = None,
    ) -> MerkleRoot:
        await self._init()
        return await asyncio.to_thread(
            self._upsert_merkle_sync,
            day_iso,
            root_hex,
            leaf_count,
            anchored_at,
            solana_signature,
        )

    def _upsert_merkle_sync(
        self,
        day_iso: str,
        root_hex: str,
        leaf_count: int,
        anchored_at: float | None,
        solana_signature: str | None,
    ) -> MerkleRoot:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            existing = conn.execute(
                "SELECT id FROM merkle_roots WHERE day_iso = ?", (day_iso,)
            ).fetchone()
            now = time.time()
            if existing is None:
                rid = "mrk_" + day_iso.replace("-", "")
                conn.execute(
                    "INSERT INTO merkle_roots "
                    "(id, day_iso, root_hex, leaf_count, anchored_at, "
                    " solana_signature, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        rid,
                        day_iso,
                        root_hex,
                        int(leaf_count),
                        anchored_at,
                        solana_signature,
                        now,
                    ),
                )
            else:
                conn.execute(
                    "UPDATE merkle_roots SET root_hex=?, leaf_count=?, "
                    "anchored_at=?, solana_signature=? WHERE day_iso=?",
                    (
                        root_hex,
                        int(leaf_count),
                        anchored_at,
                        solana_signature,
                        day_iso,
                    ),
                )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM merkle_roots WHERE day_iso = ?", (day_iso,)
            ).fetchone()
        return _row_to_merkle(row)


# ----- row → dataclass ----------------------------------------------------


def _row_to_receipt(row: sqlite3.Row) -> Receipt:
    return Receipt(
        id=row["id"],
        ts=float(row["ts"]),
        type=row["type"],
        actor=row["actor"],
        resource=row["resource"],
        payload=json.loads(row["payload_json"] or "{}"),
        prev_hash=row["prev_hash"] or "",
        hash=row["hash"] or "",
        signature=row["signature"] or "",
        public_key=row["public_key"] or "",
    )


def _row_to_merkle(row: sqlite3.Row) -> MerkleRoot:
    return MerkleRoot(
        id=row["id"],
        day_iso=row["day_iso"],
        root_hex=row["root_hex"],
        leaf_count=int(row["leaf_count"]),
        anchored_at=row["anchored_at"],
        solana_signature=row["solana_signature"],
        created_at=float(row["created_at"]),
    )


# ----- module singleton ---------------------------------------------------


_STORE: ReceiptStore | None = None


def get_store() -> ReceiptStore | None:
    """Return the process-wide receipt store, or ``None`` if disabled."""

    global _STORE
    if _is_disabled():
        return None
    if _STORE is None:
        _STORE = ReceiptStore()
    return _STORE


def reset_store() -> None:
    """Clear the singleton — used by tests that point at temp DBs."""

    global _STORE
    _STORE = None
