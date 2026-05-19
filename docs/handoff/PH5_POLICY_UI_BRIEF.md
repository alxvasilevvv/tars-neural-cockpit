# PH5 — Policy Confirmations Inbox UI (v10.2)

**Audience:** implementer (Cursor lane preferred — UI-only), 1 dev, ~1 week.
**Wave tag:** `W310-r`. **Brief file:** `docs/handoff/PH5_POLICY_UI_BRIEF.md`.
**Master plan ref:** `docs/PRODUCT_MASTER_PLAN.md §3.5`.
**IDEAS ref:** `docs/IDEAS.md #29` — "Pending confirmations panel.
Backend shipped — `/api/policy/pending` returns staged tokens with
args/preview. Owner: design — a left-rail 'approval inbox' with
one-click confirm / cancel and an audit row."

---

## §1. Motivation

The policy confirmation backend has been **fully shipped** through
Wave 101 (see `web_extras/routers/policy.py`, 499 LoC). Every primitive
the operator needs is already exposed:

| Backend capability                              | Endpoint                                  | Status |
| ----------------------------------------------- | ----------------------------------------- | ------ |
| List pending confirmations                      | `GET  /api/policy/pending`                | ✅     |
| List recent (any status)                        | `GET  /api/policy/recent`                 | ✅     |
| Approve single                                  | `POST /api/policy/confirm/{token}`        | ✅     |
| Cancel single                                   | `POST /api/policy/cancel/{token}`         | ✅     |
| Expire stale (admin/cron)                       | `POST /api/policy/expire`                 | ✅     |
| **/inbox queue (normalised)**                   | `GET  /api/policy/queue`                  | ✅     |
| Single row + full payload                       | `GET  /api/policy/queue/{id}`             | ✅     |
| Deny w/ required reason                         | `POST /api/policy/deny/{id}`              | ✅     |
| **Bulk approve** w/ safety check                | `POST /api/policy/queue/bulk-approve`     | ✅     |
| **SSE stream** for new pending                  | `GET  /api/policy/queue/stream`           | ✅     |
| Auto-approve $X threshold (settings)            | `POST /api/policy/auto-approve-threshold` | ✅     |
| Category mapping (wallet/outreach/code/trading) | server-side `_category_for()`             | ✅     |
| $-impact extraction                             | server-side `_dollar_impact()`            | ✅     |
| Thread-id back-link (meeet trace)               | `_attach_thread_id()`                     | ✅     |
| Outbound webhook fan-out (hil.approved/denied)  | server-side                               | ✅     |
| Receipt ledger entries                          | server-side                               | ✅     |

**Gap:** there is **no Cockpit UI** rendering any of it. Operators
must use `curl` or the legacy admin panel (which lives outside the
cockpit and is being deprecated for v11). This brief specs the missing
inbox surface.

---

## §2. Goals

- **G1.** Cockpit `/inbox` page renders the queue as a sortable table.
- **G2.** Real-time updates via the `/api/policy/queue/stream` SSE.
- **G3.** Single-row actions: approve, deny (with required reason),
  view full payload (drawer).
- **G4.** Bulk approve respects the safety check (refuses if any row
  exceeds the auto-approve threshold).
- **G5.** Settings sub-page lets operator change auto-approve $X cap.
- **G6.** Top-right pill on every cockpit page shows pending count;
  click → navigate to `/inbox`.
- **G7.** Pending events propagate into the per-thread timeline via the
  already-emitted `policy.confirm` / `policy.cancelled` meeet events
  (no new backend work; cockpit timeline filter already keys on
  `payload.thread_id`).
- **G8.** Keyboard-first: `j/k` to navigate rows, `a` to approve, `d`
  to deny (opens reason input), `Enter` to open drawer.

**Non-goals:**
- Approval workflow / multi-approver. Single operator only.
- Mobile/responsive — desktop cockpit only for v10.2.
- Audit replay (already lives in the meeet timeline).
- Sound notifications — defer to v10.3.

---

## §3. Target UX

```
┌─────────────────────────────────────────────────────────────────┐
│ TARS cockpit  …  [vault: 🔒 28:14]  [pending: 7 ⚡]  [user ▾] │ ← header
├──────────────────┬──────────────────────────────────────────────┤
│ ☐ wallet  ✉      │ 7 pending confirmations          [⊕ Bulk]    │
│ ☐ outreach        │  ┌──────────────────────────────────────┐    │
│ ☐ code/github    │  │ ⌖ time  category    action   $impact│    │
│ ☐ live trading   │  ├──────────────────────────────────────┤    │
│ ──────────────── │  │ 14:23  💸 wallet   send       $250  │    │
│ status: pending  │  │ 14:21  ✉ outreach gmail.send   —    │    │
│ ☐ recent         │  │ 14:18  💸 wallet   send      $1200⚠  │ ← red bg if >threshold
│ ☐ all            │  │ 14:15  💻 code     gh.merge    —    │    │
│                  │  │ …                                    │    │
│ since: [7d  ▾]   │  └──────────────────────────────────────┘    │
│                  │                                                │
│ [ + auto-approve │  ┌─ drawer (opens on row click) ───────┐    │
│   threshold:     │  │ Action: wallet.send                   │    │
│   $500 ✎ ]       │  │ Thread: thread_abc                    │    │
│                  │  │ Args:   {to: "0x…", amount: 250 USD…}│    │
│                  │  │ Pack:   wallet (signed by alice@…)   │    │
│                  │  │ ─────────────────────────────────    │    │
│                  │  │ [ ✓ Approve ] [ ✗ Deny ]              │    │
│                  │  │   reason (required for deny): [...]   │    │
│                  │  └───────────────────────────────────────┘    │
└──────────────────┴──────────────────────────────────────────────┘
```

**Color chips** (per backend `_CATEGORY_BY_PREFIX`):
- `wallet`     → indigo
- `outreach`   → violet
- `code`       → cyan
- `live_trading` → red (⚠ always; extra red background row tint)
- `other`      → grey

**Over-threshold rows** get a red background tint regardless of category
(visual reinforcement of the safety check).

---

## §4. Implementation steps (5 mechanical, sequential)

### Step 1 — Add `/inbox` page to cockpit routing

**Files:**
- `apps/cockpit/src/pages/inbox-entry.ts` (NEW, ~80 LoC)
- `apps/cockpit/src/pages/cockpit-entry.ts` (extend router, ~10 LoC)
- `apps/cockpit/index.html` (add `<link rel="modulepreload" …>`)

Hash-route only: `#/inbox` resolves to `inbox-entry.ts`. No SPA framework
required — pattern matches existing `pages/` siblings.

### Step 2 — Policy client (HTTP + SSE)

**File:** `apps/cockpit/src/lib/policy-client.ts` (NEW, ~180 LoC).

```typescript
export type PendingRow = {
  id: string; time: number; action: string; slug: string;
  resource: string; dollar_impact: number | null;
  category: 'wallet' | 'outreach' | 'code' | 'live_trading' | 'other';
  reason?: string; args: Record<string, unknown>; thread_id?: string;
};

export async function listQueue(opts: {
  status?: 'pending' | 'recent' | 'all';
  type?: string;            // category filter
  since?: string;           // "7d", "24h", "1h"
}): Promise<PendingRow[]>;

export async function approve(id: string): Promise<void>;
export async function deny(id: string, reason: string): Promise<void>;
export async function bulkApprove(ids: string[]): Promise<{
  approved: number; rejected: { id: string; reason: string }[];
}>;
export async function setAutoApproveThreshold(usd: number): Promise<void>;
export function streamPending(
  onRow: (row: PendingRow) => void,
  onError: (err: Error) => void
): { close: () => void };
```

**SSE wrapper**: native `EventSource` with `withCredentials: false` (cookies
not needed; localhost-only by default), auto-reconnect on disconnect
(exponential backoff capped at 30s).

**Tests** (`tests/playwright/policy-client.spec.ts`, ~5): list+filter,
approve roundtrip, deny requires reason, bulk over-threshold rejected,
SSE delivers new row within 1s of POST.

### Step 3 — Table + drawer components

**Files:**
- `apps/cockpit/src/components/policy-table.ts` (NEW, ~280 LoC)
- `apps/cockpit/src/components/policy-drawer.ts` (NEW, ~180 LoC)
- `apps/cockpit/src/components/policy-filters.ts` (NEW, ~110 LoC)
- `apps/cockpit/src/styles/policy.css` (NEW, ~140 LoC)

`policy-table.ts` responsibilities:
- Render rows from state held in `inbox-entry.ts`.
- Sort columns (time desc default, $impact, category, action).
- Highlight selected row (focus ring + bg).
- Keyboard nav (j/k/Enter/a/d) — see §5 below.
- Multi-select via Shift+click and `m` toggle for bulk.

`policy-drawer.ts`:
- Slide-in from right.
- JSON pretty-print for `args` (no eval, no innerHTML; use `<pre>` +
  textContent + tokenize w/ regex).
- "Approve" and "Deny" buttons; "Deny" disabled until reason ≥ 3 chars.
- Focus trap; Esc closes drawer (returns focus to last row).

`policy-filters.ts`:
- Category checkboxes (wallet/outreach/code/trading/other).
- Status radio (pending/recent/all).
- Since dropdown (1h/24h/7d/30d/all).
- Auto-approve threshold input (read current value; save on blur).

### Step 4 — Pending-count pill in cockpit header

**Files:**
- `apps/cockpit/src/components/pending-pill.ts` (NEW, ~60 LoC)
- `apps/cockpit/src/pages/cockpit-entry.ts` (mount pill, ~5 LoC delta)

Polls `/api/policy/pending?limit=1` every 30s for the count (cheap —
returns `count` field even if list is empty). Also listens to SSE for
real-time bump.

Click → navigate to `#/inbox`.

Render rules:
- `count === 0` → `[pending: 0]` muted grey
- `1 ≤ count ≤ 5` → `[pending: N]` amber
- `count > 5` → `[pending: N ⚡]` red

### Step 5 — Keyboard shortcuts + a11y polish

**File:** `apps/cockpit/src/lib/inbox-shortcuts.ts` (NEW, ~80 LoC)

| Key       | Action                          |
| --------- | ------------------------------- |
| j / ↓     | Next row                        |
| k / ↑     | Previous row                    |
| Enter     | Open drawer                     |
| a         | Approve focused row             |
| d         | Deny focused row (opens reason) |
| m         | Toggle multi-select             |
| Shift+A   | Bulk-approve all selected       |
| /         | Focus filter input              |
| Esc       | Close drawer / clear selection  |

**A11y**:
- Each row is `role="row"` with `aria-rowindex`.
- Drawer is `role="dialog"` with `aria-modal="true"`, `aria-labelledby`
  pointing to the action title.
- All buttons have visible focus ring (don't rely on `:focus` alone —
  use `:focus-visible` + `outline: 2px solid var(--accent)`).
- Bulk-approve count announced via `aria-live="polite"`.
- Lockout / error toasts use `role="alert"` only on hard errors.

---

## §5. Files touched

| Area       | File                                         | LoC est |
| ---------- | -------------------------------------------- | ------- |
| Pages      | `apps/cockpit/src/pages/inbox-entry.ts`      | +80     |
|            | `apps/cockpit/src/pages/cockpit-entry.ts`    | +15     |
|            | `apps/cockpit/index.html`                    | +3      |
| Client     | `apps/cockpit/src/lib/policy-client.ts`      | +180    |
| Components | `apps/cockpit/src/components/policy-table.ts`| +280    |
|            | `apps/cockpit/src/components/policy-drawer.ts`| +180   |
|            | `apps/cockpit/src/components/policy-filters.ts`| +110  |
|            | `apps/cockpit/src/components/pending-pill.ts` | +60    |
| Styles     | `apps/cockpit/src/styles/policy.css`         | +140    |
| Shortcuts  | `apps/cockpit/src/lib/inbox-shortcuts.ts`    | +80     |
| Tests      | `tests/playwright/inbox.spec.ts`             | +280    |
|            | `tests/playwright/policy-client.spec.ts`     | +160    |
| Docs       | Update `IDEAS.md #29` → ✅ shipped marker    | ±3      |
|            | Update master plan §3.5 → ✅ shipped marker  | ±5      |
| **Total**  |                                              | **≈ 1.5k LoC** |

**No backend changes.** Zero new endpoints. Zero schema migrations.

---

## §6. Coupling

| Brief / PR                  | Relationship                                                 |
| --------------------------- | ------------------------------------------------------------ |
| Phase 5 vault (PR #202)     | **Sibling.** Pending pill and vault pill share header slot CSS. Recommend landing vault first → policy table can assume `VaultGate` exists. |
| Phase 5 telemetry           | **Sibling.** Inbox renders a small counter `events sent: N` from the telemetry status endpoint in the filter side panel. |
| Phase 3 pairing UX (#196)   | Share `apps/cockpit/src/components/modal-base.ts` styles. Drawer reuses the focus-trap util. |
| Phase 1 W309 step 2         | Playwright suite scaffolded by #189 already includes a `pages/inbox.spec.ts` stub; this brief fills it. |

---

## §7. Test plan

### Playwright e2e (`tests/playwright/inbox.spec.ts`, ~8 scenarios)

1. **Empty state**: `/api/policy/pending` returns 0 → "No pending
   confirmations" + illustration.
2. **List renders**: seed 7 confirmations → table shows 7 rows in time
   desc order.
3. **Filter by category**: seed mixed → check `wallet` only → table shows
   only wallet rows.
4. **Approve single**: click row → drawer opens → Approve → success
   toast → row disappears → count pill decrements.
5. **Deny requires reason**: Deny button disabled with empty reason; type
   3 chars → enables; submit → row removed, recent-tab now shows it.
6. **Bulk approve over threshold**: select 3, one exceeds threshold → bulk
   API returns partial success → UI shows "2 approved, 1 rejected
   (over threshold)".
7. **SSE delivers**: open `/inbox` → POST a new confirmation via API →
   row appears within 1s without page reload.
8. **Keyboard nav**: j/k navigate, Enter opens drawer, Esc closes, a
   approves, d opens reason.

### Visual regression (`tests/playwright/inbox-visual.spec.ts`)

- Snapshot empty state.
- Snapshot 5-row populated state.
- Snapshot over-threshold row (red bg).
- Snapshot drawer open w/ wallet payload.

(Use Playwright's `toHaveScreenshot()` with `threshold: 0.02`.)

---

## §8. Open questions for operator

1. **Pill placement**: top-right header (sibling of vault pill) or
   left-rail nav? (Recommendation: header — high visibility, no nav
   restructure needed.)
2. **Default auto-approve threshold**: $0 (everything goes through
   manual approval) or $50 (small wallet txns auto-flow)? Affects
   first-run UX. (Recommendation: $0 — operator opts-in to risk
   explicitly.)
3. **Over-threshold visual**: red background on the whole row, or red
   left border only? (Recommendation: full row tint — louder = safer.)
4. **Drawer width**: 480px fixed or 35% viewport? (Recommendation:
   fixed 480px — JSON payloads need predictable wrap behavior.)
5. **Sound on new pending**: in scope? (Recommendation: out — defer to
   v10.3 with global mute setting; for v10.2 the pill ⚡ icon is enough.)

---

## §9. Effort summary

| Step  | LoC delta (incl tests) | Time   |
| ----- | ---------------------- | ------ |
| 1     | +95                    | 0.5 d  |
| 2     | +340                   | 1.5 d  |
| 3     | +710                   | 3 d    |
| 4     | +65                    | 0.5 d  |
| 5     | +80                    | 0.5 d  |
| Tests | +440                   | 1 d    |
| **Total** | **≈ 1.5k LoC + docs** | **~1 week** |

Matches master plan estimate (§3.5 = 1 week).

---

## §10. Acceptance criteria for v10.2 ship

- [ ] `/inbox` route loads, no console errors.
- [ ] All 8 Playwright scenarios green.
- [ ] Visual regression snapshots committed and passing.
- [ ] Pending pill increments live on a new confirmation (SSE works).
- [ ] Bulk approve over-threshold path returns correct partial-success UI.
- [ ] Keyboard shortcuts work (manual smoke test documented in PR).
- [ ] Axe a11y scan: zero violations on `/inbox` (CI gate).
- [ ] `IDEAS.md #29` updated to ✅ shipped.
- [ ] `docs/PRODUCT_MASTER_PLAN.md §3.5` policy bullet updated to ✅.

---

## §11. Sources & references

- **Master plan**: `docs/PRODUCT_MASTER_PLAN.md §3.5`.
- **IDEAS.md #29**: original "approval inbox" framing.
- **Backend endpoints (all shipped)**: `web_extras/routers/policy.py`
  lines 1-20 (docstring enumerates the full surface).
- **Category mapping**: `policy.py::_CATEGORY_BY_PREFIX` (lines 260-268).
- **$-impact extraction**: `policy.py::_dollar_impact` (lines 287-300).
- **Wave 101 context** (when the queue endpoints landed):
  `docs/CHANGELOG_AGENTS.md` Wave 101.
- **Cockpit page pattern** to follow:
  `apps/cockpit/src/pages/cockpit-entry.ts` for hash routing,
  `apps/cockpit/src/pages/preview-entry.ts` for sibling structure.

---

*End of brief. PR title: "PH5 — Policy confirmations inbox UI brief
(v10.2 cockpit surface)".*
