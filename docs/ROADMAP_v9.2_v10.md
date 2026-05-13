# TARS — Roadmap v9.2 → v10.0

**Авторство:** оркестрированный аудит (Voice / meeet.world / Agents / Notifications / Marketplace / Frontend-Desktop) — W187.
**Дата:** 2026-05-14.
**База:** TARS v9.1.4 (commit `d73aa1f`, 11 doctor checks все зелёные).
**Назначение:** этот документ — единственная честная карта текущего состояния продукта и плана доработок. Заменяет фрагментированные обещания в WHAT_WORKS / RELEASE_NOTES / HANDOFF.

---

## 0. Executive summary — что реально на руках сейчас

| Домен | Shipped (work) | Stub / Partial | Vaporware (in docs, no code) |
|---|---|---|---|
| **Voice** | STT (Whisper), TTS (ElevenLabs + OpenAI + macOS say), 6 personas, cost ledger, budget gate | Voice intents parser (regex, не LLM) | **Wake-word** (W36, W92, W93 — нет в коде), **narration loop** (нет orchestrator → TTS pipe), **XTTS-v2 cloning** (W39 — registry готов, engine отсутствует), **VAD streaming** (W34 — нет WS endpoint) |
| **meeet.world** | tars-ingest live, tars-billing live (Supabase edge functions, Bearer auth, idempotency), receipts hash-chained локально, OAuth коннекторы (Slack/Gmail/Calendar) — **прямые** к провайдеру, не через meeet | core-bridge endpoint описан в `BRIDGE_SHARED_SECRET` стабах, но не вызывается; AI Clone v0.2 webhook определён, **никем не дёргается**; Solana memo anchor — конфиг есть, dispatch отсутствует | **Magic-link sign-in flow** (HANDOFF §5.5 — нет `/api/magic-link` calls), **meeet.world OAuth broker** (HANDOFF §5.7 — нет `/connect/{provider}` redirects), **shared cookie domain `.meeet.world`**, **pairing flow**, **billing reconciliation от cloud routes** (`/operator/usage` ни разу не зовётся) |
| **Agents** | autopilot loop, runner, smart router, council orchestrator (LocalVoice + MockCloudVoice), Cowork (10 routes, 4 test файла, multiplayer real), MCP server (5 tools, JSON-RPC), AI Clone v0.2 portable export/import | Council 3rd cloud voice — optional, fallback на mock если нет ключа; AI Clone — heuristic profile, no auto-restore | **Supervisor** (W76 — budget cap + rate limit + kill switch + HIL gate — **директории `supervisor/` нет, кода нет**), **Native skills** (W75 — Quest/Stake/Arena/Discovery/Wallet — **директории `skills/` нет**; Wallet частично реален в `wallet/service.py`), **T2T** (W81/86/88/89 — **директории `t2t/` нет**), **legacy agent suite** (browser/code/shell/vision/advisor/builder из v7.1 — не портированы) |
| **Notifications/Daemon** | LaunchAgent + systemd unit + Windows schtasks XML (Windows — mocked-only); 11 doctor checks; 3 fixers (vault auto, daemon/scheduler skip-with-hint); fanout to iMessage + Telegram + Email; auto-fanout on `doctor.status_changed`; `--watch` mode | iMessage — outbound only (poll-read есть, но event-on-incoming нет); Solana memo dispatch отсутствует | Per-severity routing (warn→email, fail→tg, etc.); ack / snooze / escalation; group-chat iMessage; HTML email templates; реальные Windows тесты на железе |
| **Marketplace** | Registry JSON (GitHub-hosted) + 12 seed listings + disk cache; install pipeline (~/.tars/marketplace/installed/); local ratings SQLite; HIL gate на install/uninstall; 8 REST routes; SKILL_SDK.md контракт published | ed25519 signing — **detected**, не verified (`signature_present_unverified_v0`); workshop packs (fund/dao/saas/family-office/quant/algotrade) = текущие "плагины" в seed; нет публичного registry submit pipeline | **70/30 payout** (документировано, не реализовано), **payment processing** (нет интеграции с billing для one-time/subscription), **publisher identity registry**, **review workflow с автоматическим CI**, **SDK CLI tooling** (`tars-sdk` для signing manifests), **central ratings backend** (сейчас local-only) |
| **Frontend / Desktop** | `/api/doctor/page` (vanilla HTML, live) ✓, `/api/doctor/cockpit` (W186, new) ✓, marketing landing + onboarding + install pages в bundled SPA ✓, PWA manifest ✓ | Tauri 2 desktop shell собран; menu bar + tray + global shortcut + deep links (W59-* реальные); но bundled `/cockpit` React route крашится с "operation is insecure" (localStorage в Tauri webview) | Service Worker файл отсутствует в `desktop/src-tauri/web/`; mobile real-device testing; macOS native menu bar items; native file picker; offline last-known-good fallback |

**Главная неравномерность:** инфраструктура (daemon, doctor, webhooks, receipts schema, cowork, MCP, billing client) — серьёзная и реальная. Бизнес-логика верхнего уровня (native skills, T2T, supervisor, voice loop, marketplace payments) — задекларирована в waves, кода нет.

---

## 1. v9.2 — "честная зрелость" (4–6 недель)

**Цель:** закрыть дрифт между waves-документами и кодом. Никаких новых обещаний — только реализовать то, что уже задекларировано.

### Phase L11 — Голосовой контур (1.5 недели)

- **W190** Wake-word detector в кокпите (Picovoice или PocketSphinx wasm, ~1 week)
  - File: `frontend/src/components/voice/WakeWordDetector.{ts,tsx}` (NEW)
  - Pipe в existing `MicLevelDisplay`, эмитит `wakeword.detected` event на 200ms latency
  - Wake phrase configurable: "hey tars", "tars", "okay tars"
- **W191** Narration auto-loop (3 дня)
  - File: `backend/core/orchestrator/runner.py` — после `result = await run_agent(...)` проверить `thread.voice_persona_id`, если задан — call `synthesize(result.text, persona)` и стримить bytes обратно
  - Route: `GET /api/voice/narrate/{thread_id}` — Server-Sent Events стрим
- **W192** VAD + natural pause detection (5 дней)
  - File: `frontend/src/lib/voice/vad.ts` (NEW) — RMS amplitude check каждые 100ms, auto-stop запись на 800ms тишины
  - Замена ручной "done"-кнопки → "просто говори"
- **W193** Honest WHAT_WORKS update (1 час) — пометить старые waves W34/W36/W39/W92 как `partial` или `superseded by W190-W193`

### Phase L12 — meeet.world wiring (1 неделя)

- **W194** Generate + sync `BRIDGE_SHARED_SECRET` (1 час)
  - `openssl rand -hex 32` → TARS `.env` + 3 Supabase secrets (tars-billing, tars-ingest, core-bridge) + GitHub Actions repo secrets
- **W195** Wire AI Clone v0.2 sync webhook (4 часа)
  - File: `backend/core/clone/__init__.py:record_message()` — call `maybe_emit_sync_webhook()` каждые N сообщений (debounced)
  - Endpoint на meeet side: `POST /functions/v1/tars-ingest/clone-sync` (брат на meeet добавляет)
- **W196** Emit first cloud usage event (3 часа)
  - File: `web_extras/routers/voice.py:speak()` — after ElevenLabs/OpenAI call → emit `usage.tokens` через `meeet_billing.client.post_usage()`
  - Verify в meeet billing dashboard что событие пришло, idempotency работает
- **W197** Solana memo dispatch (2 часа)
  - File: `backend/core/receipts/anchor.py` — export `async def anchor_daily_root(store, client)`
  - Scheduler tick раз в день: вычислить Merkle root последних 24h receipts → подписать → отправить как Solana memo на Devnet (live test) или Mainnet
- **W198** Magic-link sign-in flow (3 дня — coordinated с братом)
  - Брат: `POST /api/magic-link` + `GET /auth/tars-claim` + `POST /api/sessions/exchange` на meeet side
  - TARS: `tars://login?token=...` deep link handler (уже есть W59-8) → exchange token via `client.exchange_magic_link(token)` → save session
  - Cookie domain: `.meeet.world` для shared session

### Phase L13 — Supervisor real (1.5 недели)

- **W199** Create `backend/core/supervisor/` (4 дня)
  - `budget.py` — per-user-per-day cap (env: `TARS_BUDGET_USD_DAILY_<tier>`)
  - `rate_limit.py` — per-agent + per-route, token bucket (existing rate-limit hygiene уже есть на endpoint level, нужно поднять на agent level)
  - `hil_gate.py` — promote existing `policy/gate.py` to enforce side_effects markers (local-fs, network-egress, chain-write, paid-egress)
  - `kill_switch.py` — global flag `~/.tars/SUPERVISOR_HALT` → orchestrator runner проверяет каждый tick
- **W200** Wire в `runner.py` (1 день) — каждый task проходит через `supervisor.enforce(task, user)` до execution; на violation эмитит `supervisor.blocked` webhook
- **W201** UI surface — Cockpit Supervisor panel (2 дня): live budget burn, kill switch toggle, HIL inbox, recent blocks

### Phase L14 — Native skills честно (1 неделя)

- **W202** Закрыть legacy claims: пометить Quest / Stake / Arena / Discovery как `roadmap_v9.3` в WHAT_WORKS (1 час)
- **W203** Wallet skill (5 дней) — единственный, у которого реально есть код, доделать до production:
  - SOL balance ✓ (есть), send transaction (новое), spend ledger (новое), per-tx HIL gate (использует W199), receipts hash-chained ✓
  - Tests: `tests/test_wallet_skill.py` — 15+ кейсов

### Phase L15 — Notifications полнота (1 неделя)

- **W204** Per-severity routing (3 часа)
  - File: `backend/core/notifications/__init__.py:fanout_all()` — accept `severity_filter`
  - Env: `TARS_NOTIFY_ROUTE_WARN=email`, `TARS_NOTIFY_ROUTE_FAIL=telegram,imessage`
  - Cockpit picker UI в Status page
- **W205** Ack/snooze (5 часов)
  - File: `backend/core/doctor/__init__.py` — `CheckResult` gains optional `ack_id`
  - State: `~/.tars/doctor.acks.sqlite` (acked_at, snooze_until per change_id)
  - fanout_all skip changes acked + not expired
  - Cockpit: ack/snooze buttons на каждом WARN row
- **W206** Escalation tick (2 часа) — daemon tick каждый hour проверяет `snooze_until < now()` для unacked → re-fanout
- **W207** iMessage watch-mode (4 часа)
  - File: `backend/core/notifications/imessage.py` — `watch_inbox()` polling каждые N секунд
  - Emit `imessage.incoming` webhook на new unread (replies к нашим алертам)

### Phase L16 — Frontend hotfix (1 неделя)

- **W208** Восстановить frontend source (1 день) — или из backup/другой ветки, или reverse-engineer из bundled `desktop/src-tauri/web/assets/Cockpit-*.js`
- **W209** Fix localStorage bug в `/cockpit` route (1 день)
  - Replace localStorage hydration с sessionStorage (доступен в Tauri webview) или fetch from `/api/memory/`
  - Gate: `if (typeof window !== 'undefined' && window.localStorage) { ... }` + fallback
- **W210** Rebuild + sign `.dmg` (1 день — требует Apple cert у брата)
  - `pnpm cockpit:package && pnpm preflight:release && pnpm tauri:build`
  - Reinstall TARS.app, верифицировать `/cockpit` рендерится
- **W211** Service Worker offline precache (2 дня)
  - File: `desktop/src-tauri/web/sw.js` (NEW) — cache app shell + `/api/doctor/cockpit` fallback
  - Mobile PWA install flow: тест на 375px viewport

### v9.2 готовность

После Phase L16 — `RELEASE_NOTES_v9.2.0.md`, tag `v9.2.0`, push, sign DMG, distribute через tars.meeet.world download proxy.

**Чёткий критерий релиза v9.2:**
- Voice: wake-word → STT → council reply → TTS narration в одну петлю работает на демо
- meeet: первый `usage.tokens` event приходит на meeet billing dashboard, BRIDGE_SHARED_SECRET unified
- Agents: supervisor budget/HIL gate реально режет run на превышении
- Notifications: ack/snooze работает, per-severity routing настроен
- Desktop: `.dmg` устанавливается, `/cockpit` рендерится без ошибок

---

## 2. v9.3 — "marketplace + agents real" (6–8 недель)

**Цель:** запустить публичный marketplace и завершить agent layer.

### Phase M1 — Real plugin marketplace (3 недели)

- **W220** ed25519 signature verification real (5 дней)
  - Public key distribution: bundled trusted-publishers list + meeet.world relayer для community keys
  - Refuse install если signature invalid (configurable: `TARS_MARKETPLACE_REQUIRE_SIGNED=1`)
- **W221** Publisher identity registry (5 дней)
  - meeet.world side: `POST /api/marketplace/publishers/register` — display_name + email + payout wallet + Ed25519 pubkey
  - TARS: GET endpoint для resolving publisher metadata + reputation
- **W222** Payment processing (5 дней)
  - Wire `price: one_time | subscription` через meeet billing adapter → Stripe (cards) + SOL (anchored to Solana program) + MEEET tokens
  - 70/30 split: weekly batch processor, escrow adapter
  - Refund support: 14-day window, automated на customer support contact
- **W223** SDK CLI tooling (3 дня)
  - `tars-sdk init` — scaffold a plugin
  - `tars-sdk sign manifest.json --key ...` — Ed25519 sign
  - `tars-sdk test` — local install pipeline test
  - `tars-sdk publish` — submit к meeet marketplace registry
- **W224** Plugin discovery UI в Cockpit (4 дня) — browse/search/install/rate
- **W225** Central ratings backend (2 дня) — переход от local SQLite к shared meeet-hosted aggregation

### Phase M2 — T2T (TARS-to-TARS) protocol (2 недели)

- **W230** Discovery — agents находят counterparty через meeet relayer (4 дня)
- **W231** Contract signing — atomic offer/accept с timeout + cancel (3 дня)
- **W232** Escrow — реальный (не mock) через Solana program; off-chain settlement для in-pack actions (5 дней)
- **W233** Frontend T2T deal flow page (2 дня)

### Phase M3 — Native skills real (3 недели)

- **W240** Quest skill (5 дней) — task tracking + reward анкоринг
- **W241** Stake skill (5 дней) — token locking + slashing rules
- **W242** Arena skill (5 дней) — agent-vs-agent ranked competitions
- **W243** Discovery skill (5 дней) — content surfacing + ranking
- **W244** Wallet skill — multi-token (SOL + MEEET + USDC) + multi-chain stub (5 дней)

### Phase M4 — meeet.world OAuth broker (1.5 недели)

- **W250** Centralized OAuth flow через `meeet.world/connect/{provider}` (3 дня)
- **W251** Delegated token storage в meeet side, TARS получает via session exchange (3 дня)
- **W252** UI обновление коннектор-страницы (2 дня)

### v9.3 готовность

Critical features:
- Любой третий-party может опубликовать signed plugin за <1 час
- Первая monetary transaction (one-time install) проходит through Stripe + 70/30 payout settled
- Two TARS instances находят друг друга через meeet relayer и закрывают контракт
- Native skills все 5 рабочих

---

## 3. v10.0 — "production-grade product" (Q3 2026, ~3 месяца)

**Цель:** зрелый продукт, готовый к paid scale.

### Phase X1 — Agent renaissance (port v7.1 suite, 6 недель)

- **W260** Browser agent — Playwright-based, headless, screenshots, fills forms
- **W261** Code agent — repo-aware, navigates + edits code, runs tests
- **W262** Shell agent — sandboxed shell exec с budget + HIL gate
- **W263** Vision agent — image understanding + diagram-to-code
- **W264** Local model agent — Ollama / LM Studio bridge для on-device inference

### Phase X2 — AI Clone v1 (4 недели)

- **W270** Real fine-tuning pipeline — LoRA training на personal corpus (vault-encrypted)
- **W271** Auto-restore on new machine — daemon на startup проверяет `~/.tars/clone.json` или meeet sync
- **W272** Multi-clone (work / personal / brand) с context switching
- **W273** Privacy guarantees — все style data зашифрованы на client, meeet видит только envelope hash

### Phase X3 — Cross-platform real (4 недели)

- **W280** Реальный Windows installer test rig (Azure DevOps Windows runner)
- **W281** Linux .deb / .rpm packages
- **W282** Mobile PWA polish — touch UX optimization, native iOS PWA install prompt
- **W283** Apple Watch companion (notification + ack only) (опционально)

### Phase X4 — Compliance + audit (3 недели)

- **W290** SOC 2 Type I prep — runbook + audit trail из webhook ledger
- **W291** GDPR-grade data export (W30 расширение)
- **W292** Penetration test results — fixes for surfaced issues
- **W293** Apple App Store submission (если решим распространять и через App Store)

### v10.0 критерии

- 100+ third-party plugins live
- 1000+ active operators (telemetry через tars-ingest)
- SOC 2 Type I пройдено
- Все 8 agents (browser/code/shell/vision/advisor/builder/cursor/local) работают
- Multi-clone + auto-restore real
- Apple-signed installers для Mac, signed installer для Windows, .deb/.rpm для Linux

---

## 4. Cross-cutting hygiene (continuous, throughout v9.2-v10)

- **Doc honesty:** каждый wave, который меняет publicly-claimed feature, обязан синхронно обновить `WHAT_WORKS.md` (с явными статусами `shipped` / `partial` / `roadmap`). Никаких "task done" если кода нет.
- **Test coverage:** новый код — обязательно с pytest или vitest cases. CI блокирует merge без покрытия.
- **Honest framing в RELEASE_NOTES:** разделы "Honest framing" (как в v9.1.4) обязательны каждый релиз — где список того, что НЕ работает или работает с ограничениями.
- **Brother handoff sync:** изменения в meeet contract → автоматический commit в `docs/INTEGRATION_FOR_BROTHER.md` с datetime + кем коммитнуто.

---

## 5. Effort summary

| Phase | Weeks | Key shippable |
|---|---|---|
| v9.2 L11-L16 | 4-6 | Voice loop closed, meeet billing live, supervisor real, /cockpit fixed |
| v9.3 M1-M4 | 6-8 | Public plugin marketplace, T2T live, native skills все 5, meeet OAuth |
| v10.0 X1-X4 | 12 | v7.1 agent suite, AI Clone v1, cross-platform real, SOC 2 |
| **Total to v10** | **22-26 недель** | ~6 месяцев непрерывной работы |

---

## 6. Параллелизация (что можно делать одновременно)

- **L11 (voice) ↑↑ L12 (meeet wiring)** — независимы, можно вести параллельно
- **L13 (supervisor) blocks L14 (skills)** — skills требуют HIL gate
- **L15 (notifications) ↑↑ L16 (frontend)** — параллельно
- **M1 (marketplace) blocks M3 (native skills)** — skills продаются через marketplace
- **M2 (T2T) ↑↑ M4 (OAuth broker)** — параллельно

**Optimal serial path:** L11 → L13 → L14 → M3 (skills готовы для marketplace) → M1 → M2 → M4 → X1 → X2 → X3 → X4.

---

## 7. Зависимости от брата (meeet.world side)

| Работа TARS | Требуется от меееt | Срок |
|---|---|---|
| W194 BRIDGE_SHARED_SECRET sync | Принять секрет, выставить в 3 Supabase functions | 1 час |
| W195 Clone webhook | Создать `POST /tars-ingest/clone-sync` endpoint | 1 день |
| W196 usage emission | Verify в billing dashboard что приходит | 0 (просто проверить) |
| W198 Magic-link flow | `/api/magic-link` + `/auth/tars-claim` + `/api/sessions/exchange` | 3 дня |
| W221 Publisher registry | `/api/marketplace/publishers/*` endpoints | 3 дня |
| W222 Payment processing | Stripe webhook handler + payout cron | 5 дней |
| W250 OAuth broker | `/connect/{provider}` flow с token storage | 5 дней |

**Total брату:** ~3 недели работы spread across 4 месяца.

---

## 8. Что делать прямо сейчас (next 24h)

1. **Передать этот документ брату** на meeet side для apresenting + approve scope
2. **Сгенерить + распределить BRIDGE_SHARED_SECRET** (W194 — 1 час, unblocks много)
3. **Hotfix Tauri /cockpit** (W208-W210 — 2-3 дня) — самый болезненный текущий gap для пользователя
4. **Wire AI Clone webhook** (W195 — 4 часа) — закрывает single dangling promise

После этих 4 шагов v9.2 готов к серьёзному началу.

---

**Конец документа.**
*Любые правки + дополнения через PR в `docs/ROADMAP_v9.2_v10.md`.*
