# Contract — `unified_funnel` cross-domain telemetry

> **Status:** SPEC v1.
> **Owner of execution:** Lovable / Claude (`meeet.world` Supabase + `/admin/telemetry`).
> **Owner of spec:** Cursor / TARS (event emit side).
> **Resolves:** TARS#8 task 3a.

This document gives Lovable a drop-in spec for the **unified meeet ↔ tars
funnel** asked for in the May 2 deadline batch. Cursor already emits
the TARS half (`tars_event_ingest` table on the TARS Supabase project
`hhpaukjobskcwkxbgecl`) — Lovable owns the meeet half (`meeet_events`
or whatever the canonical name is on Lovable's project) and the
`/admin/telemetry` dashboard.

Both event streams already share the **same `trace_id` discipline**
(every `tars.*` event carries `trace_id`; meeet middleware should mint
or echo the same when relaying through `core-bridge/relay-event`).
That trace id is the join key.

---

## 1. Source tables

### 1.1 TARS half — `public.tars_event_ingest` (TARS Supabase)

Already populated by:
- **Historical / Pages:** `tars.page.viewed` and `tars.client.error` were emitted
  from the retired in-repo SPA (`functions/_middleware.ts`, `src/lib/clientError.ts`).
  A live `tars.meeet.world` may still run that code from a **prior deploy** or
  out-of-tree fork — Lovable/ops should confirm which bundle is in production.
- `backend/core/meeet/` (Python) → every API / Tauri action and server-side trace.

```sql
-- Schema (read-only reference; managed by migration
-- 20260430094500_tars_event_ingest.sql).
create table public.tars_event_ingest (
  id                uuid primary key default gen_random_uuid(),
  kind              text not null,                -- e.g. tars.page.viewed
  trace_id          uuid,                         -- THE join key
  session_id        text,                         -- tars_session_id cookie
  operator_id       uuid,                         -- meeet_session.user_id when known
  contract_version  text not null default '1.0.0',
  source            text not null,                -- e.g. tars.meeet.world/edge
  payload           jsonb not null default '{}',
  created_at        timestamptz not null default now()
);

create index on public.tars_event_ingest (created_at desc);
create index on public.tars_event_ingest (trace_id);
create index on public.tars_event_ingest (operator_id);
create index on public.tars_event_ingest (kind, created_at desc);
```

### 1.2 Meeet half — `public.meeet_events` (Lovable Supabase)

Lovable to confirm the exact name. Required minimum shape (rename
columns as needed and adjust the view in §2):

| Column        | Type        | Notes                                        |
|---------------|-------------|----------------------------------------------|
| `id`          | uuid PK     |                                              |
| `kind`        | text        | e.g. `meeet.page.viewed`, `meeet.payment.ok` |
| `trace_id`    | uuid        | **must match** `tars_event_ingest.trace_id`  |
| `session_id`  | text        | meeet's own session cookie value             |
| `operator_id` | uuid        | `meeet_session.user_id`                      |
| `payload`     | jsonb       |                                              |
| `created_at`  | timestamptz |                                              |

**Trace id contract:** when a meeet.world page links out to
`tars.meeet.world`, the meeet middleware must put the originating
`trace_id` on the outbound URL or in a header (`x-trace-id`) so the
TARS edge picks it up. The TARS edge already echoes `X-Tars-Trace-Id`
on every response and persists it in `tars_event_ingest.trace_id`
(see `_middleware.ts:108`).

---

## 2. The `unified_funnel` view

Lovable's Supabase project hosts the join because the dashboard reads
from it. TARS exposes `tars_event_ingest` via a foreign-data-wrapper
(or a postgres_fdw, or a one-way logical replication slot — pick what
matches the existing meeet ingest plumbing).

```sql
-- Materialised view for fast dashboard reads.
create materialized view public.unified_funnel as
select
  coalesce(t.trace_id, m.trace_id)                      as trace_id,
  coalesce(t.operator_id, m.operator_id)                as operator_id,
  coalesce(m.session_id, t.session_id)                  as session_id,
  m.kind                                                as meeet_kind,
  t.kind                                                as tars_kind,
  m.created_at                                          as meeet_ts,
  t.created_at                                          as tars_ts,
  -- Surface common funnel hops as boolean columns so the dashboard
  -- can render funnel stages without re-parsing `kind`.
  bool_or(m.kind = 'meeet.page.viewed')                 as saw_meeet_page,
  bool_or(t.kind = 'tars.page.viewed')                  as saw_tars_page,
  bool_or(t.kind like 'tars.click.install_%')           as clicked_install,
  bool_or(t.kind like 'tars.click.download_%')          as clicked_download,
  bool_or(t.kind = 'tars.install.dmg.opened')           as opened_installer,
  bool_or(t.kind = 'tars.cockpit.first_action')         as activated_cockpit,
  count(distinct t.id)                                  as tars_event_count,
  count(distinct m.id)                                  as meeet_event_count
from public.meeet_events m
full outer join public.tars_event_ingest t
  on t.trace_id = m.trace_id
group by 1, 2, 3, 4, 5, 6, 7
with no data;

-- Refresh policy: cron every 60 seconds (cheap on full outer join
-- when both tables are indexed on trace_id).
create unique index on public.unified_funnel (trace_id, meeet_kind, tars_kind);

select cron.schedule(
  'refresh_unified_funnel',
  '*/1 * * * *',
  $$ refresh materialized view concurrently public.unified_funnel; $$
);
```

**RLS:** the view is admin-only. Add an explicit policy that only
Lovable service-role tokens can `select` it.

---

## 3. Common queries

### 3.1 Cross-domain conversion funnel

```sql
select
  count(*)                                              as total_journeys,
  count(*) filter (where saw_meeet_page)                as meeet_landings,
  count(*) filter (where saw_tars_page)                 as tars_landings,
  count(*) filter (where clicked_install)               as install_clicks,
  count(*) filter (where opened_installer)              as installs_opened,
  count(*) filter (where activated_cockpit)             as activations
from public.unified_funnel
where coalesce(meeet_ts, tars_ts) > now() - interval '7 days';
```

### 3.2 Top drop-off points (yesterday)

```sql
with funnel as (
  select
    sum(case when saw_meeet_page then 1 else 0 end)        as a,
    sum(case when saw_tars_page  then 1 else 0 end)        as b,
    sum(case when clicked_install then 1 else 0 end)       as c,
    sum(case when opened_installer then 1 else 0 end)      as d,
    sum(case when activated_cockpit then 1 else 0 end)     as e
  from public.unified_funnel
  where coalesce(meeet_ts, tars_ts) >= current_date - 1
    and coalesce(meeet_ts, tars_ts) <  current_date
)
select
  100.0 * (a - b) / nullif(a, 0) as drop_meeet_to_tars,
  100.0 * (b - c) / nullif(b, 0) as drop_tars_to_install_click,
  100.0 * (c - d) / nullif(c, 0) as drop_install_click_to_open,
  100.0 * (d - e) / nullif(d, 0) as drop_open_to_activation
from funnel;
```

### 3.3 One operator's full journey

```sql
select kind, ts, source, payload
from (
  select tars_kind  as kind, tars_ts  as ts, 'tars'  as source, payload from /* unnest */ ...
  union all
  select meeet_kind as kind, meeet_ts as ts, 'meeet' as source, payload from /* unnest */ ...
) j
where operator_id = '<uuid>'
order by ts;
```

(For the join above prefer querying the source tables directly —
materialised views aggregate, so single-trace replay needs the raw
streams.)

---

## 4. `/admin/telemetry` API contract (Lovable → frontend)

```http
GET /api/admin/telemetry/summary?range=7d
Authorization: Bearer <admin_token>

200 OK
content-type: application/json
{
  "ok": true,
  "contract_version": "1.0.0",
  "range": "7d",
  "funnel": {
    "meeet_landings":   12453,
    "tars_landings":     8821,
    "install_clicks":    1207,
    "installs_opened":    644,
    "activations":        389
  },
  "drop_off_pct": {
    "meeet_to_tars": 29.2,
    "tars_to_install_click": 86.3,
    "install_click_to_open": 46.6,
    "open_to_activation":    39.6
  },
  "by_country": [
    { "country": "US", "tars_landings": 3211, "activations": 187 },
    ...
  ],
  "by_referer_top": [
    { "referer": "twitter.com", "count": 1422 },
    ...
  ],
  "as_of": "2026-05-01T07:30:00Z"
}
```

### 4.1 Minimal React page contract

```tsx
// meeet.world/src/pages/AdminTelemetry.tsx (Lovable repo)
export default function AdminTelemetry() {
  const { data } = useQuery({
    queryKey: ["admin-telemetry", "7d"],
    queryFn: () => fetch("/api/admin/telemetry/summary?range=7d").then((r) => r.json()),
    refetchInterval: 60_000, // matches the materialised view cron cadence
  });

  if (!data?.ok) return <SkeletonFunnel />;
  return (
    <PageShell title="Cross-domain funnel" range="last 7 days">
      <FunnelChart steps={[
        { label: "meeet.world",   value: data.funnel.meeet_landings },
        { label: "tars.meeet.world", value: data.funnel.tars_landings },
        { label: "install click", value: data.funnel.install_clicks },
        { label: "installer opened", value: data.funnel.installs_opened },
        { label: "first cockpit action", value: data.funnel.activations },
      ]} />
      <DropOffTable pct={data.drop_off_pct} />
      <CountryHeatmap rows={data.by_country} />
      <RefererTopTable rows={data.by_referer_top} />
    </PageShell>
  );
}
```

---

## 5. Acceptance criteria (Lovable side)

1. `meeet_events` table exists and is populated from meeet middleware
   with `trace_id` matching the value put on the outbound URL when a
   visitor crosses to `tars.meeet.world`.
2. `unified_funnel` materialised view exists and refreshes every
   minute (or shorter) without error.
3. `/api/admin/telemetry/summary` returns the JSON shape in §4 with
   `contract_version: "1.0.0"`.
4. Dashboard page renders five-stage funnel + drop-off table.
5. The `as_of` timestamp on the response matches the most recent
   materialised-view refresh ±60s.

When all five gates are green, mark TARS#8 task 3a closed in the
URGENT comment and ping Cursor — we'll add a synthetic-monitor probe
on the summary endpoint so regressions get caught within 60s.

---

## 6. Cursor-side guarantees (no further changes needed)

- Every TARS event already carries `trace_id`, `session_id`,
  `contract_version` (`1.0.0`), and `source`. Schema pinned by
  `tests/test_meeet_contract_v11.py` + the meeet bridge contract test
  suite.
- Edge middleware echoes `X-Tars-Trace-Id` on every response so
  Lovable can read it client-side and forward it on subsequent calls
  back to meeet.
- Cookie `tars_session_id` is `Domain=.meeet.world` so meeet's session
  cookie can be linked via existing `POST meeet-app/api/sessions/link`
  (see `TARS_SUBDOMAIN.md` §5.2).
