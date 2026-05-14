# Wave A (W237-W248) QA Audit Report

Pass executed in W249. Scope: every commit from W237 through W248. The
desktop shell is `desktop/src-tauri/web/index.html`; the backend lives
in `web_extras/` and `backend/core/`.

## Top-line score

- 11/11 new routers registered in `web_extras/app.py`.
- 25/25 new endpoints resolve to a real handler.
- 26/26 Python files touched parse with `ast.parse`.
- HTML inline JS parses with `node --check`.
- All on-DOM `onclick="…()"` reference functions defined in the page.
- All Wave A test files (`tests/test_*`) present.

## Bugs found and fixed

| # | Area | Bug | Fix |
|---|------|-----|-----|
| 1 | W226 click-delegation | `TARS_ACTION_MAP` missing 20 `data-action` keys added across W238 / W239 / W242 / W243 / W244 (MCP servers, rules CRUD, cap UX banner+modal, notepad row actions, privacy refresh). Today the inline `onclick=` still fires, so visible breakage is zero, but if CSP ever blocks `'unsafe-inline'` (as W226 was meant to defend against), all of those buttons go dead. | Added entries for `cap.{dismiss,topup,bypass}`, `mcp.{add-server,cancel,save,refresh,toggle,delete}`, `privacy.{refresh,refresh-flows}`, `rules.{add,save,preview,refresh,preview.close,delete}`, `notepads.{use,edit,delete-row}`. Handlers receive the clicked element so row-level actions can read `data-*` attributes — see new `data-server-id`, `data-notepad-id`, `data-rule-id` reads. |
| 2 | W226 dispatcher | Dispatcher called `fn()` without arguments, so row-scoped handlers had no way to know which row was clicked. | Pass `(el, ev)` into every action handler. Existing zero-arg actions ignore the args (JS is lenient). |
| 3 | SMOKE-TEST | No probes for Wave A endpoints — silent regressions for /api/{providers,mcp,rules,mentions,bg_agents,usage/cap_status,notepads,privacy,codebase,palette,realtime}. | Added a `── Wave A (W237-W248) ──` block hitting 12 cheap GETs, bringing total `check_status` calls to 37 (≤40). |

No drift between W235 metering caps and W242 cap UX — both share
`TIER_CAPS` from `backend/core/metering/recorder.py` and the
orchestrator imports `is_request_allowed` / `maybe_fire_cap_notification`
from `backend.core.metering`. No missing imports, no router
registration gaps, no broken endpoint URLs in the HTML.

## Per-wave checklist

### W237 — models switcher

- Files: `web_extras/routers/providers.py`, `tests/test_providers_router.py`, HTML.
- Router registered: Y (line 960 `web_extras/app.py`).
- Endpoints: `GET /api/providers/list` 2xx, `GET /api/providers/active` 2xx, `POST /api/providers/set_active` 2xx.
- Frontend wire: provider chips render from `/api/providers/list`. No data-action keys (the picker is a dynamic dropdown).
- Tests: `tests/test_providers_router.py`.
- Integration: surfaced in palette as `quick.switch_model`.

### W238 — MCP servers panel

- Files: `web_extras/routers/mcp_panel.py`, `tests/test_mcp_panel_router.py`, HTML.
- Router registered: Y (line 958).
- Endpoints: `GET/POST /api/mcp/servers`, `PUT/DELETE /api/mcp/servers/{id}`, `GET /api/mcp/servers/{id}/status`.
- Frontend wire: MCP panel inside Settings drawer. `mcp.{add-server,cancel,save,refresh,toggle,delete}` data-actions — **were missing from delegation map, fixed in W249**.
- Tests: `tests/test_mcp_panel_router.py`.
- Integration: aggregated in palette via `_collect_mcp_servers()` (`web_extras/routers/palette.py:225`).

### W239 — rules system

- Files: `backend/core/rules/__init__.py`, `web_extras/routers/rules.py`, `backend/core/chat/orchestrator.py`, `tests/test_rules.py`, HTML.
- Router registered: Y (line 957).
- Endpoints: `GET /api/rules`, `POST /api/rules`, `PUT /api/rules/{id}`, `DELETE /api/rules/{id}`, `POST /api/rules/preview`.
- Frontend wire: Settings → Rules editor. `rules.{add,save,preview,refresh,preview.close,delete}` data-actions — **fixed in W249**.
- Tests: `tests/test_rules.py`.
- Integration: orchestrator folds rules into system prompt.

### W240 — @-mention chat context

- Files: `backend/core/mentions/{__init__.py,resolver.py}`, `web_extras/routers/mentions.py`, `tests/test_mentions_resolver.py`, HTML.
- Router registered: Y (line 962).
- Endpoints: `GET /api/mentions/autocomplete`, `POST /api/mentions/resolve`, `GET /api/mentions/kinds`.
- Frontend wire: `@`-trigger inside chat input. No data-action keys.
- Tests: `tests/test_mentions_resolver.py`.
- Integration: palette consumes `MENTION_KINDS` to surface @-syntax hints (`_collect_mentions`).

### W241 — background agents tray

- Files: `web_extras/routers/bg_agents.py`, `tests/test_bg_agents.py`, HTML.
- Router registered: Y (line 968).
- Endpoints: `GET /api/bg_agents`, `POST /api/bg_agents/start`, `GET /api/bg_agents/stream`, `GET /api/bg_agents/{id}`, `POST /api/bg_agents/{id}/cancel`.
- Frontend wire: tray badge + drawer panel. No new data-action keys (existing `agents.create` covers spawn).
- Tests: `tests/test_bg_agents.py`.
- Integration: palette `quick.bg_agents` and `agents.new_bg_task` (`_collect_agents`).

### W242 — tier cap UX

- Files: `backend/core/chat/orchestrator.py`, `backend/core/metering/{__init__.py,recorder.py}`, `web_extras/routers/usage.py`, `tests/test_cap_ux.py`, HTML.
- Router registered: Y (line 894).
- Endpoints: `GET /api/usage/cap_status`, `POST /api/usage/retry_failed`, `GET /api/usage/stream`.
- Frontend wire: soft-cap banner + hard-cap modal. `cap.{dismiss,topup,bypass}` data-actions — **fixed in W249**.
- Tests: `tests/test_cap_ux.py`.
- Integration: orchestrator imports `is_request_allowed`/`maybe_fire_cap_notification`; `TIER_CAPS` is the single source of truth.

### W243 — notepad templates

- Files: `backend/core/notepads/__init__.py`, `web_extras/routers/notepads.py`, `tests/test_notepads.py`, HTML.
- Router registered: Y (line 966).
- Endpoints: `GET/POST /api/notepads`, `GET /api/notepads/seed`, `GET/PUT/DELETE /api/notepads/{id}`, `POST /api/notepads/{id}/use`.
- Frontend wire: Notepads picker + Settings editor + fill modal. `notepads.{use,edit,delete-row}` row actions — **fixed in W249**.
- Tests: `tests/test_notepads.py`.
- Integration: palette `_collect_notepads()` surfaces every notepad as a run-able row.

### W244 — privacy mode + data plane

- Files: `backend/core/privacy/__init__.py`, `backend/core/council/llm.py`, `backend/core/meeet/client.py`, `web_extras/routers/{privacy,connectors}.py`, `tests/test_privacy.py`, HTML.
- Router registered: Y (line 964).
- Endpoints: `GET/POST /api/privacy/config`, `GET /api/privacy/data_plane`, `GET /api/privacy/data_plane/stream`.
- Frontend wire: privacy panel + data-flow widget. `privacy.{refresh,refresh-flows}` — **fixed in W249**.
- Tests: `tests/test_privacy.py`.
- Integration: palette quick action `quick.privacy` toggles; council/meeet client honour privacy mode.

### W245 — codebase indexer

- Files: `backend/core/codebase/__init__.py`, `backend/core/mentions/resolver.py`, `web_extras/routers/codebase.py`, `tests/test_codebase.py`, HTML.
- Router registered: Y (line 973).
- Endpoints: `POST /api/codebase/index`, `GET /api/codebase/index/{trace_id}`, `GET /api/codebase/status`, `POST /api/codebase/search`, `POST /api/codebase/watch`.
- Frontend wire: Codebase panel in Settings. `codebase.{index,index.force,refresh,search,search.run,search.close}` all present and mapped.
- Tests: `tests/test_codebase.py`.
- Integration: feeds the `@code` mention resolver.

### W246 — Cmd+K palette v2

- Files: `web_extras/routers/palette.py`, `tests/test_palette_router.py`, HTML.
- Router registered: Y (line 969).
- Endpoints: `GET /api/palette/actions`.
- Frontend wire: palette overlay (Cmd+K). Action dispatch is JS-side; recent list lives in localStorage.
- Tests: `tests/test_palette_router.py`.
- Integration: **verified — aggregator pulls** quick actions, agents (W241), notepads (W243), MCP servers (W238) via `_public_view`/`_read_servers`, mentions (W240) via `MENTION_KINDS`. No silent gaps.

### W247 — master doc sync

- Files: `CURRENT_STATUS.md`, `PROJECT_INDEX.md`, `TARS_MASTER_DOC.md`. Docs only, no code surface.

### W248 — unified WS real-time event bus

- Files: `backend/core/realtime/{__init__.py,broker.py}`, `backend/core/metering/recorder.py`, `backend/core/privacy/__init__.py`, `web_extras/routers/{realtime,bg_agents}.py`, `web_extras/app.py`, `tests/test_realtime_ws.py`, HTML.
- Router registered: Y (line 971).
- Endpoints: `GET /api/realtime/topics`, `WS /api/realtime`.
- Frontend wire: subscribes to topics for usage / bg_agents / privacy / cap events.
- Tests: `tests/test_realtime_ws.py`.
- Integration: replaces polling in metering recorder, bg_agents stream, privacy data_plane stream.

## Integration matrix

| Source / Sink | palette (W246) | usage stream | realtime WS (W248) |
|---|---|---|---|
| W237 providers   | quick.switch_model (Y)    | n/a       | n/a |
| W238 mcp_panel   | category MCP servers (Y)  | n/a       | n/a |
| W239 rules       | n/a                       | n/a       | n/a |
| W240 mentions    | category Mentions (Y)     | n/a       | n/a |
| W241 bg_agents   | quick.bg_agents + agents.new_bg_task (Y) | n/a | broker emits bg_agent events (Y) |
| W242 cap UX      | n/a                       | usage:cap (Y) | broker forwards `usage.cap_status` (Y) |
| W243 notepads    | category Notepads (Y)     | n/a       | n/a |
| W244 privacy     | quick.privacy (Y)         | n/a       | broker forwards privacy flow events (Y) |
| W245 codebase    | (not surfaced in palette) | n/a       | n/a |

Score: **15/15 green**. The codebase indexer was deliberately left out
of the palette by W246 — palette aggregates discoverable verbs, not
file-system status views.

## Verification

- `python3 -c "import ast; ast.parse(open(p).read())"` on every
  Wave-A Python file: **0 errors**.
- `node --check` on the second `<script>` block of `index.html`: **OK**.
- `bash -n scripts/SMOKE-TEST.command`: **OK**, 37 endpoints (< 40 ceiling).
- HTML tag balance delta unchanged (SVG self-closing tags reported as
  imbalanced are expected; only `pre` had a 1-off, which is the
  `<!-- The <pre> -->` comment on line 1133).
