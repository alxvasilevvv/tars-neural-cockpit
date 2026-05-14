"""backend/core/onprem/pg_migrations.py — W263.

Postgres schema parity with the ~21 SQLite stores listed in
docs/DB_AUDIT_v9.2.md, plus Alembic-style versioned migrations.

Why this exists. On the desktop .app path TARS uses sqlite per concern
(receipts, codebase, tasks, notepad, memory, etc). For self-hosted
multi-user deployments the operator wants:

  - one DB endpoint, not 21 files
  - real concurrent writes
  - point-in-time restore
  - replica / read-only standby support

So on-prem runs the same code against Postgres. The schema in this
module mirrors what each SQLite store carries (table names, column
types are aligned; we use BIGSERIAL where sqlite used INTEGER PK auto-
increment, JSONB where sqlite used TEXT-json, TIMESTAMPTZ where sqlite
used INTEGER unix-epoch).

Execution model. The entrypoint of the backend container runs:

    python -m backend.core.onprem.pg_migrations && exec uvicorn ...

so every container boot is a no-op when the schema is already current,
and a forward-migrate when a new release adds tables. We do NOT auto-
drop tables ever — destructive migrations are a manual operator step
behind ONPREM_ALLOW_DROP=1.

Versioning. Each migration is a dict {id, sql, rolled_at_unix?}. The
`_meta` table tracks which ones have applied. Adding a new migration:

    MIGRATIONS.append({
        "id": "20260601_add_workspaces_foo",
        "sql": '''ALTER TABLE workspaces ADD COLUMN foo TEXT;''',
    })

Idempotent. Safe to invoke against an already-migrated DB.

Smoke test path (no Postgres locally): pass --dry-run to print the SQL
that would be executed without opening a connection.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from typing import Any

log = logging.getLogger("tars.onprem.pg")


# ────────────────────────────────────────────────────────────────────
# Schema (initial + per-feature increments)
# ────────────────────────────────────────────────────────────────────

MIGRATIONS: list[dict[str, Any]] = [
    {
        "id": "20260514_initial_schema",
        "sql": """
        -- _meta tracks every applied migration; idempotency hinges on this.
        CREATE TABLE IF NOT EXISTS _meta (
            id TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        -- ── Users + sessions (replaces ~/.tars/onprem_users.sqlite) ────
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            tier TEXT NOT NULL DEFAULT 'business',
            pw_hash TEXT,
            external_id TEXT,            -- IdP sub claim (OIDC) or SAML nameID
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS users_external_id_idx ON users(external_id);

        CREATE TABLE IF NOT EXISTS sessions (
            jti TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ NOT NULL,
            revoked_at TIMESTAMPTZ,
            user_agent TEXT
        );

        CREATE TABLE IF NOT EXISTS bootstrap (
            token TEXT PRIMARY KEY,
            burned_at TIMESTAMPTZ
        );

        -- ── Receipts (replaces ~/.tars/receipts.sqlite + ndjson) ──────
        -- Per-event ed25519 signed receipts; hash-chained.
        CREATE TABLE IF NOT EXISTS receipts (
            id BIGSERIAL PRIMARY KEY,
            receipt_id TEXT UNIQUE NOT NULL,
            ts TIMESTAMPTZ NOT NULL DEFAULT now(),
            user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            action TEXT NOT NULL,
            payload JSONB NOT NULL,
            prev_hash TEXT,
            hash TEXT NOT NULL,
            sig TEXT NOT NULL,
            day_bucket DATE NOT NULL
        );
        CREATE INDEX IF NOT EXISTS receipts_day_bucket_idx ON receipts(day_bucket);
        CREATE INDEX IF NOT EXISTS receipts_user_idx ON receipts(user_id);
        CREATE INDEX IF NOT EXISTS receipts_action_idx ON receipts(action);

        CREATE TABLE IF NOT EXISTS receipts_merkle (
            day_bucket DATE PRIMARY KEY,
            merkle_root TEXT NOT NULL,
            receipt_count INTEGER NOT NULL,
            anchored_at TIMESTAMPTZ,
            anchor_tx TEXT          -- Solana memo signature, when anchored
        );

        -- ── Usage / metering (W235) ─────────────────────────────────
        CREATE TABLE IF NOT EXISTS usage_events (
            id BIGSERIAL PRIMARY KEY,
            ts TIMESTAMPTZ NOT NULL DEFAULT now(),
            user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            kind TEXT NOT NULL,         -- 'usage.tokens' | 'usage.action' | ...
            action TEXT,
            model TEXT,
            tokens_in INTEGER,
            tokens_out INTEGER,
            cost_usd NUMERIC(12, 6),
            meta JSONB NOT NULL DEFAULT '{}'::jsonb
        );
        CREATE INDEX IF NOT EXISTS usage_events_ts_idx ON usage_events(ts);
        CREATE INDEX IF NOT EXISTS usage_events_user_idx ON usage_events(user_id);

        -- ── Tasks / background agents (W241) ────────────────────────
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            status TEXT NOT NULL,        -- pending | running | done | cancelled | error
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            progress REAL DEFAULT 0,
            meta JSONB NOT NULL DEFAULT '{}'::jsonb
        );
        CREATE INDEX IF NOT EXISTS tasks_user_status_idx ON tasks(user_id, status);

        -- ── Notepad (W243) — templates and runs ─────────────────────
        CREATE TABLE IF NOT EXISTS notepad_templates (
            slug TEXT PRIMARY KEY,
            user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            variables JSONB NOT NULL DEFAULT '[]'::jsonb,
            visibility TEXT NOT NULL DEFAULT 'private',  -- private | shared
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        -- ── Memory (W133 / Iter C) ──────────────────────────────────
        CREATE TABLE IF NOT EXISTS memory_items (
            id BIGSERIAL PRIMARY KEY,
            user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            key TEXT,
            value JSONB NOT NULL,
            tags TEXT[],
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS memory_user_kind_idx ON memory_items(user_id, kind);

        -- ── Codebase indexer (W245) — symbols + chunks ──────────────
        -- The vector column is left TEXT here because pgvector is opt-in
        -- (operator installs the extension; see ONPREM guide). Cast to
        -- vector(384) once extension is present.
        CREATE TABLE IF NOT EXISTS codebase_files (
            id BIGSERIAL PRIMARY KEY,
            user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            path TEXT NOT NULL,
            sha TEXT NOT NULL,
            language TEXT,
            last_indexed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS codebase_files_user_path_idx
            ON codebase_files(user_id, path);

        CREATE TABLE IF NOT EXISTS codebase_symbols (
            id BIGSERIAL PRIMARY KEY,
            file_id BIGINT REFERENCES codebase_files(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,           -- function | class | const | type | ...
            line_start INTEGER NOT NULL,
            line_end INTEGER NOT NULL,
            embedding TEXT                -- pgvector at runtime
        );
        CREATE INDEX IF NOT EXISTS codebase_symbols_name_idx ON codebase_symbols(name);

        -- ── Cowork (W129 / W149) ────────────────────────────────────
        CREATE TABLE IF NOT EXISTS cowork_sessions (
            id TEXT PRIMARY KEY,
            owner_user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            title TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            closed_at TIMESTAMPTZ
        );

        CREATE TABLE IF NOT EXISTS cowork_presence (
            session_id TEXT REFERENCES cowork_sessions(id) ON DELETE CASCADE,
            user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (session_id, user_id)
        );

        -- ── Compliance export (W104) ────────────────────────────────
        CREATE TABLE IF NOT EXISTS compliance_exports (
            id TEXT PRIMARY KEY,
            requested_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            range_start TIMESTAMPTZ NOT NULL,
            range_end TIMESTAMPTZ NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            artifact_path TEXT
        );

        -- ── Workspaces (W110) ───────────────────────────────────────
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            tier TEXT NOT NULL DEFAULT 'business',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS workspace_members (
            workspace_id TEXT REFERENCES workspaces(id) ON DELETE CASCADE,
            user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            role TEXT NOT NULL DEFAULT 'member',
            PRIMARY KEY (workspace_id, user_id)
        );
        """,
    },
    {
        "id": "20260514_rules_mentions_clone",
        "sql": """
        -- ── Rules (W239) ────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS rules (
            id TEXT PRIMARY KEY,
            user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            scope TEXT NOT NULL,          -- project | pack:<slug> | default
            yaml_body TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        -- ── @-mentions resolver cache (W240) ────────────────────────
        CREATE TABLE IF NOT EXISTS mention_cache (
            cache_key TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            body TEXT NOT NULL,
            cached_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        -- ── AI Clone (W151 / W195) ──────────────────────────────────
        CREATE TABLE IF NOT EXISTS clone_messages (
            id BIGSERIAL PRIMARY KEY,
            user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            ts TIMESTAMPTZ NOT NULL DEFAULT now(),
            role TEXT NOT NULL,           -- assistant | user
            text TEXT NOT NULL,
            style_hints JSONB NOT NULL DEFAULT '{}'::jsonb
        );
        CREATE INDEX IF NOT EXISTS clone_user_ts_idx ON clone_messages(user_id, ts DESC);
        """,
    },
    {
        "id": "20260515_marketplace_composer",
        "sql": """
        -- ── Agent marketplace (W261) ────────────────────────────────
        CREATE TABLE IF NOT EXISTS marketplace_listings (
            slug TEXT PRIMARY KEY,
            publisher_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            title TEXT NOT NULL,
            description TEXT,
            price_meeet NUMERIC(20, 9),
            rating_avg REAL,
            rating_count INTEGER NOT NULL DEFAULT 0,
            installs INTEGER NOT NULL DEFAULT 0,
            published_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS marketplace_installs (
            user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            slug TEXT REFERENCES marketplace_listings(slug) ON DELETE CASCADE,
            installed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, slug)
        );

        -- ── Composer / voice-first pair programming (W253 / W262) ──
        CREATE TABLE IF NOT EXISTS composer_plans (
            id TEXT PRIMARY KEY,
            user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            title TEXT,
            steps JSONB NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS composer_diffs (
            id BIGSERIAL PRIMARY KEY,
            plan_id TEXT REFERENCES composer_plans(id) ON DELETE CASCADE,
            path TEXT NOT NULL,
            patch TEXT NOT NULL,
            accepted BOOLEAN,
            receipt_id TEXT REFERENCES receipts(receipt_id)
        );
        """,
    },
]


# ────────────────────────────────────────────────────────────────────
# Runner
# ────────────────────────────────────────────────────────────────────

def _db_url() -> str:
    url = os.environ.get("TARS_DB_URL", "").strip()
    if not url:
        raise SystemExit(
            "TARS_DB_URL is empty. Set it in .env.onprem before invoking "
            "pg_migrations. Example: postgresql+psycopg://tars:pass@postgres:5432/tars"
        )
    return url


def _connect():
    """Connect via psycopg3. We deliberately do not pull SQLAlchemy here
    to keep migrations runnable from a thin container."""
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit(
            "psycopg is not installed. Add 'psycopg[binary,pool]>=3.2' to "
            "requirements.txt (already pinned in scripts/ONPREM-DEPLOY/Dockerfile.backend)."
        ) from exc
    # Translate SQLAlchemy URL form back to libpq form if needed.
    url = _db_url().replace("postgresql+psycopg://", "postgresql://", 1)
    return psycopg.connect(url, autocommit=False)


def applied_ids(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS _meta (id TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        conn.commit()
        cur.execute("SELECT id FROM _meta")
        return {row[0] for row in cur.fetchall()}


def run(dry_run: bool = False) -> int:
    """Apply pending migrations. Returns exit code (0 = success)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if dry_run:
        log.info("dry-run — would apply %d migrations", len(MIGRATIONS))
        for m in MIGRATIONS:
            log.info("--- %s ---\n%s", m["id"], m["sql"][:200] + ("..." if len(m["sql"]) > 200 else ""))
        return 0

    try:
        conn = _connect()
    except SystemExit:
        raise
    except Exception as exc:
        log.warning("could not connect (%s); deferring migrations to next boot", exc)
        return 0  # don't crash backend boot — watchdog will retry

    try:
        done = applied_ids(conn)
        applied_now = []
        with conn.cursor() as cur:
            for m in MIGRATIONS:
                if m["id"] in done:
                    continue
                log.info("applying migration: %s", m["id"])
                cur.execute(m["sql"])
                cur.execute("INSERT INTO _meta (id) VALUES (%s)", (m["id"],))
                applied_now.append(m["id"])
            conn.commit()
        if applied_now:
            log.info("migrations applied: %s", ", ".join(applied_now))
        else:
            log.info("schema up-to-date (%d migrations on record)", len(done))
        return 0
    except Exception:
        conn.rollback()
        log.exception("migration failed; rolled back. Backend boot will retry on next start.")
        return 0  # soft-fail so the backend container still comes up
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print SQL without connecting")
    args = parser.parse_args()
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
