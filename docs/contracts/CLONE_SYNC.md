# AI Clone v0.2 — sync envelope contract (Wave 151)

**Module:** `backend/core/clone/sync.py` · **Schema:** v1 · **Contract:** `0.2.0`

Closes the W148 reality-audit gap: Clone v0.1 (style hint, W73)
persists locally to `~/.tars/clone.sqlite` but is lost when the
operator switches machines or wipes the laptop. v0.2 ships
**portability** — not a deeper model.

## Honest framing

- **NOT** a fine-tuned model. The export carries the same v0.1
  heuristic profile + recent traits — same metric set, same
  trigram-bag fallback, same draft path.
- **NOT** automatic restore. A fresh TARS install does not pull
  the envelope automatically; the operator hits the import
  endpoint (or `tars-ops → import`) manually.
- **NOT** real-time. Webhook emits are debounced at 50-message
  intervals (env-tunable). Worst case lag = 50 messages.

## Envelope shape (v1)

```jsonc
{
  "schema_version": 1,
  "contract_version": "0.2.0",
  "exported_at": 1747252800.0,
  "profile": {                            // StyleProfile.to_dict()
    "version": "0.1",
    "sample_count": 124,
    "avg_sentence_length": 14.3,
    "casual_vs_formal": "casual",
    "top_vocab": ["deal", "sync", "ship", ...],
    ...
  },
  "traits": [
    {"id": "st_...", "text": "Hey team, quick sync...", "created_at": 1747251000.0},
    ...                                    // up to _PROFILE_WINDOW (500)
  ],
  "sample_count": 124
}
```

Per-trait shape is intentionally lean — `text` + `created_at` are
the minimum needed to re-seed the local store. The importer
recomputes metrics from text and inserts at the original
`created_at` (preserving the rolling-window ordering).

## Endpoints

### `POST /api/clone/export`

Body: empty. Returns:

```json
{"ok": true, "envelope": <envelope>}
```

The caller hashes + signs the envelope before transmitting. The
server does not sign on export — separation of concerns.

### `POST /api/clone/import`

Body: `{envelope: <envelope>}` *or* the envelope directly.

Returns:

```json
{
  "ok": true,
  "imported": 42,
  "skipped": 3,
  "schema_version": 1,
  "contract_version": "0.2.0"
}
```

Errors:

| Wire | Meaning |
| --- | --- |
| 400 `envelope_required` | body has no envelope dict |
| 400 `envelope_invalid: ...` | shape failed `StyleEnvelope.from_dict` |
| 200 `{ok: false, error: "schema_version_unsupported"}` | envelope schema > 1 (future version) |
| 200 `{ok: false, error: "clone_store_disabled"}` | `CLONE_STORE=disabled` |

Idempotent: re-importing the same envelope dedups by exact `text`
match against the existing store window. Re-import of a populated
store typically reports `imported=0, skipped=N`.

## Webhook sync (debounced)

On every Nth `record_message` call (default N=50, env-tunable via
`TARS_CLONE_SYNC_INTERVAL`), the in-process counter trips and a
fire-and-forget task emits a webhook event:

| Event | Payload |
| --- | --- |
| `clone.profile.synced` | `{schema_version, contract_version, exported_at, sample_count, profile, trait_count}` |

The full envelope (with `traits[]`) is **not** in the webhook —
the trait blob can be heavy (500 messages × ~280 chars).
Consumers that want the full envelope call `POST /api/clone/export`
in response to the webhook.

Failure modes (any of these swallow the emit; never break
`record_message`):

- No running asyncio loop (init/sync-thread context)
- `backend.core.webhooks.emit` raises
- `export_profile` raises

All failures land in the `tars.clone.sync` debug log.

## Schema versioning

- **v1 (this release):** profile dict + traits list + sample_count
- **v2 (future):** add embedding blob (base64 float32) per trait —
  full embedding restore, not just text re-seed
- **v3 (future):** add per-trait metadata (channel, conversation_id)
  for downstream RAG isolation

Bump `ENVELOPE_SCHEMA_VERSION` on every breaking change. Importer
refuses unknown future versions with `schema_version_unsupported`.

## Brother (meeet.world) responsibilities

The meeet.world edge function receives `clone.profile.synced` via
the brother handoff bridge and:

1. Stores the latest envelope-summary under the user's tenant.
2. Exposes `GET /tars/clone/snapshot` to authed clients so the
   tars-ops "Restore from cloud" path can pull it.
3. Holds the full envelope only when the operator opts in
   (Pro tier + explicit `clone.cloud_backup` consent flag).

See `docs/HANDOFF_FOR_BROTHER.md` for the meeet.world side wiring.

## Roadmap

- **v0.2.0 (this release):** envelope + export/import endpoints + debounced webhook
- **v0.2.1 (v9.1.3 target):** include embedding blob in v2 schema
- **v0.3 (v9.2 target):** signed envelope (ed25519, key from vault)
- **v1.0 (v9.3 target):** real fine-tune over the trait corpus (drops the "style hint" caveat)
