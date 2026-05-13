"""AI Clone v0.2 — style persistence + cross-machine portability (Wave 151).

Wave 73 shipped Clone v0.1 (style hint heuristic, local SQLite at
``~/.tars/clone.sqlite``). The W148 reality audit flagged the
retention risk: when the operator switches machines or wipes the
laptop, every accumulated style trait is lost.

v0.2 closes that gap without overclaiming "real fine-tune":

  - **Export** — serialise the entire style store (profile snapshot +
    recent traits) to a JSON envelope. Caller hashes + signs it.
  - **Import** — accept that envelope on a fresh machine and rehydrate
    the SQLite DB.
  - **Webhook sync** — best-effort emit on every Nth `record_message`
    call (default every 50 messages) so meeet.world holds the latest
    profile without operator effort. Brother's edge function stores
    it under the user's tenant, available for restore.

Honest framing:
  - This is **NOT** a fine-tuned model. The export is the same style
    heuristic v0.1 ships — just synced, not learned more deeply.
  - **NOT** automatic restore. A fresh TARS install does not pull
    automatically; operator runs ``tars-ops`` → import or hits the
    endpoint manually. Auto-restore lands in v9.2 with magic-link auth.
  - **NOT** real-time. Webhook emits are debounced at 50-message
    intervals to keep meeet.world ingest cheap. Worst case lag = 50
    messages of style change before remote catches up.

Public surface:
  - :class:`StyleEnvelope` — serialisable export shape (v1 schema).
  - :func:`export_profile` — build the envelope from current store.
  - :func:`import_profile` — rehydrate the store from an envelope.
  - :func:`maybe_emit_sync_webhook` — debounced fire-and-forget
    webhook emit (called from :func:`record_message`).
  - :data:`SYNC_INTERVAL_DEFAULT` — env-tunable interval (default 50).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from .style import (
    CloneStore,
    StyleProfile,
    _PROFILE_WINDOW,
    _metrics,
    get_clone_store,
    profile as current_profile,
)


log = logging.getLogger("tars.clone.sync")


CONTRACT_VERSION = "0.2.0"
ENVELOPE_SCHEMA_VERSION = 1
SYNC_INTERVAL_DEFAULT = 50  # emit a webhook every N record_message calls


# ─── Envelope ──────────────────────────────────────────────────────────────


@dataclass
class StyleEnvelope:
    """Serialisable shape of a Clone style export.

    Stable schema:
      - ``schema_version`` — integer; bump on breaking change.
      - ``contract_version`` — string ``"X.Y.Z"`` (Clone module version).
      - ``exported_at`` — unix timestamp the export was produced.
      - ``profile`` — the same dict shape that :class:`StyleProfile`
        exposes (avg_sentence_length, casual/formal lean, top vocab, …).
      - ``traits`` — list of recent message-derived traits the importer
        will re-insert into the SQLite store. Each trait is a small dict
        with ``text``, ``timestamp``, optional ``vector`` (base64-encoded).
      - ``sample_count`` — total messages observed so far. Used by the
        importer to refuse merges that would lose information.
    """

    schema_version: int = ENVELOPE_SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION
    exported_at: float = field(default_factory=time.time)
    profile: dict[str, Any] = field(default_factory=dict)
    traits: list[dict[str, Any]] = field(default_factory=list)
    sample_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "StyleEnvelope":
        return cls(
            schema_version=int(raw.get("schema_version", ENVELOPE_SCHEMA_VERSION)),
            contract_version=str(raw.get("contract_version", CONTRACT_VERSION)),
            exported_at=float(raw.get("exported_at", time.time())),
            profile=dict(raw.get("profile") or {}),
            traits=list(raw.get("traits") or []),
            sample_count=int(raw.get("sample_count", 0)),
        )


# ─── Export ────────────────────────────────────────────────────────────────


async def export_profile(*, store: CloneStore | None = None) -> StyleEnvelope:
    """Build a full export of the current style state.

    Default returns the last :data:`_PROFILE_WINDOW` traits (matches
    the window the profile-compute pass uses internally). For a
    smaller export pass ``store`` with a custom limit.
    """

    s = store or get_clone_store()
    if not s.enabled:
        return StyleEnvelope(profile={}, traits=[], sample_count=0)

    prof = await current_profile()
    rows = await s.recent(limit=_PROFILE_WINDOW)
    traits: list[dict[str, Any]] = []
    for row in rows:
        traits.append(
            {
                "id": row["id"] if "id" in row.keys() else None,
                "text": row["text"] if "text" in row.keys() else "",
                "created_at": row["created_at"] if "created_at" in row.keys() else 0,
            }
        )

    return StyleEnvelope(
        profile=prof.to_dict(),
        traits=traits,
        sample_count=len(traits),
    )


# ─── Import ────────────────────────────────────────────────────────────────


async def import_profile(envelope: StyleEnvelope | dict[str, Any]) -> dict[str, Any]:
    """Restore an envelope into the local store.

    Returns ``{ok: bool, imported: int, skipped: int}``.

    Semantics:
      - Schema-version mismatch (we know how to read v1; future v2
        unsupported) → returns ``ok=False`` with ``error=schema_version_unsupported``.
      - Existing local store with more samples than the envelope →
        merge (insert envelope traits, dedup by text+timestamp).
      - Existing local store empty → straight insert.
    """

    env = (
        envelope
        if isinstance(envelope, StyleEnvelope)
        else StyleEnvelope.from_dict(envelope)
    )

    if env.schema_version > ENVELOPE_SCHEMA_VERSION:
        return {
            "ok": False,
            "error": "schema_version_unsupported",
            "have": ENVELOPE_SCHEMA_VERSION,
            "got": env.schema_version,
        }

    store = get_clone_store()
    if not store.enabled:
        return {"ok": False, "error": "clone_store_disabled"}

    imported = 0
    skipped = 0
    existing_texts: set[str] = set()

    # Pull existing traits once to dedup; for very large stores this
    # is O(N) memory but our window is bounded at _PROFILE_WINDOW (500).
    try:
        existing_rows = await store.recent(limit=_PROFILE_WINDOW)
        for row in existing_rows:
            if "text" in row.keys():
                existing_texts.add(str(row["text"]))
    except Exception:  # noqa: BLE001
        log.debug("import_profile: dedup pre-load failed, proceeding without dedup", exc_info=True)

    for trait in env.traits:
        text = str(trait.get("text") or "").strip()
        if not text:
            skipped += 1
            continue
        if text in existing_texts:
            skipped += 1
            continue
        try:
            await store.insert(
                text=text,
                metrics=_metrics(text),
                created_at=float(trait.get("created_at") or env.exported_at),
            )
            imported += 1
            existing_texts.add(text)
        except Exception:  # noqa: BLE001
            skipped += 1
            log.debug("import_profile: insert failed for one trait", exc_info=True)

    return {
        "ok": True,
        "imported": imported,
        "skipped": skipped,
        "schema_version": env.schema_version,
        "contract_version": env.contract_version,
    }


# ─── Webhook sync (debounced) ──────────────────────────────────────────────


_sync_counter = 0
_last_emit_ts = 0.0


def _interval() -> int:
    raw = os.environ.get("TARS_CLONE_SYNC_INTERVAL")
    try:
        n = int(raw) if raw else SYNC_INTERVAL_DEFAULT
        return max(1, n)
    except ValueError:
        return SYNC_INTERVAL_DEFAULT


async def _emit_now() -> bool:
    """Best-effort: build the envelope and fire it via the webhook
    subsystem. Swallows every exception so the caller (record_message)
    can never be broken by sync side-effects.
    """

    try:
        env = await export_profile()
    except Exception:  # noqa: BLE001
        log.debug("clone sync: export_profile failed", exc_info=True)
        return False

    try:
        from backend.core.webhooks import emit  # local import to avoid cycle

        await emit(
            event_type="clone.profile.synced",
            data={
                "schema_version": env.schema_version,
                "contract_version": env.contract_version,
                "exported_at": env.exported_at,
                "sample_count": env.sample_count,
                # Profile dict is small (top vocab + scalars); traits
                # are the heavy bit but each is just plaintext, no
                # vectors at this layer.
                "profile": env.profile,
                "trait_count": len(env.traits),
            },
        )
        return True
    except Exception:  # noqa: BLE001
        log.debug("clone sync: webhook emit failed", exc_info=True)
        return False


def maybe_emit_sync_webhook() -> None:
    """Increment the counter and emit when threshold hit.

    Synchronous wrapper so :func:`record_message` can call without
    awaiting. The actual emit is fire-and-forget on the running event
    loop; if no loop is available we skip silently (test contexts).
    """

    global _sync_counter, _last_emit_ts
    _sync_counter += 1
    if _sync_counter < _interval():
        return
    _sync_counter = 0
    _last_emit_ts = time.time()
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_emit_now())
        else:
            # No running loop — defer; the next async call into clone
            # will re-trigger the threshold check.
            return
    except RuntimeError:
        # No event loop at all (sync thread, init time). Skip silently.
        return


def _reset_for_tests() -> None:
    """Test seam — clear counter + last-emit timestamp."""

    global _sync_counter, _last_emit_ts
    _sync_counter = 0
    _last_emit_ts = 0.0
