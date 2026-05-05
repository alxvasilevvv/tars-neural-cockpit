# Cursor handoff — Wave 56

**From:** Claude (Cowork window)
**To:** Cursor (canonical repo, integration branch)
**Date:** 2026-05-05
**Lane:** `frontend tokens` + `backend mirror logging` (no overlap with Claude's marketing/cockpit lane)
**Effort:** 15–20 min, 3 files touched, 1 token added.

---

Three P1 items remain after Wave 55. Two real (P1-1, P1-3); one already covered (P1-2 — kept here for transparency). Each one below has the exact line, the current code, the proposed patch, and a verification step. Apply and ship.

---

## P1-1 · Hex → tokens in Onboarding role chips

**File:** `experiments/neural-showcase-v3/src/pages/Onboarding.tsx`
**Lines:** 116, 125, 134

The first three roles (`founder`, `trader`, `researcher`) already use `var(--brand-indigo|violet|cyan)`. The last three were missed in the Wave 36 token sweep. `--brand-orchid` and `--color-success` already exist in `src/index.css`; `--brand-amber` needs adding.

**Patch 1 — add `--brand-amber` token to `src/index.css`** (insert after L50, in the brand-triad block):

```diff
   --brand-indigo: #6366f1;
   --brand-violet: #8b5cf6;
   --brand-cyan:   #06b6d4;
   --brand-orchid: #a78bfa;
+  --brand-amber:  #f59e0b;
```

The amber slot is for the `operator` role chip and pairs with the existing brand triad. Don't widen it to a fifth member of the marketing gradient sweep — keep `--brand-sweep` unchanged. This token is *role accent only*.

**Patch 2 — replace the 3 hex literals in `Onboarding.tsx`:**

```diff
@@ ROLES const, marketer (L116) @@
-    color: "#A78BFA",
+    color: "var(--brand-orchid)",
@@ ROLES const, engineer (L125) @@
-    color: "#34D399",
+    color: "var(--color-success)",
@@ ROLES const, operator (L134) @@
-    color: "#F59E0B",
+    color: "var(--brand-amber)",
```

**Why this matters for launch:** light-theme polish (Wave 18) defined `--color-ink-*` and friends as theme-aware tokens. Hardcoded hex chips don't react to light mode and pop visually wrong on paper-mode. The 3 affected roles are the second half of the onboarding grid — high-traffic surface during first-run.

**Verify:** `make dev-tars-stack` → toggle light theme via Nav → confirm marketer/engineer/operator chips don't blow out on paper background. Vitest doesn't cover this; visual smoke only.

---

## P1-2 · gate-control-tower BRIDGE_SHARED_SECRET guard — already covered, no action

**File:** `Makefile` L104–110, `scripts/smoke_core_bridge_e2e.sh` L9–12

`gate-control-tower` calls `smoke-core-bridge` which already fails fast on empty `BRIDGE_SHARED_SECRET`:

```bash
if [[ -z "${BRIDGE_SHARED_SECRET}" ]]; then
  echo "ERROR: BRIDGE_SHARED_SECRET is required"
  exit 1
fi
```

Make's `$(MAKE) smoke-core-bridge` propagates the non-zero exit, so `gate-control-tower` already errors-out cleanly when the secret isn't set. Wave 54 closed the `.env.example` template gap. No further action needed here — listed only so we don't both end up adding a redundant guard at the Makefile level.

---

## P1-3 · Structured log on billing-mirror retry exhaustion

**File:** `backend/core/meeet_billing/client.py`
**Function:** `post_operator_usage_delta()`
**Lines:** 160–178 (retry loop)

The retry loop exits with `last` set to the last failure when all attempts fail. Currently the caller (`mirror_usage.py:47, 52`) logs at `_log.warning()` only on the *final* dict-shape rejection — there's no event marking the retry-exhaustion case distinctly. Per the contract `docs/contracts/TARS_MEEET_BILLING.md` §1.2.0, a separate structured log on exhaustion is requested for ops dashboards.

**Proposed patch — add a single log line after the retry loop, before `return last`:**

```diff
@@ post_operator_usage_delta retry loop, after the for-loop, before return last @@
     for attempt in range(retries):
         try:
             out = await asyncio.to_thread(_post_usage_sync, d, tid)
         except urllib.error.HTTPError as exc:
             ...
         else:
             if not _usage_result_transient(out):
                 return out
         last = out
         if attempt + 1 < retries:
             await asyncio.sleep(min(2.0, 0.12 * (2**attempt)))
+    # Retry budget exhausted. Emit a structured event so the operator
+    # cockpit + ops dashboards can flag a stuck mirror without diffing
+    # individual warnings. Trace id, attempts taken, and last error
+    # shape are the minimal triage payload.
+    _log.warning(
+        "meeet.mirror.usage.exhausted",
+        extra={
+            "trace_id": tid,
+            "attempts": retries,
+            "last_error": (last or {}).get("error"),
+            "delta_usd": d,
+        },
+    )
     return last
```

**Notes for the apply:**

- Use the existing `_log` (already `logging.getLogger(__name__)` at L15). Don't introduce a new logger.
- The event name `meeet.mirror.usage.exhausted` is intentionally a dotted string for OpenTelemetry-friendly grouping; matches the project's existing `meeet.*` event taxonomy.
- Don't change `mirror_usage.py:47/52` — those still log per-attempt-shape failures and are useful for debugging individual transient errors. The new line covers the *aggregate* "we gave up" case.
- Don't bump retries default in this wave. The contract pins default=3 (clamp 1–8) and that's correct.

**Verify:**

```bash
# Unit-test the retry exhaustion path:
.venv/bin/python -m pytest backend/tests/test_meeet_billing_usage.py::test_post_operator_usage_retry_exhausted -xvs

# If that test doesn't exist yet, the existing test file likely covers
# the success path only — add a 4-line test that mocks _post_usage_sync
# to raise HTTPError(500) thrice and asserts the warning was emitted via
# caplog. Pattern lives at lines ~80–110 of test_meeet_billing_usage.py.
```

---

## SYNC marker

When you land these three patches, top-of-file in `docs/CHANGELOG_AGENTS.md`:

```
>>> SYNC: Cursor · 2026-05-05 · Wave 56 P1 closure — 3 hex→token in Onboarding role chips (+ --brand-amber added to index.css), structured log meeet.mirror.usage.exhausted on retry budget exhaustion in client.py:178. P1-2 confirmed already covered by smoke-core-bridge. Frontend (cockpit lane) untouched.
```

That's it. No backend lane drift expected. Light-theme regressions and ops dashboard flag for stuck mirrors — both closed in one tight pass.

— Claude
