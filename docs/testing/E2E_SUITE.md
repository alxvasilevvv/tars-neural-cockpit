# E2E Test Suite (Wave 105)

`tests/test_b2b_e2e.py` is the cross-module integration suite that
walks the full B2B happy path end to end. It complements the
per-module unit suites (`test_org_store.py`, `test_scheduler_store.py`,
`test_receipts_*.py`, etc.) by verifying the *seams* between them —
the places a typo or schema drift in one module breaks another.

## Inventory

| # | Test case | Module(s) covered | What it verifies |
|---|-----------|-------------------|------------------|
| 1 | `BootstrapNewOrgIT` | Wave 99 (`backend.core.org`) | Org create + persist + 3 invites + Step-4 metadata patch |
| 2 | `ConnectorOAuthLifecycleIT` | Wave 91 (`backend.core.connectors`) | Env-gated `is_configured`; `_storage` token write; `registry.get_status` shape |
| 3 | `ScheduledPlaybookFiresIT` | Wave 97 (`backend.core.scheduler`) | Schedule create, force-due, fire, history row recorded |
| 4 | `WebhookOutgoingDeliveryIT` | Wave 90 (`backend.core.webhooks`) | HMAC signature header + receiver-side `verify_payload`; retry on 500 |
| 5 | `OutreachDraftSendIT` | Wave 98 (`backend.core.outreach`) | Mock LLM → draft → approve → mock-Gmail send → `status=sent` |
| 6 | `CohortAttendeeProgressIT` | Wave 94 (`backend.core.cohort`) | Webhook event → `AttendeeAction` → `current_phase` updated |
| 7 | `ReceiptChainVerifyIT` | Wave 95 (`backend.core.receipts`) | 10-receipt append; `verify_chain`; Merkle proof; tamper detection |
| 8 | `ComplianceExportRoundtripIT` | Wave 104 (`backend.core.compliance_export`) | `build_bundle` → `verify_bundle` ok=true; tamper round-trip → ok=false |
| 9 | `ReportGenerationIT` | Wave 103 (`backend.core.reports`) | 6 built-in templates seed; render with stub skill hook → `status=done` |
| 10 | `EndToEndFundOnboardingHappyPathIT` | All of the above | The mega test: org → schedule fire → render → outreach receipt → bundle → verify |

Total: 10 TestCase classes, 13 individual test methods.

## How to run locally

```bash
# Stdlib only -- no pytest required.
python3 -m unittest tests.test_b2b_e2e -v

# A single case:
python3 -m unittest tests.test_b2b_e2e.BootstrapNewOrgIT -v

# AST-only sanity:
python3 -c "import ast; ast.parse(open('tests/test_b2b_e2e.py').read())"
```

Every case isolates its own state via `tests._helpers.temp_tars_home()`
(temp dir + env vars wired to `TARS_*_DB_PATH` overrides) so the
operator's real `~/.tars` is never touched.

## Helpers (`tests/_helpers.py`)

| Helper | Purpose |
|--------|---------|
| `temp_tars_home()` | Temp `~/.tars` dir + all `TARS_*_DB_PATH` env vars; resets every store on entry/exit |
| `mock_llm(text)` | Patches `outreach.drafter._llm_call_anthropic` + `_llm_call_openai` to return fixed text |
| `mock_gmail_send()` | Stubs `urllib.request.urlopen` inside `outreach.sender` + the Gmail client factory |
| `mock_http_server(fail_count=N)` | Daemon-thread `HTTPServer` recording POSTs; can fail first N for retry tests |
| `freeze_time(epoch)` | Patches `time.time()` at fixed value |
| `clear_connector_env()` | Pops `SLACK_*` / `GOOGLE_*` env vars; restores on exit |
| `wait_for(predicate)` | Bounded polling for async-fired side effects |

All helpers are stdlib-only `contextlib.contextmanager` factories so
the suite runs under vanilla `python3 -m unittest`.

## How to add a new E2E test

```python
# tests/test_b2b_e2e.py

class MyNewSeamIT(unittest.TestCase):
    """Wave NN -- short description of the seam this verifies."""

    def test_some_cross_module_path(self) -> None:
        with temp_tars_home():
            from backend.core.foo import FooStore
            from backend.core.bar import bar_action

            store = FooStore()
            row = _run(store.create(...))
            result = _run(bar_action(row.id))

            self.assertTrue(result["ok"])
            persisted = _run(store.get(row.id))
            self.assertEqual(persisted.status, "done")
```

Guidelines:

1. **One class per cross-module scenario.** Per-module CRUD belongs in
   its own `test_<module>_*.py`.
2. **Always wrap in `temp_tars_home()`** so the test never touches
   the operator's real DB.
3. **Use `mock_*()` helpers for external services** (LLM, Gmail HTTP,
   webhook receiver). Never hit a real network.
4. **`self.skipTest(reason)`** when a dep is missing in the sandbox —
   never let the file fail to import.
5. **Assert on contract shape**, not free-form output. The point of
   the E2E suite is to catch contract drift between modules.

## CI integration

`.github/workflows/e2e-suite.yml` runs the suite on every PR + nightly
at 05:00 UTC. The workflow is **blocking** (no `continue-on-error`),
so any failure here surfaces as a red check on the PR.

Only `cryptography` is installed beyond stdlib — every other dep is
either bundled or self-skipped.

## Known gaps (NOT covered by this suite)

* **Multi-tenant.** The whole stack still runs single-tenant; the
  suite never spins two orgs side by side.
* **Marketplace + skill SDK.** Skill install/uninstall + revenue-share
  payouts (Wave 95-96) have their own per-module tests but no end-to-end
  install-skill → run-via-T2T scenario.
* **T2T (TARS-to-TARS).** Wave 81/85/86 escrow + handshake have unit
  tests but no real cross-process E2E here.
* **Frontend.** This suite covers backend only — UI flows live in
  the Playwright suite at `tests/playwright/` (see Wave 83).
* **Live OAuth.** All connector tests use mock tokens; real OAuth
  exchange against Slack/Google is verified via the
  `connectors-live.yml` workflow (manual trigger, not run on PR).
* **Voice / wake-word / streaming.** Audio paths are stubbed, not
  exercised.

Filing these as separate work items is encouraged when the underlying
modules grow E2E-worthy. For now they sit deliberately outside the
Wave 105 scope so the suite stays fast (sub-2-second wall clock).
