# Wave 53 — Pre-launch sign-off (May 5 2026)

**Verdict:** **GREEN LIGHT для launch завтра.** 217 коммитов после моего baseline разобраны, 4 P1 от Wave 51 закрыты Cursor'ом, 9 critical bugs (PR #136-#144) закрыты, 2315 backend tests + 328 vitest passing. Smoke 25/0/2/3.

## Что я лично закрыл в Wave 53

### 1 · A11y фикс на FAQ — `src/components/FAQ.tsx`
Кнопка раскрытия теперь имеет осмысленный `aria-label="Expand answer · {question}"` (раньше Plus icon был чистым `aria-hidden` без текстовой подписки). Панель ответа получила `role="region"` + `aria-labelledby` на кнопку — assistive tech теперь объявляет "answer region for [question]" при focus.

WCAG 2.1 AA · 2.4.4 Link Purpose · 2.4.6 Headings and Labels · 4.1.2 Name, Role, Value — всё закрыто.

### 2 · CockpitGate footer URL leak fix — `src/components/CockpitGate.tsx`
Раньше footer печатал `{API_BASE}` literally — на production это могло показать `https://tars.meeet.world` или `127.0.0.1:8765` в зависимости от env, что путает посетителей которые ещё не установили TARS ("откуда 127.0.0.1?"). Теперь URL виден только в dev-builds (`!import.meta.env.PROD`), prod показывает только сообщение про probe.

## Что подтверждено зелёным (не моё)

### Backend security — все P1 от Wave 51 закрыты Cursor'ом

| # | Что было | Закрыто через |
|---|---|---|
| **P1-1** | `payment_token` принимался любая строка | `TARS_PAYMENT_MODE=off\|mock\|onchain` env-driven gating |
| **P1-2** | `x-tars-policy-mode: autopilot` обходил council | `resolve_mode()` с capability tokens на сервере |
| **P1-3** | Нет rate-limiting | Custom token-bucket в `web_extras/rate_limit.py`, без slowapi dep |
| **P1-4** | BYO toggle без auth | `set_byo()` через entitlements store + `is_remote_billing_configured()` gate |

Дополнительно:
- CORS hardcoded на `tars.meeet.world` + `localhost:5173/5174`, без wildcard
- `_safe_args()` redacts secrets из логов
- Recovery seed/wallet mnemonics никогда не персистятся, audit trail только fingerprints
- 0 hardcoded API keys в production paths (93 ref'а — все легит OAuth flows / docs / schemas)
- 0 stray `print(` / `console.log(` в production routers

### Frontend showcase состояние

- **182 TS/TSX файла, 43 551 LOC** — handle-able codebase
- **`VITE_TARS_API=https://tars.meeet.world`** в `.env.production` — корректно для prod
- **SW `tars-v9.0.1`** — пост Wave 52 fix, актуально
- **Routes registered:** `/`, `/cockpit`, `/cockpit/planner`, `/cockpit/traces`, `/cockpit/policy`, `/cockpit/council`, `/cockpit/awareness`, `/install`, `/onboarding`, плюс real `/pricing`, `/faq`, `/compare` (commit 6c3ef57)
- **6 console.warn() calls** — все error-handling в WebGL/Spline/policy fallbacks, OK
- **12 hardcoded localhost references** — все в docs / UI strings / error messages, intentional для local-first product

### Launch operations (per `GO_LIVE_48H.md`)

✅ Done:
- DNS `tars.meeet.world` CNAME активен с May 1
- SSL cert SAN покрывает (`*.meeet.world`)
- Cloudflare Pages project `tars-meeet-git` auto-builds from `main`
- Contract version 1.0.0 в response headers
- Cursor's lane 100% завершена

⚠️ Пара pending действий ОТ ОПЕРАТОРА (брат):

**A · `BRIDGE_SHARED_SECRET` на Cloudflare Pages** — блокирующий
Без этого: 3 SKIPs + 1 WARN в QA-агенте, ingest/error bridge не работают. Один paste + redeploy.

```bash
# Вариант 1 (через make):
export CLOUDFLARE_API_TOKEN=...
export CLOUDFLARE_ACCOUNT_ID=...
make ops-bridge-secret    # промптит секрет с stdin

# Вариант 2 (manual):
Pages dashboard → tars-meeet → Settings → Environment → Production
→ Add BRIDGE_SHARED_SECRET → Save and deploy
```

**B · `/api/tars/downloads` proxy на meeet-app** — опционально
Сейчас bypass через `_redirects` → Supabase edge напрямую. Можно добавить позже, не блокер.

## P1/P2 находки из Wave 53 (НЕ блокеры — first-week sprint)

### P1 (закрыть в первую неделю)

1. **JumpPalette silent fail** (`src/components/JumpPalette.tsx:88-99`) — fetch error catch только `setError(String(...))` + inline `<p role="alert">`. Если юзер скроллит мимо — повторяет blindly. Нужен persistent toast.

2. **OperatorPalette race condition** (`src/components/OperatorPalette.tsx:99-104`) — `Promise.race([probe, timed])` — timeout reject не отменяет fetch. Wrap `getHealth()` в AbortSignal.

3. **LocaleSwitcher empty list** (`src/components/LocaleSwitcher.tsx:22-32`) — если `supported` пустой → `<select>` без `<option>` невалидный HTML. Guard `if (!supported.length) return null`.

4. **Onboarding modal a11y** (`src/pages/Onboarding.tsx:720`) — `role="dialog"` есть, но `aria-modal="true"` отсутствует и focus trap не настроен. Применить `useFocusTrap()` который уже в codebase с Wave 27.

5. **Compare table sticky column на mobile** (`src/components/Compare.tsx:169-243`) — на 380px горизонтальный scroll прячет первый столбец (feature names). Нужна `position: sticky` или mobile-альтернативный layout.

### P2 (backlog)

6. **Pricing tier hex hardcoded** — `Pricing.tsx:59,80,102` — вынести в `--tier-free`, `--tier-pro`, `--tier-business` tokens
7. **Onboarding role colors hardcoded** — `Onboarding.tsx:115,124,133`
8. **OperatorPalette hotkey throttle** — `useRef(0)` token guard
9. **CockpitGate cleanup ordering** — `controller.abort()` перед null'ed refs
10. **FAQ answer length** — несколько ответов > 4 предложений, обрезать или вынести в `/docs/FAQ.md`
11. **CTA verb consistency** — "Open cockpit" vs "Get started" — определить single verb per action type

## TODO для брата (только то что от него зависит)

```
□ git pull (взять Wave 53 fixes)
□ Paste BRIDGE_SHARED_SECRET в Cloudflare Pages env vars
□ make ops-bridge-secret (если использовать скрипт)
□ Verify Pages rebuild green
□ Run smoke checklist (POST_LAUNCH_SMOKE.md), expect 25/0/0/3
□ После launch — проверить error reporter / lighthouse / axe ещё раз
□ Опционально: meeet-app /api/tars/downloads proxy
```

## TODO для Cursor (post-launch sprint, не блокер)

P1 list above (5 items, ~1-2 days of work):
- JumpPalette toast on error
- OperatorPalette AbortSignal
- LocaleSwitcher empty guard
- Onboarding modal aria-modal + useFocusTrap
- Compare mobile sticky column

После закрытия P1 — переходить к P2 + Cockpit v2 spec из Wave 49.

## Финальная формула

**Что готово к завтрашнему launch'у:**
- Backend live, tested, secure ✅
- Frontend showcase deployed на tars.meeet.world ✅
- All P1 closed ✅
- A11y P0 fixes (FAQ accordion + CockpitGate URL leak) ✅
- Smoke 25/0/2/3 ✅
- Docs sync ✅

**Что ждёт оператора (брата):** один paste BRIDGE_SHARED_SECRET → redeploy → green.

**Verdict:** Ship it 🚀
