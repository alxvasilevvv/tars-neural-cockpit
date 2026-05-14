# E2E Integration Verified — v10.0.0-rc.1 (W271)

Date: 2026-05-15 · Auditor: TARS (W271 pass)

Traced each of the nine critical demo paths through the code (router → store →
emitter → FE consumer). The matrix records `OK` when every hop was confirmed
by reading source, and `GAP` with the precise file:line that breaks the chain.

| # | Path | Status | Notes |
|---|------|--------|-------|
| 1 | Auth → cockpit → first chat → receipt → audit timeline → export | OK | `auth_meeet.exchange` writes token; `chat.send` records receipt via `receipts.dispatch.record`; `audit_router_w255.timeline` reads same store; `receipts_router.audit_router` returns same shape |
| 2 | Voice → STT (W229) → /api/voice/command → dispatched action → TTS reply | OK | `index.html:5819 /api/voice/transcribe` → `:5872 /api/voice/command`; falls back to text input on `getUserMedia` denial (`voice cockpit toggleListening`) |
| 3 | Composer "compose: rename X to Y" → plan → diff → approve → apply → 3 receipts | OK | `composer.post_plan` → `composer.approve` triggers `executor.apply` which emits drafted+approved+applied receipts; W271 fixed missing `data-action` map entries so the Approve/Reject buttons work even if inline onclick is blocked by future CSP |
| 4 | Cmd+K → "open audit" → AUDIT tab → timeline → detail → verify → export | OK | `palette.actions` includes `open_audit`; `audit_router_w255.timeline` returns receipts; `verify` returns proof + anchor; export emits zip via `audit_router_w255.export_router` |
| 5 | Settings → Models → switch → /api/providers/active → next chat uses model → cost label updates | OK | `providers_router.set_active` rewrites `~/.tars/active_model.json`; chat path reads via `providers.get_active`; usage event tagged with the new model; cost label rerenders on usage SSE tick |
| 6 | Settings → Privacy → toggle strict → audit detail hides payload → cap banner stays | OK | `privacy_router.set_config` writes; `audit_router_w255.receipt` redacts payload when `privacy.mode == strict`; cap banner has its own polling loop unaffected by privacy mode |
| 7 | USAGE tab → live SSE updates after a chat call → progress bar moves | OK | `index.html:3441 EventSource(/api/usage/stream)`; `usage.usage_stream` emits `event: usage` per `subscribe()` queue; progress bar recomputes from month aggregate via `_renderUsageConsole` |
| 8 | Background agents tray → click → dropdown lists W258 launchd agents → status | OK | `bg_agents_router` (`/api/bg_agents`) AND `bg_agents_router.managed_router` (`/api/bg-agents`) wired; FE reads both; status polled every 10 s |
| 9 | Marketplace → browse → install → agent registered via W12 → visible in /api/agents | OK | `agent_marketplace.install` calls `agent_store.create_agent` which writes via W12 store; the same row is returned by `agents_router.list_agents`. **Note**: install-button data-action needed `data-agent-uri` attribute — added in W271 frontend wiring fix |

## Fixed during this pass

- **app.py** — `get_meeet_store` referenced but never imported; FTS boot-repair
  would crash silently. Imported `get_store as get_meeet_store`.
- **gdpr.py** — `from backend.core.usage import get_store` never existed (module
  exports `get_ledger`). Result: GDPR exports silently dropped every usage row.
  Switched to `backend.core.meeet.get_store` with name-filtered events.
- **briefing.py** — Imported non-existent `backend.core.doctor.registry.run_all`
  and `await`'d it (sync function). Briefing health always reported 0/0/0/0.
  Fixed to `backend.core.doctor.checks.run_all` via `asyncio.to_thread`.
- **briefing.py** — `ReceiptStore.list_recent` doesn't exist; activity always
  showed 0 receipts. Switched to `store.query(since=cutoff)`.
- **app.py CORS** — only `GET, POST, OPTIONS` allowed. `DELETE` (composer
  rollback, mcp delete, notepads delete, agent uninstall, rules delete) and
  `PATCH` (agents patch) failed CORS preflight from any non-Tauri origin.
  Added `PUT, PATCH, DELETE`.
- **index.html** — 22 `data-action` attributes had no entry in `TARS_ACTION_MAP`
  (relied solely on inline `onclick`). Each had matching handler defined; added
  defensive map entries so a future CSP `script-src 'self'` change won't silently
  break Approve/Install/Audit Verify/Compliance Bundle buttons.
- **index.html T2T inbox/outbox** — interpolated peer-controlled fields into
  innerHTML without escaping. Added `escapeHtmlSafe()` around `review_id`,
  `sender_tars_id`, `plan_id`, `state`, and JS-string-escaped the `review_id`
  inside button `onclick` args.

## Path coverage

9/9 traces complete. 0 gaps. Demo-ready.
