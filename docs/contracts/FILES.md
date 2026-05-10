# Files contract — Wave 102

The `/api/files` surface is a thread-agnostic browser on top of the
existing `backend.core.attachments` ingest pipeline. It does not
replace the per-thread `/api/chat/threads/{id}/attachments` endpoints;
it sits next to them and exposes the same rows under a richer
filter / tag / category / search envelope.

The router lives at `web_extras/routers/files.py` and is mounted
under the standard `include_router` block in `web_extras/app.py`.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET    | `/api/files`                  | List with filters + sort + pagination + FTS5 search |
| GET    | `/api/files/stats`            | Aggregate counts + sizes |
| GET    | `/api/files/categories`       | Standard catalogue |
| GET    | `/api/files/{id}`             | Single file metadata + chunk preview |
| GET    | `/api/files/{id}/download`    | Raw bytes (FileResponse, 410 on bytes_missing/deleted) |
| POST   | `/api/files/upload`           | Multipart, **multiple files per request** |
| PATCH  | `/api/files/{id}`             | Patch tags / category / pinned / filename |
| DELETE | `/api/files/{id}`             | Soft-delete (HIL gated) |
| POST   | `/api/files/{id}/restore`     | Undo soft-delete |
| POST   | `/api/files/bulk-tag`         | `{ids, tags, operation: add\|remove\|replace}` |
| POST   | `/api/files/bulk-categorize`  | `{ids, category}` |
| POST   | `/api/files/bulk-delete`      | `{ids, reason}` (HIL gated, skips pinned) |
| POST   | `/api/files/auto-categorize`  | LLM/heuristic classifier |

### `GET /api/files` query params

- `category` — restrict to a single slug (standard or custom).
- `tag` — single tag membership probe (JSON LIKE-based).
- `pinned` — boolean.
- `since` / `until` — POSIX seconds against `created_at`.
- `thread_id` — restrict to one chat thread.
- `include_deleted` — surface soft-deleted rows.
- `sort` — `created_desc` (default) / `created_asc` / `size_desc` /
  `size_asc` / `filename_asc` / `filename_desc`.
- `query` — when present, switches to FTS5-ranked branch (sort key
  becomes `relevance`).
- `limit` (1..500, default 100), `offset`.

## Standard categories

Defined in `backend/core/attachments/categories.py`:

- `contracts` — LP agreements, term sheets, MSAs
- `decks` — pitch decks, board updates, all-hands
- `reports` — audit, KPI, monthly memos
- `research` — papers, market data, briefings
- `legal` — privacy, ToS, NDAs, regulatory
- `correspondence` — emails saved as PDF, letters, memos
- `code` — snippets, screenshots, diffs
- `uncategorized` — default

Custom slugs are accepted (≤64 chars). The FE renders custom slugs
in a separate "Custom" group below the standard list.

### Auto-categorize

`POST /api/files/auto-categorize` calls
`backend.core.attachments.categories.auto_categorize`, which:

1. If `TARS_AUTO_CATEGORIZE_ENABLED=1`, asks the council LLM for a
   slug constrained to the standard set.
2. Otherwise (or on any error), falls back to
   `heuristic_category(filename, mime)` — extension + filename
   keyword pass.

Cost-gated by env var so a desktop sidecar doesn't burn tokens.

## Tags model

- Free-form strings, max **32 characters** each.
- Up to **64 tags** per file (server-side dedup).
- Case-insensitive uniqueness (display retains original casing).
- Stored as a JSON array on the `attachments.tags_json` column.

## Bulk operations

| Operation | Body | Verb on file |
| --- | --- | --- |
| `bulk-tag` | `{ids, tags, operation: "add"\|"remove"\|"replace"}` | merge / drop / overwrite |
| `bulk-categorize` | `{ids, category}` | overwrite |
| `bulk-delete` | `{ids, reason}` | soft-delete (skips pinned) |

Bulk endpoints cap at `TARS_FILES_MAX_BULK_IDS` (default 200) ids per
request and return `missing` / `skipped` lists alongside successes.

## HIL gates

- Single `DELETE /api/files/{id}` and bulk `POST /api/files/bulk-delete`
  call `policy_gate.require_confirm(action="file.delete", ...)`. A
  fresh confirm token from `POST /api/wallet/.../confirm` (or the
  cockpit's automatic minting) is required when
  `TARS_REQUIRE_OPERATOR_CONFIRM=1`.
- Pinned files are rejected with `409 file_pinned` in single-delete
  and skipped with reason `pinned` in bulk-delete.

## Upload limits

- `TARS_FILES_MAX_FILE_BYTES` — default `100 * 1024 * 1024` (100 MB)
  per file.
- `TARS_FILES_MAX_BULK_BYTES` — default `1024 * 1024 * 1024` (1 GB)
  cumulative per multipart request.

Per-file failures are reported individually in the response
`errors[]` so the FE can mark just the offending row.

## Storage / privacy

Files are stored under `~/.tars/attachments/<id>/<filename>` on the
operator's disk and indexed in the local SQLite database (same DB
that owns the chat threads). The FE never sees raw paths — only the
proxied `/api/files/{id}/download` URL.

Soft-delete sets `deleted_at` to `time.time()` but keeps bytes on
disk so `restore` is a one-call undo. Permanent delete (via the
existing `DELETE /api/chat/attachments/{id}` endpoint) drops bytes
and chunks.

Cloud sync is opt-in via the vault-encryption flow described in
`docs/contracts/CORE_BRIDGE.md`; the file management surface itself
makes no outbound calls.
