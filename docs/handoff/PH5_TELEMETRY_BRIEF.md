# PH5 — Differential telemetry (opt-in, k-anonymized, v10.2)

**Audience:** implementer (Cursor lane preferred — small backend +
small UI), 1 dev, ~1 week.
**Wave tag:** `W310-s`. **Brief file:** `docs/handoff/PH5_TELEMETRY_BRIEF.md`.
**Master plan ref:** `docs/PRODUCT_MASTER_PLAN.md §3.5`.
**IDEAS ref:** `docs/IDEAS.md #17` — "Differential telemetry. Default-off
counters with k-anon aggregation that meeet can stream anonymised;
opt-in switch in settings."

---

## §1. Motivation

A first-time reader of `IDEAS.md #17` might think differential
telemetry is greenfield. **It is not.** Almost the whole substrate is
already in place:

| Capability                                 | Where                                        | Status |
| ------------------------------------------ | -------------------------------------------- | ------ |
| Meeet client w/ event emission             | `backend/core/meeet/client.py`               | ✅     |
| Durable WAL store (replay on reconnect)    | `backend/core/meeet/store.py`                | ✅     |
| Privacy modes (normal/privacy/strict)      | `backend/core/privacy/__init__.py`           | ✅     |
| `block_meeet_telemetry` toggle             | `PrivacyConfig.block_meeet_telemetry`        | ✅     |
| Per-destination gating (`check_can_call`)  | `privacy/__init__.py::check_can_call`        | ✅     |
| Ring-buffer of data-plane events           | `privacy/__init__.py::_RING`                 | ✅     |
| Real-time WS bus for data-plane events     | `realtime.publish_event`                     | ✅     |
| Snapshot endpoint for cockpit              | `/api/privacy/data_plane`                    | ✅     |

**What's missing:**

1. **Default-OFF for telemetry**: today `PrivacyConfig.normal` mode has
   `block_meeet_telemetry=False` — operator opts OUT explicitly. IDEAS
   #17 demands opt-IN.
2. **K-anonymization**: events today carry full payload (thread_id,
   args, etc.). For aggregated telemetry we need a parallel "counters
   only" stream — bucket → count, no identifiers.
3. **Differential payload**: today every event sends the full row.
   "Differential" means: aggregate locally for N minutes, send the
   delta, never the raw events.
4. **Cockpit settings UI**: privacy toggle exists in the data model
   but there's no UI for it (only `/api/privacy/data_plane` shows
   *what was sent*, not *what will be sent*).
5. **Transparency surface**: operator must see exactly which counters
   ship — schema preview before turning telemetry on.

---

## §2. Goals

- **G1.** New `telemetry_enabled: bool = False` flag in `PrivacyConfig`,
  separate from `block_meeet_telemetry` (which still controls full-event
  ingest). Two switches:
  - `telemetry_enabled = True` → ship k-anonymized differential counters
    every N minutes.
  - `block_meeet_telemetry = True` → block full-event ingest entirely.
  These compose: operator can have `telemetry_enabled=True` AND
  `block_meeet_telemetry=True` (counters yes, raw events no — the
  intended public default for v10.2).
- **G2.** New `DifferentialAggregator` accumulates counters in process
  memory, flushed every 15 min to a new `/api/telemetry/diff/flush`
  ingest endpoint on the meeet.world side. K=3 minimum bucket size
  (suppress buckets with <3 events; deferred to next flush window).
- **G3.** Counter schema is **fixed and small** (see §3.2). Adding new
  counters requires a brief + bump of contract version.
- **G4.** Cockpit settings page surfaces:
  - Telemetry switch (off by default, with explanation).
  - "What gets sent" preview — live JSON of the next flush.
  - "What was sent" history — last 10 flushes with timestamps + sizes.
  - "Turn off" big-red-button if currently on.
- **G5.** Telemetry is **vault-gated**: if vault is locked
  (per #202 Phase 5 vault), counters queue to disk but do NOT flush.
  Flush resumes on unlock. Operator sees "queued: N counters" status.
- **G6.** Zero-PII guarantee: counters NEVER include thread_id, args,
  resource names, slugs (only category buckets), or any string that
  could be operator-identifying. Enforced by allowlist in
  `DifferentialAggregator.add()`.

**Non-goals:**
- Differential privacy with proven epsilon (full DP requires noise
  injection; v10.2 settles for k-anon w/o noise, document this).
- A/B experimentation infra. This is observability, not product
  measurement.
- Per-feature usage analytics. Bucket counts only.
- Server-side aggregation across operators. Out of scope; that's a
  meeet.world deliverable.

---

## §3. Target architecture

```
┌─────────────────────────────────────────────────────────┐
│  cockpit settings page (/settings#/privacy)             │
│   - telemetry switch  [○ off / ● on]                    │
│   - what gets sent (live preview)                       │
│   - what was sent (history)                             │
└──────────────────┬──────────────────────────────────────┘
                   │ GET  /api/telemetry/preview
                   │ GET  /api/telemetry/history
                   │ POST /api/telemetry/toggle
                   ▼
       ┌──────────────────────────────────────────────┐
       │  web_extras/routers/telemetry.py (NEW)       │
       │   - read aggregator state                    │
       │   - mutate PrivacyConfig.telemetry_enabled   │
       │   - return last 10 flush manifests           │
       └────────────┬─────────────────────────────────┘
                    │
                    ▼
   ┌──────────────────────────────────────────────────┐
   │  backend/core/telemetry/aggregator.py (NEW)      │
   │   - in-process counter dict                      │
   │   - add(bucket: str, *, amount: int = 1)         │
   │   - snapshot() → {bucket: count}                 │
   │   - flush_due() → bool (15 min cadence)          │
   │   - flush() → manifest                           │
   │   - k_anon_filter(buckets, k=3)                  │
   └────────────┬─────────────────────────────────────┘
                │
                │ called from action emit, policy.emit,
                │ chat.send, etc. (instrumented sites)
                ▼
   ┌──────────────────────────────────────────────────┐
   │  flush_loop in MeeetClient (extends client.py)   │
   │   - if aggregator.flush_due() and                │
   │     PrivacyConfig.telemetry_enabled and          │
   │     vault unlocked:                              │
   │       manifest = aggregator.flush()              │
   │       POST manifest to meeet.world               │
   │       record in history (last 10)                │
   └──────────────────────────────────────────────────┘
```

### 3.1 Counter buckets (fixed schema for v10.2)

| Bucket name                           | When                                       |
| ------------------------------------- | ------------------------------------------ |
| `action.invoked.<category>`           | Any pack action invoked (cat per `_CATEGORY_BY_PREFIX`) |
| `action.completed.<category>`         | Completion success                         |
| `action.failed.<category>`            | Completion failure                         |
| `policy.pending.<category>`           | Confirmation queued                        |
| `policy.confirmed.<category>`         | Confirmation approved                      |
| `policy.denied.<category>`            | Confirmation denied                        |
| `policy.expired.<category>`           | Confirmation expired                       |
| `chat.send`                           | Cockpit message sent                       |
| `chat.recv`                           | Model reply received                       |
| `pack.installed`                      | Pack installed                             |
| `pack.uninstalled`                    | Pack uninstalled                           |
| `error.<class>`                       | Exception (class name, allow-listed)       |
| `boot`                                | Process boot                               |
| `boot.crash_recovery`                 | Boot after unclean shutdown                |

**14 bucket families.** Each emits an integer counter per 15 min window.
**No category string is ever operator-controlled** — they're picked from
the 5-element enum from policy + a closed enum for error classes
(see §3.3).

### 3.2 Flush manifest wire shape

```jsonc
{
  "schema": "tars.telemetry.v1",
  "host_id": "9ebd45c6de53f838",       // already in privacy config
  "window_start": 1779000000,
  "window_end": 1779000900,             // 15 min
  "counters": {
    "action.invoked.wallet": 12,
    "action.invoked.outreach": 5,
    "policy.pending.wallet": 12,
    "policy.confirmed.wallet": 10,
    "policy.denied.wallet": 2,
    "chat.send": 47,
    "chat.recv": 47,
    "boot": 1
  },
  "k": 3,
  "suppressed_count": 4   // number of <k buckets dropped this window
}
```

**Wire size**: ≤ 2 KB typical, ≤ 10 KB worst case (all bucket families
populated).

### 3.3 Error class allowlist

```python
ERROR_CLASS_ALLOWLIST = frozenset({
    "TimeoutError", "ConnectionError", "PermissionError",
    "ValueError", "TypeError", "KeyError", "FileNotFoundError",
    "RuntimeError", "VaultLockedError", "VaultBadPassphraseError",
    "RateLimitError", "AuthError",
})
```

Any error class NOT in the allowlist → bucketed as `error.other`.
Prevents operator-controlled exception names (e.g. domain-specific)
from leaking.

---

## §4. Implementation steps (5 mechanical, sequential)

### Step 1 — `DifferentialAggregator` core

**File:** `backend/core/telemetry/__init__.py` + `aggregator.py` (NEW, ~220 LoC)

```python
class DifferentialAggregator:
    def __init__(self, window_s: int = 900, k: int = 3): ...
    def add(self, bucket: str, *, amount: int = 1) -> None:
        """Increment counter. Raises if bucket not in BUCKET_SCHEMA."""
    def snapshot(self) -> dict[str, int]: ...
    def flush_due(self) -> bool: ...
    def flush(self) -> dict[str, Any]:
        """Returns manifest dict; resets in-memory counters."""
    def k_anon_filter(
        self, counters: dict[str, int]
    ) -> tuple[dict[str, int], int]:
        """Returns (kept, suppressed_count)."""
```

**Constants** (module level):

```python
BUCKET_SCHEMA = frozenset({
    "action.invoked.<cat>", "action.completed.<cat>", "action.failed.<cat>",
    "policy.pending.<cat>", "policy.confirmed.<cat>",
    "policy.denied.<cat>", "policy.expired.<cat>",
    "chat.send", "chat.recv",
    "pack.installed", "pack.uninstalled",
    "error.<class>",
    "boot", "boot.crash_recovery",
})
```

Validation: `add()` parses `<cat>` and `<class>` against the enums; if
they don't match, raises `InvalidTelemetryBucket` (caught at call site
so a buggy instrumentation point can't crash the host).

**Tests** (`tests/test_telemetry_aggregator.py`, ~12 cases): counter
increments, k-anon suppresses <3, flush resets, schema validation,
window boundary correctness, concurrent add safe (lock).

### Step 2 — Privacy config + persistence

**File:** `backend/core/privacy/__init__.py` (extend, ~20 LoC delta)

Add `telemetry_enabled: bool = False` to `PrivacyConfig`. Update
`from_dict` / `to_dict` / `preset_for` (telemetry stays off across all
three presets — operator opts-in always).

Wire `~/.tars/privacy.json` migration: missing field → default False.

**Tests** (`tests/test_privacy_config.py`, ~4 cases extend): new field
defaults False, persists round-trip, preset_for normal preserves False.

### Step 3 — Instrumentation call sites

**Files** (modify, +2-5 LoC each):
- `backend/core/domains/registry.py` — pack action emit → `aggregator.add("action.invoked.<cat>")`
- `web_extras/routers/policy.py` — confirm/deny/expire → policy bucket emits
- `web_extras/routers/chat.py` (or wherever chat.send originates) → chat buckets
- `backend/core/packs/loader.py` — install/uninstall → pack buckets
- `backend/core/boot.py` — boot bucket

Use `_CATEGORY_BY_PREFIX` from policy.py (already-shipped) so category
mapping is consistent. Import via:

```python
from backend.core.telemetry import aggregator as _tel_agg
try:
    _tel_agg.add(f"action.invoked.{category}")
except Exception:
    pass  # never let telemetry crash the host
```

**Tests** (`tests/test_telemetry_instrumentation.py`, ~6 cases): hit
each instrumentation site under load, assert bucket counts.

### Step 4 — Flush loop + HTTP surface

**Files:**
- `backend/core/meeet/client.py` (extend `_lifespan` w/ flush loop, ~30 LoC)
- `web_extras/routers/telemetry.py` (NEW, ~120 LoC)

**Flush loop pseudocode:**

```python
async def _telemetry_flush_loop(self):
    while True:
        await asyncio.sleep(60)
        cfg = load_privacy()
        if not cfg.telemetry_enabled:
            continue
        if not _aggregator.flush_due():
            continue
        if not _vault.is_unlocked():
            continue   # vault locked → queue stays in memory
        manifest = _aggregator.flush()
        await self._push_manifest_diff(manifest)
        _flush_history.append(manifest)
        if len(_flush_history) > 10:
            _flush_history.pop(0)
```

**HTTP endpoints:**

```python
GET  /api/telemetry/status     → {enabled, queued, last_flush, vault_state}
GET  /api/telemetry/preview    → {next_flush_in_s, counters: {...}}
GET  /api/telemetry/history    → {flushes: [...]}  (last 10)
POST /api/telemetry/toggle     {enabled: bool}     → 200
POST /api/telemetry/flush_now                       → 200 (admin/test)
```

**Tests** (`tests/test_telemetry_router.py`, ~8 cases): toggle persists,
preview shows live counters, history truncated to 10, flush_now drains,
vault-locked queues without flushing.

### Step 5 — Cockpit settings UI

**Files:**
- `apps/cockpit/src/pages/settings-entry.ts` (NEW or extend)
- `apps/cockpit/src/components/telemetry-panel.ts` (NEW, ~220 LoC)
- `apps/cockpit/src/lib/telemetry-client.ts` (NEW, ~80 LoC)

**Layout:**

```
┌─ Telemetry ─────────────────────────────────────────────┐
│ Send anonymized usage counters to meeet.world           │
│ Default: off.                                           │
│                                                         │
│  [○ off ─────●]    Telemetry: ON                        │
│                                                         │
│  ▸ What gets sent (preview, refreshes every 30s)        │
│     {                                                   │
│       "schema": "tars.telemetry.v1",                    │
│       "window_end": "in 8 min",                         │
│       "counters": {                                     │
│         "action.invoked.wallet": 4,                     │
│         "chat.send": 12,                                │
│         ...                                             │
│       },                                                │
│       "suppressed_count": 2                             │
│     }                                                   │
│                                                         │
│  ▸ History (last 10 flushes)                            │
│     14:00 → 2.1 KB, 47 counters, 3 suppressed           │
│     13:45 → 1.8 KB, 41 counters, 5 suppressed           │
│     …                                                   │
│                                                         │
│  ▸ Schema (closed set, 14 bucket families)              │
│     [open spec]                                         │
│                                                         │
│  [ Turn off ]                                           │
└─────────────────────────────────────────────────────────┘
```

- Toggle: animated switch, 300ms ease. Click → POST `/api/telemetry/toggle`.
  Optimistic update with rollback on failure.
- Preview: `<pre>` w/ JSON syntax highlighting (regex tokenizer; no eval).
- History: simple table, click row → expand manifest.
- Schema link → in-page modal with the §3.1 bucket list as
  human-readable text + click-to-copy raw schema JSON.
- "Turn off" button always visible at bottom when ON; red destructive
  styling.

---

## §5. Files touched

| Area              | File                                            | LoC est |
| ----------------- | ----------------------------------------------- | ------- |
| Core aggregator   | `backend/core/telemetry/__init__.py` (NEW)      | +30     |
|                   | `backend/core/telemetry/aggregator.py` (NEW)    | +220    |
| Privacy config    | `backend/core/privacy/__init__.py` (extend)     | +20     |
| Instrumentation   | `backend/core/domains/registry.py` (modify)     | +5      |
|                   | `web_extras/routers/policy.py` (modify)         | +12     |
|                   | `web_extras/routers/chat.py` (modify)           | +5      |
|                   | `backend/core/packs/loader.py` (modify)         | +5      |
|                   | `backend/core/boot.py` (modify)                 | +5      |
| Flush loop        | `backend/core/meeet/client.py` (extend)         | +30     |
| HTTP surface      | `web_extras/routers/telemetry.py` (NEW)         | +120    |
| Cockpit           | `apps/cockpit/src/pages/settings-entry.ts`      | +60     |
|                   | `apps/cockpit/src/components/telemetry-panel.ts`| +220    |
|                   | `apps/cockpit/src/lib/telemetry-client.ts`      | +80     |
| Tests             | `tests/test_telemetry_aggregator.py` (NEW)      | +260    |
|                   | `tests/test_privacy_config.py` (extend)         | +60     |
|                   | `tests/test_telemetry_instrumentation.py` (NEW) | +180    |
|                   | `tests/test_telemetry_router.py` (NEW)          | +220    |
|                   | `tests/playwright/telemetry.spec.ts` (NEW)      | +180    |
| Docs              | `docs/TELEMETRY_SCHEMA.md` (NEW)                | +120    |
|                   | `IDEAS.md #17` → ✅ shipped marker              | ±3      |
|                   | Master plan §3.5 → ✅ shipped marker            | ±5      |
| **Total**         |                                                 | **≈ 1.8k LoC** |

---

## §6. Coupling

| Brief / PR                  | Relationship                                                 |
| --------------------------- | ------------------------------------------------------------ |
| Phase 5 vault (PR #202)     | **Hard dep.** Flush loop checks `_vault.is_unlocked()`; queues during locked windows. Vault MUST land first. |
| Phase 5 policy UI (PR #203) | **Soft dep.** Telemetry references `_CATEGORY_BY_PREFIX` from policy.py — already shipped, no version constraint. |
| Phase 3 keyring (PR #195)   | No direct coupling. |
| Phase 11 brother handoff (#198) | **Hard dep.** Adds `POST /api/telemetry/diff/flush` to brother handoff — meeet.world side must accept the schema. |

---

## §7. Test plan

| Category    | Coverage                                                       |
| ----------- | -------------------------------------------------------------- |
| Unit        | Aggregator add/snapshot/flush, k-anon math, schema validation  |
| Integration | All instrumentation call sites fire; counters match expected   |
| Privacy     | `block_meeet_telemetry=True` blocks full events, telemetry still works (composability) |
| Privacy     | `telemetry_enabled=False` (default) → zero network calls       |
| K-anon      | Bucket w/ <3 events → suppressed; suppression count surfaced   |
| Vault       | Vault locked → counters queue but no flush; unlock → flush     |
| Soak        | 24h run: <50 MB heap growth; flush manifests ≤ 10 KB each      |
| Schema      | Adding instrumentation w/ invalid bucket name raises in tests  |
| Cockpit e2e | Toggle on → preview refreshes; turn off → no further flushes   |
| Wire        | Manifest validates against `tars.telemetry.v1` JSON schema     |

---

## §8. Open questions for operator

1. **Flush window**: 15 min suggested. Acceptable for v10.2 or shorter
   (5 min) for faster feedback? (Recommendation: 15 min — minimizes
   network noise, k-anon works better w/ larger windows.)
2. **K threshold**: k=3 minimum bucket size suggested. Stricter
   (k=5)? (Recommendation: k=3 — single operator, smaller k still useful;
   document tradeoff in `TELEMETRY_SCHEMA.md`.)
3. **First-run prompt**: explicit "would you like to enable telemetry?"
   modal at first boot, or stay silent (operator finds it in settings)?
   (Recommendation: silent — minimizes onboarding friction, matches
   "default off, opt-in" framing.)
4. **Differential privacy noise**: out of scope per §2 non-goals. Confirm.
5. **Composability with `strict` mode**: should `strict` mode force
   telemetry off even if operator toggled it on? (Recommendation: yes —
   strict mode means strict, document this clearly. Toggle persists for
   when operator leaves strict mode.)

---

## §9. Effort summary

| Step  | LoC delta (incl tests) | Time   |
| ----- | ---------------------- | ------ |
| 1     | +480                   | 2 d    |
| 2     | +80                    | 0.5 d  |
| 3     | +212                   | 1 d    |
| 4     | +470                   | 2 d    |
| 5     | +540                   | 2 d    |
| Docs  | +130                   | 0.5 d  |
| **Total** | **≈ 1.8k LoC + docs** | **~1 week** |

Master plan §3.5 estimates 1 week for the joint policy+telemetry block.
The split (policy UI ~1 wk, telemetry ~1 wk) extends that to 2 weeks
of parallel-able work.

---

## §10. Acceptance criteria for v10.2 ship

- [ ] Default `~/.tars/privacy.json` ships with `telemetry_enabled=False`.
- [ ] Operator can opt-in via cockpit settings; toggle persists.
- [ ] Counters flush every 15 min while enabled; queue while disabled.
- [ ] Vault-locked → queue without flush; unlock → flush resumes.
- [ ] Aggregator's `add()` rejects unknown buckets (test gate in CI).
- [ ] `tars.telemetry.v1` JSON schema documented in
  `docs/TELEMETRY_SCHEMA.md` and matches wire shape.
- [ ] Brother handoff updated: meeet.world ingests
  `POST /api/telemetry/diff/flush` and validates schema.
- [ ] `IDEAS.md #17` ✅ shipped.
- [ ] `docs/PRODUCT_MASTER_PLAN.md §3.5` telemetry bullet ✅ shipped.

---

## §11. Sources & references

- **Master plan**: `docs/PRODUCT_MASTER_PLAN.md §3.5`.
- **IDEAS.md #17**: original differential telemetry framing.
- **Privacy module (already shipped)**: `backend/core/privacy/__init__.py`
  (full file, ~350 LoC).
- **Category enum**: `web_extras/routers/policy.py::_CATEGORY_BY_PREFIX`
  (lines 260-268).
- **Meeet client**: `backend/core/meeet/client.py::MeeetClient`.
- **Vault unlock check**: see PR #202 (`MasterVault.is_unlocked()`).
- **K-anonymity reference**: Samarati & Sweeney, "Protecting Privacy
  when Disclosing Information" (1998) — k-anon foundation, no noise.
- **Brother handoff**: `docs/handoff/PH11_BROTHER_HANDOFF_BRIEF.md`
  (PR #198) — extend §6 with telemetry endpoint contract.

---

*End of brief. PR title: "PH5 — Differential telemetry brief
(v10.2 opt-in, k-anonymized)".*
